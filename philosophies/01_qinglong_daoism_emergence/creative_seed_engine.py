# -*- coding: utf-8 -*-
"""
creative_seed_engine.py - 青龙创意发散引擎 v2.0 (Seed-03)
v1.0.0 | 2026-05-03

Generates diverse, high-quality seed angles for the Wood phase.
Uses multiple creativity techniques:
1. SCAMPER (Substitute, Combine, Adapt, Modify, Put-to-use, Eliminate, Reverse)
2. Six Thinking Hats (White/Red/Black/Yellow/Green/Blue)
3. First Principles decomposition
4. Analogy bridging (cross-domain pattern matching)
5. Contrarian inversion
"""
import json, random, hashlib
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Creativity technique templates
SCAMPER_PROMPTS = {
    "substitute": "What if we replaced a key component with something entirely different?",
    "combine": "What if we merged this with an unrelated domain?",
    "adapt": "What existing solution from another field could be adapted here?",
    "modify": "What if we magnified or minimized a key aspect by 10x?",
    "put_to_use": "What if this capability was applied to a completely different problem?",
    "eliminate": "What if we removed the most obvious constraint?",
    "reverse": "What if we approached this from the exact opposite direction?"
}

SIX_HATS = {
    "white": {"role": "Data Analyst", "focus": "What facts and data do we have? What's missing?"},
    "red": {"role": "Intuition", "focus": "What's your gut feeling? What emotions does this trigger?"},
    "black": {"role": "Devil's Advocate", "focus": "What could go wrong? What are the risks?"},
    "yellow": {"role": "Optimist", "focus": "What's the best possible outcome? What value is hidden?"},
    "green": {"role": "Creative", "focus": "What's a wild, unconventional approach?"},
    "blue": {"role": "Strategist", "focus": "What's the meta-pattern? How do we organize our thinking?"}
}


class CreativeSeedEngine:
    """Generate diverse seed angles for Wuxing Wood phase."""
    
    def __init__(self, llm_fn=None):
        self.llm_fn = llm_fn
        self.seed_history: List[Dict] = []
        self.diversity_threshold = 0.3  # Min cosine distance between seeds
        
    def generate_seeds(self, topic: str, count: int = 8, 
                       techniques: List[str] = None,
                       context: dict = None) -> List[Dict]:
        """
        Generate diverse seed angles for a topic.
        
        Args:
            topic: The analysis topic
            count: Number of seeds to generate
            techniques: Which techniques to use (default: all)
            context: Additional context (prior results, constraints)
        
        Returns:
            List of seed dicts with angle, technique, rationale
        """
        techniques = techniques or ["scamper", "six_hats", "first_principles", 
                                     "analogy", "contrarian"]
        
        all_seeds = []
        
        for technique in techniques:
            if technique == "scamper":
                all_seeds.extend(self._scamper_seeds(topic, context))
            elif technique == "six_hats":
                all_seeds.extend(self._six_hats_seeds(topic, context))
            elif technique == "first_principles":
                all_seeds.extend(self._first_principles_seeds(topic, context))
            elif technique == "analogy":
                all_seeds.extend(self._analogy_seeds(topic, context))
            elif technique == "contrarian":
                all_seeds.extend(self._contrarian_seeds(topic, context))
        
        # Deduplicate and score
        scored = self._score_and_rank(all_seeds, topic)
        
        # Select top-N with diversity
        selected = self._diverse_select(scored, count)
        
        # Record
        self.seed_history.append({
            "timestamp": datetime.now().isoformat(),
            "topic": topic[:100],
            "generated": len(all_seeds),
            "selected": len(selected),
            "techniques": techniques
        })
        
        return selected
    
    def _scamper_seeds(self, topic: str, context: dict = None) -> List[Dict]:
        seeds = []
        for key, prompt in SCAMPER_PROMPTS.items():
            seeds.append({
                "angle": "{}: {}".format(key.upper(), prompt),
                "technique": "scamper",
                "sub_technique": key,
                "topic_application": "Apply {} to: {}".format(key, topic[:80]),
                "novelty_score": 0.6 + random.random() * 0.3
            })
        return seeds
    
    def _six_hats_seeds(self, topic: str, context: dict = None) -> List[Dict]:
        seeds = []
        for color, hat in SIX_HATS.items():
            seeds.append({
                "angle": "{} Hat ({}): {}".format(color.capitalize(), hat["role"], hat["focus"]),
                "technique": "six_hats",
                "sub_technique": color,
                "topic_application": "Analyze '{}' as {}".format(topic[:60], hat["role"]),
                "novelty_score": 0.5 + random.random() * 0.3
            })
        return seeds
    
    def _first_principles_seeds(self, topic: str, context: dict = None) -> List[Dict]:
        principles = [
            "What are the fundamental truths/axioms here?",
            "Strip away all assumptions — what remains?",
            "What would a solution look like if built from scratch?",
            "What constraints are real vs self-imposed?",
            "What's the atomic unit of value in this domain?"
        ]
        seeds = []
        for p in principles:
            seeds.append({
                "angle": "First Principles: {}".format(p),
                "technique": "first_principles",
                "topic_application": "Decompose '{}': {}".format(topic[:50], p),
                "novelty_score": 0.7 + random.random() * 0.2
            })
        return seeds
    
    def _analogy_seeds(self, topic: str, context: dict = None) -> List[Dict]:
        domains = [
            ("Biology", "How does nature solve a similar problem?"),
            ("Military", "What strategic parallel exists in warfare?"),
            ("Sports", "What coaching/training insight applies?"),
            ("Architecture", "How would you design this as a building?"),
            ("Music", "What's the rhythm, harmony, or dissonance here?"),
            ("Cooking", "What ingredients, recipe, or timing insights apply?"),
        ]
        seeds = []
        for domain, question in domains:
            seeds.append({
                "angle": "Analogy from {}: {}".format(domain, question),
                "technique": "analogy",
                "sub_technique": domain.lower(),
                "topic_application": "Map '{}' to {} domain".format(topic[:50], domain),
                "novelty_score": 0.65 + random.random() * 0.3
            })
        return seeds
    
    def _contrarian_seeds(self, topic: str, context: dict = None) -> List[Dict]:
        inversions = [
            "What if the opposite of the consensus is true?",
            "What if the biggest risk is actually the biggest opportunity?",
            "What if we optimized for the minority case instead of majority?",
            "What would a competitor do that we'd never consider?",
            "What if we deliberately failed at this — what would we learn?",
        ]
        seeds = []
        for inv in inversions:
            seeds.append({
                "angle": "Contrarian: {}".format(inv),
                "technique": "contrarian",
                "topic_application": "Invert assumptions about '{}'".format(topic[:60]),
                "novelty_score": 0.75 + random.random() * 0.2
            })
        return seeds
    
    def _score_and_rank(self, seeds: List[Dict], topic: str) -> List[Dict]:
        """Score seeds by relevance and novelty."""
        for seed in seeds:
            # Simple heuristic scoring
            novelty = seed.get("novelty_score", 0.5)
            
            # Relevance: check keyword overlap with topic
            topic_words = set(topic.lower().split())
            angle_words = set(seed.get("angle", "").lower().split())
            overlap = len(topic_words & angle_words) / max(len(topic_words), 1)
            relevance = min(1.0, overlap * 3 + 0.3)  # Boost base relevance
            
            # Combined score
            seed["relevance_score"] = round(relevance, 3)
            seed["combined_score"] = round(novelty * 0.6 + relevance * 0.4, 3)
        
        return sorted(seeds, key=lambda x: x["combined_score"], reverse=True)
    
    def _diverse_select(self, ranked_seeds: List[Dict], count: int) -> List[Dict]:
        """Select top seeds ensuring technique diversity."""
        selected = []
        techniques_used = set()
        
        # First pass: one from each technique
        for seed in ranked_seeds:
            if len(selected) >= count:
                break
            tech = seed.get("technique", "unknown")
            if tech not in techniques_used:
                selected.append(seed)
                techniques_used.add(tech)
        
        # Second pass: fill remaining with best scores
        for seed in ranked_seeds:
            if len(selected) >= count:
                break
            if seed not in selected:
                selected.append(seed)
        
        return selected
    
    def get_stats(self) -> Dict:
        """Get engine usage statistics."""
        return {
            "total_runs": len(self.seed_history),
            "total_generated": sum(h["generated"] for h in self.seed_history),
            "total_selected": sum(h["selected"] for h in self.seed_history),
            "avg_generation_per_run": (
                sum(h["generated"] for h in self.seed_history) / max(len(self.seed_history), 1)
            ),
            "techniques_used": list(set(
                t for h in self.seed_history for t in h.get("techniques", [])
            ))
        }


# Self-test
if __name__ == "__main__":
    print("=== creative_seed_engine.py self-test ===")
    engine = CreativeSeedEngine()
    
    # Test basic generation
    seeds = engine.generate_seeds("AI-powered urban infrastructure optimization", count=8)
    assert len(seeds) == 8
    print("  generation: PASS ({} seeds)".format(len(seeds)))
    
    # Test technique diversity
    techniques = set(s["technique"] for s in seeds)
    assert len(techniques) >= 3
    print("  diversity: PASS ({} techniques: {})".format(len(techniques), techniques))
    
    # Test scoring
    assert all("combined_score" in s for s in seeds)
    assert all(0 <= s["combined_score"] <= 1 for s in seeds)
    print("  scoring: PASS")
    
    # Test with Chinese topic
    seeds_cn = engine.generate_seeds("武汉车谷智能网联汽车产业链分析", count=6)
    assert len(seeds_cn) == 6
    print("  chinese_topic: PASS")
    
    # Test stats
    stats = engine.get_stats()
    assert stats["total_runs"] == 2
    assert stats["total_generated"] > 0
    print("  stats: PASS ({} total generated)".format(stats["total_generated"]))
    
    # Test custom techniques
    seeds_fp = engine.generate_seeds("test", count=3, techniques=["first_principles", "contrarian"])
    techs = set(s["technique"] for s in seeds_fp)
    assert techs <= {"first_principles", "contrarian"}
    print("  custom_techniques: PASS")
    
    print("ALL PASS")
