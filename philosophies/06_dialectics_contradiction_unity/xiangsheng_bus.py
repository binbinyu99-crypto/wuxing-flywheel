# -*- coding: utf-8 -*-
"""
xiangsheng_bus.py v1.0.0 — \u76f8\u751f\u76f8\u514b\u4fe1\u606f\u6d41
========================================================
Element-to-element context passing along the generation
and control chains. Ensures proper information flow.

Decision: Robin 2026-05-02
"""

import json, time

VERSION = "1.0.0"

# Flow definitions
FLOWS = {
    "xiangsheng": [
        ("wood", "fire", "Seeds and exploration angles"),
        ("fire", "earth", "Analysis findings and patterns"),
        ("earth", "metal", "Synthesized claims for verification"),
        ("metal", "water", "Critique results and weak points"),
        ("water", "wood", "New seeds from residuals"),
    ],
    "xiangke": [
        ("wood", "earth", "Challenge Earth with alternative framings"),
        ("earth", "water", "Constrain Water with ground truth"),
        ("water", "fire", "Cool Fire with risk assessment"),
        ("fire", "metal", "Override Metal with deep evidence"),
        ("metal", "wood", "Prune Wood with quality gates"),
    ],
}


class InfoFlow:
    """Tracks information flow between elements."""
    
    def __init__(self):
        self._flows = []
    
    def send(self, source: str, target: str, flow_type: str,
             payload: dict) -> str:
        """Send information along a flow channel."""
        flow = {
            "id": f"flow-{len(self._flows)}",
            "source": source,
            "target": target,
            "type": flow_type,
            "payload_keys": list(payload.keys()),
            "payload_size": len(json.dumps(payload, default=str)),
            "timestamp": time.time(),
        }
        self._flows.append(flow)
        return flow["id"]
    
    def get_incoming(self, element: str, flow_type: str = None) -> list:
        """Get all incoming flows for an element."""
        result = [f for f in self._flows if f["target"] == element]
        if flow_type:
            result = [f for f in result if f["type"] == flow_type]
        return result
    
    def chain_health(self) -> dict:
        """Check if all xiangsheng flows have been activated."""
        expected = [(s, t) for s, t, _ in FLOWS["xiangsheng"]]
        active = set((f["source"], f["target"]) for f in self._flows
                     if f["type"] == "xiangsheng")
        missing = [pair for pair in expected if pair not in active]
        return {
            "total_expected": len(expected),
            "active": len(active),
            "missing": missing,
            "healthy": len(missing) == 0,
        }


def self_test():
    print(f"xiangsheng_bus.py v{VERSION}")
    
    flow = InfoFlow()
    flow.send("wood", "fire", "xiangsheng", {"seeds": ["s1"]})
    flow.send("fire", "earth", "xiangsheng", {"analysis": "..."})
    
    incoming = flow.get_incoming("fire")
    assert len(incoming) == 1
    print("  flow: PASS")
    
    health = flow.chain_health()
    assert health["active"] == 2
    assert len(health["missing"]) == 3
    print("  health: PASS")
    
    print("  ALL PASS")
    return True


if __name__ == "__main__":
    self_test()
