# -*- coding: utf-8 -*-
"""
Seed Evaluator v1.0
青龙·种子飞轮 — 种子质量评估

10维评估模型（对应Robin的10个认知API）:
1. 问题定义清晰度
2. 问题分解可行性
3. 价值函数明确度
4. 解决方案多样性
5. 风险可识别性
6. 资源可估算性
7. 约束可映射性
8. 竞争可分析性
9. 执行计划可行性
10. 叙事输出完整度
"""
import json, os
from datetime import datetime
import random

class SeedEvaluator:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "seed_evaluations.json")
        self.data = self._load()
        self.dimensions = [
            "problem_clarity", "decomposition", "value_function",
            "solution_diversity", "risk_identification", "resource_estimation",
            "constraint_mapping", "competition_analysis", "execution_plan",
            "narrative_output"
        ]
    
    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"evaluations": [], "stats": {}, "meta": {"version": "1.0"}}
    
    def _save(self):
        self.data["meta"]["updated"] = datetime.now().isoformat()
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def evaluate_seed(self, seed_id, seed_name, domain, scores):
        """
        scores: dict with 10 dimension scores (0-10 each)
        Returns: evaluation with overall score and recommendation
        """
        overall = sum(scores.values()) / len(scores)
        
        # Weighted: value_function and execution_plan matter more
        weighted = (
            scores.get("problem_clarity", 5) * 1.0 +
            scores.get("decomposition", 5) * 1.0 +
            scores.get("value_function", 5) * 1.5 +
            scores.get("solution_diversity", 5) * 1.0 +
            scores.get("risk_identification", 5) * 1.2 +
            scores.get("resource_estimation", 5) * 1.0 +
            scores.get("constraint_mapping", 5) * 0.8 +
            scores.get("competition_analysis", 5) * 1.0 +
            scores.get("execution_plan", 5) * 1.5 +
            scores.get("narrative_output", 5) * 1.0
        ) / 11.0
        
        if weighted >= 8:
            recommendation = "immediate_execute"
            priority = "P0"
        elif weighted >= 6:
            recommendation = "incubate"
            priority = "P1"
        elif weighted >= 4:
            recommendation = "needs_work"
            priority = "P2"
        else:
            recommendation = "archive"
            priority = "P3"
        
        weak_dims = [d for d, s in scores.items() if s < 5]
        strong_dims = [d for d, s in scores.items() if s >= 8]
        
        evaluation = {
            "seed_id": seed_id, "seed_name": seed_name, "domain": domain,
            "scores": scores, "overall": round(overall, 1),
            "weighted": round(weighted, 1),
            "recommendation": recommendation, "priority": priority,
            "weak_dimensions": weak_dims, "strong_dimensions": strong_dims,
            "timestamp": datetime.now().isoformat()
        }
        
        self.data["evaluations"].append(evaluation)
        self._update_stats(domain, weighted)
        self._save()
        return evaluation
    
    def _update_stats(self, domain, score):
        if domain not in self.data["stats"]:
            self.data["stats"][domain] = {"count": 0, "total_score": 0, "avg": 0}
        self.data["stats"][domain]["count"] += 1
        self.data["stats"][domain]["total_score"] += score
        self.data["stats"][domain]["avg"] = round(
            self.data["stats"][domain]["total_score"] / self.data["stats"][domain]["count"], 1)
    
    def get_portfolio_analysis(self):
        """分析种子组合的健康度"""
        evals = self.data["evaluations"]
        if not evals:
            return {}
        
        by_priority = {}
        for e in evals:
            p = e["priority"]
            by_priority[p] = by_priority.get(p, 0) + 1
        
        by_domain = {}
        for e in evals:
            d = e["domain"]
            if d not in by_domain:
                by_domain[d] = []
            by_domain[d].append(e["weighted"])
        
        domain_health = {d: {"count": len(s), "avg": round(sum(s)/len(s), 1)} 
                        for d, s in by_domain.items()}
        
        return {
            "total_seeds": len(evals),
            "by_priority": by_priority,
            "domain_health": domain_health,
            "avg_quality": round(sum(e["weighted"] for e in evals) / len(evals), 1)
        }


def main():
    evaluator = SeedEvaluator()
    
    seeds = [
        ("S-001", "四流合一清算引擎", "finance", {
            "problem_clarity": 9, "decomposition": 8, "value_function": 9,
            "solution_diversity": 7, "risk_identification": 8, "resource_estimation": 7,
            "constraint_mapping": 8, "competition_analysis": 9, "execution_plan": 8,
            "narrative_output": 8
        }),
        ("S-002", "SiC外延片供应链路由", "semiconductor", {
            "problem_clarity": 8, "decomposition": 7, "value_function": 8,
            "solution_diversity": 6, "risk_identification": 7, "resource_estimation": 6,
            "constraint_mapping": 7, "competition_analysis": 8, "execution_plan": 6,
            "narrative_output": 7
        }),
        ("S-003", "DRG/DIP医疗清算", "medical", {
            "problem_clarity": 7, "decomposition": 6, "value_function": 7,
            "solution_diversity": 5, "risk_identification": 8, "resource_estimation": 5,
            "constraint_mapping": 6, "competition_analysis": 6, "execution_plan": 5,
            "narrative_output": 6
        }),
        ("S-004", "碳纤维产业链数据库", "materials", {
            "problem_clarity": 8, "decomposition": 8, "value_function": 7,
            "solution_diversity": 7, "risk_identification": 6, "resource_estimation": 7,
            "constraint_mapping": 7, "competition_analysis": 7, "execution_plan": 7,
            "narrative_output": 8
        }),
        ("S-005", "量子材料模拟平台", "materials", {
            "problem_clarity": 6, "decomposition": 5, "value_function": 5,
            "solution_diversity": 8, "risk_identification": 4, "resource_estimation": 3,
            "constraint_mapping": 4, "competition_analysis": 5, "execution_plan": 3,
            "narrative_output": 5
        }),
    ]
    
    print("=== Seed Evaluator v1.0 (10-dim) ===")
    for sid, name, domain, scores in seeds:
        ev = evaluator.evaluate_seed(sid, name, domain, scores)
        print(f"  {sid} {name:20s} | weighted={ev['weighted']:.1f} | "
              f"{ev['priority']} {ev['recommendation']}")
        if ev["weak_dimensions"]:
            print(f"         weak: {', '.join(ev['weak_dimensions'][:3])}")
    
    portfolio = evaluator.get_portfolio_analysis()
    print(f"\n  Portfolio: {portfolio['total_seeds']} seeds | "
          f"avg quality={portfolio['avg_quality']}")
    print(f"  By priority: {portfolio['by_priority']}")

if __name__ == "__main__":
    main()
