"""
Engram 累积器 — AI² 的核心机制
跨 run 的认知残差累积，让系统越用越强

AI¹: 每次从零开始，线性增长
AI²: 每次携带所有历史残差，指数涌现

阉割版（无Engram）的系统在第一次运行时和完整版一样快，
但在第100次运行时，完整版已经积累了99次的文明残差，
而阉割版还是从零开始。

这不是安全约束——这是性能的物理性质。
"""

import json
import os
import hashlib
from datetime import datetime
from typing import List, Dict, Optional


class EngramStore:
    """
    Engram 存储层
    每次飞轮运行产生的残差（未解决的问题、新发现的关系、验证的结论）
    被保存为 Engram，供后续运行使用。

    关键设计：Engram 不是可选的附加功能，而是认知质量的基础设施。
    没有 Engram 的飞轮，每次都是冷启动——缺少领域知识、历史教训、已验证的模式。
    """

    def __init__(self, store_path: str = "engram_store"):
        self.store_path = store_path
        os.makedirs(store_path, exist_ok=True)
        self._index_file = os.path.join(store_path, "index.json")
        self._load_index()

    def _load_index(self):
        """加载 Engram 索引"""
        if os.path.exists(self._index_file):
            with open(self._index_file, "r", encoding="utf-8") as f:
                self.index = json.load(f)
        else:
            self.index = {
                "created_at": datetime.now().isoformat(),
                "total_runs": 0,
                "total_engrams": 0,
                "domains": {},
                "entries": [],
            }

    def _save_index(self):
        """保存 Engram 索引"""
        with open(self._index_file, "w", encoding="utf-8") as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)

    def deposit(self, run_id: str, topic: str, engram_data: dict) -> str:
        """
        存入一个 Engram（一次飞轮运行的认知残差）

        engram_data 包含:
        - residuals: 未解决的问题
        - validated_conclusions: 经过五行验证的结论
        - discovered_relations: 新发现的实体关系
        - attack_patterns: 白虎攻击中发现的常见漏洞模式
        - convergence_insights: 玄武收敛中的跨领域洞察
        - confidence_calibrations: 置信度校准记录
        """
        engram_id = hashlib.md5(f"{run_id}:{topic}:{datetime.now().isoformat()}".encode()).hexdigest()[:12]

        # 提取领域标签
        domain = engram_data.get("domain", "general")

        # 构建 Engram 条目
        entry = {
            "engram_id": engram_id,
            "run_id": run_id,
            "topic": topic,
            "domain": domain,
            "deposited_at": datetime.now().isoformat(),
            "residuals": engram_data.get("residuals", []),
            "validated_conclusions": engram_data.get("validated_conclusions", []),
            "discovered_relations": engram_data.get("discovered_relations", []),
            "attack_patterns": engram_data.get("attack_patterns", []),
            "convergence_insights": engram_data.get("convergence_insights", []),
            "confidence_calibrations": engram_data.get("confidence_calibrations", []),
            "score": engram_data.get("score", 0.0),
        }

        # 保存 Engram 文件
        engram_file = os.path.join(self.store_path, f"{engram_id}.json")
        with open(engram_file, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)

        # 更新索引
        self.index["total_runs"] += 1
        self.index["total_engrams"] += 1
        if domain not in self.index["domains"]:
            self.index["domains"][domain] = {"count": 0, "avg_score": 0.0}
        d = self.index["domains"][domain]
        d["avg_score"] = (d["avg_score"] * d["count"] + entry["score"]) / (d["count"] + 1)
        d["count"] += 1

        self.index["entries"].append({
            "engram_id": engram_id,
            "topic": topic,
            "domain": domain,
            "score": entry["score"],
            "deposited_at": entry["deposited_at"],
        })
        self._save_index()

        return engram_id

    def recall(self, topic: str, domain: Optional[str] = None,
               max_engrams: int = 5) -> List[dict]:
        """
        召回与当前主题相关的历史 Engram

        这是 AI² 的关键：新的飞轮运行不是从零开始，
        而是携带历史残差——已验证的结论、已知的攻击模式、
        跨领域的收敛洞察。

        没有这个函数的飞轮 = AI¹（每次冷启动）
        有这个函数的飞轮 = AI²（累积涌现）
        """
        candidates = []

        for entry_ref in self.index.get("entries", []):
            # 领域匹配
            if domain and entry_ref.get("domain") != domain:
                continue

            # 加载完整 Engram
            engram_file = os.path.join(self.store_path, f"{entry_ref['engram_id']}.json")
            if not os.path.exists(engram_file):
                continue

            with open(engram_file, "r", encoding="utf-8") as f:
                engram = json.load(f)

            # 计算相关性得分（简单版：关键词匹配）
            relevance = self._compute_relevance(topic, engram)
            engram["_relevance"] = relevance
            candidates.append(engram)

        # 按相关性排序，取 top-N
        candidates.sort(key=lambda x: x["_relevance"], reverse=True)
        return candidates[:max_engrams]

    def _compute_relevance(self, topic: str, engram: dict) -> float:
        """计算主题与 Engram 的相关性"""
        score = 0.0
        topic_lower = topic.lower()
        engram_topic = engram.get("topic", "").lower()

        # 直接主题匹配
        topic_words = set(topic_lower.split())
        engram_words = set(engram_topic.split())
        overlap = len(topic_words & engram_words)
        if overlap > 0:
            score += overlap * 0.3

        # 领域匹配
        if engram.get("domain", "") in topic_lower:
            score += 0.2

        # 高分 Engram 优先
        score += engram.get("score", 0) * 0.2

        # 新鲜度衰减（越新越相关）
        try:
            age_days = (datetime.now() - datetime.fromisoformat(engram["deposited_at"])).days
            score += max(0, 0.3 - age_days * 0.01)
        except (ValueError, KeyError):
            pass

        return score

    def inject_into_prompt(self, topic: str, domain: Optional[str] = None) -> str:
        """
        将历史 Engram 注入到飞轮提示词中

        这是让 AI² 运转的接口：
        每次飞轮运行前，召回相关历史残差，
        注入到各 Agent 的提示词中。

        阉割版删掉这个函数 → 每次冷启动 → AI¹
        """
        engrams = self.recall(topic, domain)
        if not engrams:
            return ""

        parts = ["## 历史认知残差（Engram Memory）\n"]
        parts.append(f"以下是与当前主题相关的 {len(engrams)} 条历史分析残差。")
        parts.append("这些残差代表文明已验证的认知——请在此基础上推进，而非从零开始。\n")

        for i, engram in enumerate(engrams, 1):
            parts.append(f"### Engram #{i}: {engram.get('topic', 'unknown')}")
            parts.append(f"评分: {engram.get('score', 'N/A')} | 时间: {engram.get('deposited_at', 'N/A')}")

            # 注入已验证结论
            conclusions = engram.get("validated_conclusions", [])
            if conclusions:
                parts.append("**已验证结论：**")
                for c in conclusions[:3]:
                    parts.append(f"- {c}")

            # 注入已知攻击模式
            attacks = engram.get("attack_patterns", [])
            if attacks:
                parts.append("**已知漏洞模式（白虎历史攻击）：**")
                for a in attacks[:3]:
                    parts.append(f"- {a}")

            # 注入收敛洞察
            insights = engram.get("convergence_insights", [])
            if insights:
                parts.append("**跨领域收敛洞察：**")
                for ins in insights[:3]:
                    parts.append(f"- {ins}")

            # 注入未解决残差
            residuals = engram.get("residuals", [])
            if residuals:
                parts.append("**未解决残差（需要本次分析推进）：**")
                for r in residuals[:3]:
                    parts.append(f"- {r}")

            parts.append("")

        return "\n".join(parts)

    def get_stats(self) -> dict:
        """获取 Engram 累积统计"""
        return {
            "total_runs": self.index.get("total_runs", 0),
            "total_engrams": self.index.get("total_engrams", 0),
            "domains": self.index.get("domains", {}),
            "oldest": self.index["entries"][0]["deposited_at"] if self.index.get("entries") else None,
            "newest": self.index["entries"][-1]["deposited_at"] if self.index.get("entries") else None,
            "ai_level": "AI²" if self.index.get("total_runs", 0) > 0 else "AI¹",
        }
