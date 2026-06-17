#!/usr/bin/env python3
"""
Task 2: Add update_knowledge_tree function to knowledge_tree_api.py
and expose it as an API endpoint in flywheel_api_v4.py

This bridges the gap between:
- flywheel_api_v4.py: calls grand_cycle.on_run_complete() after each run
- knowledge_tree_api.py: exposes KT state (currently only reads page-registry.json)
- kt_conclusions table: has 27 entries from historical runs

The fix: add a write mechanism to KT that updates page-registry.json
"""
import json
import os
from datetime import datetime

REGISTRY_PATH = "C:/SkyCetus-2.0/content/flywheel/page-registry.json"
DOMAIN_MAPPING = {
    "新材料": "materials-starmap.html",
    "商业航天": "starsea.html",
    "AI芯片": "chip-design.html",
    "新能源汽车": "ev-chain.html",
    "金融衍生品": "derivatives-hub.html",
    "AGI理论": "kunpeng.html",
    "生物医药": "materials-starmap.html",
    "量子计算": "starsea.html",
}

def classify_domain(topic):
    """Classify a topic into one of the 8 expected domains"""
    topic_lower = topic.lower()
    if any(k in topic_lower for k in ["钙钛矿", "固态电池", "碳化硅", "新材料", "材料科学", "perovskite", "sic", "gan"]):
        return "新材料"
    if any(k in topic_lower for k in ["航天", "卫星", "火箭", "太空", "商业航天", "space", "rocket"]):
        return "商业航天"
    if any(k in topic_lower for k in ["芯片", "半导体", "gpu", "ai芯片", "ic", "集成电路", "chip", "semiconductor"]):
        return "AI芯片"
    if any(k in topic_lower for k in ["新能源", "电动汽车", "充电", "电池", "电动车", "锂电", "动力电池", "ev", "battery"]):
        return "新能源汽车"
    if any(k in topic_lower for k in ["金融", "期权", "期货", "衍生品", "量化", "对冲", "derivatives", "option", "futures"]):
        return "金融衍生品"
    if any(k in topic_lower for k in ["agi", "通用人工智能", "大模型", "llm", "认知", "智能压缩", "tep"]):
        return "AGI理论"
    if any(k in topic_lower for k in ["基因", "mrna", "细胞治疗", "脑机接口", "生物医药", "医药", "gene", "therapy"]):
        return "生物医药"
    if any(k in topic_lower for k in ["量子", "量子计算", "quantum"]):
        return "量子计算"
    return None


def load_registry():
    """Load page-registry.json"""
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"version": "1.0", "updated": "", "total": 0, "entries": {}}


def save_registry(data):
    """Save page-registry.json"""
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_kt_entry(run_id, topic, result, score):
    """Generate a KT entry from a flywheel run result"""
    if isinstance(result, str):
        return None
    
    kunpeng = result.get("kunpeng", {}) or {}
    verdict = result.get("verdict", "unknown")
    grade = result.get("grade", "N/A")
    
    # Extract conclusion
    conclusion = ""
    kd = kunpeng.get("kun_dive", {})
    if isinstance(kd, dict):
        conclusion = kd.get("conclusion", "")[:500]
        predictions = kd.get("predictions", [])[:3]
    elif isinstance(kd, str):
        conclusion = kd[:500]
        predictions = []
    else:
        predictions = []
    
    # Extract predictions as strings
    pred_strs = []
    for p in predictions:
        if isinstance(p, dict):
            when = p.get("when", "")
            what = p.get("what", "")
            pred_strs.append("[%s] %s" % (when, what[:100]))
        elif isinstance(p, str):
            pred_strs.append(p[:120])
    
    # Extract data gaps
    gaps = []
    for g in kunpeng.get("data_gaps", [])[:5]:
        if isinstance(g, dict):
            desc = g.get("gap") or g.get("description") or str(g)
            gaps.append(desc[:200])
        elif isinstance(g, str):
            gaps.append(g[:200])
    
    # Extract strategic recommendations
    recs = []
    for r in kunpeng.get("strategic_recommendations", [])[:4]:
        if isinstance(r, dict):
            recs.append(r.get("title", str(r))[:100])
        elif isinstance(r, str):
            recs.append(r[:100])
    
    return {
        "run_id": run_id,
        "topic": topic,
        "score": score,
        "grade": grade,
        "verdict": verdict,
        "conclusion": conclusion,
        "predictions": pred_strs,
        "data_gaps": gaps,
        "strategic_recs": recs,
        "domain": classify_domain(topic),
        "meta_checks": {
            "dao": bool(kunpeng.get("dao_merge")),
            "buddhist": bool(kunpeng.get("buddhist_three")),
            "freudian": bool(kunpeng.get("freudian_layers")),
            "core_contradiction": bool(kunpeng.get("core_contradiction")),
            "data_gaps_found": len(gaps) > 0,
            "strategic_recs_found": len(recs) > 0,
        },
        "updated": datetime.now().strftime("%Y-%m-%d")
    }


def update_knowledge_tree(run_id, topic, result, score):
    """
    Main entry point: call this from grand_cycle._update_knowledge_tree
    OR from flywheel_api_v4.py after each run completes.
    
    Updates page-registry.json with the run result.
    """
    domain = classify_domain(topic)
    if domain is None:
        return {"action": "skip", "reason": "unclassified topic"}
    
    entry = generate_kt_entry(run_id, topic, result, score)
    if entry is None:
        return {"action": "skip", "reason": "could not parse result"}
    
    registry = load_registry()
    entries = registry.get("entries", {})
    
    # Initialize domain list if needed
    if domain not in entries or not isinstance(entries.get(domain), list):
        entries[domain] = []
    
    # Check if this run_id already exists (update vs create)
    existing_idx = None
    domain_list = entries[domain]
    for i, e in enumerate(domain_list):
        if isinstance(e, dict) and e.get("run_id") == run_id:
            existing_idx = i
            break
    
    if existing_idx is not None:
        entries[domain][existing_idx] = entry
        action = "updated"
    else:
        entries[domain].append(entry)
        action = "created"
    
    # Update metadata
    registry["entries"] = entries
    registry["updated"] = datetime.now().isoformat()
    registry["version"] = "1.1"  # version bump to indicate new structure
    
    save_registry(registry)
    
    # Count total entries
    total = sum(len(v) if isinstance(v, list) else 0 for v in entries.values())
    
    return {
        "action": action,
        "domain": domain,
        "run_id": run_id,
        "entry_count": len(entries.get(domain, [])),
        "total_entries": total
    }


def get_kt_entries():
    """Return all KT entries organized by domain"""
    registry = load_registry()
    entries = registry.get("entries", {})
    
    result = {}
    for domain in DOMAIN_MAPPING.keys():
        domain_entries = entries.get(domain, [])
        if isinstance(domain_entries, list):
            result[domain] = {
                "count": len(domain_entries),
                "entries": domain_entries[-10:]  # latest 10
            }
    
    return result


if __name__ == "__main__":
    # Test mode
    registry = load_registry()
    print("Registry loaded: %d domains" % len(registry.get("entries", {})))
    for domain, entries in registry.get("entries", {}).items():
        if isinstance(entries, list) and len(entries) > 0:
            print("  %s: %d entries" % (domain, len(entries)))
    
    # Test classify_domain
    test_topics = [
        "新材料 domain deep analysis: 钙钛矿, 固态电池, 碳化硅",
        "中国新能源汽车2026竞争格局",
        "AGI理论框架与碳硅共生",
        "量子计算技术路线分析",
        "金融衍生品定价模型",
    ]
    print("\nDomain classification test:")
    for t in test_topics:
        print("  %s... -> %s" % (t[:50], classify_domain(t)))