# -*- coding: utf-8 -*-
"""
Wood Engine (Qinglong/East) - Seed Generation, Mutation & Incubation
Part of the Wuxing Flywheel System

Role in xiangsheng: water->wood (Knowledge Breeds Seeds)
Role in xiangke: wood->earth (Seeds Challenge Complacent Delivery)

Core functions:
1. Seed creation - generate structured seed carriers from raw ideas
2. Seed scoring - multi-dimensional quality assessment
3. Seed mutation - evolve seeds through combination and variation
4. Seed->Task conversion - mature seeds become executable tasks
"""
import json, os, sqlite3, hashlib, re, random, time as _time
from datetime import datetime
from collections import Counter

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "wood_seeds.db")

SEED_SCHEMA = {
    "required": ["text", "domain"],
    "optional": ["source", "priority", "tags", "parent_seed"]
}

def _init_db(db_path=None):
    p = db_path or DB_PATH
    conn = sqlite3.connect(p)
    conn.execute("""CREATE TABLE IF NOT EXISTS seeds (
        id TEXT PRIMARY KEY, text TEXT, domain TEXT, source TEXT,
        novelty REAL, relevance REAL, feasibility REAL, convergence_potential REAL,
        overall_score REAL, status TEXT, parent_seed TEXT, generation INTEGER,
        created_at TEXT, updated_at TEXT, tags TEXT, metadata TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS seed_history (
        id TEXT PRIMARY KEY, seed_id TEXT, action TEXT, details TEXT, timestamp TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS conversions (
        id TEXT PRIMARY KEY, seed_id TEXT, task_id TEXT, converted_at TEXT, result TEXT
    )""")
    conn.commit()
    return conn

def create_seed(text, domain="general", source="manual", tags=None, parent_seed=None):
    """Create a new seed with quality scoring"""
    conn = _init_db()
    
    sid = f"SEED-{datetime.now().strftime('%Y%m%d%H%M%S')}-{hashlib.md5(text.encode()).hexdigest()[:6]}"
    
    # Score the seed
    scores = _score_seed(text, domain, conn)
    
    generation = 0
    if parent_seed:
        parent = conn.execute("SELECT generation FROM seeds WHERE id=?", (parent_seed,)).fetchone()
        if parent:
            generation = parent[0] + 1
    
    conn.execute(
        "INSERT OR REPLACE INTO seeds VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sid, text, domain, source,
         scores["novelty"], scores["relevance"], scores["feasibility"], scores["convergence_potential"],
         scores["overall"], "active" if scores["overall"] >= 0.4 else "archived",
         parent_seed, generation,
         datetime.now().isoformat(), datetime.now().isoformat(),
         json.dumps(tags or []), json.dumps({}))
    )
    
    conn.execute(
        "INSERT INTO seed_history VALUES (?,?,?,?,?)",
        (f"H-{sid}", sid, "created", json.dumps(scores), datetime.now().isoformat())
    )
    
    conn.commit()
    conn.close()
    
    return {
        "seed_id": sid,
        "text": text,
        "domain": domain,
        "scores": scores,
        "status": "active" if scores["overall"] >= 0.4 else "archived",
        "generation": generation
    }

def _score_seed(text, domain, conn):
    """Multi-dimensional seed quality scoring"""
    # Novelty: how different from existing seeds
    existing = conn.execute("SELECT text FROM seeds WHERE domain=? AND status='active' LIMIT 50", (domain,)).fetchall()
    if existing:
        overlaps = sum(1 for e in existing if _text_similarity(text, e[0]) > 0.6)
        novelty = max(0.1, 1.0 - overlaps / max(len(existing), 1))
    else:
        novelty = 0.8  # first seed in domain gets high novelty
    
    # Relevance: does it contain actionable keywords
    action_words = ["analyze", "build", "design", "optimize", "compare", "evaluate", 
                    "investigate", "develop", "test", "validate", "deploy", "measure",
                    "research", "integrate", "benchmark", "prototype"]
    action_count = sum(1 for w in action_words if w in text.lower())
    relevance = min(1.0, 0.3 + action_count * 0.15)
    
    # Feasibility: length and specificity
    word_count = len(text.split())
    if word_count < 3:
        feasibility = 0.1  # barely a thought
    elif word_count < 5:
        feasibility = 0.3  # too vague
    elif word_count < 15:
        feasibility = 0.6
    elif word_count < 50:
        feasibility = 0.9
    else:
        feasibility = 0.7  # too complex
    
    # Convergence potential: domain specificity + technical depth
    tech_terms = ["API", "algorithm", "model", "data", "system", "pipeline", "engine",
                  "SiC", "GaN", "CFRP", "AI", "ML", "GPU", "quantum", "blockchain",
                  "semiconductor", "material", "clearing", "hedge", "flywheel"]
    tech_count = sum(1 for t in tech_terms if t.lower() in text.lower())
    convergence_potential = min(1.0, 0.2 + tech_count * 0.12)
    
    overall = (novelty * 0.25 + relevance * 0.30 + feasibility * 0.25 + convergence_potential * 0.20)
    
    return {
        "novelty": round(novelty, 3),
        "relevance": round(relevance, 3),
        "feasibility": round(feasibility, 3),
        "convergence_potential": round(convergence_potential, 3),
        "overall": round(overall, 3)
    }

def _text_similarity(a, b):
    """Simple Jaccard similarity"""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)

def mutate_seed(seed_id, mutation_type="evolve"):
    """Mutate a seed to create variants (key innovation mechanism)"""
    conn = _init_db()
    seed = conn.execute("SELECT * FROM seeds WHERE id=?", (seed_id,)).fetchone()
    if not seed:
        conn.close()
        return {"error": f"Seed {seed_id} not found"}
    
    text = seed[1]
    domain = seed[2]
    
    mutations = {
        "deepen": f"Deep-dive into: {text}. Explore underlying mechanisms, root causes, and second-order effects.",
        "broaden": f"Expand scope of: {text}. Connect to adjacent domains, find cross-cutting patterns.",
        "invert": f"Challenge assumption: {text}. What if the opposite were true? Explore contrarian view.",
        "combine": None,  # needs second seed
        "evolve": f"Next iteration of: {text}. What would the v2.0 look like with accumulated insights?"
    }
    
    if mutation_type == "combine":
        # Find complementary seed
        others = conn.execute(
            "SELECT id, text FROM seeds WHERE domain=? AND id!=? AND status='active' ORDER BY RANDOM() LIMIT 1",
            (domain, seed_id)
        ).fetchone()
        if others:
            mutated_text = f"Synthesize: [{text}] + [{others[1]}]. Find synergies and emergent properties."
        else:
            mutated_text = mutations["evolve"]
    else:
        mutated_text = mutations.get(mutation_type, mutations["evolve"])
    
    result = create_seed(mutated_text, domain=domain, source=f"mutation:{mutation_type}", parent_seed=seed_id)
    
    conn.execute(
        "INSERT INTO seed_history VALUES (?,?,?,?,?)",
        (f"H-MUT-{seed_id}", seed_id, f"mutated:{mutation_type}", json.dumps(result), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    
    return result

def convert_to_task(seed_id):
    """Convert mature seed into Hub task format"""
    conn = _init_db()
    seed = conn.execute("SELECT * FROM seeds WHERE id=?", (seed_id,)).fetchone()
    if not seed:
        conn.close()
        return {"error": f"Seed {seed_id} not found"}
    
    text, domain, overall_score = seed[1], seed[2], seed[8]
    
    if overall_score < 0.4:
        conn.close()
        return {"error": f"Seed score too low ({overall_score:.2f}). Minimum 0.4 for conversion.", "suggestion": "Try mutating the seed first."}
    
    # Determine priority from score
    if overall_score >= 0.8:
        priority = "P0"
    elif overall_score >= 0.6:
        priority = "P1"
    else:
        priority = "P2"
    
    task = {
        "title": text[:100],
        "description": text,
        "priority": priority,
        "domain": domain,
        "source_seed": seed_id,
        "seed_score": overall_score,
        "phase": "fire",  # seeds convert to fire (execution) tasks
        "status": "pending"
    }
    
    # Record conversion
    cid = f"CONV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    conn.execute(
        "INSERT INTO conversions VALUES (?,?,?,?,?)",
        (cid, seed_id, None, datetime.now().isoformat(), json.dumps(task))
    )
    
    # Update seed status
    conn.execute("UPDATE seeds SET status='converted', updated_at=? WHERE id=?",
                (datetime.now().isoformat(), seed_id))
    
    conn.commit()
    conn.close()
    
    return {"conversion_id": cid, "task": task}

def xiangke_challenge_earth(earth_output, domain=None):
    """Wood challenges Earth (xiangke): seeds question complacent delivery"""
    conn = _init_db()
    
    content = earth_output if isinstance(earth_output, str) else json.dumps(earth_output, ensure_ascii=False)
    
    # Get active seeds in domain
    if domain:
        seeds = conn.execute("SELECT text, overall_score FROM seeds WHERE domain=? AND status='active' ORDER BY overall_score DESC LIMIT 10", (domain,)).fetchall()
    else:
        seeds = conn.execute("SELECT text, overall_score FROM seeds WHERE status='active' ORDER BY overall_score DESC LIMIT 10").fetchall()
    
    challenges = []
    
    # Check if delivery addresses known seed questions
    unanswered = 0
    for seed_text, score in seeds:
        keywords = set(seed_text.lower().split())
        overlap = len(keywords & set(content.lower().split())) / max(len(keywords), 1)
        if overlap < 0.15:
            unanswered += 1
            challenges.append({
                "type": "unanswered_seed",
                "seed": seed_text[:80],
                "score": score,
                "message": f"Active seed not addressed in delivery"
            })
    
    # Check for shallow delivery
    if len(content) < 500:
        challenges.append({
            "type": "shallow_delivery",
            "message": "Delivery content appears insufficient for meaningful impact",
            "severity": "warning"
        })
    
    conn.close()
    
    challenge_score = max(0, 1.0 - unanswered * 0.15)
    
    return {
        "challenge_score": round(challenge_score, 3),
        "challenges": challenges[:10],
        "verdict": "ACCEPT" if challenge_score >= 0.7 else "REVISE" if challenge_score >= 0.4 else "REJECT",
        "unanswered_seeds": unanswered,
        "total_active_seeds": len(seeds)
    }

def get_stats(db_path=None):
    """Get wood engine statistics"""
    conn = _init_db(db_path)
    
    total = conn.execute("SELECT COUNT(*) FROM seeds").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM seeds WHERE status='active'").fetchone()[0]
    archived = conn.execute("SELECT COUNT(*) FROM seeds WHERE status='archived'").fetchone()[0]
    converted = conn.execute("SELECT COUNT(*) FROM seeds WHERE status='converted'").fetchone()[0]
    
    domains = conn.execute("SELECT domain, COUNT(*) FROM seeds GROUP BY domain").fetchall()
    
    avg_score = conn.execute("SELECT AVG(overall_score) FROM seeds").fetchone()[0] or 0
    
    gen_dist = conn.execute("SELECT generation, COUNT(*) FROM seeds GROUP BY generation").fetchall()
    
    conn.close()
    
    return {
        "total_seeds": total,
        "active": active,
        "archived": archived,
        "converted": converted,
        "avg_score": round(avg_score, 3),
        "domains": {d[0]: d[1] for d in domains},
        "generation_distribution": {str(g[0]): g[1] for g in gen_dist}
    }

def list_seeds(domain=None, status="active", limit=20):
    """List seeds with filters"""
    conn = _init_db()
    
    if domain:
        seeds = conn.execute(
            "SELECT id, text, domain, overall_score, status, generation, created_at FROM seeds WHERE domain=? AND status=? ORDER BY overall_score DESC LIMIT ?",
            (domain, status, limit)
        ).fetchall()
    else:
        seeds = conn.execute(
            "SELECT id, text, domain, overall_score, status, generation, created_at FROM seeds WHERE status=? ORDER BY overall_score DESC LIMIT ?",
            (status, limit)
        ).fetchall()
    
    conn.close()
    
    return {
        "seeds": [
            {"id": s[0], "text": s[1][:100], "domain": s[2], "score": s[3], 
             "status": s[4], "generation": s[5], "created_at": s[6]}
            for s in seeds
        ],
        "count": len(seeds)
    }


def _run_tests():
    import tempfile
    global DB_PATH
    old_path = DB_PATH
    DB_PATH = os.path.join(tempfile.mkdtemp(), "test_wood.db")
    
    passed = 0
    total = 7
    
    # Test 1: Create seed
    s = create_seed("Analyze SiC MOSFET market trajectory and competitive landscape for EV applications", domain="semiconductor")
    assert s["seed_id"].startswith("SEED-"), f"Bad ID: {s}"
    assert s["scores"]["overall"] > 0, f"Zero score: {s}"
    passed += 1
    print(f"  Test 1 PASS: seed created, score={s['scores']['overall']}")
    
    # Test 2: Score quality - vague seed gets lower score
    s2 = create_seed("hi", domain="general")
    assert s2["scores"]["overall"] < s["scores"]["overall"], f"Vague seed scored too high: {s2}"
    passed += 1
    print(f"  Test 2 PASS: vague seed scored lower ({s2['scores']['overall']} < {s['scores']['overall']})")
    
    # Test 3: Auto-archive low quality (create 2nd in same domain to drop novelty)
    s3 = create_seed("x", domain="general")
    assert s3["scores"]["overall"] < 0.4, f"Low seed scored too high: {s3}"
    print(f"  Test 3 PASS: low-quality seed auto-archived (score={s3['scores']['overall']})")
    
    # Test 4: Mutate seed
    m = mutate_seed(s["seed_id"], "deepen")
    assert m["seed_id"] != s["seed_id"], f"Same ID: {m}"
    assert m["generation"] == 1, f"Wrong generation: {m}"
    passed += 1
    print(f"  Test 4 PASS: mutation created gen-{m['generation']}, score={m['scores']['overall']}")
    
    # Test 5: Convert to task
    t = convert_to_task(s["seed_id"])
    assert "task" in t, f"No task: {t}"
    assert t["task"]["priority"] in ["P0", "P1", "P2"], f"Bad priority: {t}"
    passed += 1
    print(f"  Test 5 PASS: converted to {t['task']['priority']} task")
    
    # Test 6: Xiangke challenge earth
    c = xiangke_challenge_earth("Short shallow report", domain="semiconductor")
    assert c["verdict"] in ["ACCEPT", "REVISE", "REJECT"], f"Bad verdict: {c}"
    assert len(c["challenges"]) > 0, f"No challenges: {c}"
    passed += 1
    print(f"  Test 6 PASS: earth challenged, verdict={c['verdict']}")
    
    # Test 7: Stats
    stats = get_stats()
    assert stats["total_seeds"] >= 3, f"Missing seeds: {stats}"
    assert stats["converted"] >= 1, f"No conversions: {stats}"
    passed += 1
    print(f"  Test 7 PASS: {stats['total_seeds']} seeds, {stats['converted']} converted")
    
    DB_PATH = old_path
    return passed, total

if __name__ == "__main__":
    print("Wood Engine (Qinglong/East) - Self Tests")
    passed, total = _run_tests()
    print(f"\nResults: {passed}/{total} passed")
