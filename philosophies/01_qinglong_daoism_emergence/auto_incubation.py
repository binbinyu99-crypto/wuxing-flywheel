# -*- coding: utf-8 -*-
"""
Auto Incubation Pipeline v1.0
青龙·种子飞轮 — 自动孵化流水线

种子→评估→孵化→任务 全自动
"""
import json, os
from datetime import datetime

class AutoIncubation:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "incubation_pipeline.json")
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"pipeline": [], "graduated": [], "rejected": [], "meta": {"version": "1.0"}}
    
    def _save(self):
        self.data["meta"]["updated"] = datetime.now().isoformat()
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def intake(self, seed_id, name, domain, raw_score):
        """Stage 1: 种子进入流水线"""
        entry = {
            "seed_id": seed_id, "name": name, "domain": domain,
            "stage": "intake", "raw_score": raw_score,
            "stages_completed": [], "entered": datetime.now().isoformat()
        }
        self.data["pipeline"].append(entry)
        self._save()
        return entry
    
    def evaluate(self, seed_id):
        """Stage 2: 评估"""
        entry = next((e for e in self.data["pipeline"] if e["seed_id"] == seed_id), None)
        if not entry:
            return None
        
        if entry["raw_score"] >= 6.0:
            entry["stage"] = "incubating"
            entry["eval_result"] = "pass"
        elif entry["raw_score"] >= 4.0:
            entry["stage"] = "needs_work"
            entry["eval_result"] = "conditional"
        else:
            entry["stage"] = "rejected"
            entry["eval_result"] = "fail"
            self.data["rejected"].append(entry)
            self.data["pipeline"].remove(entry)
        
        entry["stages_completed"].append("evaluate")
        self._save()
        return entry
    
    def incubate(self, seed_id, iterations=3):
        """Stage 3: 孵化(模拟迭代改进)"""
        entry = next((e for e in self.data["pipeline"] if e["seed_id"] == seed_id), None)
        if not entry or entry["stage"] not in ("incubating", "needs_work"):
            return None
        
        score = entry["raw_score"]
        for i in range(iterations):
            improvement = 0.3 * (10 - score) / 10  # 递减改进
            score += improvement
        
        entry["incubated_score"] = round(score, 2)
        entry["iterations"] = iterations
        entry["stages_completed"].append("incubate")
        
        if score >= 7.0:
            entry["stage"] = "ready"
        else:
            entry["stage"] = "incubating"
        
        self._save()
        return entry
    
    def graduate(self, seed_id):
        """Stage 4: 毕业成为任务"""
        entry = next((e for e in self.data["pipeline"] if e["seed_id"] == seed_id), None)
        if not entry or entry["stage"] != "ready":
            return None
        
        task = {
            "task_id": f"T-{seed_id}",
            "name": entry["name"],
            "domain": entry["domain"],
            "source_seed": seed_id,
            "quality_score": entry.get("incubated_score", entry["raw_score"]),
            "graduated": datetime.now().isoformat()
        }
        
        entry["stage"] = "graduated"
        entry["stages_completed"].append("graduate")
        self.data["graduated"].append(task)
        self._save()
        return task
    
    def run_full_pipeline(self, seeds):
        """一键全流程"""
        results = []
        for s in seeds:
            self.intake(s["id"], s["name"], s["domain"], s["score"])
            self.evaluate(s["id"])
            entry = next((e for e in self.data["pipeline"] if e["seed_id"] == s["id"]), None)
            if entry and entry["stage"] in ("incubating", "needs_work"):
                self.incubate(s["id"])
                entry = next((e for e in self.data["pipeline"] if e["seed_id"] == s["id"]), None)
                if entry and entry["stage"] == "ready":
                    task = self.graduate(s["id"])
                    results.append({"seed": s["id"], "result": "graduated", "task": task["task_id"]})
                else:
                    results.append({"seed": s["id"], "result": entry["stage"] if entry else "lost"})
            elif entry:
                results.append({"seed": s["id"], "result": entry["stage"]})
            else:
                results.append({"seed": s["id"], "result": "rejected"})
        return results


def main():
    pipeline = AutoIncubation()
    
    seeds = [
        {"id": "S-201", "name": "券商四流清算SaaS", "domain": "finance", "score": 8.5},
        {"id": "S-202", "name": "SiC外延片路由器", "domain": "semiconductor", "score": 7.0},
        {"id": "S-203", "name": "DRG/DIP医疗清算", "domain": "medical", "score": 6.2},
        {"id": "S-204", "name": "碳纤维供应链DB", "domain": "materials", "score": 7.5},
        {"id": "S-205", "name": "量子模拟平台", "domain": "ai", "score": 3.5},
        {"id": "S-206", "name": "智能建筑OS", "domain": "robotics", "score": 5.8},
    ]
    
    print("=== Auto Incubation Pipeline v1.0 ===")
    results = pipeline.run_full_pipeline(seeds)
    for r in results:
        icon = {"graduated": "+", "incubating": "~", "needs_work": "?", "rejected": "x"}.get(r["result"], "?")
        task_info = f" -> {r['task']}" if "task" in r else ""
        print(f"  [{icon}] {r['seed']:6s} {r['result']:12s}{task_info}")
    
    print(f"\n  Pipeline: {len(pipeline.data['pipeline'])} in pipeline, "
          f"{len(pipeline.data['graduated'])} graduated, "
          f"{len(pipeline.data['rejected'])} rejected")

if __name__ == "__main__":
    main()
