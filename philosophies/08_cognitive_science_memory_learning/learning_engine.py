# -*- coding: utf-8 -*-
"""
Learning Engine v1.0
玄武·认知飞轮 — 知识学习引擎

核心: 从执行残差中提取可复用的知识模式
- 成功模式提取
- 失败教训归档
- 知识图谱更新
- 经验迁移建议
"""
import json, os
from datetime import datetime
from collections import Counter

class LearningEngine:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "learning.json")
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "lessons": [], "patterns": [], "knowledge_base": {},
            "transfer_suggestions": [], "meta": {"version": "1.0"}
        }
    
    def _save(self):
        self.data["meta"]["updated"] = datetime.now().isoformat()
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def record_lesson(self, task_id, domain, lesson_type, description, 
                      root_cause=None, fix=None, transferable=True):
        lesson = {
            "id": f"L-{len(self.data['lessons'])+1:04d}",
            "task_id": task_id, "domain": domain,
            "type": lesson_type,  # success / failure / insight
            "description": description,
            "root_cause": root_cause, "fix": fix,
            "transferable": transferable,
            "applied_count": 0,
            "timestamp": datetime.now().isoformat()
        }
        self.data["lessons"].append(lesson)
        self._save()
        return lesson
    
    def extract_patterns(self):
        """从经验中提取可复用模式"""
        domain_lessons = {}
        for l in self.data["lessons"]:
            d = l["domain"]
            if d not in domain_lessons:
                domain_lessons[d] = {"success": [], "failure": [], "insight": []}
            domain_lessons[d][l["type"]].append(l)
        
        patterns = []
        for domain, lessons in domain_lessons.items():
            success_rate = len(lessons["success"]) / max(
                len(lessons["success"]) + len(lessons["failure"]), 1)
            
            pattern = {
                "domain": domain,
                "total_lessons": sum(len(v) for v in lessons.values()),
                "success_rate": round(success_rate, 2),
                "top_failures": [l["root_cause"] for l in lessons["failure"] if l["root_cause"]][:3],
                "key_insights": [l["description"] for l in lessons["insight"]][:3],
                "maturity": "mature" if success_rate > 0.7 else 
                           "developing" if success_rate > 0.4 else "early"
            }
            patterns.append(pattern)
        
        self.data["patterns"] = patterns
        self._save()
        return patterns
    
    def suggest_transfers(self):
        """建议经验迁移"""
        transferable = [l for l in self.data["lessons"] if l["transferable"]]
        domains = set(l["domain"] for l in self.data["lessons"])
        
        suggestions = []
        for lesson in transferable:
            other_domains = [d for d in domains if d != lesson["domain"]]
            for target in other_domains:
                suggestions.append({
                    "lesson_id": lesson["id"],
                    "from_domain": lesson["domain"],
                    "to_domain": target,
                    "lesson": lesson["description"][:80],
                    "confidence": 0.7 if lesson["type"] == "success" else 0.5
                })
        
        suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        self.data["transfer_suggestions"] = suggestions[:10]
        self._save()
        return suggestions[:10]


def main():
    engine = LearningEngine()
    
    lessons = [
        ("T-001", "infra", "failure", "GBK编码导致中文乱码", "write工具输出混合编码", "用Python脚本显式UTF-8", True),
        ("T-002", "infra", "success", "paramiko SSH+SCP是唯一可靠部署方式", None, None, True),
        ("T-003", "infra", "failure", "Hub NSSM服务化失败", "asyncio在SYSTEM上下文导入失败", "使用mini_hub替代", True),
        ("T-004", "finance", "success", "四流合一架构有效分离数据源", None, None, True),
        ("T-005", "finance", "insight", "恒生UF3.0占52%市场,差异化定位是唯一出路", None, None, True),
        ("T-006", "materials", "success", "41种材料×8条产业链形成知识壁垒", None, None, True),
        ("T-007", "materials", "insight", "磷化铟国产替代率<20%,最大机会窗口", None, None, True),
        ("T-008", "ai", "success", "MiniMax用curl绕过SSL问题", None, None, True),
        ("T-009", "ai", "failure", "DashScope认证错误", "sk-sp-前缀key不兼容标准端点", "使用coding.dashscope", True),
        ("T-010", "deploy", "insight", "大文件>22KB必须分块处理", None, None, True),
    ]
    
    print("=== Learning Engine v1.0 ===")
    for tid, domain, ltype, desc, cause, fix, trans in lessons:
        lesson = engine.record_lesson(tid, domain, ltype, desc, cause, fix, trans)
        icon = {"success": "+", "failure": "x", "insight": "!"}[ltype]
        print(f"  [{icon}] {lesson['id']} [{domain:10s}] {desc[:50]}")
    
    patterns = engine.extract_patterns()
    print(f"\n  Patterns extracted: {len(patterns)}")
    for p in patterns:
        print(f"    {p['domain']:10s} | {p['total_lessons']} lessons | "
              f"success={p['success_rate']:.0%} | {p['maturity']}")
    
    transfers = engine.suggest_transfers()
    print(f"\n  Transfer suggestions: {len(transfers)}")
    for t in transfers[:5]:
        print(f"    {t['from_domain']:10s} -> {t['to_domain']:10s} | "
              f"conf={t['confidence']:.1f} | {t['lesson'][:40]}")

if __name__ == "__main__":
    main()
