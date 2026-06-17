# -*- coding: utf-8 -*-
"""
Wuxing Balance Monitor - Five Elements Imbalance Detection
Detects when any single element dominates and triggers auto-rebalancing.

Wuxing Basis:
- Each element should occupy ~20% of system activity
- imbalance_ratio > 2.0 triggers rebalancing
- Rebalancing uses xiangke (mutual restraint) to suppress dominant element
"""
import json, os, time, urllib.request
from datetime import datetime

HUB_URL = "http://localhost:19104"

# Five elements and their task phase mappings
ELEMENT_PHASES = {
    "wood":  {"keywords": ["seed", "idea", "diverge", "create", "brainstorm", "explore", "wood", "mu", "qinglong"],
              "label": "Wood/Mu", "emoji": "wood", "role": "Seed/Divergence"},
    "fire":  {"keywords": ["execute", "analyze", "build", "deploy", "run", "fire", "huo", "zhuque", "implement"],
              "label": "Fire/Huo", "emoji": "fire", "role": "Execution/Output"},
    "earth": {"keywords": ["deliver", "feedback", "review", "report", "earth", "tu", "hub", "integrate", "merge"],
              "label": "Earth/Tu", "emoji": "earth", "role": "Delivery/Feedback"},
    "metal": {"keywords": ["validate", "adversarial", "audit", "check", "metal", "jin", "baihu", "quality", "test"],
              "label": "Metal/Jin", "emoji": "metal", "role": "Validation/Adversarial"},
    "water": {"keywords": ["learn", "converge", "knowledge", "research", "water", "shui", "xuanwu", "study", "cognition"],
              "label": "Water/Shui", "emoji": "water", "role": "Learning/Convergence"},
}

# Xiangke pairs: dominant -> suppressed_by
XIANGKE_SUPPRESS = {
    "wood":  "metal",   # jin ke mu
    "fire":  "water",   # shui ke huo
    "earth": "wood",    # mu ke tu
    "metal": "fire",    # huo ke jin
    "water": "earth",   # tu ke shui
}

# Rebalancing actions
REBALANCE_ACTIONS = {
    "wood":  {"action": "throttle_seeds", "boost": "fire", "desc": "Too many seeds - throttle creation, boost execution"},
    "fire":  {"action": "slow_claiming", "boost": "earth", "desc": "Execution overload - slow claiming, force delivery"},
    "earth": {"action": "trigger_review", "boost": "metal", "desc": "Delivery backlog - auto-trigger adversarial review"},
    "metal": {"action": "ease_standards", "boost": "wood", "desc": "Over-validation - ease standards, boost diversity"},
    "water": {"action": "force_seeding", "boost": "wood", "desc": "Cognition idle - force seed generation from knowledge"},
}

IMBALANCE_THRESHOLD = 2.0
CRITICAL_THRESHOLD = 3.0

def classify_task(task):
    """Classify a task into a Wuxing element based on keywords"""
    title = (task.get("title", "") + " " + task.get("description", "")).lower()
    task_id = task.get("task_id", "").lower()
    combined = title + " " + task_id
    
    scores = {}
    for element, config in ELEMENT_PHASES.items():
        score = sum(1 for kw in config["keywords"] if kw in combined)
        scores[element] = score
    
    if max(scores.values()) == 0:
        return "earth"  # default to earth (delivery/general)
    
    return max(scores, key=scores.get)

def fetch_tasks():
    """Fetch all tasks from Hub"""
    try:
        req = urllib.request.Request(f"{HUB_URL}/api/v1/tasks?limit=500")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                return data
            return data.get("tasks", data.get("data", []))
    except Exception as e:
        print(f"Hub fetch error: {e}")
        return []

def analyze_balance(tasks=None):
    """Analyze current Wuxing balance across all tasks"""
    if tasks is None:
        tasks = fetch_tasks()
    
    # Count by element
    counts = {e: 0 for e in ELEMENT_PHASES}
    pending_counts = {e: 0 for e in ELEMENT_PHASES}
    completed_counts = {e: 0 for e in ELEMENT_PHASES}
    
    for task in tasks:
        element = classify_task(task)
        counts[element] += 1
        status = task.get("status", "pending")
        if status in ("pending", "claimed", "in_progress"):
            pending_counts[element] += 1
        elif status in ("completed", "done"):
            completed_counts[element] += 1
    
    total = sum(counts.values())
    if total == 0:
        return {"balanced": True, "counts": counts, "total": 0, "alerts": []}
    
    avg = total / 5.0
    
    # Calculate ratios
    ratios = {}
    for e in ELEMENT_PHASES:
        ratios[e] = counts[e] / avg if avg > 0 else 0
    
    # Detect imbalances
    alerts = []
    dominant = max(ratios, key=ratios.get)
    weakest = min(ratios, key=ratios.get)
    
    if ratios[dominant] > CRITICAL_THRESHOLD:
        suppressor = XIANGKE_SUPPRESS[dominant]
        action = REBALANCE_ACTIONS[dominant]
        alerts.append({
            "level": "CRITICAL",
            "dominant": dominant,
            "ratio": round(ratios[dominant], 2),
            "suppressor": suppressor,
            "action": action["action"],
            "boost": action["boost"],
            "description": action["desc"],
        })
    elif ratios[dominant] > IMBALANCE_THRESHOLD:
        suppressor = XIANGKE_SUPPRESS[dominant]
        action = REBALANCE_ACTIONS[dominant]
        alerts.append({
            "level": "WARNING",
            "dominant": dominant,
            "ratio": round(ratios[dominant], 2),
            "suppressor": suppressor,
            "action": action["action"],
            "boost": action["boost"],
            "description": action["desc"],
        })
    
    if ratios[weakest] < 0.3 and total > 20:
        alerts.append({
            "level": "DEFICIT",
            "element": weakest,
            "ratio": round(ratios[weakest], 2),
            "description": f"{ELEMENT_PHASES[weakest]['label']} severely underrepresented",
        })
    
    return {
        "balanced": len(alerts) == 0,
        "timestamp": datetime.now().isoformat(),
        "total_tasks": total,
        "counts": counts,
        "pending": pending_counts,
        "completed": completed_counts,
        "ratios": {e: round(r, 2) for e, r in ratios.items()},
        "dominant": dominant,
        "weakest": weakest,
        "imbalance_ratio": round(ratios[dominant], 2),
        "alerts": alerts,
        "xiangke_map": XIANGKE_SUPPRESS,
    }

def get_rebalance_recommendations(analysis):
    """Generate actionable recommendations from balance analysis"""
    if analysis["balanced"]:
        return ["System is balanced. No action needed."]
    
    recs = []
    for alert in analysis["alerts"]:
        if alert["level"] in ("CRITICAL", "WARNING"):
            dom = alert["dominant"]
            sup = alert["suppressor"]
            recs.append(f"[{alert['level']}] {ELEMENT_PHASES[dom]['label']} dominates (ratio {alert['ratio']}x)")
            recs.append(f"  -> Apply {ELEMENT_PHASES[sup]['label']} constraint ({XIANGKE_SUPPRESS[dom]})")
            recs.append(f"  -> Action: {alert['description']}")
            recs.append(f"  -> Boost: {ELEMENT_PHASES[alert['boost']]['label']}")
        elif alert["level"] == "DEFICIT":
            elem = alert["element"]
            recs.append(f"[DEFICIT] {ELEMENT_PHASES[elem]['label']} underrepresented (ratio {alert['ratio']}x)")
            recs.append(f"  -> Generate more {elem} tasks")
    
    return recs

def format_balance_report(analysis):
    """Format a human-readable balance report"""
    lines = []
    lines.append("=== Wuxing Balance Report ===")
    lines.append(f"Time: {analysis.get('timestamp', 'N/A')}")
    lines.append(f"Total Tasks: {analysis['total_tasks']}")
    lines.append("")
    
    for e in ["wood", "fire", "earth", "metal", "water"]:
        cfg = ELEMENT_PHASES[e]
        count = analysis["counts"][e]
        ratio = analysis["ratios"].get(e, 0)
        bar = "#" * int(ratio * 10)
        status = "OK" if 0.5 <= ratio <= 2.0 else ("HIGH" if ratio > 2.0 else "LOW")
        lines.append(f"  {cfg['label']:12s} | {count:4d} | ratio {ratio:.2f} | {bar:20s} | {status}")
    
    lines.append("")
    lines.append(f"Dominant: {analysis['dominant']} ({analysis['imbalance_ratio']}x)")
    lines.append(f"Weakest:  {analysis['weakest']}")
    lines.append(f"Balanced: {analysis['balanced']}")
    
    if analysis["alerts"]:
        lines.append("")
        lines.append("ALERTS:")
        for rec in get_rebalance_recommendations(analysis):
            lines.append(f"  {rec}")
    
    return "\n".join(lines)


if __name__ == "__main__":
    print("=== Wuxing Balance Self-Test ===")
    
    # Test with mock tasks
    mock_tasks = []
    for i in range(30):
        mock_tasks.append({"title": f"seed idea {i}", "task_id": f"T-SEED-{i}", "status": "pending"})
    for i in range(10):
        mock_tasks.append({"title": f"execute analysis {i}", "task_id": f"T-EXEC-{i}", "status": "completed"})
    for i in range(5):
        mock_tasks.append({"title": f"validate audit {i}", "task_id": f"T-AUDIT-{i}", "status": "pending"})
    for i in range(3):
        mock_tasks.append({"title": f"research learn {i}", "task_id": f"T-LEARN-{i}", "status": "completed"})
    for i in range(2):
        mock_tasks.append({"title": f"deliver report {i}", "task_id": f"T-REPORT-{i}", "status": "completed"})
    
    analysis = analyze_balance(mock_tasks)
    print(format_balance_report(analysis))
    
    assert not analysis["balanced"], "Should detect imbalance"
    assert analysis["dominant"] == "wood", f"Wood should dominate, got {analysis['dominant']}"
    assert len(analysis["alerts"]) > 0, "Should have alerts"
    assert analysis["alerts"][0]["suppressor"] == "metal", "Metal should suppress wood"
    
    print("\nAll tests passed!")
    
    # Try real Hub data
    print("\n=== Live Hub Analysis ===")
    live = analyze_balance()
    if live["total_tasks"] > 0:
        print(format_balance_report(live))
    else:
        print("No Hub data available (Hub may be down)")
