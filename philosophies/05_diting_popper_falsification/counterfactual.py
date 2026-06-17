# -*- coding: utf-8 -*-
"""
counterfactual.py — 反事实分析引擎 (MEU-04)
Based on flywheel design v0.9: evidence extraction + counterfactual analysis

Core question: "If the opposite of this conclusion were true, what would the world look like?"
If the counterfactual world is easily imaginable and internally consistent,
the original conclusion is WEAK.

v1.0.0 — 2026-05-03
"""
VERSION = "1.0.0"

import json, time

# ============================================================
# Prompts
# ============================================================

COUNTERFACTUAL_PROMPT = """You are a counterfactual analyst. For each key conclusion in this analysis,
construct an internally consistent counter-scenario where the OPPOSITE is true.

Analysis:
{analysis}

For each conclusion (max 5):
1. original_claim: the conclusion as stated
2. counterfactual: a plausible scenario where the opposite holds
3. plausibility: 0.0-1.0 (how easily imaginable is the counter-scenario?)
4. key_assumption_exposed: what hidden assumption does the counterfactual reveal?
5. robustness_impact: "fatal" (conclusion collapses), "weakening" (needs caveats), "resilient" (survives)

Return ONLY valid JSON:
{{"counterfactuals": [{{"original_claim": "...", "counterfactual": "...", "plausibility": 0.6, "key_assumption_exposed": "...", "robustness_impact": "weakening"}}]}}
"""

# ============================================================
# Engine
# ============================================================

class CounterfactualEngine:
    """Generates and evaluates counterfactual scenarios for analysis conclusions."""
    
    def __init__(self, llm_fn=None):
        self.llm_fn = llm_fn
    
    def analyze(self, analysis: str, max_claims: int = 5) -> dict:
        """Run counterfactual analysis on an analysis text.
        
        Returns:
            {
                "counterfactuals": [...],
                "avg_plausibility": float,
                "fatal_count": int,
                "robustness_rating": str,  # "strong" / "moderate" / "fragile"
                "elapsed_s": float
            }
        """
        t0 = time.time()
        
        if not self.llm_fn or not analysis:
            return self._empty_result(time.time() - t0)
        
        prompt = COUNTERFACTUAL_PROMPT.format(analysis=analysis[:4000])
        
        try:
            raw = self.llm_fn(prompt, model="deepseek", timeout=60, thinking_budget=0)
            parsed = self._parse_json(raw)
            counterfactuals = parsed.get("counterfactuals", [])
        except Exception as e:
            print(f"[Counterfactual] LLM failed: {e}")
            return self._empty_result(time.time() - t0)
        
        # Validate and score
        valid = []
        for cf in counterfactuals[:max_claims]:
            if isinstance(cf, dict) and "original_claim" in cf:
                valid.append({
                    "original_claim": str(cf.get("original_claim", "")),
                    "counterfactual": str(cf.get("counterfactual", "")),
                    "plausibility": min(1.0, max(0.0, float(cf.get("plausibility", 0.5)))),
                    "key_assumption_exposed": str(cf.get("key_assumption_exposed", "")),
                    "robustness_impact": str(cf.get("robustness_impact", "weakening")),
                })
        
        # Aggregate
        avg_plaus = sum(c["plausibility"] for c in valid) / len(valid) if valid else 0
        fatal_count = sum(1 for c in valid if c["robustness_impact"] == "fatal")
        
        if fatal_count >= 2:
            rating = "fragile"
        elif avg_plaus > 0.7:
            rating = "fragile"
        elif avg_plaus > 0.4:
            rating = "moderate"
        else:
            rating = "strong"
        
        elapsed = time.time() - t0
        return {
            "counterfactuals": valid,
            "avg_plausibility": round(avg_plaus, 3),
            "fatal_count": fatal_count,
            "robustness_rating": rating,
            "claim_count": len(valid),
            "elapsed_s": round(elapsed, 2),
            "version": VERSION,
        }
    
    def _empty_result(self, elapsed):
        return {
            "counterfactuals": [],
            "avg_plausibility": 0,
            "fatal_count": 0,
            "robustness_rating": "unknown",
            "claim_count": 0,
            "elapsed_s": round(elapsed, 2),
            "version": VERSION,
        }
    
    def _parse_json(self, text):
        if not text:
            return {}
        # Try to find JSON in the response
        for start_char in ['{', '[']:
            idx = text.find(start_char)
            if idx >= 0:
                candidate = text[idx:]
                # Find matching end
                depth = 0
                for i, ch in enumerate(candidate):
                    if ch in '{[':
                        depth += 1
                    elif ch in '}]':
                        depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(candidate[:i+1])
                            except json.JSONDecodeError:
                                break
        return {}


# ============================================================
# Self-test
# ============================================================

if __name__ == "__main__":
    # Test without LLM
    engine = CounterfactualEngine()
    r = engine.analyze("Solar energy will dominate by 2030")
    assert r["robustness_rating"] == "unknown"
    assert r["claim_count"] == 0
    print(f"[Counterfactual] Self-test PASSED (v{VERSION})")
