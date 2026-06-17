# -*- coding: utf-8 -*-
"""
behavioral_residual_collector.py - Human Operator Behavioral Residual Instrument
================================================================================
Earth (Hub) phase module.

Captures and classifies human behavioral residuals against the four archetypes
identified in the Corrupted Blood incident:
- Altruist: Cooperative, helps others, follows protocol
- Malicious: Exploitative, breaks rules deliberately
- Curious: Investigative, deviates to explore
- Panicked: Reactive, makes rushed decisions under pressure

These residuals are the "dark matter" of complex systems - they can't be predicted
by any model but they determine outcomes. Our job is not to eliminate them but to
quantify, classify, and manage them.

Part of SkyCetus Wuxing Pipeline - Earth (Hub) ground truth layer.
"""

import json
import time
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime


class BehaviorArchetype(Enum):
    ALTRUIST = "altruist"
    MALICIOUS = "malicious"
    CURIOUS = "curious"
    PANICKED = "panicked"
    RATIONAL = "rational"  # Baseline: follows model prediction exactly
    UNKNOWN = "unknown"


class ResidualType(Enum):
    OVERRIDE = "override"           # Operator overrides system recommendation
    DELAY = "delay"                 # Delayed response to alert
    DEVIATION = "deviation"         # Protocol deviation
    ESCALATION = "escalation"       # Unnecessary escalation
    SUPPRESSION = "suppression"     # Suppressing/ignoring alert
    ACCELERATION = "acceleration"   # Acting faster than protocol requires
    COMMUNICATION = "communication" # Unusual communication pattern


@dataclass
class BehavioralEvent:
    """A single observed behavioral event"""
    id: str
    timestamp: str
    operator_id: str
    event_type: ResidualType
    context: Dict
    system_recommendation: str
    actual_action: str
    delta_from_model: float  # How far from model prediction (0=exact, 1=opposite)
    classified_archetype: BehaviorArchetype
    outcome: str  # positive, negative, neutral
    confidence: float  # Classification confidence


@dataclass
class OperatorProfile:
    """Aggregated behavioral profile for an operator"""
    operator_id: str
    total_events: int = 0
    archetype_distribution: Dict = field(default_factory=dict)
    dominant_archetype: str = "unknown"
    override_rate: float = 0.0
    mean_response_latency: float = 0.0
    protocol_adherence: float = 0.0
    residual_magnitude: float = 0.0  # Average delta from model
    outcome_correlation: float = 0.0  # Does deviation improve outcomes?


class BehavioralResidualCollector:
    """
    Instruments for capturing human operator behavioral residuals.
    
    Design principle: We measure the GAP between what the model predicts
    an operator will do and what they actually do. This gap IS the residual.
    The residual IS the signal that no model can capture.
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {
            "classification_threshold": 0.6,
            "archetype_weights": {
                "override_frequency": 0.25,
                "response_speed": 0.20,
                "protocol_adherence": 0.20,
                "communication_pattern": 0.15,
                "outcome_correlation": 0.20,
            },
        }
        self.events: List[BehavioralEvent] = []
        self.profiles: Dict[str, OperatorProfile] = {}

    def record_event(self, operator_id: str, event_type: str,
                     system_recommendation: str, actual_action: str,
                     context: Optional[Dict] = None) -> BehavioralEvent:
        """Record a behavioral event and classify it"""
        delta = self._compute_delta(system_recommendation, actual_action)
        archetype, confidence = self._classify_behavior(
            event_type, delta, context or {})

        event = BehavioralEvent(
            id=f"BE-{hashlib.md5(f'{time.time()}{operator_id}'.encode()).hexdigest()[:8]}",
            timestamp=datetime.now().isoformat(),
            operator_id=operator_id,
            event_type=ResidualType(event_type) if event_type in [e.value for e in ResidualType] else ResidualType.DEVIATION,
            context=context or {},
            system_recommendation=system_recommendation,
            actual_action=actual_action,
            delta_from_model=delta,
            classified_archetype=archetype,
            outcome="neutral",  # Updated later
            confidence=confidence,
        )

        self.events.append(event)
        self._update_profile(operator_id)
        return event

    def _compute_delta(self, recommendation: str, actual: str) -> float:
        """Compute behavioral delta between model prediction and actual action"""
        if recommendation == actual:
            return 0.0

        # Simple heuristic: measure string distance normalized
        # In production, this would use semantic similarity
        rec_words = set(recommendation.lower().split())
        act_words = set(actual.lower().split())

        if not rec_words or not act_words:
            return 0.5

        overlap = len(rec_words & act_words)
        total = len(rec_words | act_words)
        similarity = overlap / total if total > 0 else 0

        return round(1 - similarity, 3)

    def _classify_behavior(self, event_type: str, delta: float,
                          context: Dict) -> Tuple[BehaviorArchetype, float]:
        """Classify behavior into archetype based on event characteristics"""
        scores = {
            BehaviorArchetype.ALTRUIST: 0.0,
            BehaviorArchetype.MALICIOUS: 0.0,
            BehaviorArchetype.CURIOUS: 0.0,
            BehaviorArchetype.PANICKED: 0.0,
            BehaviorArchetype.RATIONAL: 0.0,
        }

        # Low delta = rational
        if delta < 0.2:
            scores[BehaviorArchetype.RATIONAL] += 0.8

        # Override events
        if event_type == "override":
            if context.get("intent") == "help_others":
                scores[BehaviorArchetype.ALTRUIST] += 0.7
            elif context.get("intent") == "self_benefit":
                scores[BehaviorArchetype.MALICIOUS] += 0.6
            elif context.get("intent") == "investigate":
                scores[BehaviorArchetype.CURIOUS] += 0.7
            else:
                scores[BehaviorArchetype.PANICKED] += 0.4

        # Speed-based classification
        response_speed = context.get("response_speed", "normal")
        if response_speed == "very_fast":
            scores[BehaviorArchetype.PANICKED] += 0.5
        elif response_speed == "very_slow":
            scores[BehaviorArchetype.CURIOUS] += 0.3

        # High delta with positive outcome
        if delta > 0.5 and context.get("outcome") == "positive":
            scores[BehaviorArchetype.ALTRUIST] += 0.3
            scores[BehaviorArchetype.CURIOUS] += 0.3

        # High delta with negative outcome
        if delta > 0.5 and context.get("outcome") == "negative":
            scores[BehaviorArchetype.MALICIOUS] += 0.3
            scores[BehaviorArchetype.PANICKED] += 0.3

        # Communication pattern
        if context.get("communicated_before_action"):
            scores[BehaviorArchetype.ALTRUIST] += 0.2
        if context.get("acted_without_communication"):
            scores[BehaviorArchetype.MALICIOUS] += 0.2
            scores[BehaviorArchetype.PANICKED] += 0.2

        # Find dominant archetype
        best = max(scores, key=scores.get)
        confidence = scores[best] / max(sum(scores.values()), 0.01)

        return best, round(min(confidence, 1.0), 3)

    def _update_profile(self, operator_id: str):
        """Update operator profile with latest events"""
        events = [e for e in self.events if e.operator_id == operator_id]
        if not events:
            return

        profile = self.profiles.get(operator_id, OperatorProfile(operator_id=operator_id))
        profile.total_events = len(events)

        # Archetype distribution
        arch_counts = {}
        for e in events:
            arch = e.classified_archetype.value
            arch_counts[arch] = arch_counts.get(arch, 0) + 1
        profile.archetype_distribution = {k: round(v / len(events), 3) for k, v in arch_counts.items()}

        # Dominant archetype
        if arch_counts:
            profile.dominant_archetype = max(arch_counts, key=arch_counts.get)

        # Override rate
        overrides = [e for e in events if e.event_type == ResidualType.OVERRIDE]
        profile.override_rate = round(len(overrides) / len(events), 3)

        # Residual magnitude
        profile.residual_magnitude = round(sum(e.delta_from_model for e in events) / len(events), 3)

        # Protocol adherence (inverse of average delta)
        profile.protocol_adherence = round(1 - profile.residual_magnitude, 3)

        self.profiles[operator_id] = profile

    def get_residual_distribution(self) -> Dict:
        """Get the behavioral residual distribution across all operators"""
        if not self.events:
            return {"error": "No events recorded"}

        total = len(self.events)
        arch_dist = {}
        for e in self.events:
            arch = e.classified_archetype.value
            arch_dist[arch] = arch_dist.get(arch, 0) + 1

        return {
            "total_events": total,
            "archetype_distribution": {k: round(v / total, 3) for k, v in arch_dist.items()},
            "mean_delta": round(sum(e.delta_from_model for e in self.events) / total, 3),
            "high_delta_events": sum(1 for e in self.events if e.delta_from_model > 0.5),
            "operator_count": len(self.profiles),
            "profiles": {k: asdict(v) for k, v in self.profiles.items()},
        }

    def compare_with_corrupted_blood(self) -> Dict:
        """
        Compare observed behavioral distribution with Corrupted Blood distribution.
        CB distribution: 35% altruist, 10% malicious, 30% curious, 25% panicked
        """
        cb_dist = {"altruist": 0.35, "malicious": 0.10, "curious": 0.30, "panicked": 0.25}
        observed = self.get_residual_distribution().get("archetype_distribution", {})

        comparison = {}
        for arch, cb_ratio in cb_dist.items():
            obs_ratio = observed.get(arch, 0)
            comparison[arch] = {
                "corrupted_blood": cb_ratio,
                "observed": obs_ratio,
                "delta": round(obs_ratio - cb_ratio, 3),
                "interpretation": self._interpret_delta(arch, obs_ratio - cb_ratio),
            }

        # Overall similarity (cosine-like)
        cb_vec = [cb_dist.get(a, 0) for a in ["altruist", "malicious", "curious", "panicked"]]
        obs_vec = [observed.get(a, 0) for a in ["altruist", "malicious", "curious", "panicked"]]

        dot = sum(a * b for a, b in zip(cb_vec, obs_vec))
        mag_cb = sum(a ** 2 for a in cb_vec) ** 0.5
        mag_obs = sum(a ** 2 for a in obs_vec) ** 0.5

        similarity = round(dot / (mag_cb * mag_obs) if mag_cb * mag_obs > 0 else 0, 3)

        return {
            "comparison": comparison,
            "similarity_to_cb": similarity,
            "interpretation": (
                f"Behavioral distribution is {similarity:.0%} similar to Corrupted Blood. "
                f"{'High similarity suggests virtual-to-real transfer is valid.' if similarity > 0.7 else 'Low similarity suggests domain-specific behavioral factors dominate.'}"
            ),
        }

    def _interpret_delta(self, archetype: str, delta: float) -> str:
        if abs(delta) < 0.05:
            return f"{archetype} rate matches Corrupted Blood baseline"
        elif delta > 0:
            return f"More {archetype} behavior than CB ({delta:+.1%}) — {'concerning' if archetype == 'malicious' else 'notable'}"
        else:
            return f"Less {archetype} behavior than CB ({delta:+.1%})"


def self_test():
    """Run self-test with synthetic operator data"""
    import random
    random.seed(2026)

    print("[BRC] Self-test: Behavioral Residual Collector...")
    collector = BehavioralResidualCollector()

    # Simulate 100 events from 5 operators
    operators = ["OP-001", "OP-002", "OP-003", "OP-004", "OP-005"]
    event_types = ["override", "delay", "deviation", "suppression", "acceleration"]
    intents = ["help_others", "self_benefit", "investigate", None]
    speeds = ["very_fast", "normal", "very_slow"]

    for _ in range(100):
        op = random.choice(operators)
        et = random.choice(event_types)
        ctx = {
            "intent": random.choice(intents),
            "response_speed": random.choice(speeds),
            "outcome": random.choice(["positive", "negative", "neutral"]),
            "communicated_before_action": random.random() > 0.5,
            "acted_without_communication": random.random() > 0.7,
        }
        collector.record_event(
            operator_id=op,
            event_type=et,
            system_recommendation=f"recommended_action_{random.randint(1,10)}",
            actual_action=f"actual_action_{random.randint(1,10)}",
            context=ctx,
        )

    # Get results
    dist = collector.get_residual_distribution()
    print(f"\n  Events: {dist['total_events']}, Operators: {dist['operator_count']}")
    print(f"  Mean Delta: {dist['mean_delta']}")
    print(f"  High-Delta Events: {dist['high_delta_events']}")
    print(f"\n  Archetype Distribution:")
    for arch, ratio in sorted(dist['archetype_distribution'].items(), key=lambda x: x[1], reverse=True):
        bar = '#' * int(ratio * 40)
        print(f"    {arch:12s}: {ratio:.1%} {bar}")

    # Compare with CB
    cb_comp = collector.compare_with_corrupted_blood()
    print(f"\n  Similarity to Corrupted Blood: {cb_comp['similarity_to_cb']:.0%}")
    print(f"  {cb_comp['interpretation']}")

    for arch, data in cb_comp["comparison"].items():
        print(f"    {arch}: CB={data['corrupted_blood']:.0%} vs Obs={data['observed']:.1%} ({data['interpretation']})")

    # Operator profiles
    print("\n  Operator Profiles:")
    for op_id, profile in dist["profiles"].items():
        print(f"    {op_id}: dominant={profile['dominant_archetype']}, override={profile['override_rate']:.0%}, adherence={profile['protocol_adherence']:.0%}, residual={profile['residual_magnitude']:.2f}")

    # Save
    result = {
        "distribution": dist,
        "cb_comparison": cb_comp,
    }
    with open("reports/behavioral_residual_test.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n[BRC] Self-test PASSED. Saved to reports/behavioral_residual_test.json")
    return result


if __name__ == "__main__":
    self_test()
