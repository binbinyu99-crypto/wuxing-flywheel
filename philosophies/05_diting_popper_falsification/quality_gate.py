# -*- coding: utf-8 -*-
"""
Quality Gate v1.0
朱雀·任务飞轮 — 质量门控

交付前自动检查质量标准
"""
import json, os
from datetime import datetime

class QualityGate:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "quality_gate.json")
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "checks": [], "rules": [], "pass_rate": 0, "meta": {"version": "1.0"}
        }
    
    def _save(self):
        self.data["meta"]["updated"] = datetime.now().isoformat()
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def add_rule(self, rule_id, name, check_fn_desc, severity="must"):
        rule = {"id": rule_id, "name": name, "check": check_fn_desc, "severity": severity}
        self.data["rules"].append(rule)
        self._save()
        return rule
    
    def check_deliverable(self, task_id, deliverable):
        """
        deliverable: {type, size, has_tests, has_docs, encoding, deployed}
        """
        results = []
        passed = True
        
        # Check 1: 非空
        if deliverable.get("size", 0) <= 0:
            results.append({"rule": "non_empty", "pass": False, "msg": "Deliverable is empty"})
            passed = False
        else:
            results.append({"rule": "non_empty", "pass": True})
        
        # Check 2: 编码正确
        if deliverable.get("encoding") != "utf-8":
            results.append({"rule": "encoding", "pass": False, "msg": f"Encoding {deliverable.get('encoding')} != utf-8"})
            if deliverable.get("type") in ("html", "py"):
                passed = False
        else:
            results.append({"rule": "encoding", "pass": True})
        
        # Check 3: 引擎必须有测试
        if deliverable.get("type") == "engine":
            if not deliverable.get("has_tests"):
                results.append({"rule": "engine_tests", "pass": False, "msg": "Engine has no tests"})
                passed = False
            else:
                results.append({"rule": "engine_tests", "pass": True})
        
        # Check 4: 页面必须已部署
        if deliverable.get("type") == "html":
            if not deliverable.get("deployed"):
                results.append({"rule": "deployed", "pass": False, "msg": "Page not deployed"})
                passed = False
            else:
                results.append({"rule": "deployed", "pass": True})
        
        # Check 5: 大小合理
        if deliverable.get("size", 0) > 200000:
            results.append({"rule": "size_limit", "pass": False, "msg": f"Too large: {deliverable['size']}B > 200KB"})
        else:
            results.append({"rule": "size_limit", "pass": True})
        
        check = {
            "task_id": task_id, "results": results,
            "overall_pass": passed,
            "pass_count": sum(1 for r in results if r["pass"]),
            "total_checks": len(results),
            "timestamp": datetime.now().isoformat()
        }
        self.data["checks"].append(check)
        
        total = len(self.data["checks"])
        passes = sum(1 for c in self.data["checks"] if c["overall_pass"])
        self.data["pass_rate"] = round(passes / total, 2) if total > 0 else 0
        
        self._save()
        return check


def main():
    gate = QualityGate()
    
    deliverables = [
        ("T-R18-01", {"type": "engine", "size": 5500, "has_tests": True, "encoding": "utf-8", "deployed": False}),
        ("T-R18-02", {"type": "html", "size": 8000, "has_tests": False, "encoding": "utf-8", "deployed": True}),
        ("T-R18-03", {"type": "engine", "size": 4200, "has_tests": False, "encoding": "utf-8", "deployed": False}),
        ("T-R18-04", {"type": "html", "size": 5100, "has_tests": False, "encoding": "gbk", "deployed": True}),
        ("T-R18-05", {"type": "html", "size": 0, "has_tests": False, "encoding": "utf-8", "deployed": False}),
    ]
    
    print("=== Quality Gate v1.0 ===")
    for tid, d in deliverables:
        result = gate.check_deliverable(tid, d)
        status = "PASS" if result["overall_pass"] else "FAIL"
        fails = [r for r in result["results"] if not r["pass"]]
        fail_msg = "; ".join(r.get("msg", "") for r in fails) if fails else ""
        print(f"  {tid} [{d['type']:6s}] {status} ({result['pass_count']}/{result['total_checks']}) {fail_msg}")
    
    print(f"\n  Overall pass rate: {gate.data['pass_rate']:.0%}")

if __name__ == "__main__":
    main()
