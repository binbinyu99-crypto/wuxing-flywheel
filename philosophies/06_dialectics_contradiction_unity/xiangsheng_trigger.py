# -*- coding: utf-8 -*-
"""
Xiangsheng Chain Auto-Trigger v1.0
Automates the generation cycle: when one phase completes, 
automatically triggers the next phase in the xiangsheng chain.

Chain: Wood -> Fire -> Earth -> Metal -> Water -> Wood
       (seed)  (exec)  (deliver) (audit) (learn) (new seed)

Each transition has conditions that must be met before triggering.
"""

import json, os, time
from datetime import datetime

# Xiangsheng chain order
CHAIN = ["wood", "fire", "earth", "metal", "water"]
CHAIN_NAMES = {
    "wood": "Seed Generation",
    "fire": "Task Execution", 
    "earth": "Delivery & Feedback",
    "metal": "Adversarial Validation",
    "water": "Knowledge Distillation",
}

# What each transition produces
TRANSITIONS = {
    "wood_to_fire": {
        "name": "Seed Ignition",
        "chinese": "Wood feeds Fire",
        "input": "structured seed with goal+scope+constraints",
        "output": "executable task with DAG and assigned node",
        "conditions": ["seed has goal", "seed has scope", "seed complexity assessed"],
    },
    "fire_to_earth": {
        "name": "Execution Delivery", 
        "chinese": "Fire feeds Earth",
        "input": "completed task with results",
        "output": "delivery record with feedback request",
        "conditions": ["task status is completed", "result is not empty", "quality score exists"],
    },
    "earth_to_metal": {
        "name": "Truth Drives Validation",
        "chinese": "Earth feeds Metal",
        "input": "delivery with feedback",
        "output": "adversarial audit task",
        "conditions": ["feedback received", "delivery accepted", "no critical issues flagged"],
    },
    "metal_to_water": {
        "name": "Validation Distills Knowledge",
        "chinese": "Metal feeds Water",
        "input": "validated result with audit report",
        "output": "knowledge entry for storage",
        "conditions": ["audit passed or conditional", "no data integrity failures"],
    },
    "water_to_wood": {
        "name": "Knowledge Breeds Seeds",
        "chinese": "Water feeds Wood",
        "input": "distilled knowledge + residuals",
        "output": "new seeds for next cycle",
        "conditions": ["residual score > 0", "knowledge stored", "no duplicate seeds"],
    },
}


class XiangshengTrigger:
    """Manages automatic phase transitions in the xiangsheng chain"""
    
    def __init__(self):
        self.pending_transitions = []
        self.completed_transitions = []
        self.cycle_count = 0
        self.stats = {phase: {"triggered": 0, "completed": 0, "failed": 0} for phase in CHAIN}
    
    def check_transition(self, from_phase, payload):
        """Check if conditions are met to trigger next phase"""
        to_phase = self._next_phase(from_phase)
        key = f"{from_phase}_to_{to_phase}"
        transition = TRANSITIONS.get(key)
        
        if not transition:
            return {"can_trigger": False, "reason": f"Unknown transition: {key}"}
        
        # Check conditions
        unmet = []
        for condition in transition["conditions"]:
            if not self._evaluate_condition(condition, payload):
                unmet.append(condition)
        
        can_trigger = len(unmet) == 0
        
        result = {
            "from_phase": from_phase,
            "to_phase": to_phase,
            "transition": transition["name"],
            "chinese": transition["chinese"],
            "can_trigger": can_trigger,
            "conditions_met": len(transition["conditions"]) - len(unmet),
            "conditions_total": len(transition["conditions"]),
            "unmet_conditions": unmet,
            "expected_output": transition["output"],
        }
        
        return result
    
    def trigger(self, from_phase, payload, force=False):
        """Trigger the next phase transition"""
        check = self.check_transition(from_phase, payload)
        
        if not check["can_trigger"] and not force:
            return {
                "triggered": False,
                "reason": f"Conditions not met: {check['unmet_conditions']}",
                "check": check
            }
        
        to_phase = check["to_phase"]
        
        transition_record = {
            "id": f"XS-{int(time.time())}",
            "from": from_phase,
            "to": to_phase,
            "name": check["transition"],
            "forced": force and not check["can_trigger"],
            "payload": payload,
            "triggered_at": datetime.now().isoformat(),
            "status": "triggered",
        }
        
        self.pending_transitions.append(transition_record)
        self.stats[from_phase]["triggered"] += 1
        
        # Check if we completed a full cycle
        if from_phase == "water" and to_phase == "wood":
            self.cycle_count += 1
        
        return {
            "triggered": True,
            "transition": transition_record,
            "cycle_count": self.cycle_count,
            "next_phase": to_phase,
            "next_phase_name": CHAIN_NAMES[to_phase],
        }
    
    def complete_transition(self, transition_id, result_payload):
        """Mark a transition as completed"""
        for t in self.pending_transitions:
            if t["id"] == transition_id:
                t["status"] = "completed"
                t["completed_at"] = datetime.now().isoformat()
                t["result"] = result_payload
                self.completed_transitions.append(t)
                self.pending_transitions.remove(t)
                self.stats[t["to"]]["completed"] += 1
                return {"completed": True, "transition": t}
        return {"completed": False, "reason": f"Transition {transition_id} not found"}
    
    def get_chain_status(self):
        """Get full xiangsheng chain status"""
        return {
            "cycle_count": self.cycle_count,
            "pending": len(self.pending_transitions),
            "completed": len(self.completed_transitions),
            "stats": self.stats,
            "chain": [
                {
                    "phase": phase,
                    "name": CHAIN_NAMES[phase],
                    "next": self._next_phase(phase),
                    "transition": f"{phase} -> {self._next_phase(phase)}",
                    "triggered": self.stats[phase]["triggered"],
                    "completed": self.stats[phase]["completed"],
                }
                for phase in CHAIN
            ],
        }
    
    def auto_cascade(self, start_phase, initial_payload, max_steps=5):
        """
        Attempt to cascade through the chain automatically.
        Returns list of triggered transitions.
        """
        results = []
        current_phase = start_phase
        current_payload = initial_payload
        
        for step in range(max_steps):
            check = self.check_transition(current_phase, current_payload)
            if not check["can_trigger"]:
                results.append({
                    "step": step + 1,
                    "blocked_at": f"{current_phase} -> {check['to_phase']}",
                    "reason": check["unmet_conditions"],
                })
                break
            
            trigger_result = self.trigger(current_phase, current_payload)
            results.append({
                "step": step + 1,
                "transition": trigger_result["transition"]["name"],
                "from": current_phase,
                "to": check["to_phase"],
            })
            
            current_phase = check["to_phase"]
            # In real system, payload would be transformed by execution
            current_payload = {**current_payload, "previous_phase": current_phase}
        
        return {
            "steps_completed": len([r for r in results if "transition" in r]),
            "steps_blocked": len([r for r in results if "blocked_at" in r]),
            "full_cycle": self.cycle_count > 0,
            "results": results,
        }
    
    def _next_phase(self, phase):
        """Get next phase in xiangsheng chain"""
        idx = CHAIN.index(phase)
        return CHAIN[(idx + 1) % len(CHAIN)]
    
    def _evaluate_condition(self, condition, payload):
        """Evaluate a single condition against payload"""
        if not payload:
            return False
        
        condition_map = {
            "seed has goal": lambda p: bool(p.get("goal")),
            "seed has scope": lambda p: bool(p.get("scope")),
            "seed complexity assessed": lambda p: "complexity" in p,
            "task status is completed": lambda p: p.get("status") == "completed",
            "result is not empty": lambda p: bool(p.get("result")),
            "quality score exists": lambda p: "quality_score" in p or "quality" in p,
            "feedback received": lambda p: bool(p.get("feedback")),
            "delivery accepted": lambda p: p.get("accepted", True),
            "no critical issues flagged": lambda p: not p.get("critical_issues"),
            "audit passed or conditional": lambda p: p.get("audit_verdict") in ("PASS", "CONDITIONAL", None),
            "no data integrity failures": lambda p: not p.get("data_integrity_failure"),
            "residual score > 0": lambda p: (p.get("residual_score", 0) or 0) > 0,
            "knowledge stored": lambda p: p.get("knowledge_stored", True),
            "no duplicate seeds": lambda p: not p.get("duplicate_seed"),
        }
        
        evaluator = condition_map.get(condition)
        if evaluator:
            return evaluator(payload)
        return True  # Unknown conditions pass by default


# === Self-test ===
if __name__ == "__main__":
    passed = 0
    total = 0
    
    trigger = XiangshengTrigger()
    
    # Test 1: Check transition conditions
    total += 1
    check = trigger.check_transition("wood", {"goal": "test", "scope": "demo", "complexity": "simple"})
    assert check["can_trigger"] == True
    assert check["to_phase"] == "fire"
    print("Test 1 PASS: Wood->Fire conditions met")
    passed += 1
    
    # Test 2: Unmet conditions
    total += 1
    check2 = trigger.check_transition("wood", {"goal": "test"})  # missing scope & complexity
    assert check2["can_trigger"] == False
    assert len(check2["unmet_conditions"]) == 2
    print(f"Test 2 PASS: Unmet conditions detected ({check2['unmet_conditions']})")
    passed += 1
    
    # Test 3: Trigger transition
    total += 1
    result = trigger.trigger("wood", {"goal": "test", "scope": "demo", "complexity": "simple"})
    assert result["triggered"] == True
    assert result["next_phase"] == "fire"
    print(f"Test 3 PASS: Triggered {result['transition']['name']}")
    passed += 1
    
    # Test 4: Full chain cascade
    total += 1
    full_payload = {
        "goal": "analyze SiC", "scope": "semiconductor", "complexity": "standard",
        "status": "completed", "result": "SiC analysis done", "quality": "good",
        "feedback": "positive", "accepted": True,
        "audit_verdict": "PASS",
        "residual_score": 0.52, "knowledge_stored": True,
    }
    cascade = trigger.auto_cascade("wood", full_payload)
    assert cascade["steps_completed"] == 5  # full cycle
    print(f"Test 4 PASS: Full cascade ({cascade['steps_completed']} steps, cycle={cascade['full_cycle']})")
    passed += 1
    
    # Test 5: Chain status
    total += 1
    status = trigger.get_chain_status()
    assert status["cycle_count"] >= 1
    assert len(status["chain"]) == 5
    print(f"Test 5 PASS: Chain status (cycles={status['cycle_count']}, pending={status['pending']})")
    passed += 1
    
    # Test 6: Force trigger with unmet conditions
    total += 1
    force_result = trigger.trigger("fire", {}, force=True)
    assert force_result["triggered"] == True
    assert force_result["transition"]["forced"] == True
    print("Test 6 PASS: Forced trigger works")
    passed += 1
    
    print(f"\n{'='*40}")
    print(f"Xiangsheng Trigger: {passed}/{total} tests PASSED")
