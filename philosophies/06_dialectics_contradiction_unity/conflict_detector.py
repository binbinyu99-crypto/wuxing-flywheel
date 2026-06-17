"""
conflict_detector.py — 逻辑冲突池 (Logic Conflict Pool)
Detects divergences between element outputs within a round,
stores them in PG, and generates conflict-seeds for next rounds.

Part of the Wuxing Flywheel evolution mechanism.
"""

import json
import uuid
import time
from datetime import datetime

# ---------------------------------------------------------------------------
# PG Schema
# ---------------------------------------------------------------------------
CONFLICT_POOL_SCHEMA_STMTS = [
    """CREATE TABLE IF NOT EXISTS conflict_pool (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        round_num INTEGER NOT NULL,
        topic TEXT NOT NULL,
        element_a TEXT NOT NULL,
        element_b TEXT NOT NULL,
        claim_a TEXT NOT NULL,
        claim_b TEXT NOT NULL,
        conflict_summary TEXT NOT NULL,
        divergence_score REAL DEFAULT 0.5,
        conflict_type TEXT DEFAULT 'inter_element',
        status TEXT DEFAULT 'active',
        resolution TEXT,
        seed_generated BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS idx_conflict_pool_run ON conflict_pool(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_conflict_pool_status ON conflict_pool(status)",
    "CREATE INDEX IF NOT EXISTS idx_conflict_pool_score ON conflict_pool(divergence_score DESC)",
]

# ---------------------------------------------------------------------------
# Element pairs to compare (based on Wuxing 相克 relationships + key pairs)
# ---------------------------------------------------------------------------
COMPARE_PAIRS = [
    ("qinglong", "baihu"),    # 金克木: seeds vs attacks — fundamental tension
    ("zhuque", "xuanwu"),     # 水克火: execution vs convergence
    ("qinglong", "diting"),   # 木克土: seeds vs verification
    ("zhuque", "baihu"),      # 火克金: execution vs attack
    ("diting", "xuanwu"),     # 土克水: verification vs convergence
]

ELEMENT_NAMES_CN = {
    "qinglong": "青龙·种子",
    "zhuque":   "朱雀·执行",
    "diting":   "谛听·审计",
    "baihu":    "白虎·攻击",
    "xuanwu":   "玄武·收敛",
}


def _gen_id():
    return f"cfl_{uuid.uuid4().hex[:12]}"


def init_conflict_pool(conn):
    """Create conflict_pool table if not exists. Works with DBConn wrapper."""
    try:
        for stmt in CONFLICT_POOL_SCHEMA_STMTS:
            conn.execute(stmt)
        conn.commit()
        print("    [conflict_pool] Table initialized")
    except Exception as e:
        print(f"    [conflict_pool] Init error: {e}")


def detect_conflicts(element_outputs, topic, round_num, run_id, call_llm_fn, conn):
    """
    Detect divergences between element outputs using LLM comparison.
    
    Args:
        element_outputs: dict of element_name -> output_text
        topic: analysis topic
        round_num: current round number
        run_id: flywheel run ID
        call_llm_fn: LLM call function (system_prompt, user_prompt, ...) -> dict with "text"
        conn: database connection
    
    Returns:
        list of conflict dicts with keys: element_a, element_b, conflict_summary, divergence_score
    """
    print(f"\n    ⚔️ 冲突检测器启动 (R{round_num})...")
    
    # Truncate outputs for comparison prompt
    truncated = {}
    for elem in ["qinglong", "zhuque", "diting", "baihu", "xuanwu"]:
        raw = element_outputs.get(elem, "")
        if not raw:
            continue
        # Try to extract key claims from JSON
        try:
            parsed = json.loads(raw.strip().strip("`").replace("```json", "").replace("```", ""))
            # Get the most meaningful content
            if elem == "qinglong":
                seeds = parsed.get("seeds", [])
                truncated[elem] = json.dumps(seeds[:3], ensure_ascii=False)[:800]
            elif elem == "zhuque":
                analyses = parsed.get("analyses", [])
                truncated[elem] = json.dumps(analyses[:3], ensure_ascii=False)[:800]
            elif elem == "diting":
                verifications = parsed.get("verifications", [])
                truncated[elem] = json.dumps(verifications[:3], ensure_ascii=False)[:800]
            elif elem == "baihu":
                attacks = parsed.get("attacks", [])
                truncated[elem] = json.dumps(attacks[:3], ensure_ascii=False)[:800]
            elif elem == "xuanwu":
                conclusion = parsed.get("conclusion", "")
                kun = parsed.get("kun_dive", {})
                truncated[elem] = json.dumps({"conclusion": conclusion, "kun_dive": kun}, ensure_ascii=False)[:800]
        except Exception:
            truncated[elem] = raw[:800]
    
    if len(truncated) < 2:
        print("    [conflict] Not enough element outputs to compare")
        return []
    
    # Build comparison prompt
    element_summaries = "\n\n".join([
        f"### {ELEMENT_NAMES_CN.get(k, k)}\n{v}" 
        for k, v in truncated.items()
    ])
    
    system_prompt = """你是五行飞轮的冲突检测器。你的任务是找出不同元素之间的认知分歧。

分歧不是错误——分歧是进化的种子。你要找的是：
1. 事实判断矛盾：两个元素对同一事实的判断相反
2. 概率分歧：对同一事件的概率估计差异>0.3
3. 因果链冲突：A认为X导致Y，B认为X导致Z
4. 优先级分歧：A认为最重要的是X，B认为最重要的是Y
5. 盲区暴露：A提到了B完全没考虑的关键因素

输出严格JSON格式。"""

    user_prompt = f"""主题：{topic}
第{round_num}轮各元素输出摘要：

{element_summaries}

请找出元素之间的认知分歧。只报告真正有意义的分歧（不是措辞差异）。
如果没有显著分歧，返回空数组。

输出格式：
{{
  "conflicts": [
    {{
      "element_a": "qinglong",
      "element_b": "baihu",
      "claim_a": "青龙的具体主张（引用原文）",
      "claim_b": "白虎的对立主张（引用原文）",
      "conflict_summary": "一句话描述冲突本质",
      "divergence_score": 0.7,
      "conflict_type": "factual|probabilistic|causal|priority|blindspot"
    }}
  ],
  "meta_observation": "整体认知分歧模式的一句话总结"
}}"""

    try:
        result = call_llm_fn(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=2000,
            model_key="diting"  # 谛听模型做冲突检测——审计视角
        )
        
        text = result.get("text", "")
        # Parse JSON from response
        text_clean = text.strip().strip("`").replace("```json", "").replace("```", "")
        parsed = json.loads(text_clean)
        conflicts = parsed.get("conflicts", [])
        meta = parsed.get("meta_observation", "")
        
        if meta:
            print(f"    [conflict] 元观察: {meta}")
        
        print(f"    [conflict] 检测到 {len(conflicts)} 个分歧")
        
        # Store conflicts in DB
        stored = 0
        for c in conflicts:
            try:
                cid = _gen_id()
                conn.execute(
                    """INSERT INTO conflict_pool 
                    (id, run_id, round_num, topic, element_a, element_b, 
                     claim_a, claim_b, conflict_summary, divergence_score, 
                     conflict_type, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (cid, run_id, round_num, topic,
                     c.get("element_a", ""), c.get("element_b", ""),
                     c.get("claim_a", "")[:2000], c.get("claim_b", "")[:2000],
                     c.get("conflict_summary", "")[:1000],
                     c.get("divergence_score", 0.5),
                     c.get("conflict_type", "inter_element"))
                )
                stored += 1
            except Exception as e:
                print(f"    [conflict] Store error: {e}")
        
        conn.commit()
        print(f"    [conflict] 存储 {stored} 个冲突到 conflict_pool")
        
        return conflicts
        
    except json.JSONDecodeError as e:
        print(f"    [conflict] JSON parse error: {e}")
        return []
    except Exception as e:
        print(f"    [conflict] Detection error: {e}")
        return []


def generate_conflict_seeds(conflicts, topic, max_seeds=3):
    """
    Transform high-divergence conflicts into seeds for the next round.
    
    Only conflicts with divergence_score >= 0.6 become seeds.
    Returns a string to inject into next round's seed input.
    """
    if not conflicts:
        return ""
    
    high_div = [c for c in conflicts if c.get("divergence_score", 0) >= 0.6]
    if not high_div:
        return ""
    
    # Sort by divergence score, take top N
    high_div.sort(key=lambda x: x.get("divergence_score", 0), reverse=True)
    top = high_div[:max_seeds]
    
    seed_lines = []
    for i, c in enumerate(top):
        seed_lines.append(
            f"[冲突种子{i+1}] {c.get('conflict_summary', '')} "
            f"({c.get('element_a', '')} vs {c.get('element_b', '')}, "
            f"分歧度: {c.get('divergence_score', 0):.1f})"
        )
    
    return "\n".join(seed_lines)


def get_unresolved_conflicts(conn, topic=None, min_score=0.6, limit=10):
    """
    Retrieve unresolved high-divergence conflicts, optionally filtered by topic.
    Useful for cross-run conflict seeding.
    """
    try:
        if topic:
            cur = conn.execute(
                """SELECT * FROM conflict_pool 
                WHERE status = 'active' AND divergence_score >= ? AND topic LIKE ?
                ORDER BY divergence_score DESC LIMIT ?""",
                (min_score, f"%{topic[:50]}%", limit)
            )
        else:
            cur = conn.execute(
                """SELECT * FROM conflict_pool 
                WHERE status = 'active' AND divergence_score >= ?
                ORDER BY divergence_score DESC LIMIT ?""",
                (min_score, limit)
            )
        return cur.fetchall()
    except Exception as e:
        print(f"    [conflict] Query error: {e}")
        return []


def resolve_conflict(conn, conflict_id, resolution_text):
    """Mark a conflict as resolved with explanation."""
    try:
        conn.execute(
            """UPDATE conflict_pool 
            SET status = 'resolved', resolution = ?, resolved_at = CURRENT_TIMESTAMP 
            WHERE id = ?""",
            (resolution_text, conflict_id)
        )
        conn.commit()
    except Exception as e:
        print(f"    [conflict] Resolve error: {e}")


def get_conflict_stats(conn, run_id=None):
    """Get conflict pool statistics."""
    try:
        if run_id:
            cur = conn.execute(
                """SELECT COUNT(*) as total, 
                       AVG(divergence_score) as avg_score,
                       MAX(divergence_score) as max_score,
                       SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) as active,
                       SUM(CASE WHEN status='resolved' THEN 1 ELSE 0 END) as resolved
                FROM conflict_pool WHERE run_id = ?""",
                (run_id,)
            )
        else:
            cur = conn.execute(
                """SELECT COUNT(*) as total, 
                       AVG(divergence_score) as avg_score,
                       MAX(divergence_score) as max_score,
                       SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) as active,
                       SUM(CASE WHEN status='resolved' THEN 1 ELSE 0 END) as resolved
                FROM conflict_pool"""
            )
        row = cur.fetchone()
        if row:
            # Handle both dict (PG RealDictCursor) and tuple (sqlite)
            if isinstance(row, dict):
                return {
                    "total": row.get("total", 0) or 0,
                    "avg_score": round(row.get("avg_score", 0) or 0, 3),
                    "max_score": round(row.get("max_score", 0) or 0, 3),
                    "active": row.get("active", 0) or 0,
                    "resolved": row.get("resolved", 0) or 0,
                }
            return {
                "total": row[0] or 0,
                "avg_score": round(row[1] or 0, 3),
                "max_score": round(row[2] or 0, 3),
                "active": row[3] or 0,
                "resolved": row[4] or 0,
            }
        return {"total": 0}
    except Exception as e:
        print(f"    [conflict] Stats error: {e}")
        return {"total": 0, "error": str(e)}
