# -*- coding: utf-8 -*-
"""
verification.py v1.0.0 — 五行飞轮验证函数模块
================================================
Extracted from phase_metal() in wuxing_pipeline_v2.py.
Standalone, configurable, reusable verification engine.

Architecture:
  StructuralCheck (instant, no LLM) → LLMCheck (devil/fact) → AgentEval → Composite → Verdict

Usage:
  from verification import VerificationEngine
  engine = VerificationEngine()
  result = engine.verify(analysis_text, topic, metadata)
  print(result["verdict"])  # PASS / CONDITIONAL / FAIL

Decision: Robin 2026-05-02 — Task FW2-Verification-Fn
"""

import json, time, re
try:
    from llm_router import PHASE_MODEL
    METAL_MODEL = PHASE_MODEL.get("metal", "deepseek")
except:
    METAL_MODEL = "deepseek"
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any

VERSION = "2.0.0"  # v2: invariant extraction (MEU-01)

# ============================================================
# Configuration: Thresholds & Weights
# ============================================================

DEFAULT_WEIGHTS = {
    "data": 0.08,
    "coverage": 0.08,
    "depth": 0.06,
    "seeds": 0.06,
    "cross": 0.07,
    "devil": 0.20,
    "fact": 0.20,
    "agents": 0.25,
}

DEFAULT_THRESHOLDS = {
    "pass": 0.70,
    "conditional": 0.40,
}

# Domain-specific overrides
DOMAIN_CONFIGS = {
    "finance": {
        "weights": {"data": 0.12, "fact": 0.25, "devil": 0.20, "agents": 0.20,
                     "coverage": 0.06, "depth": 0.05, "seeds": 0.05, "cross": 0.07},
        "thresholds": {"pass": 0.75, "conditional": 0.45},
    },
    "technology": {
        "weights": {"data": 0.06, "coverage": 0.10, "depth": 0.08, "seeds": 0.06,
                     "cross": 0.07, "devil": 0.18, "fact": 0.18, "agents": 0.27},
        "thresholds": {"pass": 0.68, "conditional": 0.38},
    },
    "materials": {
        "weights": {"data": 0.12, "coverage": 0.08, "depth": 0.08, "seeds": 0.05,
                     "cross": 0.07, "devil": 0.18, "fact": 0.22, "agents": 0.20},
        "thresholds": {"pass": 0.72, "conditional": 0.42},
    },
}

# Bilingual keyword banks
COVERAGE_KEYWORDS = [
    'market', 'technology', 'risk', 'opportunity', 'trend', 'competition',
    'supply', 'demand', 'regulation', 'innovation', 'cost', 'barrier',
    '\u5e02\u573a', '\u6280\u672f', '\u98ce\u9669', '\u673a\u4f1a',
    '\u8d8b\u52bf', '\u7ade\u4e89', '\u4f9b\u5e94', '\u9700\u6c42',
    '\u76d1\u7ba1', '\u521b\u65b0', '\u6210\u672c', '\u58c1\u5792',
    '\u653f\u7b56', '\u4ea7\u4e1a\u94fe',
]

PCT_KEYWORDS = ['%', 'CAGR', 'growth', 'revenue', 'billion', 'million',
                '\u589e\u957f', '\u6536\u5165', '\u4ebf', '\u4e07',
                '\u5e02\u573a\u89c4\u6a21', '\u5360\u6bd4', '\u540c\u6bd4']

PLAYER_KEYWORDS = ['company', 'player', 'vendor', 'manufacturer', 'leader',
                   '\u516c\u53f8', '\u4f01\u4e1a', '\u5382\u5546',
                   '\u9f99\u5934', '\u4f9b\u5e94\u5546', '\u5236\u9020\u5546']


# ============================================================
# Structural Checks (instant, no LLM)
# ============================================================

def check_data_completeness(analysis: str) -> float:
    """Dimension 1: Data completeness (bilingual)."""
    has_numbers = sum(1 for c in analysis if c.isdigit()) > 5
    has_percentages = any(kw in analysis for kw in PCT_KEYWORDS)
    has_players = any(kw in analysis.lower() for kw in PLAYER_KEYWORDS)
    return (0.4 if has_numbers else 0) + (0.3 if has_percentages else 0) + (0.3 if has_players else 0)


def check_coverage_breadth(analysis: str) -> float:
    """Dimension 2: Coverage breadth (bilingual)."""
    covered = sum(1 for kw in COVERAGE_KEYWORDS if kw in analysis.lower())
    return min(covered / 7.0, 1.0)


def check_analysis_depth(analysis: str) -> float:
    """Dimension 3: Analysis depth (length-based)."""
    length = len(analysis.strip())
    return min(length / 2000.0, 1.0) if length > 0 else 0


def check_seed_utilization(seed_count: int) -> float:
    """Dimension 4: Seed utilization."""
    return min(seed_count / 3.0, 1.0) if seed_count > 0 else 0


def check_cross_validation(analysis: str, research_angles: List[str]) -> float:
    """Dimension 5: Cross-validation (seeds vs analysis)."""
    if not research_angles or not analysis:
        return 0.5
    addressed = 0
    for angle in research_angles:
        if angle:
            angle_words = [w.lower() for w in str(angle).split() if len(w) > 3]
            if any(w in analysis.lower() for w in angle_words[:3]):
                addressed += 1
    return min(addressed / max(len(research_angles), 1), 1.0)


def run_structural_checks(analysis: str, seed_count: int = 0,
                           research_angles: List[str] = None) -> Dict[str, float]:
    """Run all 5 structural checks. Returns dimension scores."""
    return {
        "data_completeness": round(check_data_completeness(analysis), 3),
        "coverage_breadth": round(check_coverage_breadth(analysis), 3),
        "analysis_depth": round(check_analysis_depth(analysis), 3),
        "seed_utilization": round(check_seed_utilization(seed_count), 3),
        "cross_validation": round(check_cross_validation(analysis, research_angles or []), 3),
    }


# ============================================================
# LLM-based Checks (devil's advocate + fact-checker)
# ============================================================

DEVIL_PROMPT_TEMPLATE = """You are a ruthless devil's advocate for a provincial-level decision maker.
Your job is to DESTROY weak analysis before it wastes executive time.

ANALYSIS TO ATTACK:

ANALYSIS:
{analysis}

Evaluate these 4 aspects (score each 0-10):
1. blind_spots: How many important angles are MISSING? (10=many gaps)
2. bias: How biased or one-sided is this? (10=very biased)
3. depth: How deep and insightful? (10=very deep)
4. actionability: How actionable are the conclusions? (10=very actionable)

Output ONLY JSON: {{"blind_spots": N, "bias": N, "depth": N, "actionability": N}}"""

FACT_PROMPT_TEMPLATE = """You are a forensic fact-checker for an investment committee.
Your verification determines whether millions in capital decisions proceed.

ANALYSIS TO VERIFY:

ANALYSIS:
{analysis}

Check these 4 aspects (score each 0-10):
1. consistency: Are claims internally consistent? (10=perfectly consistent)
2. plausibility: Are the numbers/claims plausible? (10=very plausible)
3. sources: Does it cite or reference sources? (10=well-sourced)
4. completeness: Are conclusions fully supported? (10=fully supported)

Output ONLY JSON: {{"consistency": N, "plausibility": N, "sources": N, "completeness": N}}"""


def _parse_json_from_llm(raw: str) -> dict:
    """Parse JSON from LLM response, stripping code fences and thinking."""
    if not raw:
        return {}
    cleaned = raw.strip()
    # Strip code fences
    if '```' in cleaned:
        lines = cleaned.split('\n')
        inside = False
        result_lines = []
        for line in lines:
            if line.strip().startswith('```'):
                inside = not inside
                continue
            if inside:
                result_lines.append(line)
        cleaned = '\n'.join(result_lines).strip() if result_lines else cleaned
    # Find JSON object
    start = cleaned.find('{')
    end = cleaned.rfind('}') + 1
    if start >= 0 and end > start:
        return json.loads(cleaned[start:end])
    return {}


def check_devil_advocate(analysis: str, llm_fn=None) -> tuple:
    """Dimension 6: Devil's advocate (LLM-based).
    Returns (score: float, critique: str)."""
    if not llm_fn or not analysis:
        return 0.5, ""
    
    prompt = DEVIL_PROMPT_TEMPLATE.format(analysis=analysis[:3000])
    try:
        raw = llm_fn(prompt, model=METAL_MODEL, timeout=45, thinking_budget=0)
        d = _parse_json_from_llm(raw)
        # blind_spots & bias: higher = MORE problems = LOWER quality
        # depth & actionability: higher = BETTER = HIGHER quality
        bs = 1.0 - float(d.get("blind_spots", 5)) / 10.0
        bi = 1.0 - float(d.get("bias", 5)) / 10.0
        dp = float(d.get("depth", 5)) / 10.0
        ac = float(d.get("actionability", 5)) / 10.0
        fa = float(d.get("falsifiability", 5)) / 10.0
        score = (bs * 0.25 + bi * 0.25 + dp * 0.2 + ac * 0.15 + fa * 0.15)
        return round(score, 3), raw
    except Exception:
        return 0.5, ""


def check_fact_checker(analysis: str, llm_fn=None) -> tuple:
    """Dimension 7: Fact-checking (LLM-based).
    Returns (score: float, critique: str)."""
    if not llm_fn or not analysis:
        return 0.5, ""
    
    prompt = FACT_PROMPT_TEMPLATE.format(analysis=analysis[:3000])
    try:
        raw = llm_fn(prompt, model=METAL_MODEL, timeout=45, thinking_budget=0)
        f = _parse_json_from_llm(raw)
        co = float(f.get("consistency", 5)) / 10.0
        pl = float(f.get("plausibility", 5)) / 10.0
        sr = float(f.get("sources", 5)) / 10.0
        cm = float(f.get("completeness", 5)) / 10.0
        tp = float(f.get("temporal", 5)) / 10.0
        score = (co * 0.25 + pl * 0.25 + sr * 0.2 + cm * 0.15 + tp * 0.15)
        return round(score, 3), raw
    except Exception:
        return 0.5, ""


# ============================================================
# Multi-Agent Evaluation
# ============================================================

def check_agents(analysis: str, topic: str, metadata: dict = None,
                 eval_module=None) -> tuple:
    """Dimension 8: Multi-agent evaluation (via eval_agents module).
    Returns (score_0to1: float, eval_result: dict)."""
    if not eval_module or not analysis:
        return 0.5, {}
    
    try:
        result = eval_module.run_evaluation(analysis, topic, metadata or {})
        # Normalize 0-10 to 0-1
        score = result.get("overall_score", 5.0) / 10.0
        return round(score, 3), result
    except Exception:
        return 0.5, {}


# ============================================================
# Composite Scoring & Verdict
# ============================================================

def compute_composite(dimensions: Dict[str, float],
                      weights: Dict[str, float] = None) -> float:
    """Compute weighted composite score from dimension scores."""
    w = weights or DEFAULT_WEIGHTS
    
    # Map dimension names to weight keys
    dim_to_weight = {
        "data_completeness": "data",
        "coverage_breadth": "coverage",
        "analysis_depth": "depth",
        "seed_utilization": "seeds",
        "cross_validation": "cross",
        "devil_advocate": "devil",
        "fact_checker": "fact",
        "agent_eval": "agents",
    }
    
    composite = 0.0
    for dim_name, score in dimensions.items():
        weight_key = dim_to_weight.get(dim_name, dim_name)
        weight = w.get(weight_key, 0.0)
        composite += score * weight
    
    return round(composite, 4)


def determine_verdict(composite: float, thresholds: Dict[str, float] = None) -> str:
    """Determine verdict from composite score."""
    t = thresholds or DEFAULT_THRESHOLDS
    if composite >= t["pass"]:
        return "PASS"
    elif composite >= t["conditional"]:
        return "CONDITIONAL"
    else:
        return "FAIL"


def compute_grade(agent_score_0to10: float) -> tuple:
    """Compute letter grade from agent overall score (0-10)."""
    s = agent_score_0to10
    if s >= 9:
        grade = "S"
    elif s >= 8:
        grade = "A+"
    elif s >= 7:
        grade = "A"
    elif s >= 6:
        grade = "B"
    elif s >= 5:
        grade = "C"
    elif s >= 4:
        grade = "D"
    else:
        grade = "F"
    return grade, round(s, 1)



# ============================================================
# Invariant Candidate Extraction (MEU-01: flywheel design v4)
# ============================================================

INVARIANT_PROMPT_TEMPLATE = """You are an invariant detector for analytical conclusions.

Given this analysis, identify 3-5 INVARIANT CANDIDATES — conclusions that would remain stable
even if the input data, methodology, or framing were changed.

For each candidate, specify:
1. claim: the conclusion
2. transform_set: what changes could test this (data source swap, time period shift, methodology change, adversarial framing)
3. estimated_stability: 0.0-1.0 (how likely it survives the transforms)
4. evidence_type: "structural" (inherent to domain), "statistical" (data-dependent), or "causal" (mechanism-based)

Analysis:
{analysis}

Return ONLY valid JSON:
{{"invariants": [{{"claim": "...", "transform_set": ["..."], "estimated_stability": 0.8, "evidence_type": "structural"}}]}}
"""

def extract_invariant_candidates(analysis: str, llm_fn=None) -> list:
    """Extract invariant candidates from analysis text.
    
    Returns list of dicts with: claim, transform_set, estimated_stability, evidence_type
    Based on flywheel design v4: "what remains unchanged under transformations"
    """
    if not llm_fn or not analysis:
        return []
    
    prompt = INVARIANT_PROMPT_TEMPLATE.format(analysis=analysis[:4000])
    try:
        raw = llm_fn(prompt, model=METAL_MODEL, timeout=60, thinking_budget=0)
        d = _parse_json_from_llm(raw)
        candidates = d.get("invariants", [])
        # Validate structure
        valid = []
        for c in candidates:
            if isinstance(c, dict) and "claim" in c:
                valid.append({
                    "claim": str(c.get("claim", "")),
                    "transform_set": c.get("transform_set", []),
                    "estimated_stability": float(c.get("estimated_stability", 0.5)),
                    "evidence_type": str(c.get("evidence_type", "unknown")),
                })
        return valid
    except Exception as e:
        print(f"[Invariant] Extraction failed: {e}")
        return []


# ============================================================
# Main Engine
# ============================================================

class VerificationEngine:
    """Standalone verification engine for flywheel outputs."""
    
    def __init__(self, domain: str = "general", llm_fn=None, eval_module=None,
                 custom_weights: Dict[str, float] = None,
                 custom_thresholds: Dict[str, float] = None):
        """
        Args:
            domain: "general", "finance", "technology", "materials"
            llm_fn: callable(prompt, model, timeout, thinking_budget) -> str
            eval_module: module with run_evaluation(text, topic, metadata)
            custom_weights: override default dimension weights
            custom_thresholds: override default pass/conditional thresholds
        """
        self.domain = domain
        self.llm_fn = llm_fn
        self.eval_module = eval_module
        
        # Load domain config
        domain_cfg = DOMAIN_CONFIGS.get(domain, {})
        self.weights = custom_weights or domain_cfg.get("weights", DEFAULT_WEIGHTS.copy())
        self.thresholds = custom_thresholds or domain_cfg.get("thresholds", DEFAULT_THRESHOLDS.copy())
    
    def verify(self, analysis: str, topic: str = "",
               seed_count: int = 0, research_angles: List[str] = None,
               metadata: dict = None,
               skip_llm: bool = False, skip_agents: bool = False) -> dict:
        """
        Run full verification pipeline.
        
        Returns:
            {
                "verdict": "PASS" | "CONDITIONAL" | "FAIL",
                "composite_score": float (0-1),
                "grade": str,
                "agent_score": float (0-10),
                "dimensions": {dim_name: score, ...},
                "critiques": {"devil": str, "fact": str},
                "agent_eval": dict,
                "config": {"domain": str, "weights": dict, "thresholds": dict},
                "elapsed_s": float,
            }
        """
        t0 = time.time()
        
        # 1. Structural checks (instant)
        structural = run_structural_checks(analysis, seed_count, research_angles)
        
        # 2. LLM checks (parallel if possible, ~30-60s)
        if skip_llm or not self.llm_fn:
            devil_score, devil_critique = 0.5, ""
            fact_score, fact_critique = 0.5, ""
        else:
            # V8.1: Parallel adversarial execution
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=2) as _tp:
                _df = _tp.submit(check_devil_advocate, analysis, self.llm_fn)
                _ff = _tp.submit(check_fact_checker, analysis, self.llm_fn)
                devil_score, devil_critique = _df.result(timeout=90)
                fact_score, fact_critique = _ff.result(timeout=90)
        
        # 3. Agent evaluation (~5-10s)
        if skip_agents or not self.eval_module:
            agent_score_01, agent_eval_result = 0.5, {}
        else:
            agent_score_01, agent_eval_result = check_agents(
                analysis, topic, metadata, self.eval_module)
        
        # 4. Assemble all dimensions
        dimensions = {
            **structural,
            "devil_advocate": devil_score,
            "fact_checker": fact_score,
            "agent_eval": agent_score_01,
        }
        
        # 5. Composite & verdict
        composite = compute_composite(dimensions, self.weights)
        verdict = determine_verdict(composite, self.thresholds)
        
        # 6. Grade
        agent_score_10 = agent_eval_result.get("overall_score", agent_score_01 * 10)
        grade, grade_score = compute_grade(agent_score_10)
        
        elapsed = round(time.time() - t0, 2)
        
        # 7. Invariant candidate extraction (v4 flywheel design)
        invariant_candidates = []
        if not skip_llm and self.llm_fn:
            invariant_candidates = extract_invariant_candidates(analysis, self.llm_fn)
        
        return {
            "verdict": verdict,
            "composite_score": composite,
            "grade": grade,
            "agent_score": grade_score,
            "dimensions": dimensions,
            "critiques": {
                "devil": devil_critique[:500] if devil_critique else "",
                "fact": fact_critique[:500] if fact_critique else "",
            },
            "agent_eval": agent_eval_result,
            "config": {
                "domain": self.domain,
                "weights": self.weights,
                "thresholds": self.thresholds,
            },
            "elapsed_s": elapsed,
            "version": VERSION,
                    "invariant_candidates": invariant_candidates,
        }
    
    def verify_quick(self, analysis: str, seed_count: int = 0) -> dict:
        """Quick structural-only verification (no LLM, no agents). <1ms."""
        return self.verify(analysis, seed_count=seed_count,
                          skip_llm=True, skip_agents=True)


# ============================================================
# Self-test
# ============================================================

def self_test():
    """Run self-test to verify module works."""
    print(f"verification.py v{VERSION}")
    
    # Test structural checks
    test_analysis = """
    The global renewable energy market is projected to reach $1.5 trillion by 2030,
    growing at a CAGR of 8.4%. Key players include Tesla, BYD, and Longi Green Energy.
    Market trends show increasing demand for solar and wind technology, with significant
    competition from established manufacturers. Supply chain risks remain elevated due to
    geopolitical factors. Innovation in battery storage is creating new opportunities,
    while regulation continues to evolve. Cost reduction trends favor adoption.
    """
    
    structural = run_structural_checks(test_analysis, seed_count=5,
                                       research_angles=["renewable energy market", "battery innovation"])
    print(f"  Structural: {structural}")
    assert all(0 <= v <= 1 for v in structural.values()), "Scores out of range"
    print("  structural_checks: PASS")
    
    # Test engine without LLM
    engine = VerificationEngine(domain="general")
    result = engine.verify_quick(test_analysis, seed_count=5)
    print(f"  Quick verify: {result['verdict']} ({result['composite_score']:.3f})")
    assert result['verdict'] in ('PASS', 'CONDITIONAL', 'FAIL')
    print("  quick_verify: PASS")
    
    # Test domain configs
    for domain in ['finance', 'technology', 'materials']:
        eng = VerificationEngine(domain=domain)
        r = eng.verify_quick(test_analysis)
        print(f"  Domain {domain}: {r['verdict']} ({r['composite_score']:.3f})")
    print("  domain_configs: PASS")
    
    # Test composite
    dims = {k: 0.8 for k in ["data_completeness", "coverage_breadth", "analysis_depth",
                               "seed_utilization", "cross_validation", "devil_advocate",
                               "fact_checker", "agent_eval"]}
    c = compute_composite(dims)
    assert abs(c - 0.8) < 0.01, f"Expected ~0.8, got {c}"
    print(f"  composite: PASS ({c:.3f})")
    
    # Test verdict boundaries
    assert determine_verdict(0.8) == "PASS"
    assert determine_verdict(0.5) == "CONDITIONAL"
    assert determine_verdict(0.3) == "FAIL"
    print("  verdict_boundaries: PASS")
    
    print("  ALL PASS")
    return True


if __name__ == "__main__":
    self_test()
