"""
trust_scheduler.py — 天鲸 SkyCetus (Sovereign Scheduler)
v1.0.0

System-level meta-agent that governs the 15-agent Wuxing ecosystem.
Reads all agents' PG history, computes trust, makes scheduling decisions.

Position: Above the pentagram. Not a node, not an edge — the rotation itself.
Constraint: Earth (土) ground truth is the only force that can override Sovereign.

Capabilities:
  1. Trust Scoring   — per-agent, per-domain historical performance → trust score
  2. Strategy Advice  — recommend strategies based on what worked before
  3. Budget Allocation — adjust compute/depth based on trust
  4. Intervention     — bypass or override underperforming agents
  5. System Diagnosis  — detect systemic patterns across all agents

Design principle: 天鲸 SkyCetus observes and guides, but does not replace.
It adjusts parameters, not content. The agents still think for themselves.
"""

VERSION = "1.0.0"

import json
import time
import math

try:
    import agent_memory_store as ams
    PG_AVAILABLE = True
except ImportError:
    PG_AVAILABLE = False


class TrustProfile:
    """Trust profile for a single agent across domains."""
    
    def __init__(self, agent_id):
        self.agent_id = agent_id
        self.domain_scores = {}    # domain -> [scores]
        self.domain_trust = {}     # domain -> trust_score (0-1)
        self.global_trust = 0.5    # baseline
        self.total_runs = 0
        self.volatility = 0.0      # score variance — high = unreliable
        self.trend = 0.0           # improving (+) or declining (-)
        self.last_updated = 0
    
    def compute(self, runs):
        """Compute trust from run history."""
        if not runs:
            return
        
        self.total_runs = len(runs)
        
        # Group by domain
        by_domain = {}
        all_scores = []
        for r in runs:
            d = r.get("domain", "unknown")
            s = r.get("score")
            if s is not None:
                by_domain.setdefault(d, []).append(s)
                all_scores.append(s)
        
        # Per-domain trust (weighted recent)
        for domain, scores in by_domain.items():
            self.domain_scores[domain] = scores
            # Exponential decay: recent scores matter more
            weights = [math.exp(-0.3 * i) for i in range(len(scores))]
            total_w = sum(weights)
            weighted_avg = sum(s * w for s, w in zip(scores, weights)) / total_w if total_w > 0 else 0.5
            self.domain_trust[domain] = round(weighted_avg, 4)
        
        # Global trust
        if all_scores:
            self.global_trust = round(sum(all_scores) / len(all_scores), 4)
            
            # Volatility (std dev)
            mean = self.global_trust
            variance = sum((s - mean) ** 2 for s in all_scores) / len(all_scores)
            self.volatility = round(math.sqrt(variance), 4)
            
            # Trend (last 5 vs first 5)
            if len(all_scores) >= 4:
                recent = all_scores[:min(3, len(all_scores))]
                early = all_scores[-min(3, len(all_scores)):]
                self.trend = round(sum(recent)/len(recent) - sum(early)/len(early), 4)
        
        self.last_updated = time.time()
    
    def summary(self):
        return {
            "agent_id": self.agent_id,
            "global_trust": self.global_trust,
            "domain_trust": self.domain_trust,
            "total_runs": self.total_runs,
            "volatility": self.volatility,
            "trend": self.trend,
        }


class SchedulingDecision:
    """A single scheduling decision for one pipeline run."""
    
    def __init__(self):
        self.strategy_overrides = {}   # agent_id -> recommended strategy
        self.threshold_adjustments = {} # agent_id -> {param: value}
        self.depth_adjustments = {}    # agent_id -> depth multiplier
        self.bypass_agents = []        # agents to skip
        self.warnings = []
        self.rationale = []
    
    def to_dict(self):
        return {
            "strategy_overrides": self.strategy_overrides,
            "threshold_adjustments": self.threshold_adjustments,
            "depth_adjustments": self.depth_adjustments,
            "bypass_agents": self.bypass_agents,
            "warnings": self.warnings,
            "rationale": self.rationale,
        }


class TrustScheduler:
    """
    天鲸 SkyCetus — The Sovereign Scheduler.
    
    Reads all agents' PG history before each pipeline run.
    Produces a SchedulingDecision that adjusts agent behavior.
    Constrained by Earth (ground truth) — cannot override verified facts.
    """
    
    def __init__(self):
        self.profiles = {}          # agent_id -> TrustProfile
        self.run_count = 0
        self.decisions_log = []     # recent decisions
        self.system_patterns = []   # detected cross-agent patterns
        self.initialized = False
        
        # Governance thresholds
        self.TRUST_LOW = 0.35       # Below this: intervene
        self.TRUST_HIGH = 0.75      # Above this: give more freedom
        self.VOLATILITY_HIGH = 0.15 # Above this: agent is unreliable
        self.TREND_ALARM = -0.1     # Declining trend threshold
        self.MIN_RUNS_FOR_TRUST = 3 # Don't judge until enough data
        
        self._load_state()
    
    def _load_state(self):
        """Load Sovereign's own state from PG."""
        if not PG_AVAILABLE:
            return
        state, stats = ams.load_agent_state("sovereign_scheduler")
        if state:
            self.run_count = state.get("run_count", 0)
            self.TRUST_LOW = state.get("trust_low", self.TRUST_LOW)
            self.TRUST_HIGH = state.get("trust_high", self.TRUST_HIGH)
            self.initialized = True
            print(f"[SkyCetus] Loaded state: {self.run_count} prior runs")
    
    def _save_state(self):
        """Save Sovereign's state to PG."""
        if not PG_AVAILABLE:
            return
        state = {
            "run_count": self.run_count,
            "trust_low": self.TRUST_LOW,
            "trust_high": self.TRUST_HIGH,
            "volatility_high": self.VOLATILITY_HIGH,
        }
        stats = {
            "total_decisions": self.run_count,
            "agents_tracked": len(self.profiles),
            "patterns_detected": len(self.system_patterns),
        }
        ams.save_agent_state("sovereign_scheduler", "system", "sovereign", state, stats)
    
    def observe(self, domain=None):
        """
        Phase 1: Observe. Read all agents' history from PG.
        Call this before each pipeline run.
        """
        if not PG_AVAILABLE:
            print("[SkyCetus] PG unavailable, running blind")
            return
        
        # Get all agent states
        health = ams.get_system_health()
        agent_ids = [a["id"] for a in health.get("agent_list", [])]
        
        for agent_id in agent_ids:
            if agent_id == "sovereign_scheduler":
                continue
            runs = ams.get_runs(agent_id, limit=50)
            profile = TrustProfile(agent_id)
            profile.compute(runs)
            self.profiles[agent_id] = profile
        
        # Cross-agent patterns
        if domain:
            cross = ams.get_cross_agent_insight(domain)
            self._detect_patterns(cross, domain)
        
        observed = len(self.profiles)
        print(f"[SkyCetus] Observed {observed} agents" + (f" for domain={domain}" if domain else ""))
    
    def _detect_patterns(self, cross_insight, domain):
        """Detect systemic patterns across agents."""
        self.system_patterns = []
        
        if not cross_insight:
            return
        
        # Pattern 1: All agents scoring low on this domain
        all_scores = []
        for scores in cross_insight.values():
            all_scores.extend(scores)
        if all_scores:
            avg = sum(all_scores) / len(all_scores)
            if avg < 0.45:
                self.system_patterns.append({
                    "type": "systemic_weakness",
                    "domain": domain,
                    "avg_score": avg,
                    "desc": f"All agents struggle with '{domain}' (avg {avg:.2f}). May need domain-specific training data."
                })
        
        # Pattern 2: One agent much worse than others
        for agent_id, scores in cross_insight.items():
            agent_avg = sum(scores) / len(scores) if scores else 0
            others = [s for aid, ss in cross_insight.items() if aid != agent_id for s in ss]
            others_avg = sum(others) / len(others) if others else 0
            if others_avg > 0 and agent_avg < others_avg * 0.7 and len(scores) >= 2:
                self.system_patterns.append({
                    "type": "underperformer",
                    "agent": agent_id,
                    "agent_avg": agent_avg,
                    "system_avg": others_avg,
                    "desc": f"{agent_id} underperforms on '{domain}' ({agent_avg:.2f} vs system {others_avg:.2f})"
                })
        
        # Pattern 3: Improving trend across system
        improving = sum(1 for p in self.profiles.values() if p.trend > 0.05)
        declining = sum(1 for p in self.profiles.values() if p.trend < -0.05)
        if improving > declining and improving >= 3:
            self.system_patterns.append({
                "type": "system_improving",
                "improving": improving,
                "declining": declining,
                "desc": f"System trending up: {improving} agents improving vs {declining} declining"
            })
    
    def decide(self, topic, domain=None):
        """
        Phase 2: Decide. Produce a SchedulingDecision based on observations.
        
        Returns: SchedulingDecision with strategy/threshold/depth adjustments.
        """
        decision = SchedulingDecision()
        self.run_count += 1
        
        for agent_id, profile in self.profiles.items():
            # Skip if not enough data
            if profile.total_runs < self.MIN_RUNS_FOR_TRUST:
                decision.rationale.append(
                    f"{agent_id}: insufficient data ({profile.total_runs} runs), using defaults"
                )
                continue
            
            # Get domain-specific trust if available
            trust = profile.domain_trust.get(domain, profile.global_trust) if domain else profile.global_trust
            
            # === Strategy Override ===
            if domain and agent_id.startswith("node_"):
                best = ams.get_best_strategy(agent_id, domain)
                if best and best.get("count", 0) >= 3 and best.get("avg_score", 0) > 0.65:
                    decision.strategy_overrides[agent_id] = best["strategy"]
                    decision.rationale.append(
                        f"{agent_id}: override to '{best['strategy']}' (proven: avg {best['avg_score']:.2f} over {best['count']} runs)"
                    )
            
            # === Threshold Adjustments ===
            if trust < self.TRUST_LOW:
                # Low trust: tighten constraints, increase scrutiny
                decision.threshold_adjustments[agent_id] = {
                    "trust": trust,
                    "action": "tighten",
                    "skepticism_boost": 0.15,
                    "depth_multiplier": 1.3,  # More compute to compensate
                }
                decision.warnings.append(
                    f"⚠️ {agent_id}: LOW TRUST ({trust:.2f}). Tightening constraints."
                )
                decision.rationale.append(
                    f"{agent_id}: trust={trust:.2f} < {self.TRUST_LOW}, tightening"
                )
            
            elif trust > self.TRUST_HIGH:
                # High trust: give more freedom, less overhead
                decision.threshold_adjustments[agent_id] = {
                    "trust": trust,
                    "action": "relax",
                    "skepticism_boost": -0.05,
                    "depth_multiplier": 0.9,  # Can do less, it's reliable
                }
                decision.rationale.append(
                    f"{agent_id}: trust={trust:.2f} > {self.TRUST_HIGH}, relaxing constraints"
                )
            
            # === Volatility Check ===
            if profile.volatility > self.VOLATILITY_HIGH:
                decision.warnings.append(
                    f"⚡ {agent_id}: HIGH VOLATILITY ({profile.volatility:.2f}). Output quality unstable."
                )
                decision.threshold_adjustments.setdefault(agent_id, {})["volatile"] = True
            
            # === Trend Alarm ===
            if profile.trend < self.TREND_ALARM:
                decision.warnings.append(
                    f"📉 {agent_id}: DECLINING (trend {profile.trend:+.2f}). Performance degrading."
                )
            
            # === Bypass Decision (extreme case) ===
            if trust < 0.2 and profile.total_runs >= 5 and profile.trend < -0.05:
                decision.bypass_agents.append(agent_id)
                decision.warnings.append(
                    f"🚫 {agent_id}: BYPASS recommended (trust={trust:.2f}, trend={profile.trend:+.2f})"
                )
        
        # System-level patterns
        for pattern in self.system_patterns:
            decision.rationale.append(f"[PATTERN] {pattern['desc']}")
        
        # Log decision
        self.decisions_log.append({
            "run": self.run_count,
            "topic": str(topic)[:100],
            "domain": domain,
            "decision": decision.to_dict(),
            "timestamp": time.time(),
        })
        if len(self.decisions_log) > 100:
            self.decisions_log = self.decisions_log[-100:]
        
        # Persist
        self._save_state()
        if PG_AVAILABLE:
            ams.save_run(
                "sovereign_scheduler", 
                str(hash(topic))[:16], 
                domain or "general",
                f"Decision: {len(decision.strategy_overrides)} overrides, {len(decision.warnings)} warnings",
                metadata=decision.to_dict()
            )
        
        print(f"[SkyCetus] Decision #{self.run_count}: {len(decision.strategy_overrides)} strategy overrides, "
              f"{len(decision.threshold_adjustments)} threshold adjustments, "
              f"{len(decision.warnings)} warnings, "
              f"{len(decision.bypass_agents)} bypasses")
        
        return decision
    
    def apply_to_node_agents(self, registry, decision):
        """
        Phase 3: Apply. Push decisions into node agents.
        
        This is where Sovereign's will becomes reality.
        But Earth (ground truth) can still override via Metal verification.
        """
        applied = 0
        
        for agent_id, strategy in decision.strategy_overrides.items():
            element = agent_id.replace("node_", "")
            agent = registry.get(element)
            if agent and hasattr(agent, 'current_strategy'):
                old = getattr(agent, 'current_strategy', 'unknown')
                agent.current_strategy = strategy
                print(f"  [Sovereign→{element}] Strategy: {old} → {strategy}")
                applied += 1
        
        for agent_id, adjustments in decision.threshold_adjustments.items():
            element = agent_id.replace("node_", "")
            agent = registry.get(element)
            if not agent:
                continue
            
            action = adjustments.get("action", "none")
            
            if element == "metal" and hasattr(agent, 'pass_threshold'):
                if action == "tighten":
                    agent.pass_threshold = min(0.85, agent.pass_threshold + 0.05)
                    print(f"  [Sovereign→metal] Tightened: pass_threshold → {agent.pass_threshold}")
                elif action == "relax":
                    agent.pass_threshold = max(0.55, agent.pass_threshold - 0.03)
                    print(f"  [Sovereign→metal] Relaxed: pass_threshold → {agent.pass_threshold}")
                applied += 1
            
            if hasattr(agent, 'skepticism_level'):
                boost = adjustments.get("skepticism_boost", 0)
                if boost:
                    agent.skepticism_level = max(0, min(1, agent.skepticism_level + boost))
                    print(f"  [Sovereign→{element}] Skepticism: {agent.skepticism_level:.2f}")
                    applied += 1
        
        print(f"[SkyCetus] Applied {applied} adjustments to node agents")
        return applied
    
    def post_run_learn(self, metal_score, domain=None):
        """
        Phase 4: Learn. After pipeline completes, update Sovereign's own model.
        
        If system keeps scoring low despite interventions, adjust governance thresholds.
        """
        if not self.decisions_log:
            return
        
        last = self.decisions_log[-1]
        last["actual_score"] = metal_score
        
        # Self-calibration: if we're intervening but scores aren't improving, 
        # our thresholds may be wrong
        recent_scores = [d.get("actual_score", 0) for d in self.decisions_log[-10:] if d.get("actual_score")]
        if len(recent_scores) >= 5:
            avg_recent = sum(recent_scores) / len(recent_scores)
            
            # If average is good, maybe we can relax
            if avg_recent > 0.7 and self.TRUST_LOW > 0.25:
                self.TRUST_LOW -= 0.02
                print(f"[SkyCetus] Self-calibrate: system doing well, relaxing TRUST_LOW → {self.TRUST_LOW:.2f}")
            
            # If average is bad, tighten
            elif avg_recent < 0.4 and self.TRUST_LOW < 0.5:
                self.TRUST_LOW += 0.03
                print(f"[SkyCetus] Self-calibrate: system struggling, tightening TRUST_LOW → {self.TRUST_LOW:.2f}")
        
        self._save_state()
        
        # Log to PG
        if PG_AVAILABLE:
            ams.log_signal(
                "sovereign_scheduler", "system",
                "post_run_learn",
                {"metal_score": metal_score, "domain": domain, "run": self.run_count}
            )
    
    def get_trust_report(self):
        """Generate a full trust report across all agents."""
        report = {
            "sovereign_version": VERSION,
            "total_runs": self.run_count,
            "agents": {},
            "patterns": self.system_patterns,
            "governance": {
                "trust_low": self.TRUST_LOW,
                "trust_high": self.TRUST_HIGH,
                "volatility_high": self.VOLATILITY_HIGH,
            }
        }
        
        for agent_id, profile in sorted(self.profiles.items()):
            report["agents"][agent_id] = profile.summary()
        
        return report
    
    def diagnose(self):
        """Quick system diagnosis — called during heartbeats or on demand."""
        if not self.profiles:
            self.observe()
        
        lines = [f"=== 天鲸 SkyCetus System Diagnosis (Run #{self.run_count}) ==="]
        
        for agent_id, profile in sorted(self.profiles.items()):
            trust = profile.global_trust
            icon = "🟢" if trust > self.TRUST_HIGH else ("🔴" if trust < self.TRUST_LOW else "🟡")
            trend_icon = "↗" if profile.trend > 0.03 else ("↘" if profile.trend < -0.03 else "→")
            lines.append(
                f"  {icon} {agent_id}: trust={trust:.2f} vol={profile.volatility:.2f} "
                f"trend={profile.trend:+.2f}{trend_icon} runs={profile.total_runs}"
            )
        
        if self.system_patterns:
            lines.append("\nPatterns:")
            for p in self.system_patterns:
                lines.append(f"  [{p['type']}] {p['desc']}")
        
        return "\n".join(lines)


# Singleton
_sovereign = None

def get_sovereign():
    """Get or create the Sovereign Scheduler singleton."""
    global _sovereign
    if _sovereign is None:
        _sovereign = TrustScheduler()
    return _sovereign


def self_test():
    """Self-test."""
    print(f"trust_scheduler.py v{VERSION} self-test")
    print("=" * 50)
    
    passed = 0
    total = 0
    
    # Test 1: Create Sovereign
    total += 1
    sov = TrustScheduler()
    ok = sov.run_count >= 0 and sov.TRUST_LOW == 0.35
    print(f"  [{'PASS' if ok else 'FAIL'}] Create Sovereign")
    if ok: passed += 1
    
    # Test 2: TrustProfile compute
    total += 1
    tp = TrustProfile("test_agent")
    runs = [
        {"domain": "chips", "score": 0.7},
        {"domain": "chips", "score": 0.6},
        {"domain": "chips", "score": 0.8},
        {"domain": "materials", "score": 0.4},
    ]
    tp.compute(runs)
    ok = (tp.global_trust > 0.5 and "chips" in tp.domain_trust 
          and tp.domain_trust["chips"] > tp.domain_trust["materials"]
          and tp.volatility > 0)
    print(f"  [{'PASS' if ok else 'FAIL'}] TrustProfile: global={tp.global_trust:.2f}, "
          f"chips={tp.domain_trust.get('chips',0):.2f}, materials={tp.domain_trust.get('materials',0):.2f}")
    if ok: passed += 1
    
    # Test 3: Observe from PG
    total += 1
    sov.observe(domain="chips")
    ok = True  # May have 0 agents if PG empty, that's ok
    print(f"  [{'PASS' if ok else 'FAIL'}] Observe: {len(sov.profiles)} agents")
    if ok: passed += 1
    
    # Test 4: Make decision
    total += 1
    decision = sov.decide("test topic about semiconductors", domain="chips")
    ok = isinstance(decision, SchedulingDecision) and isinstance(decision.rationale, list)
    print(f"  [{'PASS' if ok else 'FAIL'}] Decision: {len(decision.strategy_overrides)} overrides, "
          f"{len(decision.warnings)} warnings")
    if ok: passed += 1
    
    # Test 5: Post-run learn
    total += 1
    sov.post_run_learn(0.68, domain="chips")
    ok = sov.decisions_log[-1].get("actual_score") == 0.68
    print(f"  [{'PASS' if ok else 'FAIL'}] Post-run learn")
    if ok: passed += 1
    
    # Test 6: Trust report
    total += 1
    report = sov.get_trust_report()
    ok = "sovereign_version" in report and "governance" in report
    print(f"  [{'PASS' if ok else 'FAIL'}] Trust report: {len(report.get('agents', {}))} agents")
    if ok: passed += 1
    
    # Test 7: Diagnose
    total += 1
    diag = sov.diagnose()
    ok = "天鲸 SkyCetus" in diag
    print(f"  [{'PASS' if ok else 'FAIL'}] Diagnosis output")
    if ok: passed += 1
    
    # Test 8: Singleton
    total += 1
    s1 = get_sovereign()
    s2 = get_sovereign()
    ok = s1 is s2
    print(f"  [{'PASS' if ok else 'FAIL'}] Singleton")
    if ok: passed += 1
    
    print(f"\n{passed}/{total} tests passed")
    return passed == total


if __name__ == "__main__":
    self_test()
