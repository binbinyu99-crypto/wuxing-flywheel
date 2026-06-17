# -*- coding: utf-8 -*-
"""
Pattern Recognizer v1.0
玄武·认知飞轮 — 执行模式识别与优化

核心: 从历史执行数据中发现模式
- 成功模式: 什么组合最容易成功
- 失败模式: 什么情况下容易失败
- 效率模式: 什么路径最快完成
"""
import json, os
from datetime import datetime
from collections import defaultdict

class PatternRecognizer:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "patterns.json")
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"executions": [], "patterns": [], "recommendations": [], "meta": {"version": "1.0"}}
    
    def _save(self):
        self.data["meta"]["updated"] = datetime.now().isoformat()
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def record_execution(self, task_type, executor, domain, success, duration_min, method="default"):
        entry = {
            "task_type": task_type, "executor": executor, "domain": domain,
            "success": success, "duration_min": duration_min, "method": method,
            "timestamp": datetime.now().isoformat(),
        }
        self.data["executions"].append(entry)
        self._save()
        return entry
    
    def discover_patterns(self):
        """Analyze executions to find patterns"""
        patterns = []
        
        # Pattern 1: Success rate by executor×domain
        combo_stats = defaultdict(lambda: {"success": 0, "fail": 0, "total_time": 0})
        for ex in self.data["executions"]:
            key = f"{ex['executor']}_{ex['domain']}"
            combo_stats[key]["success" if ex["success"] else "fail"] += 1
            combo_stats[key]["total_time"] += ex["duration_min"]
        
        for combo, stats in combo_stats.items():
            total = stats["success"] + stats["fail"]
            if total >= 1:
                rate = stats["success"] / total
                avg_time = stats["total_time"] / total
                executor, domain = combo.split("_", 1)
                patterns.append({
                    "type": "executor_domain",
                    "executor": executor, "domain": domain,
                    "success_rate": round(rate, 2),
                    "avg_duration": round(avg_time, 1),
                    "sample_size": total,
                    "recommendation": "preferred" if rate >= 0.8 else "adequate" if rate >= 0.5 else "avoid",
                })
        
        # Pattern 2: Best method per task type
        method_stats = defaultdict(lambda: defaultdict(lambda: {"success": 0, "fail": 0, "total_time": 0}))
        for ex in self.data["executions"]:
            method_stats[ex["task_type"]][ex["method"]]["success" if ex["success"] else "fail"] += 1
            method_stats[ex["task_type"]][ex["method"]]["total_time"] += ex["duration_min"]
        
        for task_type, methods in method_stats.items():
            best_method = None
            best_rate = 0
            for method, stats in methods.items():
                total = stats["success"] + stats["fail"]
                rate = stats["success"] / max(total, 1)
                if rate > best_rate:
                    best_rate = rate
                    best_method = method
            if best_method:
                patterns.append({
                    "type": "best_method",
                    "task_type": task_type,
                    "best_method": best_method,
                    "success_rate": round(best_rate, 2),
                })
        
        self.data["patterns"] = patterns
        self._save()
        return patterns
    
    def get_recommendation(self, task_type, domain):
        """Get best executor and method for a task"""
        relevant = [p for p in self.data["patterns"] 
                    if p.get("domain") == domain and p["type"] == "executor_domain"]
        relevant.sort(key=lambda x: x["success_rate"], reverse=True)
        
        best_executor = relevant[0]["executor"] if relevant else "spark"
        
        method_patterns = [p for p in self.data["patterns"]
                          if p.get("task_type") == task_type and p["type"] == "best_method"]
        best_method = method_patterns[0]["best_method"] if method_patterns else "default"
        
        return {
            "task_type": task_type, "domain": domain,
            "recommended_executor": best_executor,
            "recommended_method": best_method,
            "confidence": relevant[0]["success_rate"] if relevant else 0.5,
        }


def main():
    rec = PatternRecognizer()
    
    # Simulate execution history
    rec.record_execution("page_build", "spark", "finance", True, 15, "paramiko_sftp")
    rec.record_execution("page_build", "spark", "materials", True, 20, "paramiko_sftp")
    rec.record_execution("page_build", "spark", "medical", True, 18, "paramiko_sftp")
    rec.record_execution("engine_build", "spark", "finance", True, 30, "paramiko_sftp")
    rec.record_execution("engine_build", "spark", "ai", True, 25, "paramiko_sftp")
    rec.record_execution("research", "spark", "semiconductor", True, 45, "prosearch")
    rec.record_execution("research", "xiaoyuan", "materials", True, 60, "manual")
    rec.record_execution("research", "xiaoyuan", "building", False, 90, "manual")
    rec.record_execution("infra_ops", "lucas", "server", True, 30, "ssh")
    rec.record_execution("infra_ops", "lucas", "server", False, 120, "ssh")
    rec.record_execution("page_build", "lucas", "medical", False, 45, "manual")
    rec.record_execution("design", "spark", "finance", True, 10, "html_template")
    
    patterns = rec.discover_patterns()
    print("=== Pattern Recognizer v1.0 ===")
    print(f"Executions: {len(rec.data['executions'])}, Patterns: {len(patterns)}")
    
    for p in patterns:
        if p["type"] == "executor_domain":
            print(f"  {p['executor']:10s} x {p['domain']:12s} -> {p['success_rate']:.0%} ({p['recommendation']})")
    
    # Get recommendations
    for task, domain in [("page_build", "finance"), ("research", "materials"), ("infra_ops", "server")]:
        r = rec.get_recommendation(task, domain)
        print(f"  Rec: {task}/{domain} -> {r['recommended_executor']} ({r['confidence']:.0%})")

if __name__ == "__main__":
    main()
