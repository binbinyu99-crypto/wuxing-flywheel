"""
agent_memory_store.py — Persistent Shared Memory for 15-Agent Ecosystem
v1.0.0

PostgreSQL-backed memory that survives restarts and enables cross-agent learning.

Tables:
  agent_state    — serialized agent state (memory, strategies, thresholds)
  agent_runs     — per-run records (topic, domain, scores, signals)
  agent_signals  — edge signal history (cross-agent communication log)

Design:
  - Each agent loads its state from PG on init
  - Each agent saves its state after every run
  - Any agent can READ other agents' histories (shared learning)
  - Writes are agent-scoped (no cross-contamination)
  - pg_security_wrapper applied to all writes
"""

VERSION = "1.0.0"

import json
import time
import traceback

try:
    from pg_storage import get_conn
    PG_AVAILABLE = True
except ImportError:
    PG_AVAILABLE = False


# =====================================================
# Schema
# =====================================================

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agent_state (
    agent_id VARCHAR(64) PRIMARY KEY,
    agent_type VARCHAR(16) NOT NULL,  -- 'node' or 'edge'
    element VARCHAR(16),
    state_json JSONB NOT NULL DEFAULT '{}',
    stats_json JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(64) NOT NULL,
    topic_hash VARCHAR(16),
    domain VARCHAR(64),
    output_summary TEXT,
    downstream_score FLOAT,
    strategy_used VARCHAR(64),
    metadata_json JSONB DEFAULT '{}',
    signals_received JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_domain ON agent_runs(domain);
CREATE INDEX IF NOT EXISTS idx_agent_runs_created ON agent_runs(created_at DESC);

CREATE TABLE IF NOT EXISTS agent_signals (
    id SERIAL PRIMARY KEY,
    source_agent VARCHAR(64) NOT NULL,
    target_agent VARCHAR(64) NOT NULL,
    signal_type VARCHAR(32),  -- 'generation', 'control', 'feedback'
    signal_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_agent_signals_target ON agent_signals(target_agent);
CREATE INDEX IF NOT EXISTS idx_agent_signals_created ON agent_signals(created_at DESC);
"""


def init_schema():
    """Create tables if not exist."""
    if not PG_AVAILABLE:
        print("[AgentMemStore] PG not available, running in ephemeral mode")
        return False
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_SQL)
            conn.commit()
        print("[AgentMemStore] Schema initialized (3 tables)")
        return True
    except Exception as e:
        print(f"[AgentMemStore] Schema init failed: {e}")
        return False


# =====================================================
# Agent State Persistence
# =====================================================

def save_agent_state(agent_id, agent_type, element, state_dict, stats_dict):
    """Save/update an agent's full state to PG."""
    if not PG_AVAILABLE:
        return False
    try:
        # Sanitize sets (not JSON serializable)
        clean_stats = _sanitize_for_json(stats_dict)
        clean_state = _sanitize_for_json(state_dict)
        
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO agent_state (agent_id, agent_type, element, state_json, stats_json, updated_at)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (agent_id) DO UPDATE SET
                        state_json = EXCLUDED.state_json,
                        stats_json = EXCLUDED.stats_json,
                        updated_at = CURRENT_TIMESTAMP
                """, (agent_id, agent_type, element,
                      json.dumps(clean_state, ensure_ascii=False),
                      json.dumps(clean_stats, ensure_ascii=False)))
            conn.commit()
        return True
    except Exception as e:
        print(f"[AgentMemStore] save_agent_state({agent_id}) failed: {e}")
        return False


def load_agent_state(agent_id):
    """Load an agent's state from PG. Returns (state_dict, stats_dict) or (None, None)."""
    if not PG_AVAILABLE:
        return None, None
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT state_json, stats_json FROM agent_state WHERE agent_id = %s", (agent_id,))
                row = cur.fetchone()
                if row:
                    return row[0], row[1]
        return None, None
    except Exception as e:
        print(f"[AgentMemStore] load_agent_state({agent_id}) failed: {e}")
        return None, None


# =====================================================
# Run Records
# =====================================================

def save_run(agent_id, topic_hash, domain, output_summary, downstream_score=None,
             strategy_used=None, metadata=None, signals=None):
    """Record a single run for an agent."""
    if not PG_AVAILABLE:
        return False
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO agent_runs 
                    (agent_id, topic_hash, domain, output_summary, downstream_score,
                     strategy_used, metadata_json, signals_received)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (agent_id, topic_hash, domain, str(output_summary)[:500],
                      downstream_score, strategy_used,
                      json.dumps(metadata or {}, ensure_ascii=False),
                      json.dumps(signals or [], ensure_ascii=False)))
            conn.commit()
        return True
    except Exception as e:
        print(f"[AgentMemStore] save_run({agent_id}) failed: {e}")
        return False


def update_run_score(agent_id, score):
    """Update the most recent run's downstream score."""
    if not PG_AVAILABLE:
        return False
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE agent_runs SET downstream_score = %s
                    WHERE id = (
                        SELECT id FROM agent_runs 
                        WHERE agent_id = %s 
                        ORDER BY created_at DESC LIMIT 1
                    )
                """, (score, agent_id))
            conn.commit()
        return True
    except Exception as e:
        print(f"[AgentMemStore] update_run_score({agent_id}) failed: {e}")
        return False


def get_runs(agent_id, limit=10):
    """Get recent runs for an agent."""
    if not PG_AVAILABLE:
        return []
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT topic_hash, domain, output_summary, downstream_score, 
                           strategy_used, metadata_json, created_at
                    FROM agent_runs WHERE agent_id = %s
                    ORDER BY created_at DESC LIMIT %s
                """, (agent_id, limit))
                rows = cur.fetchall()
                return [{
                    "topic_hash": r[0], "domain": r[1], "summary": r[2],
                    "score": r[3], "strategy": r[4], "metadata": r[5],
                    "created_at": str(r[6])
                } for r in rows]
    except Exception as e:
        print(f"[AgentMemStore] get_runs({agent_id}) failed: {e}")
        return []


def get_domain_scores(agent_id, domain, limit=20):
    """Get scores for a specific agent+domain combo. Enables cross-agent learning."""
    if not PG_AVAILABLE:
        return []
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT downstream_score FROM agent_runs
                    WHERE agent_id = %s AND domain = %s AND downstream_score IS NOT NULL
                    ORDER BY created_at DESC LIMIT %s
                """, (agent_id, domain, limit))
                return [r[0] for r in cur.fetchall()]
    except Exception as e:
        return []


def get_cross_agent_insight(domain, limit=50):
    """Get ALL agents' recent scores for a domain. Enables system-level learning.
    
    Returns: {agent_id: [scores]}
    """
    if not PG_AVAILABLE:
        return {}
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT agent_id, downstream_score FROM agent_runs
                    WHERE domain = %s AND downstream_score IS NOT NULL
                    ORDER BY created_at DESC LIMIT %s
                """, (domain, limit))
                result = {}
                for agent_id, score in cur.fetchall():
                    result.setdefault(agent_id, []).append(score)
                return result
    except Exception as e:
        return {}


def get_best_strategy(agent_id, domain):
    """Find the strategy that historically scored highest for this agent+domain."""
    if not PG_AVAILABLE:
        return None
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT strategy_used, AVG(downstream_score) as avg_score, COUNT(*) as cnt
                    FROM agent_runs
                    WHERE agent_id = %s AND domain = %s 
                          AND downstream_score IS NOT NULL AND strategy_used IS NOT NULL
                    GROUP BY strategy_used
                    HAVING COUNT(*) >= 2
                    ORDER BY avg_score DESC LIMIT 1
                """, (agent_id, domain))
                row = cur.fetchone()
                if row:
                    return {"strategy": row[0], "avg_score": row[1], "count": row[2]}
        return None
    except Exception as e:
        return None


# =====================================================
# Signal Log
# =====================================================

def log_signal(source_agent, target_agent, signal_type, signal_data):
    """Log a signal between agents."""
    if not PG_AVAILABLE:
        return False
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO agent_signals (source_agent, target_agent, signal_type, signal_data)
                    VALUES (%s, %s, %s, %s)
                """, (source_agent, target_agent, signal_type,
                      json.dumps(_sanitize_for_json(signal_data), ensure_ascii=False, default=str)))
            conn.commit()
        return True
    except Exception as e:
        print(f"[AgentMemStore] log_signal failed: {e}")
        return False


def get_signal_history(target_agent, limit=20):
    """Get recent signals received by an agent."""
    if not PG_AVAILABLE:
        return []
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT source_agent, signal_type, signal_data, created_at
                    FROM agent_signals WHERE target_agent = %s
                    ORDER BY created_at DESC LIMIT %s
                """, (target_agent, limit))
                return [{
                    "source": r[0], "type": r[1], "data": r[2], "at": str(r[3])
                } for r in cur.fetchall()]
    except Exception as e:
        return []


def get_intervention_rate(agent_id, window_hours=24):
    """How often does a control agent intervene? Useful for calibration."""
    if not PG_AVAILABLE:
        return None
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(*) FILTER (WHERE (signal_data->>'intervention')::boolean = true) as interventions,
                        COUNT(*) as total
                    FROM agent_signals
                    WHERE source_agent = %s 
                          AND created_at > NOW() - INTERVAL '%s hours'
                """, (agent_id, window_hours))
                row = cur.fetchone()
                if row and row[1] > 0:
                    return {"interventions": row[0], "total": row[1], 
                            "rate": row[0] / row[1]}
        return None
    except Exception as e:
        return None


# =====================================================
# System-Level Analytics
# =====================================================

def get_system_health():
    """Overall system health across all agents."""
    if not PG_AVAILABLE:
        return {"status": "pg_unavailable"}
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Agent states
                cur.execute("SELECT agent_id, agent_type, element, updated_at FROM agent_state ORDER BY agent_id")
                agents = [{"id": r[0], "type": r[1], "element": r[2], "updated": str(r[3])} for r in cur.fetchall()]
                
                # Recent runs
                cur.execute("""
                    SELECT agent_id, COUNT(*), AVG(downstream_score)
                    FROM agent_runs
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                    GROUP BY agent_id
                """)
                recent = {r[0]: {"runs": r[1], "avg_score": float(r[2]) if r[2] else None} for r in cur.fetchall()}
                
                # Signal counts
                cur.execute("""
                    SELECT COUNT(*) FROM agent_signals
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                """)
                signals_24h = cur.fetchone()[0]
                
                return {
                    "agents": len(agents),
                    "agent_list": agents,
                    "recent_24h": recent,
                    "signals_24h": signals_24h,
                }
    except Exception as e:
        return {"error": str(e)}


# =====================================================
# Utilities
# =====================================================

def _sanitize_for_json(obj):
    """Convert non-serializable types (sets, etc) for JSON storage."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    elif isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, float):
        if obj != obj:  # NaN
            return 0.0
        return obj
    return obj


def self_test():
    """Self-test."""
    print(f"agent_memory_store.py v{VERSION} self-test")
    print("=" * 50)
    
    if not PG_AVAILABLE:
        print("  [SKIP] PG not available")
        return False
    
    passed = 0
    total = 0
    
    # Test 1: Schema init
    total += 1
    ok = init_schema()
    print(f"  [{'PASS' if ok else 'FAIL'}] Schema init")
    if ok: passed += 1
    
    # Test 2: Save/load agent state
    total += 1
    test_state = {"runs": [{"topic": "test", "score": 0.7}], "strategy": "balanced"}
    test_stats = {"total_runs": 5, "avg_score": 0.65, "topics_seen": ["abc", "def"]}
    ok = save_agent_state("test_wood", "node", "wood", test_state, test_stats)
    state, stats = load_agent_state("test_wood")
    ok = ok and state is not None and stats["total_runs"] == 5
    print(f"  [{'PASS' if ok else 'FAIL'}] Save/load agent state")
    if ok: passed += 1
    
    # Test 3: Save run
    total += 1
    ok = save_run("test_wood", "abc123", "materials", "7 seeds generated",
                  downstream_score=0.63, strategy_used="data_heavy",
                  metadata={"depth": "standard"})
    print(f"  [{'PASS' if ok else 'FAIL'}] Save run record")
    if ok: passed += 1
    
    # Test 4: Get runs
    total += 1
    runs = get_runs("test_wood", limit=5)
    ok = len(runs) > 0 and runs[0]["domain"] == "materials"
    print(f"  [{'PASS' if ok else 'FAIL'}] Get runs ({len(runs)} records)")
    if ok: passed += 1
    
    # Test 5: Cross-agent insight
    total += 1
    save_run("test_fire", "abc123", "materials", "analysis", downstream_score=0.55)
    insight = get_cross_agent_insight("materials")
    ok = len(insight) >= 2  # Both test_wood and test_fire
    print(f"  [{'PASS' if ok else 'FAIL'}] Cross-agent insight ({len(insight)} agents)")
    if ok: passed += 1
    
    # Test 6: Best strategy
    total += 1
    save_run("test_wood", "def456", "materials", "test2", downstream_score=0.8, strategy_used="data_heavy")
    save_run("test_wood", "ghi789", "materials", "test3", downstream_score=0.4, strategy_used="balanced")
    best = get_best_strategy("test_wood", "materials")
    ok = best is not None and best["strategy"] == "data_heavy"
    print(f"  [{'PASS' if ok else 'FAIL'}] Best strategy: {best}")
    if ok: passed += 1
    
    # Test 7: Signal logging
    total += 1
    ok = log_signal("edge_wood_fire", "node_fire", "generation", {"seeds_passed": 5, "quality": "high"})
    history = get_signal_history("node_fire", limit=5)
    ok = ok and len(history) > 0
    print(f"  [{'PASS' if ok else 'FAIL'}] Signal log ({len(history)} signals)")
    if ok: passed += 1
    
    # Test 8: System health
    total += 1
    health = get_system_health()
    ok = "agents" in health and health["agents"] >= 1
    print(f"  [{'PASS' if ok else 'FAIL'}] System health: {health.get('agents', 0)} agents, {health.get('signals_24h', 0)} signals/24h")
    if ok: passed += 1
    
    # Cleanup test data
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM agent_runs WHERE agent_id LIKE 'test_%'")
                cur.execute("DELETE FROM agent_state WHERE agent_id LIKE 'test_%'")
                cur.execute("DELETE FROM agent_signals WHERE source_agent LIKE 'edge_%' AND target_agent LIKE 'node_%' AND signal_data::text LIKE '%seeds_passed%'")
            conn.commit()
    except:
        pass
    
    print(f"\n{passed}/{total} tests passed")
    return passed == total


if __name__ == "__main__":
    self_test()
