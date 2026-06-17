# -*- coding: utf-8 -*-
"""
evidence_chain.py — 证据链追踪引擎 (MEU-05)
Based on flywheel design v0.9: evidence extraction + credibility scoring

Tracks: claim → evidence → source → credibility
Each claim has a provenance chain. Ungrounded claims get flagged.

v1.0.0 — 2026-05-03
"""
VERSION = "1.1.0"

import json, time, hashlib
from typing import List, Dict, Optional

# ============================================================
# Prompts
# ============================================================

EVIDENCE_EXTRACT_PROMPT = """You are an evidence analyst. Extract ALL factual claims from this analysis
and trace each to its evidence source.

Analysis:
{analysis}

For each claim (max 10):
1. claim: the factual assertion
2. evidence: what supports it (quote, data point, reference)
3. source_type: "data" (numbers/stats), "authority" (expert/org), "reasoning" (logical inference), "assumption" (no evidence), "hearsay" (unverified)
4. credibility: 0.0-1.0
5. verifiable: true/false (can this be independently checked?)

Return ONLY valid JSON:
{{"evidence_chain": [{{"claim": "...", "evidence": "...", "source_type": "data", "credibility": 0.8, "verifiable": true}}]}}
"""

# ============================================================
# Engine
# ============================================================

class EvidenceChain:
    """Extracts and scores evidence chains from analytical text."""
    
    # Credibility weights by source type
    SOURCE_WEIGHTS = {
        "data": 0.9,
        "authority": 0.7,
        "reasoning": 0.5,
        "assumption": 0.2,
        "hearsay": 0.1,
    }
    
    def __init__(self, llm_fn=None):
        self.llm_fn = llm_fn
        self.chains = []  # accumulated across calls
    
    def extract(self, analysis: str, search_context: str = "") -> dict:
        """Extract evidence chains from analysis text.
        
        Returns:
            {
                "evidence_chain": [...],
                "grounding_score": float (0-1, overall evidence quality),
                "ungrounded_claims": int,
                "verifiable_ratio": float,
                "source_distribution": dict,
                "weakest_links": [...],  # claims with lowest credibility
                "elapsed_s": float
            }
        """
        t0 = time.time()
        
        if not self.llm_fn or not analysis:
            return self._empty_result(time.time() - t0)
        
        # Include search context if available
        search_section = ""
        if search_context:
            search_section = f"\n\nKNOWN DATA SOURCES (use these to verify claims):\n{search_context[:2000]}"
        prompt = EVIDENCE_EXTRACT_PROMPT.format(analysis=analysis[:5000]) + search_section
        
        try:
            raw = self.llm_fn(prompt, model="deepseek", timeout=60, thinking_budget=0)
            parsed = self._parse_json(raw)
            chain = parsed.get("evidence_chain", [])
        except Exception as e:
            print(f"[EvidenceChain] LLM failed: {e}")
            return self._empty_result(time.time() - t0)
        
        # Validate
        valid = []
        for item in chain[:10]:
            if isinstance(item, dict) and "claim" in item:
                source_type = str(item.get("source_type", "assumption"))
                if source_type not in self.SOURCE_WEIGHTS:
                    source_type = "assumption"
                
                credibility = min(1.0, max(0.0, float(item.get("credibility", 0.5))))
                # Adjust credibility by source weight
                adjusted_cred = credibility * self.SOURCE_WEIGHTS.get(source_type, 0.3)
                
                entry = {
                    "claim": str(item.get("claim", "")),
                    "evidence": str(item.get("evidence", "")),
                    "source_type": source_type,
                    "raw_credibility": credibility,
                    "adjusted_credibility": round(adjusted_cred, 3),
                    "verifiable": bool(item.get("verifiable", False)),
                    "claim_hash": hashlib.md5(str(item.get("claim", "")).encode()).hexdigest()[:8],
                }
                valid.append(entry)
        
        # Aggregate
        self.chains.extend(valid)
        
        avg_cred = sum(e["adjusted_credibility"] for e in valid) / len(valid) if valid else 0
        ungrounded = sum(1 for e in valid if e["source_type"] in ("assumption", "hearsay"))
        verifiable_count = sum(1 for e in valid if e["verifiable"])
        
        # Source distribution
        source_dist = {}
        for e in valid:
            st = e["source_type"]
            source_dist[st] = source_dist.get(st, 0) + 1
        
        # Weakest links (bottom 3 by credibility)
        weakest = sorted(valid, key=lambda x: x["adjusted_credibility"])[:3]
        
        # Grounding score: penalize ungrounded and unverifiable
        grounding = avg_cred * (1 - 0.1 * ungrounded) * (0.5 + 0.5 * (verifiable_count / max(1, len(valid))))
        
        elapsed = time.time() - t0
        return {
            "evidence_chain": valid,
            "grounding_score": round(max(0, grounding), 3),
            "ungrounded_claims": ungrounded,
            "verifiable_ratio": round(verifiable_count / max(1, len(valid)), 3),
            "source_distribution": source_dist,
            "weakest_links": [{"claim": w["claim"], "credibility": w["adjusted_credibility"], "source": w["source_type"]} for w in weakest],
            "claim_count": len(valid),
            "elapsed_s": round(elapsed, 2),
            "version": VERSION,
        }
    
    def get_accumulated(self) -> List[Dict]:
        """Return all evidence chains accumulated across multiple calls."""
        return self.chains
    
    def find_contradictions(self) -> List[Dict]:
        """Find claims that may contradict each other (simple keyword overlap check)."""
        contradictions = []
        for i, a in enumerate(self.chains):
            for j, b in enumerate(self.chains):
                if i >= j:
                    continue
                # Simple heuristic: same topic but very different credibility
                a_words = set(a["claim"].lower().split())
                b_words = set(b["claim"].lower().split())
                overlap = len(a_words & b_words) / max(1, len(a_words | b_words))
                if overlap > 0.3 and abs(a["adjusted_credibility"] - b["adjusted_credibility"]) > 0.3:
                    contradictions.append({
                        "claim_a": a["claim"],
                        "claim_b": b["claim"],
                        "cred_diff": round(abs(a["adjusted_credibility"] - b["adjusted_credibility"]), 3),
                        "word_overlap": round(overlap, 3),
                    })
        return contradictions
    
    def _empty_result(self, elapsed):
        return {
            "evidence_chain": [],
            "grounding_score": 0,
            "ungrounded_claims": 0,
            "verifiable_ratio": 0,
            "source_distribution": {},
            "weakest_links": [],
            "claim_count": 0,
            "elapsed_s": round(elapsed, 2),
            "version": VERSION,
        }
    
    def _parse_json(self, text):
        if not text:
            return {}
        for start_char in ['{', '[']:
            idx = text.find(start_char)
            if idx >= 0:
                candidate = text[idx:]
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
    engine = EvidenceChain()
    r = engine.extract("GDP grew 5% according to NBS data")
    assert r["grounding_score"] == 0
    assert r["claim_count"] == 0
    print(f"[EvidenceChain] Self-test PASSED (v{VERSION})")
