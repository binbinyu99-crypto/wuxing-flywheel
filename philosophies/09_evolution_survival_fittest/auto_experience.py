# -*- coding: utf-8 -*-
"""
Auto Experience Extractor v1.0
玄武·认知飞轮 — 自动经验提取

从执行日志中自动提取经验教训
"""
import json, os, re
from datetime import datetime

class AutoExperienceExtractor:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "auto_experience.json")
        self.data = self._load()
        self.patterns = {
            "success": ["PASS", "deployed", "verified", "completed", "200 OK"],
            "failure": ["FAIL", "error", "failed", "crashed", "timeout", "404", "500"],
            "insight": ["discovered", "found that", "key finding", "important", "root cause"],
        }
    
    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"experiences": [], "meta": {"version": "1.0", "total_extracted": 0}}
    
    def _save(self):
        self.data["meta"]["updated"] = datetime.now().isoformat()
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def extract_from_log(self, log_text, context=""):
        """从日志文本中自动提取经验"""
        extracted = []
        lines = log_text.split('\n')
        
        for line in lines:
            line_lower = line.lower()
            
            for exp_type, keywords in self.patterns.items():
                for kw in keywords:
                    if kw.lower() in line_lower:
                        exp = {
                            "id": f"AE-{self.data['meta']['total_extracted']+1:04d}",
                            "type": exp_type,
                            "source_line": line.strip()[:200],
                            "keyword_matched": kw,
                            "context": context,
                            "timestamp": datetime.now().isoformat()
                        }
                        self.data["experiences"].append(exp)
                        self.data["meta"]["total_extracted"] += 1
                        extracted.append(exp)
                        break
        
        self._save()
        return extracted
    
    def get_summary(self):
        by_type = {}
        for e in self.data["experiences"]:
            t = e["type"]
            by_type[t] = by_type.get(t, 0) + 1
        return {
            "total": len(self.data["experiences"]),
            "by_type": by_type
        }


def main():
    extractor = AutoExperienceExtractor()
    
    sample_log = """
=== R18 Execution Log ===
seed_competition.py test PASS - 6 candidates, tournament completed
auto_incubation.py PASS - 3 graduated, 1 rejected
task_auto_assigner.py PASS - all 5 tasks assigned
quality_gate.py PASS - but overall pass rate only 40%
prediction_engine.py PASS - discovered that Lucas x infra has only 12% success rate
contract_lifecycle.py PASS - 2 settled, 1 disputed
Root cause: Hub still not production-ready, Lucas deploy failed twice
Key finding: cross-domain tasks have 30% higher innovation but 15% lower success rate
Error: GBK encoding still causes issues on Windows terminal
Deployed 8 pages to skycetus.cn, all verified 200 OK
Important: feedback loop shows Path A dominant at 41.1%, but C rising to 31.5%
    """
    
    results = extractor.extract_from_log(sample_log, "R18 execution")
    
    print("=== Auto Experience Extractor v1.0 ===")
    for r in results:
        icon = {"success": "+", "failure": "x", "insight": "!"}[r["type"]]
        print(f"  [{icon}] {r['id']} matched '{r['keyword_matched']}': {r['source_line'][:60]}")
    
    summary = extractor.get_summary()
    print(f"\n  Total: {summary['total']} experiences extracted")
    print(f"  By type: {summary['by_type']}")

if __name__ == "__main__":
    main()
