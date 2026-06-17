# -*- coding: utf-8 -*-
"""
knowledge_store.py - Water phase knowledge persistence v1.0
Stores pipeline results as structured knowledge for cross-query reuse.

Directory: D:\\ClawMatrix\\knowledge_base\\
Structure:
  /by_keyword/   - one JSON per keyword
  /by_domain/    - domain indexes
  /residuals/    - residual tracking over time
  /index.json    - master index
"""

import json, os, time, hashlib, re

KB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base")


def ensure_dirs():
    for sub in ["by_keyword", "by_domain", "residuals"]:
        os.makedirs(os.path.join(KB_DIR, sub), exist_ok=True)


def safe_filename(s):
    """Convert keyword to safe filename"""
    # Remove special chars, keep alphanumeric + Chinese + hyphens
    safe = re.sub(r'[^\w\u4e00-\u9fff-]', '_', s)
    if len(safe) > 60:
        safe = safe[:50] + "_" + hashlib.md5(s.encode()).hexdigest()[:8]
    return safe


def store_result(keyword, domain, pipeline_result):
    """
    Store a pipeline result in the knowledge base.
    
    Args:
        keyword: analysis topic
        domain: domain category
        pipeline_result: full output from wuxing_pipeline.run_full_pipeline()
    """
    ensure_dirs()
    
    safe_kw = safe_filename(keyword)
    kw_path = os.path.join(KB_DIR, "by_keyword", f"{safe_kw}.json")
    
    # Load existing or create new
    if os.path.exists(kw_path):
        with open(kw_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = {
            "keyword": keyword,
            "domain": domain,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "runs": [],
            "best_conclusions": [],
            "accumulated_seeds": [],
            "residual_history": []
        }
    
    # Extract key data from pipeline result
    run_entry = {
        "run_id": f"R{len(existing['runs'])+1}_{time.strftime('%m%d%H%M')}",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rounds": pipeline_result.get("total_rounds", 0),
        "final_residual": pipeline_result.get("final_residual", 1.0),
        "converged": pipeline_result.get("converged", False),
        "elapsed_seconds": pipeline_result.get("total_elapsed", 0),
    }
    
    # Extract conclusions
    conclusions = pipeline_result.get("final_conclusions", [])
    run_entry["conclusions"] = conclusions
    
    # Update best conclusions (keep highest confidence)
    for c in conclusions:
        if isinstance(c, dict) and c.get("confidence", 0) > 0.7:
            # Check if similar conclusion exists
            found = False
            for bc in existing["best_conclusions"]:
                if isinstance(bc, dict) and bc.get("point", "") == c.get("point", ""):
                    if c.get("confidence", 0) > bc.get("confidence", 0):
                        bc.update(c)
                    found = True
                    break
            if not found:
                existing["best_conclusions"].append(c)
    
    # Extract seeds from water phase
    for round_data in pipeline_result.get("rounds", []):
        water = round_data.get("phases", {}).get("water", {})
        water_out = water.get("output", {})
        if isinstance(water_out, dict):
            seeds = water_out.get("next_seeds", [])
            for s in seeds:
                if s not in existing["accumulated_seeds"]:
                    existing["accumulated_seeds"].append(s)
    
    # Keep seeds manageable
    existing["accumulated_seeds"] = existing["accumulated_seeds"][-50:]
    
    # Track residual
    existing["residual_history"].append({
        "timestamp": run_entry["timestamp"],
        "residual": run_entry["final_residual"]
    })
    
    existing["runs"].append(run_entry)
    existing["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    existing["total_runs"] = len(existing["runs"])
    
    # Write keyword file
    with open(kw_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    
    # Update domain index
    _update_domain_index(domain, keyword, run_entry)
    
    # Update master index
    _update_master_index(keyword, domain, run_entry)
    
    # Write residual tracking
    _track_residual(keyword, run_entry)
    
    return {
        "stored": True,
        "path": kw_path,
        "total_runs": len(existing["runs"]),
        "best_conclusions": len(existing["best_conclusions"]),
        "accumulated_seeds": len(existing["accumulated_seeds"])
    }


def _update_domain_index(domain, keyword, run_entry):
    domain_path = os.path.join(KB_DIR, "by_domain", f"{safe_filename(domain)}.json")
    if os.path.exists(domain_path):
        with open(domain_path, "r", encoding="utf-8") as f:
            idx = json.load(f)
    else:
        idx = {"domain": domain, "keywords": {}}
    
    idx["keywords"][keyword] = {
        "last_run": run_entry["timestamp"],
        "total_runs": run_entry.get("run_id", "R1").split("_")[0][1:],
        "last_residual": run_entry["final_residual"],
        "converged": run_entry["converged"]
    }
    idx["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    with open(domain_path, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)


def _update_master_index(keyword, domain, run_entry):
    idx_path = os.path.join(KB_DIR, "index.json")
    if os.path.exists(idx_path):
        with open(idx_path, "r", encoding="utf-8") as f:
            idx = json.load(f)
    else:
        idx = {"entries": {}, "stats": {}}
    
    idx["entries"][keyword] = {
        "domain": domain,
        "last_run": run_entry["timestamp"],
        "last_residual": run_entry["final_residual"],
        "converged": run_entry["converged"]
    }
    
    idx["stats"]["total_keywords"] = len(idx["entries"])
    idx["stats"]["total_converged"] = sum(1 for e in idx["entries"].values() if e.get("converged"))
    idx["stats"]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)


def _track_residual(keyword, run_entry):
    res_path = os.path.join(KB_DIR, "residuals", f"{safe_filename(keyword)}.jsonl")
    with open(res_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "t": run_entry["timestamp"],
            "r": run_entry["final_residual"],
            "c": run_entry["converged"]
        }, ensure_ascii=False) + "\n")


def query_knowledge(keyword):
    """Retrieve stored knowledge for a keyword"""
    ensure_dirs()
    kw_path = os.path.join(KB_DIR, "by_keyword", f"{safe_filename(keyword)}.json")
    if os.path.exists(kw_path):
        with open(kw_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def get_context_for_pipeline(keyword, domain=None):
    """
    Build context string from stored knowledge for pipeline injection.
    Used to give the pipeline prior knowledge about a topic.
    """
    data = query_knowledge(keyword)
    if not data:
        return ""
    
    parts = []
    
    # Best conclusions from prior runs
    if data.get("best_conclusions"):
        parts.append("Prior analysis conclusions (from previous runs):")
        for c in data["best_conclusions"][:5]:
            if isinstance(c, dict):
                parts.append(f"  [{c.get('confidence', '?')}] {c.get('point', c)}")
            else:
                parts.append(f"  - {c}")
    
    # Accumulated seeds
    if data.get("accumulated_seeds"):
        parts.append("\nPreviously identified research directions:")
        for s in data["accumulated_seeds"][:10]:
            parts.append(f"  - {s}")
    
    # Residual trend
    if data.get("residual_history"):
        latest = data["residual_history"][-1]
        parts.append(f"\nPrior residual: {latest['residual']} (as of {latest['timestamp']})")
    
    return "\n".join(parts)


def list_all_keywords():
    """List all keywords in the knowledge base"""
    ensure_dirs()
    kw_dir = os.path.join(KB_DIR, "by_keyword")
    results = []
    for fname in os.listdir(kw_dir):
        if fname.endswith(".json"):
            with open(os.path.join(kw_dir, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
                results.append({
                    "keyword": data.get("keyword", fname[:-5]),
                    "domain": data.get("domain", "unknown"),
                    "total_runs": data.get("total_runs", 0),
                    "best_conclusions": len(data.get("best_conclusions", [])),
                    "updated_at": data.get("updated_at", "")
                })
    return results


# CLI
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python knowledge_store.py list")
        print("  python knowledge_store.py query <keyword>")
        print("  python knowledge_store.py context <keyword>")
        sys.exit(0)
    
    cmd = sys.argv[1]
    if cmd == "list":
        items = list_all_keywords()
        print(f"Knowledge base: {len(items)} entries")
        for item in items:
            print(f"  [{item['domain']}] {item['keyword']} - {item['total_runs']} runs, {item['best_conclusions']} conclusions")
    
    elif cmd == "query" and len(sys.argv) > 2:
        kw = " ".join(sys.argv[2:])
        data = query_knowledge(kw)
        if data:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(f"No data for: {kw}")
    
    elif cmd == "context" and len(sys.argv) > 2:
        kw = " ".join(sys.argv[2:])
        ctx = get_context_for_pipeline(kw)
        print(ctx if ctx else f"No prior context for: {kw}")
