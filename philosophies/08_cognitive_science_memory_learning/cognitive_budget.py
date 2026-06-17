# -*- coding: utf-8 -*-
"""
cognitive_budget.py — 认知预算调度器 (MEU-08)
Based on flywheel design CogOS: cognitive budget scheduler

Auto-detects question complexity → allocates rounds, agents, tokens.
Simple questions get fast answers. Complex questions get deep analysis.

Complexity dimensions:
- Domain breadth (how many fields involved)
- Uncertainty level (how much is unknown)
- Stakeholder count (who is affected)
- Time horizon (short vs long term)
- Data availability (is evidence accessible)

v1.0.0 — 2026-05-03
"""
VERSION = "1.0.0"

import re, time
from typing import Dict, Optional

# ============================================================
# Complexity Heuristics
# ============================================================

COMPLEXITY_KEYWORDS = {
    "high": [
        "战略", "strategy", "architecture", "framework", "生态", "ecosystem",
        "disruption", "paradigm", "融合", "convergence", "政策", "policy",
        "宏观", "macro", "产业链", "supply chain", "国际", "international",
        "十年", "decade", "百亿", "billion", "改革", "reform",
    ],
    "medium": [
        "分析", "analysis", "比较", "compare", "趋势", "trend", "市场",
        "market", "竞争", "competition", "技术", "technology", "评估",
        "evaluate", "风险", "risk", "方案", "plan", "优化", "optimize",
    ],
    "low": [
        "查询", "lookup", "定义", "define", "什么是", "what is", "列出",
        "list", "计算", "calculate", "总结", "summarize", "翻译", "translate",
    ],
}

# ============================================================
# Engine
# ============================================================

class CognitiveBudget:
    """Evaluates question complexity and allocates cognitive resources.
    
    Resource allocation:
    - Low complexity: 1 round, no debate, fast path (< 30s)
    - Medium complexity: 2-3 rounds, basic debate, moderate (60-120s)
    - High complexity: 3-5 rounds, full debate + counterfactual, deep (120-300s)
    """
    
    # Resource profiles
    PROFILES = {
        "intuition": {
            "max_rounds": 1,
            "enable_debate": False,
            "enable_counterfactual": False,
            "enable_evidence": False,
            "wood_seed_count": 4,
            "timeout_s": 30,
            "description": "Quick judgment with confidence",
        },
        "standard": {
            "max_rounds": 2,
            "enable_debate": False,
            "enable_counterfactual": True,
            "enable_evidence": True,
            "wood_seed_count": 6,
            "timeout_s": 120,
            "description": "Balanced analysis with evidence",
        },
        "deep": {
            "max_rounds": 4,
            "enable_debate": True,
            "enable_counterfactual": True,
            "enable_evidence": True,
            "wood_seed_count": 8,
            "timeout_s": 300,
            "description": "Full multi-path analysis with debate",
        },
    }
    
    def __init__(self):
        self.history = []
    
    def evaluate(self, question: str, context: str = "") -> dict:
        """Evaluate question complexity and recommend resource profile.
        
        Returns:
            {
                "complexity": "low" / "medium" / "high",
                "complexity_score": float (0-1),
                "profile": str ("intuition" / "standard" / "deep"),
                "resources": dict (from PROFILES),
                "dimensions": dict (breakdown of complexity factors),
            }
        """
        t0 = time.time()
        text = (question + " " + context).lower()
        
        # Score each dimension
        dimensions = {
            "keyword_complexity": self._keyword_score(text),
            "length_complexity": self._length_score(question),
            "question_depth": self._question_depth(question),
            "domain_breadth": self._domain_breadth(text),
            "uncertainty_markers": self._uncertainty_score(text),
        }
        
        # Weighted composite
        weights = {
            "keyword_complexity": 0.35,
            "length_complexity": 0.10,
            "question_depth": 0.25,
            "domain_breadth": 0.15,
            "uncertainty_markers": 0.15,
        }
        
        score = sum(dimensions[k] * weights[k] for k in dimensions)
        
        # Classify
        if score >= 0.6:
            complexity = "high"
            profile_name = "deep"
        elif score >= 0.3:
            complexity = "medium"
            profile_name = "standard"
        else:
            complexity = "low"
            profile_name = "intuition"
        
        result = {
            "complexity": complexity,
            "complexity_score": round(score, 3),
            "profile": profile_name,
            "resources": self.PROFILES[profile_name],
            "dimensions": {k: round(v, 3) for k, v in dimensions.items()},
            "elapsed_s": round(time.time() - t0, 4),
            "version": VERSION,
        }
        
        self.history.append(result)
        return result
    
    def _keyword_score(self, text: str) -> float:
        """Score based on complexity keywords present."""
        high_hits = sum(1 for kw in COMPLEXITY_KEYWORDS["high"] if kw in text)
        med_hits = sum(1 for kw in COMPLEXITY_KEYWORDS["medium"] if kw in text)
        low_hits = sum(1 for kw in COMPLEXITY_KEYWORDS["low"] if kw in text)
        
        total = high_hits + med_hits + low_hits
        if total == 0:
            return 0.4  # default medium-low
        
        weighted = (high_hits * 1.0 + med_hits * 0.5 + low_hits * 0.1) / total
        return min(1.0, weighted)
    
    def _length_score(self, question: str) -> float:
        """Longer questions tend to be more complex."""
        length = len(question)
        if length < 20:
            return 0.1
        elif length < 100:
            return 0.3
        elif length < 300:
            return 0.6
        else:
            return 0.9
    
    def _question_depth(self, question: str) -> float:
        """Detect depth indicators: why, how, implications, etc."""
        depth_markers = [
            ("为什么", 0.8), ("why", 0.8),
            ("如何", 0.6), ("how", 0.6),
            ("影响", 0.7), ("impact", 0.7), ("implications", 0.8),
            ("根本", 0.9), ("fundamental", 0.9),
            ("本质", 0.9), ("essence", 0.9),
            ("可能", 0.5), ("might", 0.5),
            ("应该", 0.6), ("should", 0.6),
        ]
        
        max_depth = 0
        for marker, score in depth_markers:
            if marker in question.lower():
                max_depth = max(max_depth, score)
        
        return max_depth
    
    def _domain_breadth(self, text: str) -> float:
        """How many different domains are involved."""
        domains = {
            "tech": ["技术", "technology", "AI", "算法", "software", "hardware"],
            "finance": ["金融", "finance", "投资", "fund", "股票", "stock"],
            "policy": ["政策", "policy", "政府", "government", "法规", "regulation"],
            "social": ["社会", "social", "人口", "population", "文化", "culture"],
            "science": ["科学", "science", "物理", "physics", "生物", "biology"],
            "business": ["商业", "business", "市场", "market", "客户", "customer"],
        }
        
        hit_domains = sum(1 for domain, keywords in domains.items()
                         if any(kw in text for kw in keywords))
        
        return min(1.0, hit_domains / 3)  # 3+ domains = max
    
    def _uncertainty_score(self, text: str) -> float:
        """Detect uncertainty markers."""
        markers = ["不确定", "uncertain", "可能", "perhaps", "maybe",
                    "风险", "risk", "预测", "predict", "forecast",
                    "假设", "assume", "估计", "estimate"]
        
        hits = sum(1 for m in markers if m in text)
        return min(1.0, hits / 3)


# ============================================================
# Self-test
# ============================================================

if __name__ == "__main__":
    engine = CognitiveBudget()
    
    # Low complexity
    r1 = engine.evaluate("什么是GDP?")
    assert r1["complexity"] == "low", f"Expected low, got {r1['complexity']}"
    print(f"  Low: '{r1['complexity']}' score={r1['complexity_score']:.3f} -> {r1['profile']}")
    
    # Medium complexity
    r2 = engine.evaluate("分析中国新能源汽车市场的竞争格局和技术趋势")
    assert r2["complexity"] in ("medium", "high"), f"Expected medium+, got {r2['complexity']}"
    print(f"  Medium: '{r2['complexity']}' score={r2['complexity_score']:.3f} -> {r2['profile']}")
    
    # High complexity
    r3 = engine.evaluate("为什么中国半导体产业链的国际竞争战略需要从根本上改革生态架构？分析政策、技术和宏观经济的融合影响")
    assert r3["complexity"] == "high", f"Expected high, got {r3['complexity']}"
    print(f"  High: '{r3['complexity']}' score={r3['complexity_score']:.3f} -> {r3['profile']}")
    
    print(f"[CognitiveBudget] Self-test PASSED (v{VERSION})")
