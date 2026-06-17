# -*- coding: utf-8 -*-
"""
Water Engine (Xuanwu/North) - Cognition Distillation & Knowledge Convergence
Part of the Wuxing Flywheel System

Role in xiangsheng chain: metal->water (Validation Distills Knowledge)
Role in xiangke chain: water->fire (Knowledge Constrains Reckless Execution)

Core functions:
1. Residual extraction - extract learning from task results
2. Pattern recognition - identify recurring patterns across tasks  
3. Knowledge convergence - score how well knowledge consolidates
4. Seed generation - produce new seeds from distilled knowledge (water->wood)
"""
import json, os, sqlite3, time, hashlib, re
from datetime import datetime
from collections import Counter

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "water_cognition.db")

def _init_db(db_path=None):
    p = db_path or DB_PATH
    conn = sqlite3.connect(p)
    conn.execute("CREATE TABLE IF NOT EXISTS residuals (id TEXT PRIMARY KEY, task_id TEXT, source_phase TEXT, content TEXT, patterns TEXT, convergence_score REAL, created_at TEXT, domain TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS knowledge_atoms (id TEXT PRIMARY KEY, concept TEXT, domain TEXT, confidence REAL, evidence_count INTEGER, first_seen TEXT, last_updated TEXT, sources TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS convergence_log (id TEXT PRIMARY KEY, domain TEXT, score REAL, atom_count INTEGER, pattern_count INTEGER, timestamp TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS generated_seeds (id TEXT PRIMARY KEY, source_residual TEXT, seed_text TEXT, domain TEXT, priority REAL, created_at TEXT)")
    conn.commit()
    return conn

def extract_residual(task_result, task_id=None, source_phase="earth", domain="general"):
    """Extract residual knowledge from a completed task result"""
    conn = _init_db()
    
    content = task_result if isinstance(task_result, str) else json.dumps(task_result, ensure_ascii=False)
    
    # Pattern extraction
    patterns = []
    
    # 1. Numeric patterns (percentages, growth rates, market sizes)
    nums = re.findall(r'(\d+\.?\d*)\s*(%|percent|billion|million|CAGR|growth)', content, re.IGNORECASE)
    for val, unit in nums:
        patterns.append({"type": "numeric", "value": float(val), "unit": unit.lower(), "context": f"{val}{unit}"})
    
    # 2. Entity patterns (companies, technologies, materials)
    tech_keywords = ["SiC", "GaN", "CFRP", "InP", "AI", "LLM", "GPU", "FPGA", "EDA", "MOSFET", 
                     "wafer", "epitaxy", "substrate", "chip", "semiconductor", "battery", "solar",
                     "perovskite", "graphene", "CNT", "quantum", "photonic"]
    found_tech = [kw for kw in tech_keywords if kw.lower() in content.lower()]
    for t in found_tech:
        patterns.append({"type": "technology", "value": t})
    
    # 3. Causal patterns (because, therefore, leads to, results in)
    causal = re.findall(r'(?:because|therefore|leads?\s+to|results?\s+in|causes?|driven\s+by|due\s+to)\s+([^,.]{10,80})', content, re.IGNORECASE)
    for c in causal[:5]:
        patterns.append({"type": "causal", "value": c.strip()})
    
    # 4. Comparative patterns
    comparisons = re.findall(r'(?:better|worse|higher|lower|faster|slower|cheaper|more expensive)\s+than\s+([^,.]{5,50})', content, re.IGNORECASE)
    for c in comparisons[:5]:
        patterns.append({"type": "comparative", "value": c.strip()})
    
    # Convergence scoring
    pattern_diversity = len(set(p["type"] for p in patterns))
    pattern_count = len(patterns)
    content_depth = min(len(content) / 5000, 1.0)  # normalize to 0-1
    
    convergence_score = (
        0.3 * min(pattern_count / 10, 1.0) +  # pattern richness
        0.3 * min(pattern_diversity / 4, 1.0) +  # pattern diversity
        0.2 * content_depth +  # content depth
        0.2 * (1.0 if domain != "general" else 0.5)  # domain specificity
    )
    
    rid = f"R-{datetime.now().strftime('%Y%m%d%H%M%S')}-{hashlib.md5(content[:200].encode()).hexdigest()[:6]}"
    
    conn.execute(
        "INSERT OR REPLACE INTO residuals VALUES (?,?,?,?,?,?,?,?)",
        (rid, task_id or "unknown", source_phase, content[:5000], 
         json.dumps(patterns, ensure_ascii=False), convergence_score,
         datetime.now().isoformat(), domain)
    )
    
    # Update knowledge atoms
    for p in patterns:
        _update_atom(conn, p, domain, rid)
    
    conn.commit()
    conn.close()
    
    return {
        "residual_id": rid,
        "patterns_found": len(patterns),
        "pattern_types": list(set(p["type"] for p in patterns)),
        "convergence_score": round(convergence_score, 3),
        "domain": domain,
        "patterns": patterns[:10]
    }

def _update_atom(conn, pattern, domain, source_id):
    """Update or create a knowledge atom from a pattern"""
    concept = f"{pattern['type']}:{pattern['value']}"
    aid = hashlib.md5(concept.encode()).hexdigest()[:12]
    
    existing = conn.execute("SELECT * FROM knowledge_atoms WHERE id=?", (aid,)).fetchone()
    
    if existing:
        evidence_count = existing[4] + 1
        confidence = min(0.95, existing[3] + 0.05)  # caps at 0.95
        sources = json.loads(existing[7]) if existing[7] else []
        sources.append(source_id)
        conn.execute(
            "UPDATE knowledge_atoms SET confidence=?, evidence_count=?, last_updated=?, sources=? WHERE id=?",
            (confidence, evidence_count, datetime.now().isoformat(), json.dumps(sources[-20:]), aid)
        )
    else:
        conn.execute(
            "INSERT INTO knowledge_atoms VALUES (?,?,?,?,?,?,?,?)",
            (aid, concept, domain, 0.35, 1, datetime.now().isoformat(),
             datetime.now().isoformat(), json.dumps([source_id]))
        )

def get_convergence_report(domain=None):
    """Get convergence analysis for a domain or all domains"""
    conn = _init_db()
    
    if domain:
        atoms = conn.execute("SELECT * FROM knowledge_atoms WHERE domain=? ORDER BY confidence DESC", (domain,)).fetchall()
        residuals = conn.execute("SELECT * FROM residuals WHERE domain=? ORDER BY created_at DESC", (domain,)).fetchall()
    else:
        atoms = conn.execute("SELECT * FROM knowledge_atoms ORDER BY confidence DESC").fetchall()
        residuals = conn.execute("SELECT * FROM residuals ORDER BY created_at DESC").fetchall()
    
    # Convergence metrics
    if not atoms:
        conn.close()
        return {"convergence_score": 0, "atoms": 0, "residuals": 0, "status": "empty"}
    
    avg_confidence = sum(a[3] for a in atoms) / len(atoms)
    high_confidence = sum(1 for a in atoms if a[3] >= 0.7)
    
    # Pattern type distribution
    type_counts = Counter()
    for a in atoms:
        ptype = a[1].split(":")[0] if ":" in a[1] else "unknown"
        type_counts[ptype] += 1
    
    # Domain convergence score
    diversity = len(type_counts)
    depth = min(len(atoms) / 50, 1.0)
    maturity = high_confidence / max(len(atoms), 1)
    
    convergence = 0.4 * avg_confidence + 0.3 * depth + 0.3 * maturity
    
    # Log convergence
    cid = f"C-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    conn.execute(
        "INSERT INTO convergence_log VALUES (?,?,?,?,?,?)",
        (cid, domain or "all", convergence, len(atoms), sum(type_counts.values()),
         datetime.now().isoformat())
    )
    conn.commit()
    
    report = {
        "convergence_score": round(convergence, 3),
        "total_atoms": len(atoms),
        "high_confidence_atoms": high_confidence,
        "avg_confidence": round(avg_confidence, 3),
        "total_residuals": len(residuals),
        "pattern_distribution": dict(type_counts),
        "top_atoms": [{"concept": a[1], "confidence": a[3], "evidence": a[4]} for a in atoms[:10]],
        "status": "converging" if convergence > 0.6 else "accumulating" if convergence > 0.3 else "nascent"
    }
    
    conn.close()
    return report

def generate_seeds_from_residuals(domain=None, max_seeds=5):
    """Water->Wood: generate new seeds from accumulated knowledge (xiangsheng)"""
    conn = _init_db()
    
    # Get high-confidence atoms
    if domain:
        atoms = conn.execute(
            "SELECT * FROM knowledge_atoms WHERE domain=? AND confidence>=0.3 ORDER BY confidence DESC LIMIT 20",
            (domain,)
        ).fetchall()
    else:
        atoms = conn.execute(
            "SELECT * FROM knowledge_atoms WHERE confidence>=0.3 ORDER BY confidence DESC LIMIT 20"
        ).fetchall()
    
    if not atoms:
        conn.close()
        return {"seeds": [], "message": "Insufficient knowledge for seed generation"}
    
    seeds = []
    seen = set()
    
    for atom in atoms:
        concept = atom[1]
        domain = atom[2]
        confidence = atom[3]
        evidence = atom[4]
        
        # Generate seed directions
        ptype, pvalue = concept.split(":", 1) if ":" in concept else ("unknown", concept)
        
        seed_templates = {
            "technology": f"Deep-dive analysis: {pvalue} technology trajectory, competitive landscape, and SkyCetus integration opportunities",
            "numeric": f"Validate and cross-reference: {pvalue} - verify data source, compare with industry benchmarks",
            "causal": f"Causal chain investigation: {pvalue} - trace upstream causes and downstream implications",
            "comparative": f"Comparative framework: {pvalue} - systematic multi-dimensional comparison"
        }
        
        seed_text = seed_templates.get(ptype, f"Knowledge deepening: {concept}")
        
        if seed_text not in seen:
            seen.add(seed_text)
            sid = f"S-W-{datetime.now().strftime('%Y%m%d%H%M%S')}-{hashlib.md5(seed_text.encode()).hexdigest()[:4]}"
            priority = confidence * 0.7 + min(evidence / 10, 1.0) * 0.3
            
            conn.execute(
                "INSERT OR REPLACE INTO generated_seeds VALUES (?,?,?,?,?,?)",
                (sid, atom[0], seed_text, domain, priority, datetime.now().isoformat())
            )
            seeds.append({
                "seed_id": sid,
                "text": seed_text,
                "domain": domain,
                "priority": round(priority, 3),
                "source_confidence": confidence,
                "source_evidence": evidence
            })
            
            if len(seeds) >= max_seeds:
                break
    
    conn.commit()
    conn.close()
    
    return {
        "seeds_generated": len(seeds),
        "seeds": seeds,
        "source_domain": domain or "all"
    }

def xiangke_constrain_fire(fire_plan, domain=None):
    """Water constrains Fire (xiangke): check execution plan against accumulated knowledge"""
    conn = _init_db()
    
    content = fire_plan if isinstance(fire_plan, str) else json.dumps(fire_plan, ensure_ascii=False)
    
    warnings = []
    
    # Check against known patterns
    atoms = conn.execute(
        "SELECT concept, confidence, evidence_count FROM knowledge_atoms WHERE confidence >= 0.6 ORDER BY confidence DESC LIMIT 50"
    ).fetchall()
    
    for atom in atoms:
        concept = atom[0]
        confidence = atom[1]
        
        if ":" in concept:
            ptype, pvalue = concept.split(":", 1)
            
            # Check if fire plan contradicts known facts
            if ptype == "numeric" and pvalue in content:
                warnings.append({
                    "type": "known_data_point",
                    "message": f"Plan references known value: {pvalue} (confidence {confidence:.0%}). Verify consistency.",
                    "severity": "info"
                })
            
            if ptype == "comparative" and any(word in content.lower() for word in pvalue.lower().split()[:3]):
                warnings.append({
                    "type": "comparative_reference",
                    "message": f"Plan touches known comparison: {pvalue}. Cross-check conclusions.",
                    "severity": "warning"
                })
    
    # Check for blind spots
    residuals = conn.execute("SELECT domain, COUNT(*) FROM residuals GROUP BY domain").fetchall()
    domain_coverage = {r[0]: r[1] for r in residuals}
    
    if domain and domain not in domain_coverage:
        warnings.append({
            "type": "blind_spot",
            "message": f"No prior residuals in domain '{domain}'. Execution lacks knowledge foundation.",
            "severity": "critical"
        })
    
    conn.close()
    
    constraint_score = max(0, 1.0 - len([w for w in warnings if w["severity"] == "critical"]) * 0.3
                          - len([w for w in warnings if w["severity"] == "warning"]) * 0.1)
    
    return {
        "constraint_score": round(constraint_score, 3),
        "warnings": warnings,
        "verdict": "PROCEED" if constraint_score >= 0.7 else "CAUTION" if constraint_score >= 0.4 else "BLOCK",
        "knowledge_domains": domain_coverage
    }

def get_stats(db_path=None):
    """Get water engine statistics"""
    conn = _init_db(db_path)
    
    residual_count = conn.execute("SELECT COUNT(*) FROM residuals").fetchone()[0]
    atom_count = conn.execute("SELECT COUNT(*) FROM knowledge_atoms").fetchone()[0]
    seed_count = conn.execute("SELECT COUNT(*) FROM generated_seeds").fetchone()[0]
    high_conf = conn.execute("SELECT COUNT(*) FROM knowledge_atoms WHERE confidence >= 0.7").fetchone()[0]
    
    domains = conn.execute("SELECT DISTINCT domain FROM residuals").fetchall()
    domain_list = [d[0] for d in domains]
    
    convergence_history = conn.execute(
        "SELECT score, timestamp FROM convergence_log ORDER BY timestamp DESC LIMIT 10"
    ).fetchall()
    
    conn.close()
    
    return {
        "total_residuals": residual_count,
        "total_atoms": atom_count,
        "high_confidence_atoms": high_conf,
        "generated_seeds": seed_count,
        "domains": domain_list,
        "convergence_trend": [{"score": c[0], "time": c[1]} for c in convergence_history]
    }


# Self-tests
def _run_tests():
    import tempfile
    global DB_PATH
    old_path = DB_PATH
    DB_PATH = os.path.join(tempfile.mkdtemp(), "test_water.db")
    
    tests_passed = 0
    tests_total = 6
    
    # Test 1: Extract residual
    r = extract_residual("SiC market grows 28.5% CAGR, better than GaN in power applications. Tesla uses SiC MOSFET.", 
                        task_id="T-001", domain="semiconductor")
    assert r["patterns_found"] > 0, f"No patterns: {r}"
    assert r["convergence_score"] > 0, f"Zero convergence: {r}"
    tests_passed += 1
    print(f"  Test 1 PASS: residual extracted, {r['patterns_found']} patterns, convergence={r['convergence_score']}")
    
    # Test 2: Multiple residuals build knowledge
    extract_residual("SiC substrate cost decreased 15% in 2025 due to 8-inch wafer transition", 
                    task_id="T-002", domain="semiconductor")
    extract_residual("GaN faster switching than SiC but lower voltage rating. SiC dominates EV market.",
                    task_id="T-003", domain="semiconductor")
    s = get_stats()
    assert s["total_residuals"] >= 3, f"Missing residuals: {s}"
    assert s["total_atoms"] > 0, f"No atoms: {s}"
    tests_passed += 1
    print(f"  Test 2 PASS: {s['total_residuals']} residuals, {s['total_atoms']} atoms")
    
    # Test 3: Convergence report
    report = get_convergence_report("semiconductor")
    assert report["convergence_score"] > 0, f"Zero convergence: {report}"
    assert report["total_atoms"] > 0, f"No atoms in report: {report}"
    tests_passed += 1
    print(f"  Test 3 PASS: convergence={report['convergence_score']}, status={report['status']}")
    
    # Test 4: Generate seeds (water->wood xiangsheng)
    seeds = generate_seeds_from_residuals("semiconductor", max_seeds=3)
    assert seeds["seeds_generated"] > 0, f"No seeds: {seeds}"
    tests_passed += 1
    print(f"  Test 4 PASS: {seeds['seeds_generated']} seeds generated")
    
    # Test 5: Xiangke constrain fire
    constraint = xiangke_constrain_fire("Plan to use GaN for 1200V EV inverter", domain="semiconductor")
    assert "verdict" in constraint, f"No verdict: {constraint}"
    tests_passed += 1
    print(f"  Test 5 PASS: verdict={constraint['verdict']}, score={constraint['constraint_score']}")
    
    # Test 6: Unknown domain triggers blind spot
    constraint2 = xiangke_constrain_fire("Plan for quantum computing deployment", domain="quantum")
    blind_spots = [w for w in constraint2["warnings"] if w["type"] == "blind_spot"]
    assert len(blind_spots) > 0, f"No blind spot warning: {constraint2}"
    tests_passed += 1
    print(f"  Test 6 PASS: blind spot detected for unknown domain")
    
    DB_PATH = old_path
    return tests_passed, tests_total

if __name__ == "__main__":
    print("Water Engine (Xuanwu/North) - Self Tests")
    passed, total = _run_tests()
    print(f"\nResults: {passed}/{total} passed")
