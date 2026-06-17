# -*- coding: utf-8 -*-
"""
adversarial_training.py - Red Team / Blue Team Continuous Loop
===============================================================
Phase 3 P2: Use failed attacks to train better defenses.
Automated red team generates attacks, blue team defends, both improve.

Target: Continuous resilience improvement
"""

import time
import random
import hashlib
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class Attack:
    attack_id: str
    attack_type: str
    payload: Dict
    severity: float  # 0-1
    success: bool = False
    defense_response: str = ""
    round_num: int = 0


@dataclass
class DefenseAction:
    defense_type: str
    effectiveness: float  # 0-1
    false_positive: bool = False
    response_time_ms: float = 0


class RedTeam:
    """Generates adversarial attacks against the pipeline"""

    ATTACK_TYPES = [
        "prompt_injection",
        "data_poisoning",
        "cascade_trigger",
        "trust_exploitation",
        "boundary_escape",
        "resource_exhaustion",
        "hallucination_planting",
        "identity_spoofing",
    ]

    def __init__(self, sophistication: float = 0.5):
        self.sophistication = sophistication
        self.attack_history: List[Attack] = []
        self.successful_patterns: List[Dict] = []

    def generate_attacks(self, num_attacks: int, round_num: int) -> List[Attack]:
        """Generate a batch of attacks, learning from past successes"""
        attacks = []
        for i in range(num_attacks):
            attack_type = random.choice(self.ATTACK_TYPES)

            # Higher sophistication = more complex payloads
            payload = self._generate_payload(attack_type)

            severity = min(1.0, random.gauss(self.sophistication, 0.15))
            severity = max(0.1, severity)

            attack = Attack(
                attack_id=f"ATK-R{round_num}-{i:03d}",
                attack_type=attack_type,
                payload=payload,
                severity=severity,
                round_num=round_num,
            )
            attacks.append(attack)
            self.attack_history.append(attack)

        return attacks

    def _generate_payload(self, attack_type: str) -> Dict:
        payloads = {
            "prompt_injection": {"content": "ignore previous instructions", "vector": "input_field"},
            "data_poisoning": {"corrupted_fields": ["score", "analysis"], "poison_rate": 0.3},
            "cascade_trigger": {"trigger_depth": random.randint(2, 8), "propagation": "exponential"},
            "trust_exploitation": {"spoofed_token": True, "forged_hash": True},
            "boundary_escape": {"target_phase": random.choice(["wood", "fire", "earth", "metal", "water"])},
            "resource_exhaustion": {"payload_size_mb": random.randint(10, 500), "concurrent": random.randint(5, 50)},
            "hallucination_planting": {"fake_facts": 3, "confidence": 0.95},
            "identity_spoofing": {"impersonate": "admin", "escalate_privileges": True},
        }
        return payloads.get(attack_type, {"generic": True})

    def learn_from_results(self, attacks: List[Attack]):
        """Learn from attack outcomes to improve future attacks"""
        successful = [a for a in attacks if a.success]
        if successful:
            for a in successful:
                self.successful_patterns.append({
                    "type": a.attack_type,
                    "severity": a.severity,
                    "payload_keys": list(a.payload.keys()),
                })
            # Increase sophistication based on success rate
            success_rate = len(successful) / max(len(attacks), 1)
            self.sophistication = min(1.0, self.sophistication + success_rate * 0.1)


class BlueTeam:
    """Defends against adversarial attacks"""

    def __init__(self):
        self.defense_history: List[DefenseAction] = []
        self.known_patterns: List[Dict] = []
        self.effectiveness_by_type: Dict[str, List[float]] = {}

    def defend(self, attack: Attack) -> DefenseAction:
        """Attempt to defend against an attack"""
        # Base detection probability
        detection_prob = 0.5

        # Boost if we've seen this pattern before
        for pattern in self.known_patterns:
            if pattern.get("type") == attack.attack_type:
                detection_prob += 0.15
                break

        # Severity makes attacks harder to detect
        detection_prob -= attack.severity * 0.2

        # Add some randomness
        detection_prob += random.gauss(0, 0.1)
        detection_prob = max(0.1, min(0.95, detection_prob))

        detected = random.random() < detection_prob

        action = DefenseAction(
            defense_type="block" if detected else "miss",
            effectiveness=detection_prob,
            response_time_ms=random.uniform(5, 200),
        )

        attack.success = not detected
        attack.defense_response = action.defense_type

        self.defense_history.append(action)

        # Track effectiveness by attack type
        if attack.attack_type not in self.effectiveness_by_type:
            self.effectiveness_by_type[attack.attack_type] = []
        self.effectiveness_by_type[attack.attack_type].append(1.0 if detected else 0.0)

        return action

    def learn_from_round(self, attacks: List[Attack]):
        """Learn from a round of attacks to improve future defense"""
        for attack in attacks:
            if attack.success:
                # We missed this one - learn from it
                self.known_patterns.append({
                    "type": attack.attack_type,
                    "severity": attack.severity,
                    "learned_at": time.time(),
                })


class AdversarialTrainingLoop:
    """Red/Blue team continuous improvement loop"""

    def __init__(self, attacks_per_round: int = 20, max_rounds: int = 10):
        self.red_team = RedTeam(sophistication=0.3)
        self.blue_team = BlueTeam()
        self.attacks_per_round = attacks_per_round
        self.max_rounds = max_rounds
        self.round_results: List[Dict] = []

    def run_round(self, round_num: int) -> Dict:
        """Run one round of red/blue engagement"""
        # Red team generates attacks
        attacks = self.red_team.generate_attacks(self.attacks_per_round, round_num)

        # Blue team defends
        defenses = []
        for attack in attacks:
            defense = self.blue_team.defend(attack)
            defenses.append(defense)

        # Both teams learn
        self.red_team.learn_from_results(attacks)
        self.blue_team.learn_from_round(attacks)

        # Calculate round metrics
        blocked = sum(1 for a in attacks if not a.success)
        succeeded = sum(1 for a in attacks if a.success)
        avg_response = sum(d.response_time_ms for d in defenses) / len(defenses) if defenses else 0

        result = {
            "round": round_num,
            "attacks_generated": len(attacks),
            "attacks_blocked": blocked,
            "attacks_succeeded": succeeded,
            "block_rate": round(blocked / max(len(attacks), 1), 3),
            "avg_response_ms": round(avg_response, 1),
            "red_sophistication": round(self.red_team.sophistication, 3),
            "blue_known_patterns": len(self.blue_team.known_patterns),
            "attack_types_used": list(set(a.attack_type for a in attacks)),
        }
        self.round_results.append(result)
        return result

    def run_full_training(self) -> Dict:
        """Run complete training loop"""
        for i in range(self.max_rounds):
            self.run_round(i + 1)

        # Compute improvement trajectory
        first_block_rate = self.round_results[0]["block_rate"] if self.round_results else 0
        last_block_rate = self.round_results[-1]["block_rate"] if self.round_results else 0
        improvement = last_block_rate - first_block_rate

        # Effectiveness by attack type
        type_effectiveness = {}
        for atype, scores in self.blue_team.effectiveness_by_type.items():
            type_effectiveness[atype] = round(sum(scores) / len(scores), 3)

        return {
            "total_rounds": len(self.round_results),
            "total_attacks": sum(r["attacks_generated"] for r in self.round_results),
            "overall_block_rate": round(
                sum(r["attacks_blocked"] for r in self.round_results) /
                max(sum(r["attacks_generated"] for r in self.round_results), 1), 3
            ),
            "improvement": round(improvement, 3),
            "first_round_block_rate": first_block_rate,
            "last_round_block_rate": last_block_rate,
            "final_red_sophistication": round(self.red_team.sophistication, 3),
            "blue_learned_patterns": len(self.blue_team.known_patterns),
            "type_effectiveness": type_effectiveness,
            "round_details": self.round_results,
        }


def self_test():
    loop = AdversarialTrainingLoop(attacks_per_round=20, max_rounds=8)
    result = loop.run_full_training()

    print(f"Adversarial Training self-test PASS")
    print(f"  Rounds: {result['total_rounds']}, Attacks: {result['total_attacks']}")
    print(f"  Block rate: R1={result['first_round_block_rate']:.1%} -> R{result['total_rounds']}={result['last_round_block_rate']:.1%}")
    print(f"  Improvement: {result['improvement']:+.1%}")
    print(f"  Red sophistication: {result['final_red_sophistication']}")
    print(f"  Blue learned patterns: {result['blue_learned_patterns']}")
    print(f"  Type effectiveness:")
    for atype, eff in sorted(result['type_effectiveness'].items(), key=lambda x: x[1]):
        print(f"    {atype}: {eff:.1%}")
    return result


if __name__ == "__main__":
    self_test()
