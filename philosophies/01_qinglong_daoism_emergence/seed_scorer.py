# -*- coding: utf-8 -*-
"""
seed_scorer.py v1.0.0 — Wood Engine Seed Scoring Model
========================================================
Scores and ranks seeds before they enter the pipeline,
filtering low-quality seeds early.

Scoring dimensions:
  - Specificity (0-1): How specific vs vague
  - Novelty (0-1): How different from existing seeds
  - Actionability (0-1): Can it be analyzed?
  - Domain relevance (0-1): Fits the target domain?

Decision: Robin 2026-05-02
"""

import json, hashlib, re
from typing import List, Dict

VERSION = "1.0.0"

# Minimum score to pass into pipeline
MIN_SCORE = 0.3


def score_seed(seed: str, domain: str = "general",
               existing_seeds: List[str] = None) -> Dict:
    """Score a single seed on 4 dimensions."""
    specificity = _score_specificity(seed)
    novelty = _score_novelty(seed, existing_seeds or [])
    actionability = _score_actionability(seed)
    relevance = _score_relevance(seed, domain)
    
    composite = (specificity * 0.25 + novelty * 0.25 +
                 actionability * 0.30 + relevance * 0.20)
    
    return {
        "seed": seed[:100],
        "scores": {
            "specificity": round(specificity, 3),
            "novelty": round(novelty, 3),
            "actionability": round(actionability, 3),
            "relevance": round(relevance, 3),
        },
        "composite": round(composite, 3),
        "passes": composite >= MIN_SCORE,
    }


def score_batch(seeds: List[str], domain: str = "general") -> Dict:
    """Score and rank a batch of seeds."""
    results = []
    for i, seed in enumerate(seeds):
        existing = seeds[:i]  # Compare against earlier seeds
        result = score_seed(seed, domain, existing)
        results.append(result)
    
    results.sort(key=lambda x: -x["composite"])
    passed = [r for r in results if r["passes"]]
    
    return {
        "total": len(seeds),
        "passed": len(passed),
        "filtered": len(seeds) - len(passed),
        "ranked": results,
        "avg_score": round(sum(r["composite"] for r in results) / max(len(results), 1), 3),
    }


def _score_specificity(seed: str) -> float:
    """More specific = higher score."""
    words = seed.split()
    if len(words) < 3:
        return 0.2
    if len(words) > 20:
        return 0.6
    
    # Check for specific indicators
    score = 0.5
    if any(c.isdigit() for c in seed):
        score += 0.15
    if any(w in seed.lower() for w in ["specifically", "exactly", "particularly", "namely"]):
        score += 0.1
    if len(words) >= 8:
        score += 0.1
    if any(c in seed for c in ["%", "$", "=", ">"]):
        score += 0.1
    
    return min(score, 1.0)


def _score_novelty(seed: str, existing: List[str]) -> float:
    """More different from existing seeds = higher score."""
    if not existing:
        return 0.8
    
    seed_hash = set(seed.lower().split())
    max_overlap = 0
    for ex in existing:
        ex_hash = set(ex.lower().split())
        if not seed_hash or not ex_hash:
            continue
        overlap = len(seed_hash & ex_hash) / max(len(seed_hash | ex_hash), 1)
        max_overlap = max(max_overlap, overlap)
    
    return max(1.0 - max_overlap, 0.1)


def _score_actionability(seed: str) -> float:
    """Can this seed lead to concrete analysis?"""
    score = 0.5
    
    action_words = ["analyze", "compare", "evaluate", "assess", "measure",
                    "test", "verify", "explore", "investigate", "examine",
                    "how", "why", "what", "impact", "effect", "trend"]
    
    lower = seed.lower()
    matches = sum(1 for w in action_words if w in lower)
    score += min(matches * 0.1, 0.4)
    
    if len(seed) < 10:
        score -= 0.2
    
    return max(min(score, 1.0), 0.1)


def _score_relevance(seed: str, domain: str) -> float:
    """Does the seed match the target domain?"""
    domain_keywords = {
        "finance": ["market", "stock", "option", "fund", "price", "risk",
                    "return", "portfolio", "hedge", "trade", "bond"],
        "technology": ["algorithm", "data", "system", "network", "compute",
                      "software", "hardware", "chip", "AI", "model"],
        "materials": ["carbon", "silicon", "alloy", "fiber", "polymer",
                     "ceramic", "metal", "composite", "crystal", "nano"],
    }
    
    if domain == "general":
        return 0.7
    
    keywords = domain_keywords.get(domain, [])
    if not keywords:
        return 0.5
    
    lower = seed.lower()
    matches = sum(1 for kw in keywords if kw in lower)
    return min(0.3 + matches * 0.15, 1.0)


def self_test():
    print(f"seed_scorer.py v{VERSION}")
    
    # Single seed
    r = score_seed("Analyze the impact of SiC wafer pricing on EV battery costs", "materials")
    assert r["passes"] == True
    assert r["composite"] > 0.5
    print("  single: PASS")
    
    # Batch
    seeds = [
        "Analyze SiC market trends and pricing dynamics",
        "What is the competitive landscape for SiC suppliers?",
        "stuff",
        "How does SiC compare to GaN in power electronics?",
    ]
    batch = score_batch(seeds, "materials")
    assert batch["passed"] >= 2
    assert batch["filtered"] >= 1  # "stuff" should be filtered
    assert batch["ranked"][0]["composite"] >= batch["ranked"][-1]["composite"]
    print("  batch: PASS")
    
    # Novelty
    n = _score_novelty("completely unique topic", ["same old thing"])
    assert n > 0.5
    print("  novelty: PASS")
    
    print("  ALL PASS")
    return True


if __name__ == "__main__":
    self_test()
