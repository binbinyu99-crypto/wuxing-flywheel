# -*- coding: utf-8 -*-
"""
Memory Type Hierarchy for SkyCetus Cognitive Kernel
Extracted from ChatGPT Kernel Spec v0.1 - adapted for our pipeline architecture.

Types flow: OBSERVATION -> HYPOTHESIS -> VALIDATED -> DECISION
Each level has increasing confidence requirements and write gates.

v1.0.0 - 2026-05-03
"""
import time
import json
import hashlib
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Literal


class MemoryType(str, Enum):
    OBSERVATION = "OBSERVATION"    # Raw input, search results, user queries
    HYPOTHESIS = "HYPOTHESIS"     # Agent-generated analysis, unverified
    VALIDATED = "VALIDATED"       # Multi-agent confirmed, cross-checked
    DECISION = "DECISION"        # Final output, kernel-approved


# Confidence thresholds for write validation
WRITE_THRESHOLDS = {
    MemoryType.OBSERVATION: 0.0,     # Always writable
    MemoryType.HYPOTHESIS: 0.3,      # Minimum confidence to persist
    MemoryType.VALIDATED: 0.6,       # Needs multi-agent confirmation
    MemoryType.DECISION: 0.7,        # Needs kernel approval
}


@dataclass
class MemoryItem:
    """A typed memory unit with provenance tracking."""
    content: str
    memory_type: MemoryType
    source_agent: str
    confidence: float = 0.5
    domain: str = ""
    tags: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    confirming_agents: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None  # Links to source memory item
    item_id: str = ""

    def __post_init__(self):
        if not self.item_id:
            h = hashlib.md5(f"{self.content[:100]}:{self.source_agent}:{self.timestamp}".encode()).hexdigest()[:12]
            self.item_id = f"mem_{h}"

    def to_dict(self):
        d = asdict(self)
        d['memory_type'] = self.memory_type.value
        return d

    @classmethod
    def from_dict(cls, d):
        d['memory_type'] = MemoryType(d['memory_type'])
        return cls(**d)

    def promote(self, new_type: MemoryType, confirming_agent: str = None):
        """Promote memory item to higher type (e.g., HYPOTHESIS -> VALIDATED)."""
        type_order = [MemoryType.OBSERVATION, MemoryType.HYPOTHESIS, MemoryType.VALIDATED, MemoryType.DECISION]
        current_idx = type_order.index(self.memory_type)
        new_idx = type_order.index(new_type)
        if new_idx <= current_idx:
            raise ValueError(f"Cannot demote from {self.memory_type} to {new_type}")
        self.memory_type = new_type
        if confirming_agent and confirming_agent not in self.confirming_agents:
            self.confirming_agents.append(confirming_agent)
        return self


def validate_memory_write(item: MemoryItem, kernel_approved: bool = False) -> tuple:
    """
    Gate function for memory writes.
    Returns (allowed: bool, reason: str)
    """
    threshold = WRITE_THRESHOLDS.get(item.memory_type, 1.0)

    if item.memory_type == MemoryType.OBSERVATION:
        return True, "OBSERVATION always allowed"

    if item.memory_type == MemoryType.HYPOTHESIS:
        if item.confidence < threshold:
            return False, f"HYPOTHESIS confidence {item.confidence:.2f} < threshold {threshold}"
        return True, "HYPOTHESIS meets confidence threshold"

    if item.memory_type == MemoryType.VALIDATED:
        if item.confidence < threshold:
            return False, f"VALIDATED confidence {item.confidence:.2f} < threshold {threshold}"
        if len(item.confirming_agents) < 2:
            return False, f"VALIDATED needs >=2 confirming agents, has {len(item.confirming_agents)}"
        return True, "VALIDATED meets all criteria"

    if item.memory_type == MemoryType.DECISION:
        if not kernel_approved:
            return False, "DECISION requires kernel approval"
        if item.confidence < threshold:
            return False, f"DECISION confidence {item.confidence:.2f} < threshold {threshold}"
        return True, "DECISION approved by kernel"

    return False, f"Unknown memory type: {item.memory_type}"


# ============================================================
# PG Storage Integration
# ============================================================
def create_memory_table(conn):
    """Create the memory_items table if not exists."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS memory_items (
            item_id VARCHAR(32) PRIMARY KEY,
            memory_type VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            source_agent VARCHAR(64) NOT NULL,
            confidence FLOAT DEFAULT 0.5,
            domain VARCHAR(128) DEFAULT '',
            tags TEXT DEFAULT '[]',
            confirming_agents TEXT DEFAULT '[]',
            parent_id VARCHAR(32),
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_items(memory_type)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_domain ON memory_items(domain)
    """)
    conn.commit()
    return True


def save_memory_item(conn, item: MemoryItem, kernel_approved: bool = False) -> tuple:
    """Save a memory item with write validation. Returns (success, reason)."""
    allowed, reason = validate_memory_write(item, kernel_approved)
    if not allowed:
        return False, reason

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO memory_items (item_id, memory_type, content, source_agent, confidence, domain, tags, confirming_agents, parent_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (item_id) DO UPDATE SET
            memory_type = EXCLUDED.memory_type,
            confidence = EXCLUDED.confidence,
            confirming_agents = EXCLUDED.confirming_agents
    """, (
        item.item_id, item.memory_type.value, item.content,
        item.source_agent, item.confidence, item.domain,
        json.dumps(item.tags), json.dumps(item.confirming_agents),
        item.parent_id
    ))
    conn.commit()
    return True, reason


def query_memory(conn, domain: str = None, memory_type: MemoryType = None, min_confidence: float = 0.0, limit: int = 50):
    """Query memory items with filters."""
    cur = conn.cursor()
    conditions = ["confidence >= %s"]
    params = [min_confidence]

    if domain:
        conditions.append("domain = %s")
        params.append(domain)
    if memory_type:
        conditions.append("memory_type = %s")
        params.append(memory_type.value)

    where = " AND ".join(conditions)
    params.append(limit)

    cur.execute(f"""
        SELECT item_id, memory_type, content, source_agent, confidence, domain, tags, confirming_agents, parent_id, created_at
        FROM memory_items
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT %s
    """, params)

    items = []
    for row in cur.fetchall():
        item = MemoryItem(
            item_id=row[0],
            memory_type=MemoryType(row[1]),
            content=row[2],
            source_agent=row[3],
            confidence=row[4],
            domain=row[5],
            tags=json.loads(row[6]) if row[6] else [],
            confirming_agents=json.loads(row[7]) if row[7] else [],
            parent_id=row[8]
        )
        items.append(item)
    return items


def get_memory_stats(conn, domain: str = None):
    """Get count by memory type."""
    cur = conn.cursor()
    if domain:
        cur.execute("""
            SELECT memory_type, COUNT(*), AVG(confidence)
            FROM memory_items WHERE domain = %s
            GROUP BY memory_type
        """, (domain,))
    else:
        cur.execute("""
            SELECT memory_type, COUNT(*), AVG(confidence)
            FROM memory_items
            GROUP BY memory_type
        """)
    return {row[0]: {"count": row[1], "avg_confidence": round(float(row[2] or 0), 3)} for row in cur.fetchall()}


# ============================================================
# Self-test
# ============================================================
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("=== Memory Types Self-Test ===")

    # Test 1: Create items
    obs = MemoryItem(content="Search result: 杭州未来社区", memory_type=MemoryType.OBSERVATION, source_agent="wood")
    hyp = MemoryItem(content="Market size ~340B", memory_type=MemoryType.HYPOTHESIS, source_agent="fire", confidence=0.6)
    hyp_low = MemoryItem(content="Low confidence guess", memory_type=MemoryType.HYPOTHESIS, source_agent="fire", confidence=0.1)

    # Test 2: Write validation
    assert validate_memory_write(obs)[0] == True, "OBSERVATION should pass"
    assert validate_memory_write(hyp)[0] == True, "HYPOTHESIS 0.6 should pass"
    assert validate_memory_write(hyp_low)[0] == False, "HYPOTHESIS 0.1 should fail"

    val = MemoryItem(content="Confirmed finding", memory_type=MemoryType.VALIDATED, source_agent="earth", confidence=0.7, confirming_agents=["wood", "fire"])
    assert validate_memory_write(val)[0] == True, "VALIDATED with 2 confirmers should pass"

    val_bad = MemoryItem(content="Bad", memory_type=MemoryType.VALIDATED, source_agent="earth", confidence=0.7, confirming_agents=["wood"])
    assert validate_memory_write(val_bad)[0] == False, "VALIDATED with 1 confirmer should fail"

    dec = MemoryItem(content="Final decision", memory_type=MemoryType.DECISION, source_agent="kernel", confidence=0.8)
    assert validate_memory_write(dec, kernel_approved=False)[0] == False, "DECISION without kernel should fail"
    assert validate_memory_write(dec, kernel_approved=True)[0] == True, "DECISION with kernel should pass"

    # Test 3: Promotion
    obs2 = MemoryItem(content="Test", memory_type=MemoryType.OBSERVATION, source_agent="wood")
    obs2.promote(MemoryType.HYPOTHESIS, "fire")
    assert obs2.memory_type == MemoryType.HYPOTHESIS
    assert "fire" in obs2.confirming_agents

    # Test 4: PG integration
    sys.path.insert(0, r"D:\ClawMatrix")
    from pg_storage import get_conn
    with get_conn() as conn:
        create_memory_table(conn)
        ok, reason = save_memory_item(conn, obs)
        print(f"  Save OBSERVATION: {ok} ({reason})")
        ok, reason = save_memory_item(conn, hyp)
        print(f"  Save HYPOTHESIS 0.6: {ok} ({reason})")
        ok, reason = save_memory_item(conn, hyp_low)
        print(f"  Save HYPOTHESIS 0.1: {ok} ({reason})")
        ok, reason = save_memory_item(conn, val)
        print(f"  Save VALIDATED: {ok} ({reason})")
        ok, reason = save_memory_item(conn, dec, kernel_approved=True)
        print(f"  Save DECISION (approved): {ok} ({reason})")

        stats = get_memory_stats(conn)
        print(f"  Stats: {stats}")

        items = query_memory(conn, memory_type=MemoryType.HYPOTHESIS)
        print(f"  Query HYPOTHESIS: {len(items)} items")

    print("All tests passed!")
    print("v1.0.0 - Memory type hierarchy operational")
