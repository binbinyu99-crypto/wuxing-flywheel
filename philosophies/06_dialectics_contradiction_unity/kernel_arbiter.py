# -*- coding: utf-8 -*-
"""
Kernel Arbiter - Activates trust_scheduler as real arbitration engine.
Wraps trust_scheduler.py to add:
1. Active override decisions (not just observation)
2. Memory write gating via memory_types
3. Convergence detection for pipeline termination

v1.0.0 - 2026-05-03
"""
import sys
import json
import time
sys.path.insert(0, r"D:\ClawMatrix")

from memory_types import MemoryItem, MemoryType, validate_memory_write, save_memory_item, create_memory_table
from pg_storage import get_conn


class KernelArbiter:
    """
    The +1 Kernel agent. Controls:
    1. Memory write validation (what gets persisted)
    2. Agent trust scoring (who to listen to)
    3. Convergence detection (when to stop)
    4. Override decisions (when agents disagree)
    """

    def __init__(self):
        self.decisions_made = 0
        self.overrides = 0
        self.writes_blocked = 0
        self.writes_allowed = 0
        self.round_scores = []

    def validate_and_save(self, conn, item: MemoryItem) -> tuple:
        """Gate function: validate + save memory item."""
        # DECISION type needs kernel approval
        kernel_approved = (item.memory_type == MemoryType.DECISION)
        ok, reason = save_memory_item(conn, item, kernel_approved=kernel_approved)
        if ok:
            self.writes_allowed += 1
        else:
            self.writes_blocked += 1
        self.decisions_made += 1
        return ok, reason

    def should_override_agent(self, agent_id: str, score: float, history: list) -> tuple:
        """
        Decide if kernel should override an agent's output.
        Returns (should_override: bool, reason: str, action: str)
        """
        # Rule 1: Score too low
        if score < 0.2:
            self.overrides += 1
            return True, f"Score {score:.2f} below critical threshold 0.2", "RETRY_WITH_DIFFERENT_STRATEGY"

        # Rule 2: Score declining over 3+ rounds
        if len(history) >= 3:
            recent = history[-3:]
            if all(recent[i] > recent[i+1] for i in range(len(recent)-1)):
                self.overrides += 1
                return True, f"Score declining 3 rounds: {recent}", "FORCE_STRATEGY_SWITCH"

        # Rule 3: Same score stuck (no learning)
        if len(history) >= 2:
            delta = abs(history[-1] - history[-2])
            if delta < 0.01:
                return True, f"Score stuck (delta={delta:.4f})", "INJECT_PERTURBATION"

        return False, "Agent within acceptable range", "CONTINUE"

    def detect_convergence(self, scores: list, threshold: float = 0.05) -> tuple:
        """
        Check if pipeline has converged.
        Returns (converged: bool, reason: str)
        """
        if len(scores) < 2:
            return False, "Need at least 2 rounds"

        delta = abs(scores[-1] - scores[-2])
        if delta < threshold:
            return True, f"Converged: delta={delta:.4f} < threshold={threshold}"

        # Check if score is declining
        if len(scores) >= 2 and scores[-1] < scores[-2] * 0.7:
            return True, f"Score dropped >30%: {scores[-2]:.3f} -> {scores[-1]:.3f}, stopping"

        return False, f"Not converged: delta={delta:.4f}"

    def get_stats(self):
        return {
            "decisions_made": self.decisions_made,
            "overrides": self.overrides,
            "writes_allowed": self.writes_allowed,
            "writes_blocked": self.writes_blocked,
            "override_rate": f"{self.overrides/max(self.decisions_made,1)*100:.1f}%"
        }


# Global kernel instance
_kernel = None

def get_kernel() -> KernelArbiter:
    global _kernel
    if _kernel is None:
        _kernel = KernelArbiter()
    return _kernel


# ============================================================
# Self-test
# ============================================================
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    print("=== Kernel Arbiter Self-Test ===")

    kernel = KernelArbiter()

    # Test 1: Override detection
    override, reason, action = kernel.should_override_agent("metal", 0.15, [0.5, 0.4, 0.3, 0.15])
    print(f"  Override low score: {override} -> {action} ({reason})")
    assert override == True

    override, reason, action = kernel.should_override_agent("wood", 0.6, [0.55, 0.58, 0.6])
    print(f"  No override good score: {override} -> {action}")
    assert override == False

    override, reason, action = kernel.should_override_agent("fire", 0.5, [0.5, 0.5])
    print(f"  Stuck detection: {override} -> {action}")
    assert override == True

    # Test 2: Convergence
    conv, reason = kernel.detect_convergence([0.5, 0.52])
    print(f"  Converged (close): {conv} ({reason})")
    assert conv == True

    conv, reason = kernel.detect_convergence([0.6, 0.3])
    print(f"  Converged (drop): {conv} ({reason})")
    assert conv == True

    conv, reason = kernel.detect_convergence([0.4, 0.55])
    print(f"  Not converged: {conv} ({reason})")
    assert conv == False

    # Test 3: Memory gating
    with get_conn() as conn:
        create_memory_table(conn)

        good = MemoryItem(content="Verified finding", memory_type=MemoryType.HYPOTHESIS, source_agent="fire", confidence=0.7)
        ok, reason = kernel.validate_and_save(conn, good)
        print(f"  Save good hypothesis: {ok} ({reason})")
        assert ok == True

        bad = MemoryItem(content="Wild guess", memory_type=MemoryType.HYPOTHESIS, source_agent="wood", confidence=0.1)
        ok, reason = kernel.validate_and_save(conn, bad)
        print(f"  Block bad hypothesis: {ok} ({reason})")
        assert ok == False

    print(f"  Stats: {kernel.get_stats()}")
    print("All tests passed!")
    print("v1.0.0 - Kernel Arbiter operational")
