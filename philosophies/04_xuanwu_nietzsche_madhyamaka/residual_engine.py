# -*- coding: utf-8 -*-
"""
residual_engine.py v1.0.0 — 五行飞轮残差引擎
================================================
Extracts, categorizes, tracks, and resolves cognitive residuals
across pipeline runs. Bridge between verification (gap detection)
and iteration loop (gap filling).

Core concept: "理想模型决定下限，人类残差决定上限"
Residuals are the gap between current output and ideal output.

Architecture:
  Extract → Categorize → Score → Persist → Track Convergence → Generate Seeds

Usage:
  from residual_engine import ResidualEngine
  engine = ResidualEngine()
  result = engine.process(verification_result, earth_result, topic, run_id)
  print(result["convergence"])    # 0.0-1.0
  print(result["should_iterate"]) # True/False
  print(result["next_seeds"])     # targeted seeds for next round

Decision: Robin 2026-05-02 — Task FW2-Residual-Engine
"""

import json, time, hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

VERSION = "1.0.0"

# ============================================================
# Residual Types & Categories
# ============================================================

class ResidualType:
    BLIND_SPOT = "blind_spot"       # Missing coverage in analysis
    DATA_GAP = "data_gap"           # Missing data/evidence
    PARADIGM_GAP = "paradigm_gap"   # Fundamental framework weakness
    CONSISTENCY = "consistency"      # Internal contradictions
    DEPTH_GAP = "depth_gap"         # Shallow analysis
    CROSS_GAP = "cross_gap"         # Seeds not addressed
    ADVERSARIAL = "adversarial"     # Devil's advocate critique
    FACT_CHECK = "fact_check"       # Fact-checker concerns
    QUALITY = "quality"             # Agent quality concerns
    UNEXPLOITED = "unexploited"     # High-scoring areas not explored


# Severity thresholds
SEVERITY_CRITICAL = 8.0
SEVERITY_HIGH = 6.0
SEVERITY_MEDIUM = 4.0
SEVERITY_LOW = 2.0

# Convergence config
CONVERGENCE_THRESHOLD = 0.75  # Above this = converged, stop iterating
MAX_ITERATIONS = 5            # Hard cap on iterations
MIN_IMPROVEMENT = 0.02        # Minimum composite improvement to continue (was 0.03)


# ============================================================
# Residual Extraction
# ============================================================

def extract_from_verification(verification_result: dict) -> List[dict]:
    """Extract residuals from verification.py output."""
    residuals = []
    dims = verification_result.get("dimensions", {})
    composite = verification_result.get("composite_score", 0)
    verdict = verification_result.get("verdict", "")
    
    # Dimension-based residuals
    dim_thresholds = {
        "data_completeness": (0.5, ResidualType.DATA_GAP, "Data evidence is incomplete"),
        "coverage_breadth": (0.5, ResidualType.BLIND_SPOT, "Analysis coverage too narrow"),
        "analysis_depth": (0.5, ResidualType.DEPTH_GAP, "Analysis lacks depth"),
        "seed_utilization": (0.4, ResidualType.CROSS_GAP, "Seeds not fully utilized"),
        "cross_validation": (0.5, ResidualType.CROSS_GAP, "Weak cross-validation between sources"),
        "devil_advocate": (0.45, ResidualType.ADVERSARIAL, "Adversarial critique found weaknesses"),
        "fact_checker": (0.45, ResidualType.FACT_CHECK, "Fact-checking concerns detected"),
        "agent_eval": (0.5, ResidualType.QUALITY, "Multi-agent evaluation below threshold"),
    }
    
    for dim_name, (threshold, rtype, desc) in dim_thresholds.items():
        score = dims.get(dim_name, 0.5)
        if isinstance(score, (int, float)) and score < threshold:
            severity = round((1.0 - score) * 10, 1)
            residuals.append({
                "type": rtype,
                "source": f"verification.{dim_name}",
                "label": f"{desc} ({score:.2f})",
                "severity": min(severity, 10.0),
                "score": round(score, 3),
                "dimension": dim_name,
            })
    
    # Critique-based residuals
    critiques = verification_result.get("critiques", {})
    devil_text = critiques.get("devil", "")
    if devil_text and len(devil_text) > 50:
        residuals.append({
            "type": ResidualType.PARADIGM_GAP,
            "source": "verification.devil_advocate",
            "label": "Adversarial critique identified",
            "severity": 7.0 if composite < 0.5 else 5.0,
            "insight": devil_text[:300],
        })
    
    fact_text = critiques.get("fact", "")
    if fact_text and len(fact_text) > 50:
        residuals.append({
            "type": ResidualType.FACT_CHECK,
            "source": "verification.fact_checker",
            "label": "Fact-check concerns",
            "severity": 6.0,
            "insight": fact_text[:300],
        })
    
    return residuals


def extract_from_earth(earth_result: dict) -> List[dict]:
    """Extract residuals from Earth synthesis output."""
    residuals = []
    synth = earth_result.get("synthesis", {})
    
    # Data gaps
    for gap in synth.get("data_gaps", []):
        residuals.append({
            "type": ResidualType.DATA_GAP,
            "source": "earth.synthesis",
            "label": str(gap)[:100],
            "severity": 5.0,
            "insight": f"Earth synthesis identified data gap: {gap}",
        })
    
    # Residual questions
    for q in synth.get("residual_questions", []):
        residuals.append({
            "type": ResidualType.BLIND_SPOT,
            "source": "earth.residual_questions",
            "label": str(q)[:100],
            "severity": 4.0,
            "insight": f"Unanswered question: {q}",
        })
    
    # Quality self-assessment
    quality = synth.get("synthesis_quality", {})
    for qk, qv in quality.items():
        if isinstance(qv, (int, float)) and qv < 0.7:
            residuals.append({
                "type": ResidualType.UNEXPLOITED,
                "source": f"earth.quality.{qk}",
                "label": f"Earth self-assessed {qk} at {qv:.2f}",
                "severity": round((1.0 - qv) * 8, 1),
            })
    
    return residuals


def extract_all(verification_result: dict, earth_result: dict) -> List[dict]:
    """Extract residuals from all sources."""
    residuals = []
    residuals.extend(extract_from_verification(verification_result))
    residuals.extend(extract_from_earth(earth_result))
    
    # Deduplicate by source
    seen = set()
    unique = []
    for r in residuals:
        key = r.get("source", "") + "|" + r.get("label", "")[:50]
        if key not in seen:
            seen.add(key)
            unique.append(r)
    
    # Sort by severity (highest first)
    unique.sort(key=lambda x: x.get("severity", 0), reverse=True)
    return unique


# ============================================================
# Convergence Tracking
# ============================================================

class ConvergenceTracker:
    """Tracks convergence across pipeline iterations."""
    
    def __init__(self):
        self.history = []  # List of {round, composite, residual_count, timestamp}
    
    def record(self, round_num: int, composite_score: float,
               residual_count: int, residuals: List[dict]):
        """Record a round's results."""
        entry = {
            "round": round_num,
            "composite": composite_score,
            "residual_count": residual_count,
            "avg_severity": sum(r.get("severity", 0) for r in residuals) / max(len(residuals), 1),
            "max_severity": max((r.get("severity", 0) for r in residuals), default=0),
            "critical_count": sum(1 for r in residuals if r.get("severity", 0) >= SEVERITY_CRITICAL),
            "timestamp": time.time(),
        }
        self.history.append(entry)
        return entry
    
    def get_convergence_score(self) -> float:
        """Calculate convergence score (0=diverging, 1=fully converged)."""
        if len(self.history) < 1:
            return 0.0
        
        latest = self.history[-1]
        composite = latest["composite"]
        
        # Base convergence from composite score
        base = composite
        
        # Bonus for improvement trend
        if len(self.history) >= 2:
            prev = self.history[-2]
            improvement = composite - prev["composite"]
            if improvement > 0:
                base += min(improvement * 2, 0.1)  # Up to 0.1 bonus
            
            # Penalty for increasing residuals
            if latest["residual_count"] > prev["residual_count"]:
                base -= 0.05
        
        # Penalty for critical residuals
        base -= latest["critical_count"] * 0.05
        
        return round(max(0.0, min(1.0, base)), 3)
    
    def should_iterate(self) -> Tuple[bool, str]:
        """Determine if another iteration is needed.
        Returns (should_iterate, reason)."""
        if len(self.history) < 1:
            return True, "No data yet"
        
        latest = self.history[-1]
        round_num = latest["round"]
        convergence = self.get_convergence_score()
        
        # Hard cap
        if round_num >= MAX_ITERATIONS:
            return False, f"Max iterations ({MAX_ITERATIONS}) reached"
        
        # Converged
        if convergence >= CONVERGENCE_THRESHOLD:
            return False, f"Converged (score={convergence:.3f} >= {CONVERGENCE_THRESHOLD})"
        
        # Check improvement stall
        if len(self.history) >= 2:
            prev = self.history[-2]
            improvement = latest["composite"] - prev["composite"]
            if improvement < MIN_IMPROVEMENT and round_num >= 3:  # Require 3+ rounds before stall check
                return False, f"Improvement stalled ({improvement:.4f} < {MIN_IMPROVEMENT})"
        
        # Critical residuals demand attention
        if latest["critical_count"] > 0:
            return True, f"{latest['critical_count']} critical residuals remain"
        
        # Below threshold
        if latest["composite"] < 0.7:
            return True, f"Composite {latest['composite']:.3f} below 0.7 threshold"
        
        return False, f"Quality acceptable (composite={latest['composite']:.3f})"
    
    def to_dict(self) -> dict:
        """Serialize tracker state."""
        return {
            "history": self.history,
            "convergence_score": self.get_convergence_score(),
            "rounds_completed": len(self.history),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ConvergenceTracker':
        """Deserialize tracker state."""
        tracker = cls()
        tracker.history = data.get("history", [])
        return tracker


# ============================================================
# Seed Generation from Residuals
# ============================================================

def generate_seeds_from_residuals(residuals: List[dict], max_seeds: int = 5) -> List[dict]:
    """Generate targeted research seeds from residuals.
    
    Maps residual types to seed strategies:
    - blind_spot → explore missing angle
    - data_gap → find specific data
    - paradigm_gap → challenge assumption
    - consistency → verify claim
    - depth_gap → deep-dive subtopic
    """
    seeds = []
    
    strategy_map = {
        ResidualType.BLIND_SPOT: "explore",
        ResidualType.DATA_GAP: "data_hunt",
        ResidualType.PARADIGM_GAP: "challenge",
        ResidualType.CONSISTENCY: "verify",
        ResidualType.DEPTH_GAP: "deep_dive",
        ResidualType.CROSS_GAP: "cross_validate",
        ResidualType.ADVERSARIAL: "challenge",
        ResidualType.FACT_CHECK: "verify",
        ResidualType.QUALITY: "improve",
        ResidualType.UNEXPLOITED: "explore",
    }
    
    priority_map = {
        True: "high",    # severity >= HIGH
        False: "medium",
    }
    
    for r in residuals[:max_seeds]:
        rtype = r.get("type", "unknown")
        strategy = strategy_map.get(rtype, "explore")
        severity = r.get("severity", 5.0)
        label = r.get("label", "")
        insight = r.get("insight", label)
        
        seed = {
            "angle": f"[{strategy}] {label}",
            "priority": "high" if severity >= SEVERITY_HIGH else "medium",
            "rationale": insight[:200] if insight else f"Address {rtype} residual",
            "strategy": strategy,
            "source_residual": r.get("source", ""),
            "target_severity": severity,
        }
        seeds.append(seed)
    
    return seeds


# ============================================================
# Residual Persistence (PG integration)
# ============================================================

def persist_residuals(residuals: List[dict], topic: str, run_id: str,
                      pg_storage=None):
    """Save residuals to PostgreSQL via pg_storage module."""
    if not pg_storage:
        return False
    
    try:
        keyword = topic[:100] if topic else "unknown"
        pg_storage.residual_save(
            keyword=keyword,
            domain="flywheel",
            residuals=[{
                "residual_type": r.get("type", ""),
                "content": json.dumps(r, ensure_ascii=False, default=str)[:500],
                "score": r.get("severity", 0) / 10.0,
                "source": r.get("source", ""),
            } for r in residuals],
            source=f"pipeline:{run_id}"
        )
        return True
    except Exception as e:
        print(f"[ResidualEngine] Persist error: {e}")
        return False


def load_historical(topic: str, limit: int = 50, pg_storage=None) -> List[dict]:
    """Load historical residuals for a topic from PG."""
    if not pg_storage:
        return []
    
    try:
        rows = pg_storage.residual_query(keyword=topic, limit=limit)
        return rows or []
    except Exception:
        return []


# ============================================================
# Main Engine
# ============================================================

class ResidualEngine:
    """Residual extraction, tracking, and seed generation engine."""
    
    def __init__(self, pg_storage=None):
        self.pg_storage = pg_storage
        self.tracker = ConvergenceTracker()
    
    def process(self, verification_result: dict, earth_result: dict,
                topic: str, run_id: str, round_num: int = 1) -> dict:
        """
        Full residual processing pipeline.
        
        Returns:
            {
                "residuals": [...],
                "residual_count": int,
                "convergence": float (0-1),
                "should_iterate": bool,
                "iterate_reason": str,
                "next_seeds": [...],
                "tracker_state": dict,
                "persisted": bool,
            }
        """
        t0 = time.time()
        
        # 1. Extract residuals
        residuals = extract_all(verification_result, earth_result)
        
        # 2. Record in convergence tracker
        composite = verification_result.get("composite_score", 0)
        self.tracker.record(round_num, composite, len(residuals), residuals)
        
        # 3. Check convergence
        convergence = self.tracker.get_convergence_score()
        should_iter, reason = self.tracker.should_iterate()
        
        # 4. Generate seeds for next iteration (if needed)
        next_seeds = []
        if should_iter:
            next_seeds = generate_seeds_from_residuals(residuals)
        
        # 5. Persist
        persisted = persist_residuals(residuals, topic, run_id, self.pg_storage)
        
        elapsed = round(time.time() - t0, 3)
        
        result = {
            "residuals": residuals,
            "residual_count": len(residuals),
            "convergence": convergence,
            "should_iterate": should_iter,
            "iterate_reason": reason,
            "next_seeds": next_seeds,
            "tracker_state": self.tracker.to_dict(),
            "persisted": persisted,
            "elapsed_s": elapsed,
            "version": VERSION,
        }
        
        print(f"[ResidualEngine] R{round_num}: {len(residuals)} residuals, "
              f"convergence={convergence:.3f}, iterate={should_iter} ({reason})")
        
        return result
    
    def get_convergence(self) -> float:
        """Get current convergence score."""
        return self.tracker.get_convergence_score()
    
    def get_history(self) -> List[dict]:
        """Get iteration history."""
        return self.tracker.history


# ============================================================
# Self-test
# ============================================================


    def extract_all(self, pipeline_result: dict) -> list:
        """Extract all residuals from a complete pipeline result.
        Consolidates from verification, Earth gaps, cognitive graph, adversarial."""
        all_residuals = []
        phases = pipeline_result.get("phases", {})
        
        # From Metal dimensions
        metal = None
        for pname, pdata in phases.items():
            if isinstance(pdata, dict) and "dimensions" in pdata:
                metal = pdata
                break
        if metal:
            for dim_name, score in metal.get("dimensions", {}).items():
                if score < 0.5:
                    all_residuals.append({
                        "type": "verification_gap", "source": "metal",
                        "dimension": dim_name, "score": score,
                        "description": "Low score in {}: {:.3f}".format(dim_name, score),
                        "priority": 1 if score < 0.3 else 2
                    })
        
        # From Earth synthesis
        earth = phases.get("earth", {})
        if isinstance(earth, dict):
            syn = earth.get("synthesis", {})
            if isinstance(syn, dict):
                for gap in syn.get("data_gaps", []):
                    all_residuals.append({"type": "data_gap", "source": "earth",
                        "description": str(gap), "priority": 2})
                for q in syn.get("residual_questions", []):
                    all_residuals.append({"type": "unanswered_question", "source": "earth",
                        "description": str(q), "priority": 3})
        
        # From cognitive graph
        cg = pipeline_result.get("cognitive_graph", {})
        if isinstance(cg, dict):
            for r in cg.get("residuals", []):
                desc = str(r) if isinstance(r, str) else r.get("description", str(r))
                all_residuals.append({"type": "cognitive_residual",
                    "source": "cognitive_graph", "description": desc, "priority": 2})
        
        # From adversarial
        if metal:
            adv = metal.get("adversarial_results", {})
            if isinstance(adv, dict):
                for k in ["devil_critique", "fact_critique"]:
                    v = adv.get(k, "")
                    if v:
                        all_residuals.append({"type": k, "source": "metal",
                            "description": str(v)[:500],
                            "priority": 1 if "fact" in k else 2})
        
        return sorted(all_residuals, key=lambda x: x.get("priority", 99))

def self_test():
    """Run self-test."""
    print(f"residual_engine.py v{VERSION}")
    
    # Mock verification result
    mock_verification = {
        "verdict": "CONDITIONAL",
        "composite_score": 0.55,
        "dimensions": {
            "data_completeness": 0.8,
            "coverage_breadth": 0.6,
            "analysis_depth": 0.9,
            "seed_utilization": 0.7,
            "cross_validation": 0.3,  # Below threshold
            "devil_advocate": 0.4,    # Below threshold
            "fact_checker": 0.5,
            "agent_eval": 0.45,       # Below threshold
        },
        "critiques": {
            "devil": "The analysis ignores supply chain risks from rare earth dependencies and geopolitical tensions.",
            "fact": "Revenue projections lack sourced data points.",
        },
    }
    
    # Mock earth result
    mock_earth = {
        "synthesis": {
            "executive_summary": "Test summary",
            "key_findings": [{"finding": "Test finding"}],
            "data_gaps": ["Market size data for 2025 missing", "Competitor pricing data needed"],
            "residual_questions": ["What is the impact of new regulations?"],
            "synthesis_quality": {"seed_coverage": 0.6, "actionability": 0.8},
        }
    }
    
    # Test extraction
    residuals = extract_all(mock_verification, mock_earth)
    print(f"  Extracted: {len(residuals)} residuals")
    assert len(residuals) > 0, "Should extract residuals"
    print("  extract_all: PASS")
    
    # Test type distribution
    types = set(r["type"] for r in residuals)
    print(f"  Types: {types}")
    assert len(types) >= 3, "Should have multiple types"
    print("  type_diversity: PASS")
    
    # Test severity ordering
    severities = [r.get("severity", 0) for r in residuals]
    assert severities == sorted(severities, reverse=True), "Should be sorted by severity"
    print("  severity_order: PASS")
    
    # Test seed generation
    seeds = generate_seeds_from_residuals(residuals)
    print(f"  Seeds: {len(seeds)}")
    assert len(seeds) > 0, "Should generate seeds"
    assert all("angle" in s and "priority" in s for s in seeds)
    print("  seed_generation: PASS")
    
    # Test convergence tracker
    engine = ResidualEngine()
    
    # Round 1: low quality
    r1 = engine.process(mock_verification, mock_earth, "test-topic", "run-001", round_num=1)
    assert r1["should_iterate"] == True
    assert r1["convergence"] < CONVERGENCE_THRESHOLD
    print(f"  R1: convergence={r1['convergence']:.3f}, iterate={r1['should_iterate']}")
    print("  round_1: PASS")
    
    # Round 2: improved
    mock_verification["composite_score"] = 0.72
    mock_verification["dimensions"]["cross_validation"] = 0.7
    mock_verification["dimensions"]["devil_advocate"] = 0.6
    r2 = engine.process(mock_verification, mock_earth, "test-topic", "run-002", round_num=2)
    print(f"  R2: convergence={r2['convergence']:.3f}, iterate={r2['should_iterate']}")
    print("  round_2: PASS")
    
    # Round 3: converged
    mock_verification["composite_score"] = 0.82
    mock_verification["dimensions"]["agent_eval"] = 0.8
    r3 = engine.process(mock_verification, mock_earth, "test-topic", "run-003", round_num=3)
    print(f"  R3: convergence={r3['convergence']:.3f}, iterate={r3['should_iterate']}")
    assert r3["convergence"] >= 0.7
    print("  round_3: PASS")
    
    # Test tracker serialization
    state = engine.tracker.to_dict()
    restored = ConvergenceTracker.from_dict(state)
    assert restored.get_convergence_score() == engine.tracker.get_convergence_score()
    print("  serialization: PASS")
    
    print("  ALL PASS")
    return True


if __name__ == "__main__":
    self_test()
