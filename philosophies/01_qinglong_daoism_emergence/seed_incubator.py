# -*- coding: utf-8 -*-
"""
Seed Incubator v1.0
青龙·种子飞轮 → 朱雀·任务飞轮 转化引擎

功能:
- 从种子库读取种子
- 评估种子成熟度 (potential_value * (1-risk_score/10))
- 成熟种子 → 生成任务结构
- 输出: 可执行任务列表
"""
import json, os, hashlib
from datetime import datetime

class SeedIncubator:
    def __init__(self, seed_dir=None, output_dir=None):
        self.seed_dir = seed_dir or os.path.join(os.path.dirname(__file__), "flywheel", "seed_store")
        self.output_dir = output_dir or os.path.join(os.path.dirname(__file__), "flywheel", "incubated")
        os.makedirs(self.output_dir, exist_ok=True)
    
    def load_seeds(self, batch=None):
        """Load all seeds or a specific batch"""
        all_seeds = []
        if not os.path.exists(self.seed_dir):
            return all_seeds
        for f in os.listdir(self.seed_dir):
            if f.endswith('.json') and (batch is None or batch in f):
                path = os.path.join(self.seed_dir, f)
                with open(path, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                    if "seeds" in data:
                        all_seeds.extend(data["seeds"])
        return all_seeds
    
    def evaluate_maturity(self, seed):
        """Score seed maturity: 0-10"""
        pv = seed.get("potential_value", 5)
        rs = seed.get("risk_score", 5)
        maturity = pv * (1 - rs / 10)
        return round(maturity, 2)
    
    def incubate(self, min_maturity=3.0, max_tasks=20):
        """Convert mature seeds to tasks"""
        seeds = self.load_seeds()
        if not seeds:
            return {"tasks": [], "stats": {"total_seeds": 0}}
        
        scored = [(s, self.evaluate_maturity(s)) for s in seeds]
        scored.sort(key=lambda x: x[1], reverse=True)
        
        mature = [(s, m) for s, m in scored if m >= min_maturity]
        
        tasks = []
        for seed, maturity in mature[:max_tasks]:
            task = {
                "id": f"T-INC-{hashlib.md5(seed['id'].encode()).hexdigest()[:8]}",
                "name": f"\u5b75\u5316: {seed['name']}",
                "domain": seed.get("domain", "general"),
                "priority": "P0" if maturity > 6 else "P1" if maturity > 4 else "P2",
                "source_seed": seed["id"],
                "maturity_score": maturity,
                "description": seed.get("hypothesis", ""),
                "status": "ready",
                "created": datetime.now().isoformat(),
            }
            tasks.append(task)
        
        result = {
            "tasks": tasks,
            "stats": {
                "total_seeds": len(seeds),
                "evaluated": len(scored),
                "mature": len(mature),
                "tasks_generated": len(tasks),
                "min_maturity_threshold": min_maturity,
            }
        }
        
        # Save
        out_path = os.path.join(self.output_dir, f"incubated_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(result, ensure_ascii=False, indent=2, fp=f)
        
        return result


def main():
    incubator = SeedIncubator()
    result = incubator.incubate(min_maturity=3.0, max_tasks=15)
    
    print("=== Seed Incubator v1.0 ===")
    print(f"Seeds: {result['stats']['total_seeds']}")
    print(f"Mature: {result['stats']['mature']}")
    print(f"Tasks generated: {result['stats']['tasks_generated']}")
    
    if result["tasks"]:
        print(f"\nTop tasks:")
        for t in result["tasks"][:5]:
            print(f"  [{t['priority']}] {t['name']} (maturity={t['maturity_score']}, domain={t['domain']})")


if __name__ == "__main__":
    main()
