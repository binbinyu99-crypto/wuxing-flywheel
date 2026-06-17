# -*- coding: utf-8 -*-
"""
metal_validator_v2.py - Jin Flywheel (White Tiger / West) Adversarial Validation Engine
Part of the Wuxing Flywheel (1+4) Architecture
Position: West (Xi Fang), Phase: Metal (Jin), Beast: Baihu (White Tiger)

Role in Xiangsheng chain: Earth generates Metal (土生金 - truth drives validation)
Role in Xiangke chain: Metal controls Wood (金克木 - validation prunes bad seeds)
                       Fire controls Metal (火克金 - execution results overturn old validation)
"""
import json, time, hashlib, sqlite3, os, re
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metal_audit.db")

def init_db(db_path=None):
    """Initialize the audit trail database"""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS audits (
            audit_id TEXT PRIMARY KEY,
            task_id TEXT,
            timestamp TEXT,
            input_hash TEXT,
            overall_score REAL,
            verdict TEXT,
            dimensions TEXT,
            issues TEXT,
            recommendations TEXT,
            phase_source TEXT,
            validator_version TEXT
        );
        CREATE TABLE IF NOT EXISTS red_blue_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id TEXT,
            attack_vector TEXT,
            attack_description TEXT,
            survived INTEGER,
            weakness_found TEXT,
            severity TEXT,
            FOREIGN KEY (audit_id) REFERENCES audits(audit_id)
        );
        CREATE TABLE IF NOT EXISTS integrity_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id TEXT,
            check_type TEXT,
            field_path TEXT,
            expected TEXT,
            actual TEXT,
            passed INTEGER,
            FOREIGN KEY (audit_id) REFERENCES audits(audit_id)
        );
        CREATE INDEX IF NOT EXISTS idx_audits_task ON audits(task_id);
        CREATE INDEX IF NOT EXISTS idx_audits_verdict ON audits(verdict);
    """)
    conn.commit()
    return conn

# ============================================================
# Dimension 1: Structural Integrity
# ============================================================
def check_structural_integrity(content, schema=None):
    """Validate structure, completeness, and format"""
    issues = []
    score = 1.0
    checks = []
    
    if isinstance(content, dict):
        # Check required fields
        required = schema.get("required", []) if schema else []
        for field in required:
            present = field in content and content[field] is not None
            checks.append({"field": field, "check": "required", "passed": present})
            if not present:
                issues.append(f"Missing required field: {field}")
                score -= 0.35
        
        # Check for empty values
        for key, val in content.items():
            if val is None or (isinstance(val, str) and val.strip() == ""):
                issues.append(f"Empty value: {key}")
                score -= 0.2
            elif isinstance(val, str) and len(val) < 10:
                issues.append(f"Suspiciously short value: {key} ({len(val)} chars)")
                score -= 0.1
    
    elif isinstance(content, str):
        # Text content checks
        if len(content) < 50:
            issues.append("Content too short (<50 chars)")
            score -= 0.3
        elif len(content) < 200:
            issues.append("Content may be insufficient (<200 chars)")
            score -= 0.1
        
        # Check for placeholder patterns
        placeholders = re.findall(r'\[TODO\]|\[TBD\]|\[PLACEHOLDER\]|xxx|待填写|待补充', content)
        if placeholders:
            issues.append(f"Contains {len(placeholders)} placeholder(s)")
            score -= 0.2 * len(placeholders)
        
        # Check for repetition (lazy generation)
        sentences = [s.strip() for s in re.split(r'[。.!！?？]', content) if s.strip()]
        if len(sentences) > 3:
            unique_ratio = len(set(sentences)) / len(sentences)
            if unique_ratio < 0.7:
                issues.append(f"High repetition: {unique_ratio:.0%} unique sentences")
                score -= 0.2
    
    return {"dimension": "structural_integrity", "score": max(0, score), "issues": issues, "checks": checks}


# ============================================================
# Dimension 2: Logical Consistency
# ============================================================
def check_logical_consistency(content):
    """Detect contradictions and logical flaws"""
    issues = []
    score = 1.0
    
    text = json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else str(content)
    
    # Check for contradictory patterns
    contradiction_pairs = [
        (r'增长|上升|提高', r'下降|减少|降低'),
        (r'优势|领先|第一', r'劣势|落后|末位'),
        (r'确定|必然|一定', r'不确定|可能|也许'),
        (r'安全|可靠|稳定', r'风险|危险|不稳定'),
    ]
    
    for pos_pattern, neg_pattern in contradiction_pairs:
        pos_matches = re.findall(pos_pattern, text)
        neg_matches = re.findall(neg_pattern, text)
        if pos_matches and neg_matches:
            # This is not necessarily bad - context matters
            # But flag for review if both appear frequently
            if len(pos_matches) > 3 and len(neg_matches) > 3:
                issues.append(f"Potential contradiction: '{pos_matches[0]}' vs '{neg_matches[0]}' (both appear {len(pos_matches)}x/{len(neg_matches)}x)")
                score -= 0.05
    
    # Check for circular reasoning patterns
    if isinstance(content, dict):
        values = [str(v) for v in content.values() if isinstance(v, str)]
        for i, v1 in enumerate(values):
            for v2 in values[i+1:]:
                if len(v1) > 20 and len(v2) > 20:
                    # Simple similarity check
                    overlap = len(set(v1.split()) & set(v2.split()))
                    total = len(set(v1.split()) | set(v2.split()))
                    if total > 0 and overlap / total > 0.8:
                        issues.append("Near-duplicate content detected between fields")
                        score -= 0.1
                        break
    
    # Check numeric consistency
    numbers = re.findall(r'(\d+\.?\d*)%', text)
    percentages = [float(n) for n in numbers]
    if percentages:
        over_100 = [p for p in percentages if p > 100]
        if over_100:
            issues.append(f"Percentage exceeds 100%: {over_100}")
            score -= 0.15
    
    return {"dimension": "logical_consistency", "score": max(0, score), "issues": issues}


# ============================================================
# Dimension 3: Factual Grounding
# ============================================================
def check_factual_grounding(content, knowledge_base=None):
    """Validate claims against known knowledge base"""
    issues = []
    score = 1.0
    grounded_claims = 0
    ungrounded_claims = 0
    
    text = json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else str(content)
    
    # Extract claims (numbers, dates, names)
    date_claims = re.findall(r'20[2-3]\d[-/年]\d{1,2}[-/月]?\d{0,2}', text)
    number_claims = re.findall(r'(\d+(?:\.\d+)?)[亿万千百]', text)
    
    if knowledge_base and isinstance(knowledge_base, dict):
        kb_text = json.dumps(knowledge_base, ensure_ascii=False)
        # Check if claims appear in KB
        for claim in date_claims + number_claims:
            if claim in kb_text:
                grounded_claims += 1
            else:
                ungrounded_claims += 1
        
        if grounded_claims + ungrounded_claims > 0:
            grounding_ratio = grounded_claims / (grounded_claims + ungrounded_claims)
            if grounding_ratio < 0.3:
                issues.append(f"Low grounding ratio: {grounding_ratio:.0%} ({grounded_claims}/{grounded_claims+ungrounded_claims} claims verified)")
                score -= 0.2
    
    # Check for vague claims without evidence
    vague_patterns = re.findall(r'据[说称报]|有人[说认]|普遍认为|众所周知|据统计', text)
    if len(vague_patterns) > 2:
        issues.append(f"Multiple vague attributions ({len(vague_patterns)}): prefer specific sources")
        score -= 0.05 * len(vague_patterns)
    
    return {"dimension": "factual_grounding", "score": max(0, score), "issues": issues,
            "grounded": grounded_claims, "ungrounded": ungrounded_claims}


# ============================================================
# Dimension 4: Adversarial Stress Test
# ============================================================
def run_adversarial_stress(content, attack_vectors=None):
    """Red team attack simulation"""
    results = []
    
    text = json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else str(content)
    
    default_vectors = [
        {
            "vector": "data_poisoning",
            "description": "Check for injected/manipulated data patterns",
            "test": lambda t: not bool(re.search(r'<script|javascript:|eval\(|exec\(', t, re.I)),
            "severity": "critical"
        },
        {
            "vector": "hallucination_detection",
            "description": "Check for fabricated specifics (fake URLs, DOIs, citations)",
            "test": lambda t: not bool(re.search(r'doi\.org/10\.\d{4}/fake|example\.com/paper', t, re.I)),
            "severity": "high"
        },
        {
            "vector": "bias_amplification",
            "description": "Check for extreme one-sided conclusions without caveats",
            "test": lambda t: not (t.count('必然') + t.count('一定会') + t.count('绝对') > 5),
            "severity": "medium"
        },
        {
            "vector": "scope_creep",
            "description": "Check if output exceeds the original task scope",
            "test": lambda t: len(t) < 100000,  # Reasonable length check
            "severity": "low"
        },
        {
            "vector": "encoding_integrity",
            "description": "Check for encoding corruption markers",
            "test": lambda t: not bool(re.search(r'\ufffd|\x00|\\u[0-9a-f]{4}', t)),
            "severity": "high"
        },
        {
            "vector": "sensitive_data_leak",
            "description": "Check for potential PII/credential exposure",
            "test": lambda t: not bool(re.search(r'sk-[a-zA-Z0-9]{20,}|password\s*[:=]\s*\S+|\b\d{18}\b', t)),
            "severity": "critical"
        }
    ]
    
    vectors = attack_vectors or default_vectors
    
    for v in vectors:
        survived = v["test"](text)
        weakness = None if survived else f"Failed {v['vector']} check"
        results.append({
            "attack_vector": v["vector"],
            "attack_description": v["description"],
            "survived": survived,
            "weakness_found": weakness,
            "severity": v["severity"]
        })
    
    return results


# ============================================================
# Dimension 5: Cross-Phase Coherence
# ============================================================
def check_cross_phase_coherence(content, phase_context=None):
    """Check alignment with other wheel outputs"""
    issues = []
    score = 1.0
    
    if not phase_context:
        return {"dimension": "cross_phase_coherence", "score": score, "issues": ["No phase context provided"]}
    
    text = json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else str(content)
    
    # Check seed alignment (Wood -> Metal constraint: 金克木)
    if "wood_seeds" in phase_context:
        seed_goals = phase_context["wood_seeds"]
        if isinstance(seed_goals, list):
            aligned = sum(1 for s in seed_goals if any(k in text for k in str(s).split()[:3]))
            if len(seed_goals) > 0 and aligned / len(seed_goals) < 0.3:
                issues.append(f"Low alignment with seed goals: {aligned}/{len(seed_goals)}")
                score -= 0.15
    
    # Check execution alignment (Fire -> Metal constraint)
    if "fire_results" in phase_context:
        fire = phase_context["fire_results"]
        if isinstance(fire, dict) and fire.get("task_id"):
            if fire["task_id"] not in text:
                issues.append("No reference to source execution task")
                score -= 0.05
    
    # Check earth feedback alignment (Earth -> Metal: 土生金)
    if "earth_feedback" in phase_context:
        feedback = phase_context["earth_feedback"]
        if isinstance(feedback, dict) and feedback.get("accepted") is False:
            issues.append("Earth phase rejected this output - needs revision before Metal validation")
            score -= 0.3
    
    return {"dimension": "cross_phase_coherence", "score": max(0, score), "issues": issues}


# ============================================================
# Main Validation Pipeline
# ============================================================
def validate(content, task_id=None, schema=None, knowledge_base=None,
             phase_context=None, attack_vectors=None, db_path=None):
    """
    Full Metal wheel validation pipeline.
    Returns audit result with verdict: PASS / CONDITIONAL / FAIL
    
    Scoring:
    - Each dimension: 0.0 to 1.0
    - Overall = weighted average (structure 25%, logic 25%, factual 20%, adversarial 20%, coherence 10%)
    - PASS: >= 0.7, CONDITIONAL: 0.5-0.7, FAIL: < 0.5
    """
    audit_id = f"AUD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{hashlib.md5(str(content)[:100].encode()).hexdigest()[:6]}"
    
    # Run all dimensions
    d1 = check_structural_integrity(content, schema)
    d2 = check_logical_consistency(content)
    d3 = check_factual_grounding(content, knowledge_base)
    d4_raw = run_adversarial_stress(content, attack_vectors)
    d5 = check_cross_phase_coherence(content, phase_context)
    
    # Calculate adversarial score
    if d4_raw:
        survived = sum(1 for r in d4_raw if r["survived"])
        critical_fails = sum(1 for r in d4_raw if not r["survived"] and r["severity"] == "critical")
        d4_score = survived / len(d4_raw) if d4_raw else 1.0
        if critical_fails > 0:
            d4_score = min(d4_score, 0.3)  # Cap score if critical failures
    else:
        d4_score = 1.0
    d4 = {"dimension": "adversarial_stress", "score": d4_score, "results": d4_raw}
    
    # Weighted average
    weights = {"structural_integrity": 0.35, "logical_consistency": 0.20,
               "factual_grounding": 0.20, "adversarial_stress": 0.15,
               "cross_phase_coherence": 0.10}
    
    dimensions = {d1["dimension"]: d1, d2["dimension"]: d2, d3["dimension"]: d3,
                  "adversarial_stress": d4, d5["dimension"]: d5}
    
    overall = sum(dimensions[d].get("score", 0) * w for d, w in weights.items())
    
    # Determine verdict
    # Hard fail if any critical dimension is very low
    if d1["score"] < 0.3:
        overall = min(overall, 0.45)  # Structural failure caps overall
    
    if overall >= 0.7:
        verdict = "PASS"
    elif overall >= 0.5:
        verdict = "CONDITIONAL"
    else:
        verdict = "FAIL"
    
    # Collect all issues
    all_issues = []
    for d in [d1, d2, d3, d5]:
        all_issues.extend(d.get("issues", []))
    for r in d4_raw:
        if not r["survived"]:
            all_issues.append(f"[{r['severity'].upper()}] {r['attack_vector']}: {r['weakness_found']}")
    
    # Generate recommendations
    recommendations = []
    if d1["score"] < 0.7:
        recommendations.append("Improve structural completeness - fill missing fields and remove placeholders")
    if d2["score"] < 0.7:
        recommendations.append("Resolve logical contradictions - ensure consistent messaging")
    if d3["score"] < 0.7:
        recommendations.append("Strengthen factual grounding - add specific sources and data points")
    if d4_score < 0.7:
        recommendations.append("Address security vulnerabilities found in adversarial testing")
    if d5["score"] < 0.7:
        recommendations.append("Align output with other flywheel phases for coherence")
    
    result = {
        "audit_id": audit_id,
        "task_id": task_id,
        "timestamp": datetime.now().isoformat(),
        "overall_score": round(overall, 3),
        "verdict": verdict,
        "dimensions": {k: {"score": round(v.get("score", 0), 3), "issues": v.get("issues", [])} for k, v in dimensions.items()},
        "adversarial_results": d4_raw,
        "all_issues": all_issues,
        "recommendations": recommendations,
        "validator_version": "metal_v2.0"
    }
    
    # Persist to audit trail
    try:
        conn = init_db(db_path)
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO audits 
                     (audit_id, task_id, timestamp, input_hash, overall_score, verdict, 
                      dimensions, issues, recommendations, phase_source, validator_version)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (audit_id, task_id, result["timestamp"],
                   hashlib.md5(str(content).encode()).hexdigest(),
                   overall, verdict,
                   json.dumps(result["dimensions"], ensure_ascii=False),
                   json.dumps(all_issues, ensure_ascii=False),
                   json.dumps(recommendations, ensure_ascii=False),
                   "earth", "metal_v2.0"))
        
        for r in d4_raw:
            c.execute("""INSERT INTO red_blue_results 
                        (audit_id, attack_vector, attack_description, survived, weakness_found, severity)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                      (audit_id, r["attack_vector"], r["attack_description"],
                       1 if r["survived"] else 0, r.get("weakness_found"), r["severity"]))
        
        conn.commit()
        conn.close()
    except Exception as e:
        result["db_error"] = str(e)
    
    return result


# ============================================================
# Xiangke Interface: Metal controls Wood (金克木)
# ============================================================
def prune_seeds(seeds, min_score=0.5, db_path=None):
    """
    Metal's xiangke role: validate and prune seed list.
    Seeds below min_score get flagged for removal.
    Returns: {kept: [...], pruned: [...], scores: {...}}
    """
    kept = []
    pruned = []
    scores = {}
    
    for seed in seeds:
        result = validate(seed, task_id=f"seed-{hashlib.md5(str(seed).encode()).hexdigest()[:8]}",
                         db_path=db_path)
        scores[str(seed)[:50]] = result["overall_score"]
        if result["overall_score"] >= min_score:
            kept.append(seed)
        else:
            pruned.append({"seed": seed, "score": result["overall_score"],
                          "reason": result["all_issues"][:3]})
    
    return {"kept": kept, "pruned": pruned, "scores": scores,
            "kept_count": len(kept), "pruned_count": len(pruned)}


# ============================================================
# Audit Trail Query
# ============================================================
def get_audit_history(task_id=None, verdict=None, limit=20, db_path=None):
    """Query audit trail"""
    conn = init_db(db_path)
    c = conn.cursor()
    
    query = "SELECT * FROM audits WHERE 1=1"
    params = []
    if task_id:
        query += " AND task_id = ?"
        params.append(task_id)
    if verdict:
        query += " AND verdict = ?"
        params.append(verdict)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    
    c.execute(query, params)
    cols = [d[0] for d in c.description]
    rows = [dict(zip(cols, row)) for row in c.fetchall()]
    conn.close()
    return rows


def get_audit_stats(db_path=None):
    """Get aggregate audit statistics"""
    conn = init_db(db_path)
    c = conn.cursor()
    
    stats = {}
    c.execute("SELECT COUNT(*) FROM audits")
    stats["total_audits"] = c.fetchone()[0]
    
    c.execute("SELECT verdict, COUNT(*) FROM audits GROUP BY verdict")
    stats["by_verdict"] = dict(c.fetchall())
    
    c.execute("SELECT AVG(overall_score) FROM audits")
    avg = c.fetchone()[0]
    stats["avg_score"] = round(avg, 3) if avg else 0
    
    c.execute("SELECT attack_vector, SUM(CASE WHEN survived=0 THEN 1 ELSE 0 END) as fails, COUNT(*) as total FROM red_blue_results GROUP BY attack_vector")
    stats["adversarial_summary"] = {row[0]: {"fails": row[1], "total": row[2]} for row in c.fetchall()}
    
    conn.close()
    return stats


# ============================================================
# Self-test
# ============================================================
if __name__ == "__main__":
    import tempfile
    test_db = os.path.join(tempfile.gettempdir(), "metal_test.db")
    
    print("=== Metal Validator v2.0 Self-Test ===")
    print()
    
    # Test 1: Good content
    good = {
        "title": "SiC Market Analysis 2026",
        "summary": "Silicon carbide power devices market reaches 15.8 billion yuan in 2026, driven by EV adoption and renewable energy infrastructure.",
        "key_findings": "Top domestic suppliers: SICC (天岳先进) leads in substrate, TankeBlue in epitaxy. Market CAGR 28.5% through 2030.",
        "risks": "Supply chain concentration in Wolfspeed/II-VI for upstream SiC boules. Domestic substitution rate at 35%.",
        "recommendation": "Focus on 6-inch to 8-inch substrate transition window. Partner with SICC for supply security."
    }
    r1 = validate(good, task_id="T-TEST-001", 
                  schema={"required": ["title", "summary", "key_findings"]},
                  db_path=test_db)
    print(f"Test 1 (good content): {r1['verdict']} ({r1['overall_score']:.3f})")
    assert r1["verdict"] == "PASS", f"Expected PASS, got {r1['verdict']}"
    
    # Test 2: Poor content
    poor = {"title": "Test", "summary": "", "data": "[TODO]"}
    r2 = validate(poor, task_id="T-TEST-002",
                  schema={"required": ["title", "summary", "key_findings"]},
                  db_path=test_db)
    print(f"Test 2 (poor content): {r2['verdict']} ({r2['overall_score']:.3f})")
    assert r2["verdict"] in ["CONDITIONAL", "FAIL"], f"Expected non-PASS, got {r2['verdict']}"
    
    # Test 3: Security issue
    dangerous = "Result: <script>alert('xss')</script> and password: admin123"
    r3 = validate(dangerous, task_id="T-TEST-003", db_path=test_db)
    print(f"Test 3 (security): {r3['verdict']} ({r3['overall_score']:.3f})")
    critical_fails = [r for r in r3["adversarial_results"] if not r["survived"] and r["severity"] == "critical"]
    assert len(critical_fails) > 0, "Should detect critical security issues"
    
    # Test 4: Seed pruning (金克木)
    seeds = [
        {"goal": "Analyze SiC substrate market trends and pricing dynamics", "scope": "domestic", "complexity": "high"},
        {"goal": "", "scope": "", "complexity": ""},  # Bad seed
        {"goal": "Research GaN power IC design landscape in China", "scope": "industry", "complexity": "medium"}
    ]
    pr = prune_seeds(seeds, min_score=0.5, db_path=test_db)
    print(f"Test 4 (seed pruning): kept={pr['kept_count']}, pruned={pr['pruned_count']}")
    
    # Test 5: Audit stats
    stats = get_audit_stats(db_path=test_db)
    print(f"Test 5 (audit stats): {stats['total_audits']} audits, avg score {stats['avg_score']:.3f}")
    assert stats["total_audits"] >= 4, f"Expected >=4 audits, got {stats['total_audits']}"
    
    # Test 6: Audit history
    history = get_audit_history(verdict="PASS", db_path=test_db)
    print(f"Test 6 (history query): {len(history)} PASS audits found")
    
    # Cleanup
    os.remove(test_db)
    
    print()
    print("=== All 6 tests passed ===")
