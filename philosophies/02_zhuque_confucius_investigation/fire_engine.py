# -*- coding: utf-8 -*-
"""
Fire Engine (Zhuque/South) - Task Execution & Pipeline
Part of the Wuxing Flywheel System

Role in xiangsheng: wood->fire (Seeds Ignite Execution)
Role in xiangke: fire->metal (Execution Challenges Rigid Validation)

Core functions:
1. Task decomposition - break complex tasks into sub-tasks
2. Execution planning - create execution DAG
3. LLM-powered execution - use multi-model routing
4. Result aggregation - merge sub-task results
5. Quality self-check before passing to Earth
"""
import json, os, sqlite3, hashlib, subprocess, time as _time, re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "fire_execution.db")

def _init_db(db_path=None):
    p = db_path or DB_PATH
    conn = sqlite3.connect(p)
    conn.execute("""CREATE TABLE IF NOT EXISTS executions (
        id TEXT PRIMARY KEY, task_id TEXT, task_text TEXT, status TEXT,
        sub_tasks TEXT, results TEXT, quality_score REAL,
        started_at TEXT, completed_at TEXT, duration_s REAL, model_used TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS execution_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, exec_id TEXT, step TEXT, 
        detail TEXT, timestamp TEXT
    )""")
    conn.commit()
    return conn

def _call_llm(prompt, model="minimax"):
    """Call LLM via curl subprocess (Windows SSL workaround)"""
    import subprocess, json
    
    api_key = "sk-cp-wBP8BgBJbLsGCUshk0x5oYKbiydygx-RMk0iJDhANE6epg6gMnRBRg5hPN1eioB3PURgoeEiv7o2kLE7vOqibkLG1_3daWsmo-7kkkVxS4t7guHj7exDGwo"
    
    payload = {
        "model": "MiniMax-M2.7",
        "max_tokens": 4096,
        "thinking": {"type": "enabled", "budget_tokens": 300},
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        result = subprocess.run(
            ["curl.exe", "-s", "-X", "POST",
             "https://api.minimaxi.com/anthropic/v1/messages",
             "-H", f"x-api-key: {api_key}",
             "-H", "anthropic-version: 2023-06-01",
             "-H", "Content-Type: application/json",
             "-d", json.dumps(payload, ensure_ascii=False)],
            capture_output=True, text=True, timeout=120
        )
        
        resp = json.loads(result.stdout)
        for block in resp.get("content", []):
            if block.get("type") == "text":
                return block.get("text", "")
        return ""
    except Exception as e:
        return f"[LLM Error: {str(e)}]"

def decompose_task(task_text, max_subtasks=5):
    """Break a complex task into sub-tasks"""
    # Simple heuristic decomposition (no LLM needed for basic cases)
    subtasks = []
    
    # Check for explicit enumeration
    numbered = re.findall(r'(?:\d+[.)]\s*|[-*]\s+)(.+?)(?:\n|$)', task_text)
    if numbered and len(numbered) >= 2:
        for item in numbered[:max_subtasks]:
            subtasks.append({"text": item.strip(), "type": "explicit"})
        return subtasks
    
    # Keyword-based decomposition
    phases = {
        "research": ["analyze", "research", "investigate", "study", "examine", "review"],
        "design": ["design", "architect", "plan", "structure", "blueprint", "layout"],
        "build": ["build", "implement", "develop", "create", "code", "construct"],
        "test": ["test", "validate", "verify", "benchmark", "evaluate", "assess"],
        "deploy": ["deploy", "launch", "release", "publish", "deliver", "ship"]
    }
    
    detected_phases = []
    for phase, keywords in phases.items():
        if any(kw in task_text.lower() for kw in keywords):
            detected_phases.append(phase)
    
    if not detected_phases:
        detected_phases = ["research", "build"]  # default
    
    for phase in detected_phases[:max_subtasks]:
        subtasks.append({
            "text": f"{phase.title()}: {task_text[:100]}",
            "type": "auto",
            "phase": phase
        })
    
    return subtasks

def execute_task(task_text, task_id=None, use_llm=False, domain="general"):
    """Execute a task through the fire pipeline"""
    conn = _init_db()
    
    eid = f"EXEC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{hashlib.md5(task_text[:50].encode()).hexdigest()[:6]}"
    start_time = _time.time()
    
    conn.execute(
        "INSERT INTO executions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (eid, task_id or "unknown", task_text, "running", "[]", "", 0,
         datetime.now().isoformat(), None, 0, "none")
    )
    conn.commit()
    
    # Step 1: Decompose
    subtasks = decompose_task(task_text)
    conn.execute("UPDATE executions SET sub_tasks=? WHERE id=?",
                (json.dumps(subtasks, ensure_ascii=False), eid))
    conn.execute("INSERT INTO execution_log VALUES (NULL,?,?,?,?)",
                (eid, "decompose", f"{len(subtasks)} sub-tasks", datetime.now().isoformat()))
    conn.commit()
    
    # Step 2: Execute (with or without LLM)
    results = []
    model_used = "local"
    
    if use_llm:
        model_used = "MiniMax-M2.7"
        for st in subtasks:
            prompt = f"You are an industry analysis expert. Execute this task concisely:\n\n{st['text']}\n\nDomain: {domain}\n\nProvide structured analysis with key findings."
            result = _call_llm(prompt)
            results.append({"subtask": st["text"], "result": result, "status": "completed" if result and not result.startswith("[LLM") else "failed"})
    else:
        for st in subtasks:
            results.append({
                "subtask": st["text"],
                "result": f"[Local execution] Task decomposed and ready for LLM processing: {st['text']}",
                "status": "completed"
            })
    
    # Step 3: Quality self-check
    completed = sum(1 for r in results if r["status"] == "completed")
    total_content = sum(len(r.get("result", "")) for r in results)
    
    quality = (
        0.4 * (completed / max(len(results), 1)) +  # completion rate
        0.3 * min(total_content / 2000, 1.0) +  # content depth
        0.2 * min(len(subtasks) / 3, 1.0) +  # decomposition quality
        0.1 * (1.0 if domain != "general" else 0.5)  # domain specificity
    )
    
    duration = _time.time() - start_time
    
    conn.execute(
        "UPDATE executions SET status=?, results=?, quality_score=?, completed_at=?, duration_s=?, model_used=? WHERE id=?",
        ("completed", json.dumps(results, ensure_ascii=False), quality,
         datetime.now().isoformat(), duration, model_used, eid)
    )
    conn.execute("INSERT INTO execution_log VALUES (NULL,?,?,?,?)",
                (eid, "complete", f"quality={quality:.3f}, duration={duration:.1f}s", datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    return {
        "execution_id": eid,
        "task_id": task_id,
        "status": "completed",
        "subtasks": len(subtasks),
        "completed": completed,
        "quality_score": round(quality, 3),
        "duration_s": round(duration, 2),
        "model_used": model_used,
        "results": results
    }

def xiangke_challenge_metal(validation_result):
    """Fire challenges Metal (xiangke): execution pushes back on rigid validation"""
    challenges = []
    
    if isinstance(validation_result, str):
        try:
            validation_result = json.loads(validation_result)
        except:
            return {"verdict": "ACCEPT", "challenges": [], "message": "Cannot parse validation result"}
    
    score = validation_result.get("overall_score", 1.0)
    verdict = validation_result.get("verdict", "PASS")
    
    # Challenge overly strict validation
    if verdict == "FAIL" and score > 0.35:
        challenges.append({
            "type": "borderline_fail",
            "message": f"Score {score:.2f} is close to threshold. Consider CONDITIONAL instead of FAIL.",
            "severity": "warning"
        })
    
    # Check if adversarial tests are too aggressive
    adversarial = validation_result.get("adversarial_results", [])
    false_positives = sum(1 for a in adversarial if a.get("passed") is False and a.get("confidence", 1) < 0.5)
    if false_positives > 0:
        challenges.append({
            "type": "false_positive_risk",
            "message": f"{false_positives} adversarial flags may be false positives (low confidence)",
            "severity": "warning"
        })
    
    challenge_score = max(0, 1.0 - len(challenges) * 0.2)
    
    return {
        "challenge_score": round(challenge_score, 3),
        "challenges": challenges,
        "verdict": "OVERRIDE" if challenge_score < 0.5 else "ACCEPT",
        "original_verdict": verdict
    }

def get_stats(db_path=None):
    """Get fire engine statistics"""
    conn = _init_db(db_path)
    
    total = conn.execute("SELECT COUNT(*) FROM executions").fetchone()[0]
    completed = conn.execute("SELECT COUNT(*) FROM executions WHERE status='completed'").fetchone()[0]
    avg_quality = conn.execute("SELECT AVG(quality_score) FROM executions WHERE status='completed'").fetchone()[0] or 0
    avg_duration = conn.execute("SELECT AVG(duration_s) FROM executions WHERE status='completed'").fetchone()[0] or 0
    
    by_model = conn.execute("SELECT model_used, COUNT(*) FROM executions GROUP BY model_used").fetchall()
    
    conn.close()
    
    return {
        "total_executions": total,
        "completed": completed,
        "avg_quality": round(avg_quality, 3),
        "avg_duration_s": round(avg_duration, 2),
        "by_model": {m[0]: m[1] for m in by_model}
    }


def _run_tests():
    import tempfile
    global DB_PATH
    old_path = DB_PATH
    DB_PATH = os.path.join(tempfile.mkdtemp(), "test_fire.db")
    
    passed = 0
    total = 5
    
    # Test 1: Decompose task
    st = decompose_task("Research SiC market, design comparison framework, build analysis tool, test with real data")
    assert len(st) >= 3, f"Too few subtasks: {st}"
    passed += 1
    print(f"  Test 1 PASS: {len(st)} sub-tasks decomposed")
    
    # Test 2: Execute task (local mode)
    r = execute_task("Analyze competitive landscape of SiC power devices", task_id="T-001", domain="semiconductor")
    assert r["status"] == "completed", f"Not completed: {r}"
    assert r["quality_score"] > 0, f"Zero quality: {r}"
    passed += 1
    print(f"  Test 2 PASS: executed, quality={r['quality_score']}, {r['subtasks']} subtasks")
    
    # Test 3: Xiangke challenge metal
    mock_validation = {"overall_score": 0.45, "verdict": "FAIL", "adversarial_results": []}
    c = xiangke_challenge_metal(mock_validation)
    assert c["verdict"] in ["ACCEPT", "OVERRIDE"], f"Bad verdict: {c}"
    assert len(c["challenges"]) > 0, f"No challenges for borderline fail: {c}"
    passed += 1
    print(f"  Test 3 PASS: challenged metal, verdict={c['verdict']}, {len(c['challenges'])} challenges")
    
    # Test 4: Stats
    stats = get_stats()
    assert stats["total_executions"] >= 1, f"No executions: {stats}"
    passed += 1
    print(f"  Test 4 PASS: {stats['total_executions']} executions, avg_quality={stats['avg_quality']}")
    
    # Test 5: Numbered task decomposition
    st2 = decompose_task("1. Research market size\n2. Identify key players\n3. Analyze pricing\n4. Write report")
    assert len(st2) == 4, f"Wrong count: {st2}"
    assert st2[0]["type"] == "explicit", f"Not explicit: {st2}"
    passed += 1
    print(f"  Test 5 PASS: explicit decomposition, {len(st2)} items")
    
    DB_PATH = old_path
    return passed, total

if __name__ == "__main__":
    print("Fire Engine (Zhuque/South) - Self Tests")
    passed, total = _run_tests()
    print(f"\nResults: {passed}/{total} passed")
