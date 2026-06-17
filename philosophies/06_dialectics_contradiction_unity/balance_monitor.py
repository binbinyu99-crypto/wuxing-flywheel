# -*- coding: utf-8 -*-
"""
balance_monitor.py v1.0.0 — Wuxing Balance Monitor & Alert
============================================================
Monitors the balance between five elements during pipeline
execution and alerts when imbalances are detected.

Key metrics:
  - Phase completion rates
  - Score distribution across elements
  - Time allocation balance
  - Model reliability per element

Decision: Robin 2026-05-02
"""

import json, time
from typing import Dict, List

VERSION = "1.0.0"

ELEMENTS = ["wood", "fire", "earth", "metal", "water"]

# Ideal balance ratios
IDEAL_TIME_RATIO = {
    "wood": 0.15,   # Quick seed generation
    "fire": 0.25,   # Deep analysis takes longer
    "earth": 0.20,  # Synthesis
    "metal": 0.25,  # Verification is heavy
    "water": 0.15,  # Regeneration
}

ALERT_THRESHOLDS = {
    "time_imbalance": 0.3,     # >30% deviation from ideal
    "score_deviation": 0.25,   # >25% score gap between elements
    "phase_failure_rate": 0.2, # >20% failure rate
    "stall_seconds": 120,      # Phase stalled >2min
}


class BalanceMonitor:
    """Monitors five-element balance in real-time."""
    
    def __init__(self):
        self._phase_times = {e: [] for e in ELEMENTS}
        self._phase_scores = {e: [] for e in ELEMENTS}
        self._failures = {e: 0 for e in ELEMENTS}
        self._total_runs = {e: 0 for e in ELEMENTS}
        self._alerts = []
    
    def record_phase(self, element: str, elapsed_s: float, score: float, success: bool = True):
        """Record a phase execution."""
        if element not in ELEMENTS:
            return
        self._phase_times[element].append(elapsed_s)
        self._phase_scores[element].append(score)
        self._total_runs[element] += 1
        if not success:
            self._failures[element] += 1
        
        # Check for alerts
        self._check_alerts(element, elapsed_s, score)
    
    def _check_alerts(self, element, elapsed_s, score):
        # Stall check
        if elapsed_s > ALERT_THRESHOLDS["stall_seconds"]:
            self._alerts.append({
                "type": "stall",
                "element": element,
                "value": elapsed_s,
                "threshold": ALERT_THRESHOLDS["stall_seconds"],
                "message": f"{element} phase stalled ({elapsed_s:.0f}s > {ALERT_THRESHOLDS['stall_seconds']}s)",
                "timestamp": time.time(),
            })
        
        # Failure rate check
        total = self._total_runs[element]
        if total >= 3:
            fail_rate = self._failures[element] / total
            if fail_rate > ALERT_THRESHOLDS["phase_failure_rate"]:
                self._alerts.append({
                    "type": "failure_rate",
                    "element": element,
                    "value": fail_rate,
                    "threshold": ALERT_THRESHOLDS["phase_failure_rate"],
                    "message": f"{element} high failure rate ({fail_rate:.0%})",
                    "timestamp": time.time(),
                })
    
    def get_balance(self) -> Dict:
        """Get current five-element balance report."""
        balance = {}
        total_time = sum(sum(t) for t in self._phase_times.values())
        
        for element in ELEMENTS:
            times = self._phase_times[element]
            scores = self._phase_scores[element]
            runs = self._total_runs[element]
            fails = self._failures[element]
            
            el_time = sum(times) if times else 0
            time_ratio = el_time / total_time if total_time > 0 else 0
            ideal = IDEAL_TIME_RATIO[element]
            deviation = abs(time_ratio - ideal) / ideal if ideal > 0 else 0
            
            balance[element] = {
                "runs": runs,
                "failures": fails,
                "avg_time_s": round(sum(times) / len(times), 1) if times else 0,
                "avg_score": round(sum(scores) / len(scores), 3) if scores else 0,
                "time_ratio": round(time_ratio, 3),
                "ideal_ratio": ideal,
                "deviation": round(deviation, 3),
                "balanced": deviation < ALERT_THRESHOLDS["time_imbalance"],
            }
        
        # Overall harmony score
        deviations = [balance[e]["deviation"] for e in ELEMENTS if balance[e]["runs"] > 0]
        harmony = 1.0 - (sum(deviations) / max(len(deviations), 1))
        
        return {
            "elements": balance,
            "harmony": round(max(harmony, 0), 3),
            "total_time_s": round(total_time, 1),
            "alerts": len(self._alerts),
        }
    
    def get_alerts(self, limit: int = 10) -> List[Dict]:
        return self._alerts[-limit:]
    
    def clear_alerts(self):
        self._alerts.clear()


def self_test():
    print(f"balance_monitor.py v{VERSION}")
    
    mon = BalanceMonitor()
    mon.record_phase("wood", 8.5, 0.7)
    mon.record_phase("fire", 15.2, 0.8)
    mon.record_phase("earth", 12.0, 0.75)
    mon.record_phase("metal", 18.5, 0.65)
    mon.record_phase("water", 9.0, 0.7)
    
    balance = mon.get_balance()
    assert balance["harmony"] > 0
    assert len(balance["elements"]) == 5
    print("  balance: PASS")
    
    # Test stall alert
    mon.record_phase("fire", 150, 0.3)
    alerts = mon.get_alerts()
    assert any(a["type"] == "stall" for a in alerts)
    print("  stall_alert: PASS")
    
    print("  ALL PASS")
    return True


if __name__ == "__main__":
    self_test()
