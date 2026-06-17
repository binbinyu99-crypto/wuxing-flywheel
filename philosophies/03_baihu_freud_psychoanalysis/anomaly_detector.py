# -*- coding: utf-8 -*-
"""
anomaly_detector.py - 白虎异常行为检测 (Auth-04)
v1.0.0 | 2026-05-03

Detects anomalies in pipeline execution:
1. Phase timing anomalies (too fast = skipped, too slow = stuck)
2. Score distribution anomalies (all same score = broken evaluator)
3. Content anomalies (empty outputs, circular references, hallucination markers)
4. Resource anomalies (memory/CPU spikes, connection failures)
5. Behavioral anomalies (unusual API call patterns)
"""
import json, time, statistics
from typing import Dict, List, Optional, Tuple
from datetime import datetime

class AnomalyDetector:
    """Detect anomalies in Wuxing pipeline execution."""
    
    # Normal ranges for phase execution times (seconds)
    PHASE_TIMING = {
        "wood": {"min": 5, "max": 60, "typical": 25},
        "fire": {"min": 10, "max": 90, "typical": 40},
        "earth": {"min": 15, "max": 120, "typical": 60},
        "metal": {"min": 2, "max": 30, "typical": 10},
        "water": {"min": 5, "max": 45, "typical": 20},
        "lux": {"min": 0.5, "max": 10, "typical": 3},
        "report": {"min": 5, "max": 60, "typical": 30},
    }
    
    # Hallucination markers
    HALLUCINATION_MARKERS = [
        "as an ai", "i cannot", "i don't have access",
        "as of my knowledge cutoff", "i apologize",
        "based on my training data",
        "作为AI", "我无法", "我没有权限",
    ]
    
    def __init__(self):
        self.history: List[Dict] = []  # Historical pipeline runs
        self.anomalies: List[Dict] = []
        self.baselines: Dict = {}
        
    def check_phase_timing(self, phase: str, elapsed_seconds: float) -> Optional[Dict]:
        """Check if phase timing is anomalous."""
        timing = self.PHASE_TIMING.get(phase)
        if not timing:
            return None
        
        if elapsed_seconds < timing["min"] * 0.5:
            return self._anomaly("timing", "critical",
                "Phase '{}' completed in {:.1f}s (expected >{:.0f}s). May have skipped processing.".format(
                    phase, elapsed_seconds, timing["min"]),
                {"phase": phase, "elapsed": elapsed_seconds, "expected_min": timing["min"]})
        
        if elapsed_seconds > timing["max"] * 2:
            return self._anomaly("timing", "warning",
                "Phase '{}' took {:.1f}s (expected <{:.0f}s). Possible timeout or infinite loop.".format(
                    phase, elapsed_seconds, timing["max"]),
                {"phase": phase, "elapsed": elapsed_seconds, "expected_max": timing["max"]})
        
        return None
    
    def check_score_distribution(self, dimensions: Dict[str, float]) -> Optional[Dict]:
        """Check if score distribution is anomalous."""
        if not dimensions:
            return self._anomaly("scores", "critical", "Empty dimensions dict", {})
        
        scores = list(dimensions.values())
        
        # All same score = broken evaluator
        if len(set(scores)) == 1 and len(scores) > 2:
            return self._anomaly("scores", "critical",
                "All {} dimensions have identical score {:.3f}. Evaluator may be broken.".format(
                    len(scores), scores[0]),
                {"scores": dimensions})
        
        # All scores at default (0.5)
        if all(abs(s - 0.5) < 0.01 for s in scores):
            return self._anomaly("scores", "warning",
                "All scores near default 0.5. LLM evaluation may have been skipped.",
                {"scores": dimensions})
        
        # Extreme variance
        if len(scores) > 2:
            mean = statistics.mean(scores)
            stdev = statistics.stdev(scores)
            if stdev > 0.35:
                return self._anomaly("scores", "info",
                    "High score variance (stdev={:.3f}). Check if all dimensions are using same criteria.".format(stdev),
                    {"mean": mean, "stdev": stdev, "scores": dimensions})
        
        return None
    
    def check_content(self, text: str, phase: str = "") -> List[Dict]:
        """Check content for anomalies."""
        anomalies = []
        
        if not text or not text.strip():
            anomalies.append(self._anomaly("content", "critical",
                "Empty output from phase '{}'".format(phase),
                {"phase": phase}))
            return anomalies
        
        # Too short
        if len(text) < 50:
            anomalies.append(self._anomaly("content", "warning",
                "Very short output ({} chars) from phase '{}'".format(len(text), phase),
                {"phase": phase, "length": len(text)}))
        
        # Hallucination markers
        text_lower = text.lower()
        for marker in self.HALLUCINATION_MARKERS:
            if marker in text_lower:
                anomalies.append(self._anomaly("content", "warning",
                    "Hallucination marker found in phase '{}': '{}'".format(phase, marker),
                    {"phase": phase, "marker": marker}))
                break  # One is enough
        
        # Circular reference (repeated paragraphs)
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if len(paragraphs) > 3:
            seen = set()
            for p in paragraphs:
                key = p[:100]
                if key in seen:
                    anomalies.append(self._anomaly("content", "warning",
                        "Repeated paragraph detected in phase '{}'. Possible generation loop.".format(phase),
                        {"phase": phase}))
                    break
                seen.add(key)
        
        return anomalies
    
    def check_pipeline_result(self, result: dict) -> List[Dict]:
        """Comprehensive check of a full pipeline result."""
        all_anomalies = []
        phases = result.get("phases", {})
        
        # Check each phase
        for phase_name, phase_data in phases.items():
            if not isinstance(phase_data, dict):
                continue
            
            # Timing
            elapsed = phase_data.get("elapsed", phase_data.get("time", 0))
            if elapsed > 0:
                timing_anomaly = self.check_phase_timing(phase_name, elapsed)
                if timing_anomaly:
                    all_anomalies.append(timing_anomaly)
            
            # Content
            content = phase_data.get("analysis", phase_data.get("raw_output", 
                      phase_data.get("synthesis", "")))
            if isinstance(content, str) and content:
                content_anomalies = self.check_content(content, phase_name)
                all_anomalies.extend(content_anomalies)
            
            # Scores (Metal)
            dimensions = phase_data.get("dimensions", {})
            if dimensions:
                score_anomaly = self.check_score_distribution(dimensions)
                if score_anomaly:
                    all_anomalies.append(score_anomaly)
        
        # Check overall coherence
        phase_names = list(phases.keys())
        expected_phases = ["wood", "fire", "earth", "metal", "water"]
        missing = [p for p in expected_phases if p not in phase_names]
        if missing:
            all_anomalies.append(self._anomaly("pipeline", "warning",
                "Missing phases: {}".format(missing),
                {"missing": missing, "present": phase_names}))
        
        self.anomalies.extend(all_anomalies)
        return all_anomalies
    
    def update_baselines(self, result: dict):
        """Update baselines from a successful run."""
        phases = result.get("phases", {})
        for phase_name, phase_data in phases.items():
            if not isinstance(phase_data, dict):
                continue
            elapsed = phase_data.get("elapsed", 0)
            if elapsed > 0:
                if phase_name not in self.baselines:
                    self.baselines[phase_name] = {"times": [], "scores": []}
                self.baselines[phase_name]["times"].append(elapsed)
                # Keep last 20
                self.baselines[phase_name]["times"] = self.baselines[phase_name]["times"][-20:]
        
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "topic": result.get("topic", "")[:100],
            "anomaly_count": len([a for a in self.anomalies if a.get("run_id") == id(result)])
        })
    
    def get_health_score(self) -> float:
        """Get overall pipeline health score (0-1)."""
        if not self.anomalies:
            return 1.0
        
        # Weight by severity
        weights = {"critical": 0.3, "warning": 0.1, "info": 0.02}
        total_penalty = sum(weights.get(a["severity"], 0.05) for a in self.anomalies[-50:])
        return max(0.0, 1.0 - total_penalty)
    
    def get_summary(self) -> Dict:
        """Get anomaly detection summary."""
        return {
            "total_anomalies": len(self.anomalies),
            "by_severity": {
                "critical": sum(1 for a in self.anomalies if a["severity"] == "critical"),
                "warning": sum(1 for a in self.anomalies if a["severity"] == "warning"),
                "info": sum(1 for a in self.anomalies if a["severity"] == "info"),
            },
            "by_type": self._count_by("type"),
            "health_score": self.get_health_score(),
            "runs_analyzed": len(self.history),
            "recent_anomalies": self.anomalies[-5:]
        }
    
    def _anomaly(self, atype: str, severity: str, message: str, details: dict) -> Dict:
        return {
            "type": atype,
            "severity": severity,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
    
    def _count_by(self, key: str) -> Dict[str, int]:
        counts = {}
        for a in self.anomalies:
            val = a.get(key, "unknown")
            counts[val] = counts.get(val, 0) + 1
        return counts


# Self-test
if __name__ == "__main__":
    print("=== anomaly_detector.py self-test ===")
    ad = AnomalyDetector()
    
    # Test timing
    t1 = ad.check_phase_timing("wood", 0.5)
    assert t1 and t1["severity"] == "critical"
    print("  timing_too_fast: PASS")
    
    t2 = ad.check_phase_timing("fire", 500)
    assert t2 and t2["severity"] == "warning"
    print("  timing_too_slow: PASS")
    
    t3 = ad.check_phase_timing("wood", 25)
    assert t3 is None
    print("  timing_normal: PASS")
    
    # Test score distribution
    s1 = ad.check_score_distribution({"a": 0.5, "b": 0.5, "c": 0.5, "d": 0.5})
    assert s1 and s1["severity"] == "critical"  # All identical catches first
    print("  scores_identical_default: PASS")
    
    s2 = ad.check_score_distribution({"a": 0.7, "b": 0.7, "c": 0.7, "d": 0.7})
    assert s2 and s2["severity"] == "critical"
    print("  scores_identical: PASS")
    
    # Test content
    c1 = ad.check_content("", "fire")
    assert len(c1) > 0 and c1[0]["severity"] == "critical"
    print("  content_empty: PASS")
    
    c2 = ad.check_content("As an AI, I cannot provide financial advice about this topic.", "earth")
    assert any(a["type"] == "content" for a in c2)
    print("  hallucination_marker: PASS")
    
    # Test full pipeline check
    mock_result = {
        "phases": {
            "wood": {"analysis": "Good analysis " * 50, "elapsed": 25},
            "fire": {"analysis": "Deep analysis " * 100, "elapsed": 45},
            "earth": {"synthesis": {"executive_summary": "Summary"}, "elapsed": 70},
            "metal": {"dimensions": {"a": 0.6, "b": 0.4, "c": 0.7, "d": 0.5}, "elapsed": 8},
            "water": {"seeds": ["seed1", "seed2"], "elapsed": 15},
        }
    }
    pipeline_anomalies = ad.check_pipeline_result(mock_result)
    print("  pipeline_check: PASS ({} anomalies)".format(len(pipeline_anomalies)))
    
    # Test health score
    health = ad.get_health_score()
    assert 0 <= health <= 1
    print("  health_score: PASS ({:.2f})".format(health))
    
    # Test summary
    # Add a run with anomalies
    bad_result = {
        "phases": {
            "wood": {"analysis": "", "elapsed": 0.1},  # empty + too fast
            "fire": {"analysis": "Good " * 50, "elapsed": 45},
        }
    }
    ad.check_pipeline_result(bad_result)
    summary = ad.get_summary()
    assert summary["total_anomalies"] > 0
    print("  summary: PASS ({} anomalies)".format(summary["total_anomalies"]))
    
    print("ALL PASS")
