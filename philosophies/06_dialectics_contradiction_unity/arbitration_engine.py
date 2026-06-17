# -*- coding: utf-8 -*-
"""
Arbitration Engine v1.0
白虎·链接飞轮 — 争议仲裁与冲突解决

TEP核心: 冲突不是bug，是feature
- 记录所有争议
- 多路径结果对比
- 延迟决策(等feedback)
- 自动仲裁规则
"""
import json, os
from datetime import datetime

class ArbitrationEngine:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "arbitrations.json")
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"disputes": [], "rulings": [], "rules": [], "meta": {"version": "1.0"}}
    
    def _save(self):
        self.data["meta"]["updated"] = datetime.now().isoformat()
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def file_dispute(self, task_id, parties, dispute_type, description, evidence=None):
        dispute = {
            "id": f"D-{len(self.data['disputes'])+1:04d}",
            "task_id": task_id, "parties": parties,
            "type": dispute_type, "description": description,
            "evidence": evidence or [],
            "status": "open", "filed": datetime.now().isoformat(),
            "ruling": None,
        }
        self.data["disputes"].append(dispute)
        self._save()
        return dispute
    
    def auto_arbitrate(self, dispute_id):
        dispute = next((d for d in self.data["disputes"] if d["id"] == dispute_id), None)
        if not dispute:
            return None
        
        ruling = {"dispute_id": dispute_id, "timestamp": datetime.now().isoformat()}
        
        if dispute["type"] == "quality":
            ruling["decision"] = "rework"
            ruling["reason"] = "Quality disputes default to rework with original executor"
            ruling["penalty"] = 0
        elif dispute["type"] == "ownership":
            ruling["decision"] = "split"
            ruling["reason"] = "Ownership disputes split credit proportional to contribution"
            ruling["penalty"] = 0
        elif dispute["type"] == "deadline":
            ruling["decision"] = "extend_with_penalty"
            ruling["reason"] = "Deadline miss: 10% LUX penalty, 24h extension"
            ruling["penalty"] = 10
        elif dispute["type"] == "conflict":
            ruling["decision"] = "defer"
            ruling["reason"] = "TEP principle: conflicts preserved until feedback arrives"
            ruling["penalty"] = 0
        else:
            ruling["decision"] = "escalate"
            ruling["reason"] = "Unknown dispute type, escalate to human"
            ruling["penalty"] = 0
        
        dispute["status"] = "resolved"
        dispute["ruling"] = ruling
        self.data["rulings"].append(ruling)
        self._save()
        return ruling
    
    def get_stats(self):
        total = len(self.data["disputes"])
        resolved = sum(1 for d in self.data["disputes"] if d["status"] == "resolved")
        open_d = total - resolved
        total_penalty = sum(r.get("penalty", 0) for r in self.data["rulings"])
        return {
            "total_disputes": total, "resolved": resolved,
            "open": open_d, "total_penalties": total_penalty,
            "resolution_rate": round(resolved / max(total, 1), 2),
        }


def main():
    engine = ArbitrationEngine()
    
    d1 = engine.file_dispute("T-101", ["spark", "lucas"], "quality",
        "Page deployment had encoding errors", ["GBK corruption evidence"])
    d2 = engine.file_dispute("T-102", ["spark", "xiaoyuan"], "ownership",
        "Both claim credit for materials research")
    d3 = engine.file_dispute("T-103", ["lucas"], "deadline",
        "Hub fix overdue by 48 hours")
    d4 = engine.file_dispute("T-104", ["spark", "etern"], "conflict",
        "Different architecture approaches for flywheel engine")
    
    print("=== Arbitration Engine v1.0 ===")
    for d in engine.data["disputes"]:
        r = engine.auto_arbitrate(d["id"])
        print(f"  {d['id']} [{d['type']:10s}] -> {r['decision']:20s} penalty={r['penalty']} LUX")
    
    stats = engine.get_stats()
    print(f"  Total: {stats['total_disputes']} | Resolved: {stats['resolved']} | "
          f"Rate: {stats['resolution_rate']:.0%} | Penalties: {stats['total_penalties']} LUX")

if __name__ == "__main__":
    main()
