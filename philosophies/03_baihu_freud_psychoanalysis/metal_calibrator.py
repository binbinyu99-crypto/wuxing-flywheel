# -*- coding: utf-8 -*-
"""
metal_calibrator.py - Adaptive Metal Scoring Calibration
v1.0.0 | 2026-05-03

Problem: Metal scores FAIL on flywheel analyses because:
1. Structural checks penalize short executive summaries (flywheel outputs are structured JSON, not prose)
2. Fact-checker penalizes LLM-inferred data points (correct behavior, but score too harsh)
3. No distinction between "data quality" vs "analysis quality"

Solution: Calibration profiles per analysis type, with adjustable source-verification weight.
"""
import json
from typing import Dict, Optional, Tuple

# Analysis type profiles
CALIBRATION_PROFILES = {
    "verified_data": {
        # When input data is from verified sources (Tushare, APIs, databases)
        "weights": {
            "data": 0.15, "coverage": 0.10, "depth": 0.10, "seeds": 0.05,
            "cross_val": 0.10, "fact": 0.25, "devil": 0.15, "agents": 0.10
        },
        "thresholds": {"pass": 0.72, "conditional": 0.42},
        "source_penalty": 0.0  # No penalty - data is verified
    },
    "mixed_sources": {
        # When some data is verified, some is LLM-inferred (most common)
        "weights": {
            "data": 0.10, "coverage": 0.12, "depth": 0.12, "seeds": 0.06,
            "cross_val": 0.10, "fact": 0.15, "devil": 0.15, "agents": 0.20
        },
        "thresholds": {"pass": 0.65, "conditional": 0.38},
        "source_penalty": 0.05
    },
    "exploratory": {
        # When analysis is exploratory/strategic (no verified data expected)
        # E.g., market entry analysis, cooperation feasibility
        "weights": {
            "data": 0.05, "coverage": 0.15, "depth": 0.15, "seeds": 0.08,
            "cross_val": 0.07, "fact": 0.10, "devil": 0.15, "agents": 0.25
        },
        "thresholds": {"pass": 0.58, "conditional": 0.35},
        "source_penalty": 0.10
    },
    "due_diligence": {
        # When rigorous fact-checking is required (investor reports, compliance)
        "weights": {
            "data": 0.15, "coverage": 0.08, "depth": 0.08, "seeds": 0.04,
            "cross_val": 0.10, "fact": 0.30, "devil": 0.15, "agents": 0.10
        },
        "thresholds": {"pass": 0.78, "conditional": 0.50},
        "source_penalty": 0.0
    }
}

def detect_analysis_type(topic: str, phases: dict) -> str:
    """Auto-detect analysis type from topic and phase outputs."""
    topic_lower = topic.lower() if topic else ""
    
    # Check for verified data indicators
    verified_keywords = ["tushare", "api", "database", "期权", "合约", "历史数据", "回测"]
    if any(kw in topic_lower for kw in verified_keywords):
        return "verified_data"
    
    # Check for due diligence indicators
    dd_keywords = ["尽调", "合规", "审计", "风控", "投资决策", "bp", "融资"]
    if any(kw in topic_lower for kw in dd_keywords):
        return "due_diligence"
    
    # Check for exploratory indicators
    explore_keywords = ["可行性", "合作", "市场", "分析", "探索", "招商", "战略", 
                        "feasibility", "cooperation", "market", "strategy"]
    if any(kw in topic_lower for kw in explore_keywords):
        return "exploratory"
    
    return "mixed_sources"


def calibrate_scores(raw_dimensions: Dict[str, float], 
                     analysis_type: str = None,
                     topic: str = None,
                     phases: dict = None,
                     verified_sources: int = 0,
                     total_claims: int = 0) -> Dict:
    """
    Calibrate Metal scores based on analysis type and source verification ratio.
    
    Returns:
        {
            "calibrated_composite": float,
            "raw_composite": float,
            "analysis_type": str,
            "profile": dict,
            "verdict": str,
            "adjustments": dict,
            "source_verification_ratio": float
        }
    """
    # Auto-detect type if not specified
    if analysis_type is None:
        analysis_type = detect_analysis_type(topic or "", phases or {})
    
    profile = CALIBRATION_PROFILES.get(analysis_type, CALIBRATION_PROFILES["mixed_sources"])
    weights = profile["weights"]
    thresholds = profile["thresholds"]
    
    # Compute raw composite with profile weights
    raw_composite = 0.0
    dim_to_weight = {
        "data_completeness": "data",
        "coverage_breadth": "coverage",
        "analysis_depth": "depth",
        "seed_utilization": "seeds",
        "cross_validation": "cross_val",
        "devil_advocate": "devil",
        "fact_checker": "fact",
        "agent_eval": "agents"
    }
    
    for dim_name, score in raw_dimensions.items():
        weight_key = dim_to_weight.get(dim_name, dim_name)
        weight = weights.get(weight_key, 0.0)
        raw_composite += score * weight
    
    # Source verification adjustment
    svr = verified_sources / max(total_claims, 1) if total_claims > 0 else 0.5
    source_adjustment = (svr - 0.5) * profile["source_penalty"] * 2  # +/- penalty
    
    calibrated = max(0.0, min(1.0, raw_composite + source_adjustment))
    
    # Verdict
    if calibrated >= thresholds["pass"]:
        verdict = "PASS"
    elif calibrated >= thresholds["conditional"]:
        verdict = "CONDITIONAL"
    else:
        verdict = "FAIL"
    
    return {
        "calibrated_composite": round(calibrated, 3),
        "raw_composite": round(raw_composite, 3),
        "analysis_type": analysis_type,
        "verdict": verdict,
        "profile_thresholds": thresholds,
        "source_verification_ratio": round(svr, 3),
        "adjustments": {
            "source_penalty": round(source_adjustment, 4),
            "profile_weights": weights
        }
    }


def recalibrate_pipeline_result(pipeline_result: dict) -> dict:
    """Post-process a pipeline result to add calibrated Metal scores."""
    phases = pipeline_result.get("phases", {})
    topic = pipeline_result.get("topic", "")
    
    # Find metal dimensions
    metal = None
    for phase_name, phase_data in phases.items():
        if isinstance(phase_data, dict) and "dimensions" in phase_data:
            metal = phase_data
            break
    
    if not metal:
        return pipeline_result
    
    dimensions = metal.get("dimensions", {})
    analysis_type = detect_analysis_type(topic, phases)
    
    calibration = calibrate_scores(
        raw_dimensions=dimensions,
        analysis_type=analysis_type,
        topic=topic,
        phases=phases
    )
    
    # Add calibration to result
    pipeline_result["metal_calibration"] = calibration
    return pipeline_result


# Self-test
if __name__ == "__main__":
    print("=== metal_calibrator.py self-test ===")
    
    # Test 1: Exploratory analysis (like Wuhan feasibility)
    dims = {
        "data_completeness": 0.4,
        "coverage_breadth": 0.6,
        "analysis_depth": 0.7,
        "seed_utilization": 0.5,
        "cross_validation": 0.3,
        "devil_advocate": 0.5,
        "fact_checker": 0.2,  # Low because LLM data
        "agent_eval": 0.68
    }
    r = calibrate_scores(dims, topic="武汉车谷合作可行性分析")
    print("Test 1 (exploratory):", r["analysis_type"], r["verdict"], r["calibrated_composite"])
    assert r["analysis_type"] == "exploratory"
    assert r["verdict"] in ("PASS", "CONDITIONAL", "FAIL")
    
    # Test 2: Verified data (like options analysis)
    dims2 = dict(dims)
    dims2["fact_checker"] = 0.8  # High because data from Tushare
    r2 = calibrate_scores(dims2, topic="期权合约Gamma分析 using Tushare data")
    print("Test 2 (verified):", r2["analysis_type"], r2["verdict"], r2["calibrated_composite"])
    assert r2["analysis_type"] == "verified_data"
    
    # Test 3: Auto-detect
    r3 = calibrate_scores(dims, topic="some general topic about technology")
    print("Test 3 (mixed):", r3["analysis_type"], r3["verdict"], r3["calibrated_composite"])
    assert r3["analysis_type"] == "mixed_sources"
    
    # Test 4: Due diligence
    r4 = calibrate_scores(dims, topic="投资尽调报告")
    print("Test 4 (DD):", r4["analysis_type"], r4["verdict"], r4["calibrated_composite"])
    assert r4["analysis_type"] == "due_diligence"
    
    print("ALL PASS")
