# -*- coding: utf-8 -*-
"""
debate_engine.py — 多视角辩论引擎 (MEU-07)
Based on flywheel design v0.6-v0.7: multi-agent debate

Four agents:
- Advocate (pro): builds strongest case FOR the conclusion
- Critic (con): builds strongest case AGAINST
- Skeptic: questions methodology and hidden assumptions
- Judge: synthesizes, scores, identifies what survived debate

v1.0.0 — 2026-05-03
"""
VERSION = "1.0.0"

import json, time
from typing import Dict, Optional, Callable

# ============================================================
# Prompts
# ============================================================

ADVOCATE_PROMPT = """You are an ADVOCATE. Build the strongest possible case FOR this conclusion.
Use evidence, reasoning, analogies, and precedent.

Conclusion: {conclusion}
Context: {context}

Respond in 200-400 words. Be specific and compelling."""

CRITIC_PROMPT = """You are a CRITIC. Build the strongest possible case AGAINST this conclusion.
Find flaws, counter-evidence, alternative explanations, and risks.

Conclusion: {conclusion}
Context: {context}
Advocate's argument: {advocate_arg}

Respond in 200-400 words. Be specific and devastating."""

SKEPTIC_PROMPT = """You are a SKEPTIC. You don't argue for or against — you question the METHODOLOGY.
What assumptions are hidden? What data is missing? What biases might be at play?

Conclusion: {conclusion}
Context: {context}
Advocate says: {advocate_arg}
Critic says: {critic_arg}

Respond in 200-300 words. Focus on what everyone is MISSING."""

JUDGE_PROMPT = """You are the JUDGE. After hearing all sides, synthesize a verdict.

Conclusion being debated: {conclusion}

Advocate (FOR): {advocate_arg}
Critic (AGAINST): {critic_arg}
Skeptic (METHODOLOGY): {skeptic_arg}

Score each dimension 1-10 and provide your verdict:

Return ONLY valid JSON:
{{
    "verdict": "supported" | "weakened" | "inconclusive" | "refuted",
    "confidence": 0.0-1.0,
    "scores": {{
        "evidence_quality": 1-10,
        "logical_coherence": 1-10,
        "assumption_safety": 1-10,
        "counter_resilience": 1-10
    }},
    "surviving_claims": ["claims that survived debate"],
    "killed_claims": ["claims that were refuted"],
    "key_uncertainty": "the single biggest unresolved question",
    "synthesis": "2-3 sentence final assessment"
}}"""


# ============================================================
# Engine
# ============================================================

class DebateEngine:
    """Orchestrates multi-agent debate on analytical conclusions.
    
    Flow: Advocate → Critic → Skeptic → Judge
    Each agent sees previous agents' arguments (information accumulates).
    """
    
    def __init__(self, llm_fn: Optional[Callable] = None, model: str = "deepseek"):
        self.llm_fn = llm_fn
        self.model = model
        self.debates = []
    
    def debate(self, conclusion: str, context: str = "",
               timeout_per_agent: int = 45) -> dict:
        """Run a full 4-agent debate on a conclusion.
        
        Args:
            conclusion: the claim to debate
            context: background information
            timeout_per_agent: LLM timeout per agent
        
        Returns:
            {
                "conclusion": str,
                "advocate": str,
                "critic": str, 
                "skeptic": str,
                "judge_verdict": dict,
                "debate_quality": float (0-1),
                "elapsed_s": float
            }
        """
        t0 = time.time()
        
        if not self.llm_fn:
            return self._empty_result(conclusion, time.time() - t0)
        
        # Round 1: Advocate
        advocate_arg = self._call_agent(
            ADVOCATE_PROMPT.format(conclusion=conclusion, context=context[:1500]),
            "Advocate", timeout_per_agent
        )
        
        # Round 2: Critic (sees Advocate)
        critic_arg = self._call_agent(
            CRITIC_PROMPT.format(conclusion=conclusion, context=context[:1500],
                                advocate_arg=advocate_arg[:800]),
            "Critic", timeout_per_agent
        )
        
        # Round 3: Skeptic (sees both)
        skeptic_arg = self._call_agent(
            SKEPTIC_PROMPT.format(conclusion=conclusion, context=context[:1000],
                                 advocate_arg=advocate_arg[:500],
                                 critic_arg=critic_arg[:500]),
            "Skeptic", timeout_per_agent
        )
        
        # Round 4: Judge (sees all)
        judge_raw = self._call_agent(
            JUDGE_PROMPT.format(conclusion=conclusion,
                               advocate_arg=advocate_arg[:600],
                               critic_arg=critic_arg[:600],
                               skeptic_arg=skeptic_arg[:400]),
            "Judge", timeout_per_agent
        )
        
        # Parse judge verdict
        judge_verdict = self._parse_json(judge_raw)
        if not judge_verdict:
            judge_verdict = {
                "verdict": "inconclusive",
                "confidence": 0.5,
                "scores": {"evidence_quality": 5, "logical_coherence": 5,
                          "assumption_safety": 5, "counter_resilience": 5},
                "surviving_claims": [],
                "killed_claims": [],
                "key_uncertainty": "Judge parse failed",
                "synthesis": judge_raw[:300] if judge_raw else "No response",
            }
        
        # Debate quality: based on argument lengths and judge scores
        debate_quality = self._score_debate_quality(
            advocate_arg, critic_arg, skeptic_arg, judge_verdict
        )
        
        elapsed = time.time() - t0
        result = {
            "conclusion": conclusion,
            "advocate": advocate_arg,
            "critic": critic_arg,
            "skeptic": skeptic_arg,
            "judge_verdict": judge_verdict,
            "debate_quality": round(debate_quality, 3),
            "elapsed_s": round(elapsed, 2),
            "version": VERSION,
        }
        
        self.debates.append(result)
        return result
    
    def _call_agent(self, prompt: str, agent_name: str, timeout: int) -> str:
        """Call LLM for one agent."""
        try:
            response = self.llm_fn(prompt, model=self.model, timeout=timeout, thinking_budget=0)
            if response:
                print(f"  [{agent_name}] {len(response)} chars")
                return response
            return f"[{agent_name}] No response"
        except Exception as e:
            print(f"  [{agent_name}] Failed: {e}")
            return f"[{agent_name}] Error: {e}"
    
    def _score_debate_quality(self, advocate, critic, skeptic, judge_verdict) -> float:
        """Score overall debate quality (0-1)."""
        # Length factor: all agents should produce substantive arguments
        min_len = min(len(advocate or ""), len(critic or ""), len(skeptic or ""))
        length_score = min(1.0, min_len / 200)  # At least 200 chars each
        
        # Judge scores factor
        scores = judge_verdict.get("scores", {})
        if scores:
            avg_score = sum(scores.values()) / len(scores) / 10  # Normalize to 0-1
        else:
            avg_score = 0.5
        
        # Diversity factor: advocate and critic should disagree
        # (simple proxy: low word overlap between them)
        adv_words = set((advocate or "").lower().split()[:50])
        crit_words = set((critic or "").lower().split()[:50])
        overlap = len(adv_words & crit_words) / max(1, len(adv_words | crit_words))
        diversity = 1 - overlap  # Higher diversity = better debate
        
        return 0.3 * length_score + 0.4 * avg_score + 0.3 * diversity
    
    def get_debate_history(self):
        """Return all debates run in this session."""
        return self.debates
    
    def _empty_result(self, conclusion, elapsed):
        return {
            "conclusion": conclusion,
            "advocate": "",
            "critic": "",
            "skeptic": "",
            "judge_verdict": {"verdict": "inconclusive", "confidence": 0, "scores": {}},
            "debate_quality": 0,
            "elapsed_s": round(elapsed, 2),
            "version": VERSION,
        }
    
    def _parse_json(self, text):
        if not text:
            return {}
        for start_char in ['{']:
            idx = text.find(start_char)
            if idx >= 0:
                candidate = text[idx:]
                depth = 0
                for i, ch in enumerate(candidate):
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
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
    engine = DebateEngine()
    r = engine.debate("AI will replace 50% of jobs by 2030")
    assert r["debate_quality"] == 0
    assert r["judge_verdict"]["verdict"] == "inconclusive"
    print(f"[DebateEngine] Self-test PASSED (v{VERSION})")
