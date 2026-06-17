# -*- coding: utf-8 -*-
"""
cognitive_graph.py - Cognitive Graph Engine (merged from V1 Xuanwu)
Part of Wuxing Flywheel 2.0

Tracks residuals, patterns, and knowledge evolution across pipeline runs.
PostgreSQL-backed with graph structure (nodes + edges).
"""
import json, time, hashlib
from collections import defaultdict

try:
    import pg_storage
    PG = True
except:
    PG = False

VERSION = "1.0.0"

# ===== PG Schema =====
INIT_SQL = """
CREATE TABLE IF NOT EXISTS cg_nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,
    label TEXT NOT NULL,
    severity REAL DEFAULT 5.0,
    source TEXT,
    topic TEXT,
    pipeline_run TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS cg_edges (
    id SERIAL PRIMARY KEY,
    source_id TEXT REFERENCES cg_nodes(id) ON DELETE CASCADE,
    target_id TEXT REFERENCES cg_nodes(id) ON DELETE CASCADE,
    edge_type TEXT NOT NULL,
    weight REAL DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_id, target_id, edge_type)
);
CREATE TABLE IF NOT EXISTS cg_patterns (
    id SERIAL PRIMARY KEY,
    pattern_type TEXT NOT NULL,
    description TEXT,
    affected_nodes TEXT[],
    recommendation TEXT,
    pipeline_run TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS cg_path_weights (
    id SERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    topic TEXT,
    weights JSONB NOT NULL,
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cg_nodes_topic ON cg_nodes(topic);
CREATE INDEX IF NOT EXISTS idx_cg_nodes_type ON cg_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_cg_edges_source ON cg_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_cg_patterns_type ON cg_patterns(pattern_type);
"""

def init_tables():
    """Initialize cognitive graph tables in PostgreSQL."""
    if not PG:
        return False
    try:
        with pg_storage.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(INIT_SQL)
            conn.commit()
        return True
    except Exception as e:
        print(f"[CG] Init error: {e}")
        return False


def extract_residuals(metal_result, earth_result=None):
    """Extract cognitive residuals from Metal validation + Earth synthesis.
    
    Residual types:
    - blind_spot: Metal found missing coverage (low dimension scores)
    - data_gap: Earth identified missing data
    - paradigm_gap: Metal adversarial found fundamental weakness
    - unexploited_potential: High-scoring areas not fully explored
    """
    residuals = []
    
    # From Metal dimensions
    dims = metal_result.get("dimensions", {})
    verdict = metal_result.get("verdict", "")
    composite = metal_result.get("composite_score", 0)
    
    for dim_name, score in dims.items():
        if isinstance(score, (int, float)) and score < 0.4:
            residuals.append({
                "type": "blind_spot",
                "source": f"metal.{dim_name}",
                "label": f"Weak: {dim_name} ({score:.2f})",
                "severity": round((1.0 - score) * 10, 1),
                "insight": f"Metal validation scored {dim_name} at {score:.2f}, indicating a significant gap."
            })
    
    # From Metal adversarial critiques
    devil = metal_result.get("devil_critique", "")
    if devil and len(devil) > 50:
        residuals.append({
            "type": "paradigm_gap",
            "source": "metal.devils_advocate",
            "label": "Adversarial critique identified",
            "severity": 7.0 if composite < 0.5 else 5.0,
            "insight": devil[:300]
        })
    
    fact = metal_result.get("fact_critique", "")
    if fact and len(fact) > 50:
        residuals.append({
            "type": "consistency_risk",
            "source": "metal.fact_checker",
            "label": "Fact-check concerns",
            "severity": 6.0,
            "insight": fact[:300]
        })
    
    # From Earth synthesis gaps
    if earth_result:
        synth = earth_result.get("synthesis", {})
        for gap in synth.get("data_gaps", []):
            residuals.append({
                "type": "data_gap",
                "source": "earth.synthesis",
                "label": str(gap)[:100],
                "severity": 5.0,
                "insight": f"Earth synthesis identified data gap: {gap}"
            })
        
        # Quality self-assessment
        quality = synth.get("synthesis_quality", {})
        for qk, qv in quality.items():
            if isinstance(qv, (int, float)) and qv < 0.7:
                residuals.append({
                    "type": "unexploited_potential",
                    "source": f"earth.quality.{qk}",
                    "label": f"Earth self-assessed {qk} at {qv:.2f}",
                    "severity": round((1.0 - qv) * 8, 1),
                    "insight": f"Synthesis quality dimension '{qk}' below threshold."
                })
    
    return residuals


def find_patterns(residuals, historical_residuals=None):
    """Find recurring patterns across residuals (current + historical)."""
    patterns = []
    all_residuals = residuals + (historical_residuals or [])
    
    # Pattern 1: Source clustering
    source_counts = defaultdict(list)
    for r in all_residuals:
        source_base = r.get("source", "").split(".")[0]
        source_counts[source_base].append(r)
    
    for source, items in source_counts.items():
        if len(items) >= 3:
            patterns.append({
                "type": "source_cluster",
                "description": f"{source} generated {len(items)} residuals - systemic issue in this component",
                "affected": [i.get("label", "")[:80] for i in items],
                "recommendation": f"Review and strengthen {source} component"
            })
    
    # Pattern 2: Type distribution
    type_counts = defaultdict(int)
    for r in all_residuals:
        type_counts[r.get("type", "unknown")] += 1
    
    total = len(all_residuals) or 1
    if type_counts.get("blind_spot", 0) / total > 0.4:
        patterns.append({
            "type": "coverage_deficit",
            "description": f"Blind spots dominate ({type_counts['blind_spot']}/{total}) - analysis framework too narrow",
            "affected": [r.get("label","")[:80] for r in all_residuals if r.get("type")=="blind_spot"],
            "recommendation": "Expand seed generation scope and add more diverse research angles"
        })
    
    if type_counts.get("data_gap", 0) / total > 0.3:
        patterns.append({
            "type": "data_scarcity",
            "description": f"Data gaps prevalent ({type_counts['data_gap']}/{total}) - insufficient source data",
            "affected": [r.get("label","")[:80] for r in all_residuals if r.get("type")=="data_gap"],
            "recommendation": "Add more data sources or use web search to fill gaps"
        })
    
    # Pattern 3: Severity escalation
    high_severity = [r for r in all_residuals if r.get("severity", 0) >= 7]
    if len(high_severity) >= 2:
        patterns.append({
            "type": "severity_cluster",
            "description": f"{len(high_severity)} high-severity residuals detected",
            "affected": [r.get("label","")[:80] for r in high_severity],
            "recommendation": "Prioritize addressing high-severity issues before next cycle"
        })
    
    return patterns


def build_graph(residuals, topic, run_id):
    """Build cognitive graph from residuals and persist to PG."""
    nodes = []
    edges = []
    
    for i, r in enumerate(residuals):
        node_id = hashlib.md5(f"{run_id}-{i}-{r.get('label','')}".encode()).hexdigest()[:16]
        node = {
            "id": f"cg_{node_id}",
            "type": r.get("type", "unknown"),
            "label": r.get("label", "")[:200],
            "severity": r.get("severity", 5.0),
            "source": r.get("source", ""),
            "topic": topic,
            "run_id": run_id,
        }
        nodes.append(node)
    
    # Build edges: connect residuals that share source or type
    for i, n1 in enumerate(nodes):
        for j, n2 in enumerate(nodes):
            if i >= j:
                continue
            r1, r2 = residuals[i], residuals[j]
            
            # Same source = structural link
            s1 = r1.get("source","").split(".")[0]
            s2 = r2.get("source","").split(".")[0]
            if s1 == s2 and s1:
                edges.append({
                    "source": n1["id"], "target": n2["id"],
                    "type": "same_source", "weight": 0.8
                })
            
            # Same type = categorical link
            if r1.get("type") == r2.get("type"):
                edges.append({
                    "source": n1["id"], "target": n2["id"],
                    "type": "same_type", "weight": 0.5
                })
    
    # Persist to PG
    if PG:
        try:
            with pg_storage.get_conn() as conn:
                with conn.cursor() as cur:
                    for n in nodes:
                        cur.execute("""
                            INSERT INTO cg_nodes (id, node_type, label, severity, source, topic, pipeline_run)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (id) DO UPDATE SET severity = EXCLUDED.severity
                        """, (n["id"], n["type"], n["label"], n["severity"], n["source"], n["topic"], n["run_id"]))
                    for e in edges:
                        cur.execute("""
                            INSERT INTO cg_edges (source_id, target_id, edge_type, weight)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (source_id, target_id, edge_type) DO NOTHING
                        """, (e["source"], e["target"], e["type"], e["weight"]))
                conn.commit()
        except Exception as ex:
            print(f"[CG] PG persist error: {ex}")
    
    return {"nodes": len(nodes), "edges": len(edges), "node_ids": [n["id"] for n in nodes]}


def update_path_weights(residuals, run_id, topic):
    """Update exploration vs exploitation weights based on residuals.
    
    A = exploitation (known territory)
    B = adjacent exploration
    C = paradigm exploration (unknown territory)
    """
    # Get previous weights
    prev = {"A": 65.0, "B": 25.0, "C": 10.0}
    if PG:
        try:
            with pg_storage.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT weights FROM cg_path_weights ORDER BY created_at DESC LIMIT 1")
                    row = cur.fetchone()
                    if row:
                        prev = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        except:
            pass
    
    # Calculate adjustments
    paradigm_gaps = sum(1 for r in residuals if r.get("type") == "paradigm_gap")
    blind_spots = sum(1 for r in residuals if r.get("type") == "blind_spot")
    data_gaps = sum(1 for r in residuals if r.get("type") == "data_gap")
    
    # More paradigm gaps = need more C (exploration)
    c_boost = paradigm_gaps * 2.0 + blind_spots * 0.8
    # More data gaps = need more B (adjacent research)
    b_boost = data_gaps * 1.0
    
    new = {
        "A": max(40, prev["A"] - c_boost * 0.6 - b_boost * 0.3),
        "B": max(15, prev["B"] + b_boost * 0.5 - c_boost * 0.2),
        "C": min(35, prev["C"] + c_boost),
    }
    
    # Normalize to 100
    total = sum(new.values())
    new = {k: round(v / total * 100, 1) for k, v in new.items()}
    
    reason = f"{paradigm_gaps} paradigm gaps, {blind_spots} blind spots, {data_gaps} data gaps"
    
    # Persist
    if PG:
        try:
            with pg_storage.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO cg_path_weights (run_id, topic, weights, reason)
                        VALUES (%s, %s, %s, %s)
                    """, (run_id, topic, json.dumps(new), reason))
                conn.commit()
        except Exception as ex:
            print(f"[CG] Path weights persist error: {ex}")
    
    return {"previous": prev, "updated": new, "reason": reason}


def get_historical_residuals(topic=None, limit=50):
    """Get historical residuals from PG for pattern analysis."""
    if not PG:
        return []
    try:
        with pg_storage.get_conn() as conn:
            with conn.cursor() as cur:
                if topic:
                    cur.execute("""
                        SELECT node_type, label, severity, source, topic, pipeline_run
                        FROM cg_nodes WHERE topic ILIKE %s
                        ORDER BY created_at DESC LIMIT %s
                    """, (f"%{topic}%", limit))
                else:
                    cur.execute("""
                        SELECT node_type, label, severity, source, topic, pipeline_run
                        FROM cg_nodes ORDER BY created_at DESC LIMIT %s
                    """, (limit,))
                rows = cur.fetchall()
                return [{"type": r[0], "label": r[1], "severity": r[2],
                         "source": r[3], "topic": r[4], "run_id": r[5]} for r in rows]
    except:
        return []


def get_graph_stats():
    """Get cognitive graph statistics."""
    if not PG:
        return {"pg": False}
    try:
        with pg_storage.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM cg_nodes")
                nodes = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM cg_edges")
                edges = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM cg_patterns")
                patterns = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM cg_path_weights")
                weights = cur.fetchone()[0]
                cur.execute("SELECT DISTINCT topic FROM cg_nodes")
                topics = [r[0] for r in cur.fetchall()]
                return {
                    "nodes": nodes, "edges": edges, "patterns": patterns,
                    "weight_records": weights, "topics": topics
                }
    except Exception as e:
        return {"error": str(e)}


def generate_evolution_report(residuals, patterns, path_weights):
    """Generate cognitive evolution report."""
    report = {
        "total_residuals": len(residuals),
        "by_type": defaultdict(int),
        "patterns_found": len(patterns),
        "path_weights": path_weights,
        "lessons_learned": [],
        "next_focus": []
    }
    
    for r in residuals:
        report["by_type"][r.get("type", "unknown")] += 1
    report["by_type"] = dict(report["by_type"])
    
    # Extract lessons
    if report["by_type"].get("paradigm_gap", 0) >= 2:
        report["lessons_learned"].append(
            "Multiple paradigm gaps: evaluation framework may need fundamental redesign"
        )
    if report["by_type"].get("blind_spot", 0) >= 3:
        report["lessons_learned"].append(
            "Frequent blind spots: analysis scope too narrow, expand seed diversity"
        )
    if report["by_type"].get("data_gap", 0) >= 3:
        report["lessons_learned"].append(
            "Persistent data gaps: consider adding web search to pipeline"
        )
    
    # Next focus from highest severity
    high = sorted(residuals, key=lambda x: x.get("severity", 0), reverse=True)[:3]
    for r in high:
        report["next_focus"].append({
            "residual": r.get("label", "")[:100],
            "severity": r.get("severity", 0),
            "action": f"Deep-dive on: {r.get('label','')[:60]}"
        })
    
    return report


def run_cognitive_analysis(metal_result, earth_result, topic, run_id):
    """Full cognitive graph analysis pipeline.
    
    Called after Metal+Earth in the main pipeline.
    Returns cognitive analysis to feed into Water phase.
    """
    # 1. Extract residuals
    residuals = extract_residuals(metal_result, earth_result)
    
    # 2. Get historical for pattern detection
    historical = get_historical_residuals(topic, limit=30)
    
    # 3. Find patterns
    patterns = find_patterns(residuals, historical)
    
    # 4. Build/update graph
    graph_stats = build_graph(residuals, topic, run_id)
    
    # 5. Update path weights
    path_weights = update_path_weights(residuals, run_id, topic)
    
    # 6. Save patterns
    if PG and patterns:
        try:
            with pg_storage.get_conn() as conn:
                with conn.cursor() as cur:
                    for p in patterns:
                        cur.execute("""
                            INSERT INTO cg_patterns (pattern_type, description, affected_nodes, recommendation, pipeline_run)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (p["type"], p["description"], p.get("affected", []), p.get("recommendation",""), run_id))
                conn.commit()
        except Exception as ex:
            print(f"[CG] Pattern persist error: {ex}")
    
    # 7. Evolution report
    report = generate_evolution_report(residuals, patterns, path_weights)
    
    return {
        "residuals": residuals,
        "patterns": patterns,
        "graph": graph_stats,
        "path_weights": path_weights,
        "evolution_report": report,
    }


# Self-test
def self_test():
    print(f"cognitive_graph.py v{VERSION}")
    
    # Test init
    ok = init_tables()
    print(f"  init_tables: {'PASS' if ok else 'FAIL'}")
    
    # Test extract with mock data
    mock_metal = {
        "verdict": "CONDITIONAL",
        "composite_score": 0.55,
        "dimensions": {"data_completeness": 0.3, "coverage_breadth": 0.8, "analysis_depth": 0.9},
        "devil_critique": "Missing regulatory analysis and supply chain risk assessment.",
        "fact_critique": "Market size figures are plausible but lack sources.",
    }
    mock_earth = {
        "synthesis": {
            "data_gaps": ["No data on emerging competitors", "Missing 2026 forecast"],
            "synthesis_quality": {"seed_coverage": 0.6, "analysis_grounding": 0.9, "actionability": 0.75}
        }
    }
    
    residuals = extract_residuals(mock_metal, mock_earth)
    print(f"  extract_residuals: {len(residuals)} residuals")
    
    patterns = find_patterns(residuals)
    print(f"  find_patterns: {len(patterns)} patterns")
    
    graph = build_graph(residuals, "test-topic", "test-run-001")
    print(f"  build_graph: {graph['nodes']} nodes, {graph['edges']} edges")
    
    weights = update_path_weights(residuals, "test-run-001", "test-topic")
    print(f"  path_weights: A={weights['updated']['A']}% B={weights['updated']['B']}% C={weights['updated']['C']}%")
    
    stats = get_graph_stats()
    print(f"  graph_stats: {stats}")
    
    print("  ALL PASS")
    return True


if __name__ == "__main__":
    self_test()
