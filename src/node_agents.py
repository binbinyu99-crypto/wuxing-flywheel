"""
node_agents.py - 5 Node Agents for 15-Agent Wuxing Architecture
v1.0.0

Transforms stateless phase functions into stateful, adaptive agents.

Each node agent has:
  1. Memory — remembers past analyses, what worked, what failed
  2. Strategy — adapts prompts and parameters based on experience
  3. Edge Signal Reception — listens to incoming generation + control signals
  4. Self-Evaluation — tracks downstream scores for self-improvement
  5. Identity — knows its position in the Wuxing graph

"Smart synapses connecting dumb neurons is backwards.
 Both nodes and edges must have intelligence."
"""

VERSION = "2.0.0-shared-memory"

import json
import time
import hashlib

# V7.5: Persistent shared memory
try:
    import agent_memory_store as ams
    ams.init_schema()
    SHARED_MEMORY = True
except ImportError:
    SHARED_MEMORY = False


class NodeMemory:
    """Persistent memory for a node agent.
    
    Tracks: run history, strategy effectiveness, downstream feedback,
    edge signal history, topic expertise.
    """
    
    def __init__(self, node_id, max_history=30):
        self.node_id = node_id
        self.max_history = max_history
        self.runs = []  # [{topic, domain, output_summary, downstream_score, timestamp}]
        self.strategy_log = []  # [{strategy_name, params, result_score}]
        self.edge_signals_received = []  # [{edge_id, signal_type, content}]
        self.stats = {
            "total_runs": 0,
            "avg_downstream_score": 0.0,
            "best_score": 0.0,
            "worst_score": 1.0,
            "topics_seen": set(),
            "domain_scores": {},  # domain -> [scores]
        }
    
    def record_run(self, topic, domain, output_summary, metadata=None):
        """Record a completed run."""
        entry = {
            "topic_hash": hashlib.md5(topic[:50].encode()).hexdigest()[:8],
            "domain": domain,
            "output_summary": str(output_summary)[:300],
            "timestamp": time.time(),
            "downstream_score": None,
            "metadata": metadata or {},
        }
        self.runs.append(entry)
        if len(self.runs) > self.max_history:
            self.runs = self.runs[-self.max_history:]
        self.stats["total_runs"] += 1
        self.stats["topics_seen"].add(entry["topic_hash"])

        # V7.5: Persist to PG
        if SHARED_MEMORY:
            ams.save_run(self.node_id, entry['topic_hash'], domain,
                        output_summary, strategy_used=metadata.get('strategy') if metadata else None,
                        metadata=metadata)
    
    def record_feedback(self, score):
        """Receive downstream feedback score (0-1)."""
        if self.runs:
            self.runs[-1]["downstream_score"] = score
        
        n = self.stats["total_runs"]
        if n > 0:
            old = self.stats["avg_downstream_score"]
            self.stats["avg_downstream_score"] = old + (score - old) / n
        self.stats["best_score"] = max(self.stats["best_score"], score)
        self.stats["worst_score"] = min(self.stats["worst_score"], score)

        # V7.5: Update PG
        if SHARED_MEMORY:
            ams.update_run_score(self.node_id, score)
        
        # Track by domain
        if self.runs:
            domain = self.runs[-1].get("domain", "general")
            self.stats["domain_scores"].setdefault(domain, []).append(score)
    
    def record_edge_signal(self, edge_id, signal_type, content):
        """Record an incoming edge signal."""
        self.edge_signals_received.append({
            "edge_id": edge_id,
            "signal_type": signal_type,
            "content": str(content)[:200],
            "timestamp": time.time(),
        })

        # V7.5: Log signal to PG
        if SHARED_MEMORY:
            ams.log_signal(edge_id, self.node_id, signal_type, content if isinstance(content, dict) else {'content': str(content)[:200]})
        if len(self.edge_signals_received) > 50:
            self.edge_signals_received = self.edge_signals_received[-50:]
    
    def record_strategy(self, name, params, score=None):
        """Log a strategy choice and its outcome."""
        self.strategy_log.append({
            "name": name,
            "params": params,
            "score": score,
            "timestamp": time.time(),
        })
        if len(self.strategy_log) > 30:
            self.strategy_log = self.strategy_log[-30:]
    
    def get_domain_avg(self, domain):
        """Get average score for a specific domain."""
        scores = self.stats["domain_scores"].get(domain, [])
        return sum(scores) / len(scores) if scores else 0.5
    
    def has_seen_topic(self, topic):
        """Check if we've analyzed this topic before."""
        topic_hash = hashlib.md5(topic[:50].encode()).hexdigest()[:8]
        return topic_hash in self.stats["topics_seen"]
    
    def get_recent_scores(self, n=5):
        """Get last N downstream scores."""
        scored = [r["downstream_score"] for r in self.runs if r.get("downstream_score") is not None]
        return scored[-n:] if scored else []
    
    def summary(self):
        return {
            "node_id": self.node_id,
            "total_runs": self.stats["total_runs"],
            "avg_score": round(self.stats["avg_downstream_score"], 3),
            "best": round(self.stats["best_score"], 3),
            "worst": round(self.stats["worst_score"], 3),
            "topics_seen": len(self.stats["topics_seen"]),
            "domains": {d: round(sum(s)/len(s), 2) for d, s in self.stats["domain_scores"].items() if s},
            "history_len": len(self.runs),
            "strategies_tried": len(self.strategy_log),
            "signals_received": len(self.edge_signals_received),
        }


class NodeAgent:
    """Base class for all 5 node agents."""
    
    element = "base"
    chinese_name = "基"
    beast = "none"
    
    def __init__(self):
        self.memory = NodeMemory(f"node_{self.element}")
        self.active_signals = {}  # Current round's incoming edge signals
    

    def load_from_pg(self):
        """Load persistent state from PG on init."""
        if not SHARED_MEMORY:
            return
        state, stats = ams.load_agent_state(f'node_{self.element}')
        if state and stats:
            # Restore memory stats
            self.memory.stats['total_runs'] = stats.get('total_runs', 0)
            self.memory.stats['avg_downstream_score'] = stats.get('avg_score', 0.0)
            self.memory.stats['best_score'] = stats.get('best', 0.0)
            self.memory.stats['worst_score'] = stats.get('worst', 1.0)
            ts = stats.get('topics_seen', [])
            self.memory.stats['topics_seen'] = set(ts) if isinstance(ts, (list, set)) else set()
            # Restore agent-specific state
            for k, v in state.items():
                if hasattr(self, k) and k not in ('memory', 'active_signals'):
                    setattr(self, k, v)
            print(f'[V7.5] {self.element} loaded from PG: {self.memory.stats["total_runs"]} runs')

    def save_to_pg(self):
        """Save current state to PG."""
        if not SHARED_MEMORY:
            return
        # Collect agent-specific state
        state = {}
        for attr in ['current_strategy', 'seed_strategies', 'depth_preference',
                     'synthesis_style', 'skepticism_level', 'pass_threshold',
                     'conditional_threshold', 'exploration_weight', 'direction_history']:
            if hasattr(self, attr):
                state[attr] = getattr(self, attr)
        stats = self.memory.summary()
        ams.save_agent_state(f'node_{self.element}', 'node', self.element, state, stats)

    def get_cross_agent_insight(self, domain):
        """See how OTHER agents are doing on this domain. Shared learning."""
        if not SHARED_MEMORY:
            return {}
        return ams.get_cross_agent_insight(domain)

    def get_best_historical_strategy(self, domain):
        """What strategy worked best historically for this domain?"""
        if not SHARED_MEMORY:
            return None
        return ams.get_best_strategy(f'node_{self.element}', domain)

    def receive_generation_signal(self, edge_id, signal):
        """Receive a nurturing (相生) signal from upstream edge agent."""
        self.active_signals[f"gen_{edge_id}"] = signal
        self.memory.record_edge_signal(edge_id, "generation", signal)
    
    def receive_control_signal(self, edge_id, signal):
        """Receive a restraining (相克) signal from controlling edge agent."""
        self.active_signals[f"ctrl_{edge_id}"] = signal
        self.memory.record_edge_signal(edge_id, "control", signal)
    
    def clear_signals(self):
        """Clear signals after processing (ready for next round)."""
        self.active_signals = {}
    
    def adapt_prompt(self, base_prompt, topic, domain):
        """Adapt the LLM prompt based on memory and signals.
        Override in subclasses for element-specific adaptation.
        """
        additions = []
        
        # Memory-based adaptation
        if self.memory.has_seen_topic(topic):
            additions.append("NOTE: You have analyzed this topic before. Build on previous insights, don't repeat.")
        
        recent_scores = self.memory.get_recent_scores(3)
        if recent_scores and sum(recent_scores)/len(recent_scores) < 0.4:
            additions.append("IMPORTANT: Recent analyses scored low. Be more specific, use more data, and cite sources.")
        
        domain_avg = self.memory.get_domain_avg(domain)
        if domain_avg < 0.4:
            additions.append(f"CAUTION: Your {domain} domain analyses tend to score low ({domain_avg:.1f}). Extra rigor needed.")
        
        # Edge signal adaptation
        for sig_key, sig_data in self.active_signals.items():
            if isinstance(sig_data, dict):
                if sig_data.get("intervention"):
                    action = sig_data.get("action", "")
                    if action == "flag":
                        risks = sig_data.get("risks", [])
                        additions.append(f"EDGE CONTROL WARNING: {len(risks)} risks flagged — avoid absolute claims.")
                    elif action == "constrain":
                        flagged = sig_data.get("flagged_seeds", [])
                        additions.append(f"EDGE CONTROL: {len(flagged)} angles overlap with disproven claims — diversify.")
                    elif action == "dampen_skepticism":
                        additions.append("EDGE CONTROL: System detecting over-skepticism — be more balanced.")
                    elif action == "direction_change":
                        additions.append("EDGE CONTROL: Topic direction failing — pivot to new angles.")
        
        if additions:
            return base_prompt + "\n\n" + "\n".join(additions)
        return base_prompt
    
    def feedback(self, score):
        """Receive downstream feedback."""
        self.memory.record_feedback(score)
    
    def summary(self):
        return {
            "element": self.element,
            "chinese": self.chinese_name,
            "beast": self.beast,
            "memory": self.memory.summary(),
            "active_signals": len(self.active_signals),
        }


class WoodAgent(NodeAgent):
    """木/青龙: Seed Generation Agent
    
    Generates diverse research angles. Adapts based on:
    - Which seed types historically score well (strategy memory)
    - Water→Wood direction signal (residual-driven seeds)
    - Metal→Wood constraint (avoid disproven angles)
    """
    
    element = "wood"
    chinese_name = "木"
    beast = "qinglong"
    
    def __init__(self):
        super().__init__()
        self.seed_strategies = {
            "balanced": {"weight": 1.0, "desc": "Equal mix of dimensions"},
            "data_heavy": {"weight": 1.0, "desc": "Focus on quantitative angles"},
            "contrarian": {"weight": 1.0, "desc": "Emphasize non-obvious angles"},
            "gap_filling": {"weight": 1.0, "desc": "Target known weak areas"},
        }
        self.current_strategy = "balanced"
    
        # V7.5: Load persistent state
        self.load_from_pg()
    def select_strategy(self, domain):
        """Select seed generation strategy based on memory."""

        # V7.5: Check PG for historically best strategy
        if SHARED_MEMORY:
            best = self.get_best_historical_strategy(domain)
            if best and best.get('count', 0) >= 3 and best.get('avg_score', 0) > 0.65:
                return best['strategy']  # Proven winner
        recent = self.memory.get_recent_scores(5)
        
        if not recent:
            # v8.0.2: Fallback to PG stats when runs empty
            pg_avg = self.memory.stats.get("avg_downstream_score", 0)
            pg_runs = self.memory.stats.get("total_runs", 0)
            if pg_runs >= 2 and pg_avg > 0:
                avg = pg_avg
                recent = [pg_avg]  # Synthetic for threshold checks
            else:
                return "balanced"
        
        avg = sum(recent) / len(recent)  # Uses PG fallback if set above
        
        # If scores declining, switch strategy
        if len(recent) >= 2 and recent[-1] < recent[0] - 0.05:
            # Try contrarian if we've been doing balanced
            if self.current_strategy == "balanced":
                return "contrarian"
            elif self.current_strategy == "contrarian":
                return "data_heavy"
            else:
                return "gap_filling"
        
        # v8.0: CONDITIONAL range -> try data_heavy for grounding
        if 0.4 <= avg < 0.65 and self.current_strategy == "balanced":
            return "data_heavy"

        # If doing well, stay the course
        if avg > 0.65:
            return self.current_strategy
        
        # Low scores → data_heavy (more grounded)
        if avg < 0.4:
            return "data_heavy"
        
        return self.current_strategy
    
    def adapt_prompt(self, base_prompt, topic, domain):
        """Wood-specific prompt adaptation."""
        prompt = super().adapt_prompt(base_prompt, topic, domain)
        
        # Strategy-based adaptation
        strategy = self.select_strategy(domain)
        self.current_strategy = strategy
        
        strategy_instructions = {
            "balanced": "",
            "data_heavy": "\nSTRATEGY: Focus on quantitative, data-driven angles. Market sizes, growth rates, specific numbers.",
            "contrarian": "\nSTRATEGY: Emphasize non-obvious, contrarian angles. What is everyone missing?",
            "gap_filling": "\nSTRATEGY: Focus on filling gaps from previous analysis rounds. Target weak dimensions.",
        }
        prompt += strategy_instructions.get(strategy, "")
        
        # Water→Wood direction signal
        water_signal = self.active_signals.get("gen_water_generates_wood")
        if isinstance(water_signal, dict):
            residual_seeds = water_signal.get("residual_seeds", [])
            if residual_seeds:
                seed_text = "\n".join(f"- {s.get('angle','')[:80]}" for s in residual_seeds[:5] if isinstance(s, dict))
                prompt += f"\n\nDIRECTION FROM PREVIOUS ROUND (must incorporate):\n{seed_text}"
        
        self.memory.record_strategy(strategy, {"domain": domain})
        return prompt
    
    def post_run(self, seeds, topic, domain):
        """Post-processing after seed generation."""
        self.memory.record_run(topic, domain, f"{len(seeds)} seeds generated")
        self.clear_signals()
        self.save_to_pg()  # V7.5: Persist


class FireAgent(NodeAgent):
    """火/朱雀: Deep Analysis Agent
    
    Conducts thorough analysis. Adapts based on:
    - Wood→Fire seed quality signal
    - Water→Fire sunk cost signal (abort if direction failing)
    - Historical analysis depth that scored well
    """
    
    element = "fire"
    chinese_name = "火"
    beast = "zhuque"
    
    def __init__(self):
        super().__init__()
        self.depth_preference = "standard"  # "shallow", "standard", "deep"
        self.successful_patterns = []  # What analysis patterns scored high
    
        # V7.5: Load persistent state
        self.load_from_pg()
    def adapt_prompt(self, base_prompt, topic, domain):
        """Fire-specific prompt adaptation."""
        prompt = super().adapt_prompt(base_prompt, topic, domain)
        
        # Adapt depth based on historical performance
        recent = self.memory.get_recent_scores(3)
        if recent:
            avg = sum(recent) / len(recent)
            if avg < 0.4:
                self.depth_preference = "deep"
                prompt += "\n\nDEPTH: Go DEEPER than usual. Previous analyses lacked depth. Provide extensive data, multiple sources, and detailed breakdowns."
            elif avg > 0.8:
                self.depth_preference = "standard"
                # High scores — maintain approach
        
        # Water→Fire sunk cost signal
        sunk_cost = self.active_signals.get("ctrl_water_controls_fire")
        if isinstance(sunk_cost, dict) and sunk_cost.get("intervention"):
            if sunk_cost.get("action") == "direction_change":
                prompt += "\n\nWARNING: This topic direction has been failing repeatedly. Consider fundamentally different analytical framing."
        
        return prompt
    
    def post_run(self, analysis, topic, domain):
        """Post-processing after analysis."""
        self.memory.record_run(topic, domain, f"analysis {len(analysis)} chars", 
                              {"depth": self.depth_preference})
        self.clear_signals()
        self.save_to_pg()  # V7.5: Persist


class EarthAgent(NodeAgent):
    """土/中枢: Ground Truth Synthesis Agent (CENTER)
    
    The hub of the Wuxing system. Synthesizes all inputs.
    Adapts based on:
    - Fire→Earth analysis quality signal
    - Wood→Earth hallucination control signal
    - Historical synthesis patterns that produced actionable output
    """
    
    element = "earth"
    chinese_name = "土"
    beast = "center"
    
    def __init__(self):
        super().__init__()
        self.synthesis_style = "balanced"  # "conservative", "balanced", "aggressive"
    
        # V7.5: Load persistent state
        self.load_from_pg()
    def adapt_prompt(self, base_prompt, topic, domain):
        """Earth-specific prompt adaptation."""
        prompt = super().adapt_prompt(base_prompt, topic, domain)
        
        # Hallucination warnings from Wood→Earth control
        hall_signal = self.active_signals.get("ctrl_wood_controls_earth")
        if isinstance(hall_signal, dict) and hall_signal.get("intervention"):
            risks = hall_signal.get("risks", [])
            prompt += f"\n\nHALLUCINATION WARNING: {len(risks)} risky claims detected in input seeds. Be extra careful to verify claims against the Fire analysis. Do not accept unsubstantiated assertions."
        
        # Coverage signal from Fire→Earth edge
        coverage_signal = self.active_signals.get("gen_fire_generates_earth")
        if isinstance(coverage_signal, dict):
            cov = coverage_signal.get("coverage", 1.0)
            if cov < 0.3:
                prompt += "\n\nCOVERAGE WARNING: Fire analysis covers less than 30% of seed angles. Explicitly flag unaddressed angles as data gaps."
        
        # Adapt synthesis style based on history
        recent = self.memory.get_recent_scores(3)
        if recent:
            avg = sum(recent) / len(recent)
            if avg < 0.4:
                self.synthesis_style = "conservative"
                prompt += "\n\nSTYLE: Be CONSERVATIVE. Only include findings with clear evidence. Mark everything else as uncertain."
            elif avg > 0.8:
                self.synthesis_style = "balanced"
        
        return prompt
    
    def post_run(self, synthesis, topic, domain):
        """Post-processing after synthesis."""
        findings_count = len(synthesis.get("key_findings", [])) if isinstance(synthesis, dict) else 0
        self.memory.record_run(topic, domain, f"{findings_count} findings, style={self.synthesis_style}",
                              {"style": self.synthesis_style})
        self.clear_signals()
        self.save_to_pg()  # V7.5: Persist


class MetalAgent(NodeAgent):
    """金/白虎: Adversarial Verification Agent
    
    Validates and stress-tests. Adapts based on:
    - Earth→Metal verification intensity signal
    - Fire→Metal skepticism control signal
    - Calibration of scoring thresholds based on history
    """
    
    element = "metal"
    chinese_name = "金"
    beast = "baihu"
    
    def __init__(self):
        super().__init__()
        self.skepticism_level = 0.5  # 0=lenient, 1=harsh
        self.pass_threshold = 0.70
        self.conditional_threshold = 0.40
    
        # V7.5: Load persistent state
        self.load_from_pg()
    def adapt_thresholds(self):
        """Adapt scoring thresholds based on history."""
        recent = self.memory.get_recent_scores(5)
        if not recent or len(recent) < 3:
            return
        
        avg = sum(recent) / len(recent)
        
        # If consistently passing everything (avg > 0.8), tighten
        if avg > 0.8:
            self.skepticism_level = min(0.8, self.skepticism_level + 0.05)
            self.pass_threshold = min(0.80, self.pass_threshold + 0.02)
        
        # If consistently failing everything (avg < 0.3), loosen
        elif avg < 0.3:
            self.skepticism_level = max(0.2, self.skepticism_level - 0.05)
            self.pass_threshold = max(0.60, self.pass_threshold - 0.02)
    
    def adapt_prompt(self, base_prompt, topic, domain):
        """Metal-specific prompt adaptation."""
        prompt = super().adapt_prompt(base_prompt, topic, domain)
        
        self.adapt_thresholds()
        
        # Earth→Metal intensity signal
        intensity_signal = self.active_signals.get("gen_earth_generates_metal")
        if isinstance(intensity_signal, dict):
            intensity = intensity_signal.get("verification_intensity", "standard")
            if intensity == "thorough":
                prompt += "\n\nINTENSITY: THOROUGH verification required. Earth synthesis quality was low. Apply maximum adversarial rigor."
                self.skepticism_level = min(0.9, self.skepticism_level + 0.1)
            elif intensity == "light":
                prompt += "\n\nINTENSITY: Light verification. Earth synthesis was high quality. Focus on edge cases only."
                self.skepticism_level = max(0.3, self.skepticism_level - 0.1)
        
        # Fire→Metal skepticism control
        skeptic_signal = self.active_signals.get("ctrl_fire_controls_metal")
        if isinstance(skeptic_signal, dict) and skeptic_signal.get("intervention"):
            prompt += "\n\nSKEPTICISM CONTROL: Over-skepticism detected. Be more balanced in your evaluation. Acknowledge strengths, not just weaknesses."
            self.skepticism_level = max(0.3, self.skepticism_level - 0.15)
        
        return prompt
    
    def post_run(self, verdict, score, topic, domain):
        """Post-processing after verification."""
        self.memory.record_run(topic, domain, f"{verdict} {score:.2f}",
                              {"skepticism": self.skepticism_level, "threshold": self.pass_threshold})
        self.clear_signals()
        self.save_to_pg()  # V7.5: Persist


class WaterAgent(NodeAgent):
    """水/玄武: Knowledge Distillation & Direction Agent
    
    Distills knowledge, sets direction for next cycle.
    Adapts based on:
    - Metal→Water residual collection signal
    - Earth→Water memory purification control signal
    - Accumulated wisdom about what topics/directions work
    """
    
    element = "water"
    chinese_name = "水"
    beast = "xuanwu"
    
    def __init__(self):
        super().__init__()
        self.direction_history = []  # [{topic, direction, outcome}]
        self.exploration_weight = 0.3  # 0=exploit only, 1=explore only
    
        # V7.5: Load persistent state
        self.load_from_pg()
    def adapt_exploration(self):
        """Adapt explore/exploit balance based on history."""
        recent = self.memory.get_recent_scores(5)
        if not recent:
            return
        
        avg = sum(recent) / len(recent)
        
        # High scores → more exploitation (deepen what works)
        if avg > 0.7:
            self.exploration_weight = max(0.1, self.exploration_weight - 0.05)
        
        # Low scores → more exploration (try new directions)
        elif avg < 0.4:
            self.exploration_weight = min(0.6, self.exploration_weight + 0.05)
    
    def adapt_prompt(self, base_prompt, topic, domain):
        """Water-specific prompt adaptation."""
        prompt = super().adapt_prompt(base_prompt, topic, domain)
        
        self.adapt_exploration()
        
        # Metal→Water residual signal
        residual_signal = self.active_signals.get("gen_metal_generates_water")
        if isinstance(residual_signal, dict):
            signal_type = residual_signal.get("signal", "expand")
            severity = residual_signal.get("severity", "low")
            weak_dims = residual_signal.get("weak_dimensions", {})
            prioritized = residual_signal.get("prioritized_gaps", [])
            
            if signal_type == "direction_change":
                prompt += "\n\nDIRECTION: CRITICAL — verification failed. Generate seeds that fundamentally rethink the approach."
                self.exploration_weight = 0.8  # Force exploration
            elif signal_type == "refine":
                gaps_text = ", ".join(f"{g['dimension']}({g['score']:.1f})" for g in prioritized[:5])
                prompt += f"\n\nDIRECTION: REFINE — target these weak dimensions: {gaps_text}"
            
            if residual_signal.get("devil_critique"):
                prompt += f"\n\nADVERSARIAL FEEDBACK: {residual_signal['devil_critique'][:300]}"
        
        # Earth→Water memory purification control
        purify_signal = self.active_signals.get("ctrl_earth_controls_water")
        if isinstance(purify_signal, dict) and purify_signal.get("intervention"):
            flagged = purify_signal.get("flagged_findings", [])
            if flagged:
                prompt += f"\n\nMEMORY PURIFICATION: {len(flagged)} low-confidence findings flagged. Do NOT treat these as established facts."
        
        # Exploration weight
        exploit_pct = int((1 - self.exploration_weight) * 100)
        explore_pct = int(self.exploration_weight * 100)
        prompt += f"\n\nBALANCE: {exploit_pct}% exploit (deepen known areas) / {explore_pct}% explore (new directions)"
        
        return prompt
    
    def post_run(self, new_seeds, topic, domain):
        """Post-processing after distillation."""
        self.memory.record_run(topic, domain, f"{len(new_seeds)} direction seeds",
                              {"exploration": self.exploration_weight})
        self.direction_history.append({
            "topic_hash": hashlib.md5(topic[:50].encode()).hexdigest()[:8],
            "seed_count": len(new_seeds),
            "exploration": self.exploration_weight,
            "timestamp": time.time(),
        })
        if len(self.direction_history) > 20:
            self.direction_history = self.direction_history[-20:]
        self.clear_signals()
        self.save_to_pg()  # V7.8: Fix — Water was missing persistence


# =====================================================
# Node Agent Registry
# =====================================================

class NodeAgentRegistry:
    """Singleton registry for all 5 node agents.
    
    Node agents maintain state across pipeline rounds.
    Combined with EdgeAgentRegistry, forms the complete 15-agent ecosystem.
    """
    
    def __init__(self):
        self.wood = WoodAgent()
        self.fire = FireAgent()
        self.earth = EarthAgent()
        self.metal = MetalAgent()
        self.water = WaterAgent()
        self._agents = {
            "wood": self.wood,
            "fire": self.fire,
            "earth": self.earth,
            "metal": self.metal,
            "water": self.water,
        }
    
    def get(self, element):
        return self._agents.get(element)
    
    def feedback_all(self, metal_score):
        """Propagate Metal's score as feedback to upstream nodes."""
        # Metal score reflects the whole pipeline's quality
        for agent in [self.wood, self.fire, self.earth]:
            agent.feedback(metal_score)
        self.metal.feedback(metal_score)
    
    def save_all_to_pg(self):
        """Persist ALL node agents to PG after feedback. V7.8 fix."""
        for name, agent in self._agents.items():
            try:
                agent.save_to_pg()
            except Exception as e:
                print(f"[V7.8] save_to_pg failed for {name}: {e}")

    def summary(self):
        return {name: agent.summary() for name, agent in self._agents.items()}


def self_test():
    """Self-test of all node agents."""
    print(f"node_agents.py v{VERSION} self-test")
    print("=" * 50)
    
    registry = NodeAgentRegistry()
    passed = 0
    total = 0
    
    # Test 1: WoodAgent strategy selection
    total += 1
    wood = registry.wood
    assert wood.select_strategy("general") == "balanced"  # Default
    # Simulate low scores
    for _ in range(3):
        wood.memory.record_run("test", "general", "test")
        wood.memory.record_feedback(0.3)
    assert wood.select_strategy("general") == "data_heavy"  # Low → data heavy
    passed += 1
    print("  [PASS] WoodAgent strategy adaptation")
    
    # Test 2: MetalAgent threshold adaptation
    total += 1
    metal = registry.metal
    original_threshold = metal.pass_threshold
    # Simulate consistently failing
    for _ in range(5):
        metal.memory.record_run("test", "general", "test")
        metal.memory.record_feedback(0.2)
    metal.adapt_thresholds()
    assert metal.pass_threshold < original_threshold  # Should loosen
    passed += 1
    print(f"  [PASS] MetalAgent threshold: {original_threshold:.2f} -> {metal.pass_threshold:.2f}")
    
    # Test 3: WaterAgent exploration adaptation
    total += 1
    water = registry.water
    original_explore = water.exploration_weight
    for _ in range(5):
        water.memory.record_run("test", "general", "test")
        water.memory.record_feedback(0.2)
    water.adapt_exploration()
    assert water.exploration_weight > original_explore  # Low scores → more exploration
    passed += 1
    print(f"  [PASS] WaterAgent exploration: {original_explore:.2f} -> {water.exploration_weight:.2f}")
    
    # Test 4: Edge signal reception
    total += 1
    earth = registry.earth
    earth.receive_control_signal("wood_controls_earth", {
        "intervention": True,
        "risks": [{"seed": "test", "risk": "absolute_claim"}],
        "action": "flag",
    })
    assert len(earth.active_signals) == 1
    prompt = earth.adapt_prompt("Analyze this", "test", "general")
    assert "HALLUCINATION WARNING" in prompt
    earth.clear_signals()
    assert len(earth.active_signals) == 0
    passed += 1
    print("  [PASS] EarthAgent edge signal reception + prompt adaptation")
    
    # Test 5: FireAgent depth adaptation
    total += 1
    fire = registry.fire
    for _ in range(3):
        fire.memory.record_run("test", "general", "test")
        fire.memory.record_feedback(0.25)
    prompt = fire.adapt_prompt("Analyze this", "test", "general")
    assert "DEEPER" in prompt
    assert fire.depth_preference == "deep"
    passed += 1
    print(f"  [PASS] FireAgent depth adaptation: {fire.depth_preference}")
    
    # Test 6: Registry summary
    total += 1
    summary = registry.summary()
    assert len(summary) == 5
    for name in ["wood", "fire", "earth", "metal", "water"]:
        assert name in summary
        assert "element" in summary[name]
        assert "memory" in summary[name]
    passed += 1
    print(f"  [PASS] Registry: {len(summary)} node agents")
    
    # Test 7: Feedback propagation
    total += 1
    reg2 = NodeAgentRegistry()
    reg2.wood.memory.record_run("test", "general", "test")
    reg2.fire.memory.record_run("test", "general", "test")
    reg2.earth.memory.record_run("test", "general", "test")
    reg2.metal.memory.record_run("test", "general", "test")
    reg2.feedback_all(0.75)
    assert reg2.wood.memory.stats["avg_downstream_score"] == 0.75
    assert reg2.metal.memory.stats["avg_downstream_score"] == 0.75
    passed += 1
    print("  [PASS] Feedback propagation to all nodes")
    
    print(f"\n{passed}/{total} tests passed")
    return passed == total


if __name__ == "__main__":
    self_test()
