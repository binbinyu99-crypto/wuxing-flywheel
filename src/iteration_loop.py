# -*- coding: utf-8 -*-
"""
iteration_loop.py v1.0.0 — 五行飞轮 N轮迭代核心循环
=====================================================
Orchestrates multi-round pipeline execution with verification
and residual-driven convergence.

Architecture:
  Round N: Wood→Fire→Earth→Metal(verify)→ResidualEngine→
           if should_iterate: inject seeds → Round N+1
           else: CognitiveGraph→Water→Lux→Report

Usage:
  from iteration_loop import IterationLoop
  loop = IterationLoop()
  result = loop.run("lithium battery recycling", max_rounds=3)

Decision: Robin 2026-05-02 — Task FW2-Loop
"""

import json, time, hashlib, uuid
from counterfactual import CounterfactualEngine
from evidence_chain import EvidenceChain
from confidence_engine import ConfidenceEngine, confidence_label
from debate_engine import DebateEngine
from cognitive_budget import CognitiveBudget
from typing import Dict, List, Optional, Any

VERSION = "2.2.0"  # v2: policy shift tracking (MEU-03)

# Default config
DEFAULT_MAX_ROUNDS = 3
DEFAULT_CONVERGENCE_THRESHOLD = 0.75
DEFAULT_TIMEOUT_S = 600  # 10 min total budget

# ============================================================
# Policy Shift Tracking (MEU-03: flywheel design AGI indicator)
# ============================================================

def compute_policy_shift(seeds_prev: List[str], seeds_curr: List[str]) -> dict:
    """Compute strategy evolution between two rounds.
    
    Measures how much the research direction changed.
    AGI indicator 3: "different iterations produce different plans"
    
    Returns:
        {
            "shift_score": float (0=identical, 1=completely different),
            "new_seeds": int (seeds in curr but not prev),
            "dropped_seeds": int (seeds in prev but not curr),
            "overlap_ratio": float (0-1),
            "jaccard_similarity": float (0-1),
            "content_similarity": float (TF-IDF cosine, 0-1),
        }
    """
    if not seeds_prev or not seeds_curr:
        return {"shift_score": 1.0, "new_seeds": len(seeds_curr or []),
                "dropped_seeds": len(seeds_prev or []),
                "overlap_ratio": 0.0, "jaccard_similarity": 0.0,
                "content_similarity": 0.0}
    
    # Normalize seeds to lowercase strings
    prev_set = set((s.get('angle', str(s)) if isinstance(s, dict) else str(s)).lower().strip() for s in seeds_prev if s)
    curr_set = set((s.get('angle', str(s)) if isinstance(s, dict) else str(s)).lower().strip() for s in seeds_curr if s)
    
    # Jaccard similarity
    intersection = prev_set & curr_set
    union = prev_set | curr_set
    jaccard = len(intersection) / len(union) if union else 0.0
    
    # Overlap ratio
    overlap = len(intersection) / max(len(prev_set), len(curr_set)) if max(len(prev_set), len(curr_set)) > 0 else 0.0
    
    # Content similarity using word overlap (lightweight TF-IDF approximation)
    def tokenize(texts):
        words = set()
        for t in texts:
            s = t.get('angle', str(t)) if isinstance(t, dict) else str(t)
            words.update(s.lower().split())
        return words
    
    prev_words = tokenize(seeds_prev)
    curr_words = tokenize(seeds_curr)
    word_intersection = prev_words & curr_words
    word_union = prev_words | curr_words
    content_sim = len(word_intersection) / len(word_union) if word_union else 0.0
    
    # Composite shift score (higher = more different = more evolution)
    shift_score = 1.0 - (0.4 * jaccard + 0.3 * overlap + 0.3 * content_sim)
    
    return {
        "shift_score": round(shift_score, 4),
        "new_seeds": len(curr_set - prev_set),
        "dropped_seeds": len(prev_set - curr_set),
        "overlap_ratio": round(overlap, 4),
        "jaccard_similarity": round(jaccard, 4),
        "content_similarity": round(content_sim, 4),
    }




class IterationLoop:
    """N-round flywheel iteration with verification-driven convergence."""
    
    def __init__(self, pipeline_module=None, verification_module=None,
                 residual_module=None, cg_module=None, pg_module=None,
                 max_rounds: int = DEFAULT_MAX_ROUNDS,
                 convergence_threshold: float = DEFAULT_CONVERGENCE_THRESHOLD,
                 timeout_s: float = DEFAULT_TIMEOUT_S,
                 llm_fn=None):
        """
        Args:
            pipeline_module: module with phase_wood, phase_fire, phase_earth, phase_metal,
                            phase_water, phase_lux (wuxing_pipeline_v2)
            verification_module: verification.py module
            residual_module: residual_engine.py module
            cg_module: cognitive_graph.py module
            pg_module: pg_storage.py module
            max_rounds: max iteration rounds
            convergence_threshold: stop when convergence >= this
            timeout_s: total time budget
        """
        self.pipeline = pipeline_module
        self.verification = verification_module
        self.residual = residual_module
        self.cg = cg_module
        self.pg = pg_module
        self.max_rounds = max_rounds
        self.convergence_threshold = convergence_threshold
        self.timeout_s = timeout_s
        self.llm_fn = llm_fn
    
    def run(self, topic: str, domain: str = "general",
            initial_seeds: List[str] = None,
            on_round_complete=None) -> dict:
        """
        Execute multi-round iteration loop.
        
        Args:
            topic: analysis topic
            domain: "general", "finance", "technology", "materials"
            initial_seeds: optional starting seeds
            on_round_complete: callback(round_num, round_result) for progress
        
        Returns:
            {
                "topic": str,
                "rounds_completed": int,
                "final_verdict": str,
                "final_composite": float,
                "final_grade": str,
                "convergence": float,
                "converged": bool,
                "stop_reason": str,
                "rounds": [round_result, ...],
                "total_elapsed_s": float,
                "version": str,
            }
        """
        run_id = f"loop-{uuid.uuid4().hex[:8]}-{int(time.time())}"
        t0 = time.time()
        
        print(f"[Loop] Starting: topic='{topic}' domain={domain} max_rounds={self.max_rounds}")
        
        # Initialize residual engine
        if self.residual:
            res_engine = self.residual.ResidualEngine(pg_storage=self.pg)
        else:
            res_engine = None
        
        rounds = []
        current_seeds = initial_seeds
        stop_reason = "max_rounds"

        # Initialize cognitive modules
        enable_counterfactual = True
        enable_evidence = True
        enable_debate = True
        max_rounds = self.max_rounds

        # Confidence tracker
        confidence_tracker = ConfidenceEngine(initial_belief=0.5, alpha=0.3)

        # Evidence chain tracker
        evidence_tracker = EvidenceChain(llm_fn=self.llm_fn)

        # Cognitive budget
        budget = CognitiveBudget()
        
        for round_num in range(1, self.max_rounds + 1):
            # Check timeout
            elapsed = time.time() - t0
            if elapsed > self.timeout_s:
                stop_reason = f"Timeout ({elapsed:.0f}s > {self.timeout_s}s)"
                print(f"[Loop] {stop_reason}")
                break
            
            round_id = f"{run_id}-R{round_num}"
            rt0 = time.time()
            
            print(f"\n[Loop] === Round {round_num}/{self.max_rounds} ===")
            
            # ---- PHASE 1: Wood (seed generation) ----
            wood_result = {}
            if self.pipeline:
                try:
                    wood_result = self.pipeline.phase_wood(topic, domain=domain)
                    # Merge with injected seeds from previous round
                    if current_seeds:
                        existing = wood_result.get("seeds", [])
                        # Prepend residual seeds (higher priority)
                        merged = []
                        for s in current_seeds:
                            if isinstance(s, dict):
                                merged.append(s)
                            else:
                                merged.append({"angle": str(s), "priority": "high", "source": "residual"})
                        # Ensure existing seeds are also dicts
                        for s in existing:
                            if isinstance(s, dict):
                                merged.append(s)
                            else:
                                merged.append({"angle": str(s), "priority": "medium"})
                        wood_result["seeds"] = merged[:10]  # Cap at 10
                        print(f"[Loop] Wood: {len(existing)} base + {len(current_seeds)} residual seeds")
                except Exception as e:
                    print(f"[Loop] Wood error: {e}")
                    wood_result = {"seeds": current_seeds or [], "error": str(e)}
            
            # ---- PHASE 2: Fire (analysis) ----
            fire_result = {}
            if self.pipeline:
                try:
                    # In R2+, pass prior analysis as context for deepening
                    fire_seeds = wood_result.get("seeds")
                    fire_result = self.pipeline.phase_fire(
                        topic, seeds=fire_seeds, domain=domain)
                except Exception as e:
                    print(f"[Loop] Fire error: {e}")
                    fire_result = {"analysis": "", "error": str(e)}
            
            # ---- PHASE 3: Earth (synthesis) ----
            earth_result = {}
            if self.pipeline:
                try:
                    earth_result = self.pipeline.phase_earth(
                        wood_result, fire_result, topic)
                except Exception as e:
                    print(f"[Loop] Earth error: {e}")
                    earth_result = {"synthesis": {}, "error": str(e)}
            
            # ---- PHASE 4: Metal (verification) ----
            metal_result = {}
            verification_result = {}
            if self.pipeline:
                try:
                    metal_result = self.pipeline.phase_metal(earth_result, topic)
                    # Extract verification-compatible result
                    verification_result = {
                        "verdict": metal_result.get("verdict", "FAIL"),
                        "composite_score": metal_result.get("composite_score", 0),
                        "dimensions": metal_result.get("dimensions", {}),
                        "critiques": metal_result.get("adversarial", {}),
                        "agent_eval": metal_result.get("agent_eval", {}),
                    }
                except Exception as e:
                    print(f"[Loop] Metal error: {e}")
                    metal_result = {"verdict": "FAIL", "composite_score": 0}
                    verification_result = metal_result
            
            # ---- PHASE 5: Residual Engine ----
            residual_result = {}
            should_iterate = False
            iterate_reason = "No residual engine"
            
            if res_engine:
                residual_result = res_engine.process(
                    verification_result, earth_result, topic, round_id, round_num)
                should_iterate = residual_result.get("should_iterate", False)
                iterate_reason = residual_result.get("iterate_reason", "")
                current_seeds = residual_result.get("next_seeds", [])

                # R2+: Add weak dimension focus seeds from previous Metal
                if rounds and round_num > 1:
                    prev_dims = rounds[-1].get("dimensions", {})
                    weak_dims = [k for k, v in prev_dims.items()
                                if isinstance(v, (int, float)) and v < 0.5]
                    if weak_dims:
                        dim_seeds = [f"补充分析：{d.replace('_', ' ')}" for d in weak_dims[:3]]
                        current_seeds = (current_seeds or []) + dim_seeds
                        print(f"[Loop] R{round_num} weak_dims focus: {weak_dims[:3]}")
            
            
            # P1 post-Metal cognitive analysis
            earth_text = ""
            if isinstance(earth_result, dict):
                earth_text = str(earth_result.get("synthesis", earth_result.get("executive_summary", "")))
            elif isinstance(earth_result, str):
                earth_text = earth_result
            
            # MEU-06: Confidence update
            metal_score = metal_result.get("composite_score", 0.5) if isinstance(metal_result, dict) else 0.5
            cf_penalty = 0.0
            counterfactual_result = {}
            evidence_result = {}
            debate_result = {}
            
            if enable_counterfactual and hasattr(self, 'llm_fn') and self.llm_fn and earth_text:
                try:
                    cf_engine = CounterfactualEngine(llm_fn=self.llm_fn)
                    counterfactual_result = cf_engine.analyze(earth_text)
                    cf_penalty = counterfactual_result.get("avg_plausibility", 0) * 0.5
                    print(f"[Loop] R{round_num} Counterfactual: rating={counterfactual_result.get('robustness_rating')}, "
                          f"avg_plausibility={counterfactual_result.get('avg_plausibility', 0):.3f}")
                except Exception as e:
                    print(f"[Loop] Counterfactual failed: {e}")
            
            if enable_evidence and evidence_tracker and earth_text:
                try:
                    # Build search context from Wood's preserved search sources
                    search_ctx = ""
                    for src in wood_result.get("search_sources", []):
                        if isinstance(src, dict) and src.get("title"):
                            search_ctx += f"- [{src.get('source','')}] {src['title']}: {src.get('snippet','')[:150]}\n"
                    if not search_ctx:
                        # Fallback: use seed angles
                        for s in wood_result.get("seeds", []):
                            if isinstance(s, dict):
                                search_ctx += f"- {s.get('angle', '')[:200]}\n"
                    evidence_result = evidence_tracker.extract(earth_text, search_context=search_ctx)
                    print(f"[Loop] R{round_num} Evidence: grounding={evidence_result.get('grounding_score', 0):.3f}, "
                          f"ungrounded={evidence_result.get('ungrounded_claims', 0)}")
                except Exception as e:
                    print(f"[Loop] Evidence extraction failed: {e}")
            
            # evidence_weight: use grounding_score if positive, else 1.0 (no evidence = neutral)
            _ev_weight = evidence_result.get("grounding_score", 0) if evidence_result else 0
            _ev_weight = _ev_weight if _ev_weight > 0.01 else 1.0
            confidence_update = confidence_tracker.update(
                metal_score, round_num=round_num,
                evidence_weight=_ev_weight,
                counterfactual_penalty=cf_penalty,
            )
            print(f"[Loop] R{round_num} Confidence: belief={confidence_update['belief_after']:.3f}, "
                  f"CI={confidence_update['confidence_interval']}, converged={confidence_update['converged']}")
            
            # Debate only on final round of deep analysis
            if enable_debate and round_num == max_rounds and hasattr(self, 'llm_fn') and self.llm_fn:
                try:
                    top_claim = earth_text[:300] if earth_text else str(metal_result)[:300]
                    debate_engine_inst = DebateEngine(llm_fn=self.llm_fn)
                    debate_result = debate_engine_inst.debate(top_claim, context=topic)
                    print(f"[Loop] Debate verdict={debate_result.get('judge_verdict', {}).get('verdict', 'N/A')}, "
                          f"quality={debate_result.get('debate_quality', 0):.3f}")
                except Exception as e:
                    print(f"[Loop] Debate failed: {e}")
            
            # Compute policy shift (MEU-03: AGI strategy evolution indicator)
            policy_shift = {}
            if round_num > 1 and rounds:
                prev_seeds = rounds[-1].get("phases", {}).get("wood", {}).get("seed_texts", [])
                curr_seed_texts = [s.get("content", s) if isinstance(s, dict) else str(s) 
                                   for s in wood_result.get("seeds", [])]
                policy_shift = compute_policy_shift(prev_seeds, curr_seed_texts)
                print(f"[Loop] R{round_num} Policy Shift: {policy_shift['shift_score']:.3f} "
                      f"(new={policy_shift['new_seeds']}, dropped={policy_shift['dropped_seeds']})")
            
            # Build round result
            round_elapsed = time.time() - rt0
            round_result = {
                "round": round_num,
                "run_id": round_id,
                "verdict": metal_result.get("verdict", "FAIL"),
                "composite_score": metal_result.get("composite_score", 0),
                "residual_count": residual_result.get("residual_count", 0),
                "convergence": residual_result.get("convergence", 0),
                "should_iterate": should_iterate,
                "iterate_reason": iterate_reason,
                "elapsed_s": round(round_elapsed, 1),
                "policy_shift": policy_shift,
                "counterfactual": counterfactual_result,
                "evidence": evidence_result,
                "confidence": confidence_update,
                "debate": debate_result,
                "phases": {
                    "wood": {"seed_count": len(wood_result.get("seeds", [])),
                             "seed_texts": [s.get("content", s) if isinstance(s, dict) else str(s) for s in wood_result.get("seeds", [])]},
                    "fire": {"analysis_length": len(fire_result.get("analysis", "")),
                             "analysis": fire_result.get("analysis", "")},
                    "earth": {"has_synthesis": bool(earth_result.get("synthesis")),
                              "synthesis": earth_result.get("synthesis", {}),
                              "findings": earth_result.get("findings", [])},
                    "metal": metal_result,
                },
            }
            rounds.append(round_result)
            
            # Callback
            if on_round_complete:
                try:
                    on_round_complete(round_num, round_result)
                except Exception:
                    pass
            
            print(f"[Loop] R{round_num}: {round_result['verdict']} "
                  f"{round_result['composite_score']:.2f} "
                  f"residuals={round_result['residual_count']} "
                  f"convergence={round_result['convergence']:.3f} "
                  f"[{round_elapsed:.1f}s]")
            
            # ---- Decision: iterate or stop? ----
            if not should_iterate:
                stop_reason = iterate_reason
                print(f"[Loop] Stopping: {stop_reason}")
                break
            
            if round_num >= self.max_rounds:
                stop_reason = f"Max rounds ({self.max_rounds}) reached"
                print(f"[Loop] {stop_reason}")
                break
            
            print(f"[Loop] Iterating: {iterate_reason}")
        
        # ---- POST-LOOP: CG + Water + Lux + Report ----
        final_round = rounds[-1] if rounds else {}
        final_metal = final_round.get("phases", {}).get("metal", {})
        
        cg_result = {}
        water_result = {}
        lux_result = {}
        report_result = {}
        
        if self.pipeline and final_metal:
            # Cognitive Graph
            if self.cg:
                try:
                    cg_result = self.cg.run_cognitive_analysis(
                        final_metal, earth_result, topic, run_id)
                except Exception as e:
                    print(f"[Loop] CG error: {e}")
            
            # Water
            try:
                water_result = self.pipeline.phase_water(
                    fire_result, final_metal, topic, domain=domain,
                    earth_result=earth_result, cg_result=cg_result)
            except Exception as e:
                print(f"[Loop] Water error: {e}")
            
            # Lux
            try:
                lux_result = {}
                if hasattr(self.pipeline, '_auto_distribute_lux'):
                    lux_result = self.pipeline._auto_distribute_lux(round_result, round_id)
            except Exception as e:
                print(f"[Loop] Lux error: {e}")
        
        total_elapsed = round(time.time() - t0, 1)
        
        result = {
            "topic": topic,
            "domain": domain,
            "run_id": run_id,
            "rounds_completed": len(rounds),
            "final_verdict": final_round.get("verdict", "FAIL"),
            "final_composite": final_round.get("composite_score", 0),
            "final_grade": final_metal.get("grade", "?") if isinstance(final_metal, dict) else "?",
            "convergence": final_round.get("convergence", 0),
            "converged": not final_round.get("should_iterate", True),
            "stop_reason": stop_reason,
            "rounds": rounds,
            "cognitive_budget": budget,
            "confidence_summary": confidence_tracker.get_summary(),
            "confidence_label": confidence_label(
                confidence_tracker.get_summary()["final_belief"],
                confidence_tracker.get_summary()["uncertainty"]
            ),
            "policy_evolution": {
                "total_shifts": [r.get("policy_shift", {}).get("shift_score", 0) for r in rounds if r.get("policy_shift")],
                "avg_shift": sum(r.get("policy_shift", {}).get("shift_score", 0) for r in rounds if r.get("policy_shift")) / max(1, sum(1 for r in rounds if r.get("policy_shift"))),
                "strategy_evolved": any(r.get("policy_shift", {}).get("shift_score", 0) > 0.3 for r in rounds),
            },
            "post_loop": {
                "cg": bool(cg_result),
                "water_seeds": len(water_result.get("new_seeds", water_result.get("seeds", []))),
                "lux_distributed": lux_result.get("total_distributed", 0),
            },
            "total_elapsed_s": total_elapsed,
            "version": VERSION,
        }
        
        print(f"\n[Loop] Complete: {len(rounds)} rounds, "
              f"{result['final_verdict']} {result['final_composite']:.2f}, "
              f"converged={result['converged']}, "
              f"reason='{stop_reason}', "
              f"[{total_elapsed:.1f}s]")
        
        return result


# ============================================================
# Convenience: run_iterative_pipeline
# ============================================================

def run_iterative_pipeline(topic: str, domain: str = "general",
                           max_rounds: int = 3) -> dict:
    """Convenience function that auto-imports modules and runs the loop.
    
    Usage:
        from iteration_loop import run_iterative_pipeline
        result = run_iterative_pipeline("lithium battery recycling")
    """
    import importlib
    
    modules = {}
    for name in ['wuxing_pipeline_v2', 'verification', 'residual_engine',
                  'cognitive_graph', 'pg_storage']:
        try:
            modules[name] = importlib.import_module(name)
        except ImportError:
            modules[name] = None
    
    loop = IterationLoop(
        pipeline_module=modules.get('wuxing_pipeline_v2'),
        verification_module=modules.get('verification'),
        residual_module=modules.get('residual_engine'),
        cg_module=modules.get('cognitive_graph'),
        pg_module=modules.get('pg_storage'),
        max_rounds=max_rounds,
    )
    
    return loop.run(topic, domain=domain)


# ============================================================
# Self-test (no external deps)
# ============================================================

def self_test():
    """Run self-test without external modules."""
    print(f"iteration_loop.py v{VERSION}")
    
    # Test with mock pipeline
    class MockPipeline:
        call_count = 0
        
        def phase_wood(self, topic, domain="general"):
            return {"seeds": ["seed1", "seed2", "seed3"]}
        
        def phase_fire(self, topic, seeds=None, domain="general"):
            MockPipeline.call_count += 1
            quality = min(0.5 + MockPipeline.call_count * 0.15, 0.95)
            text = "Analysis " * int(300 * quality)
            return {"analysis": text}
        
        def phase_earth(self, wood, fire, topic):
            return {
                "synthesis": {
                    "executive_summary": "Test synthesis",
                    "key_findings": [{"finding": "Finding 1"}],
                    "data_gaps": ["Gap 1"] if MockPipeline.call_count < 3 else [],
                    "residual_questions": [],
                    "synthesis_quality": {
                        "seed_coverage": min(0.5 + MockPipeline.call_count * 0.1, 0.9),
                        "actionability": 0.8,
                    },
                }
            }
        
        def phase_metal(self, earth, topic):
            c = MockPipeline.call_count
            composite = min(0.4 + c * 0.15, 0.85)
            return {
                "verdict": "PASS" if composite >= 0.7 else "CONDITIONAL",
                "composite_score": composite,
                "dimensions": {
                    "data_completeness": min(0.5 + c * 0.1, 0.9),
                    "coverage_breadth": min(0.4 + c * 0.15, 0.9),
                    "analysis_depth": min(0.6 + c * 0.1, 0.9),
                    "devil_advocate": min(0.3 + c * 0.1, 0.8),
                    "fact_checker": min(0.4 + c * 0.1, 0.8),
                    "agent_eval": min(0.45 + c * 0.1, 0.85),
                },
                "adversarial": {"devil": "", "fact": ""},
                "agent_eval": {},
            }
        
        def phase_water(self, fire, metal, topic, domain="general",
                        earth_result=None, cg_result=None):
            return {"seeds": ["next_seed_1"]}
        
        def phase_lux(self, topic, metal, run_id):
            return {"total_distributed": 100}
    
    # Import residual_engine for the test
    import residual_engine
    
    mock = MockPipeline()
    loop = IterationLoop(
        pipeline_module=mock,
        residual_module=residual_engine,
        max_rounds=5,
    )
    
    result = loop.run("test topic", domain="general")
    
    print(f"  Rounds: {result['rounds_completed']}")
    print(f"  Final: {result['final_verdict']} {result['final_composite']:.2f}")
    print(f"  Converged: {result['converged']}")
    print(f"  Stop: {result['stop_reason']}")
    
    assert result['rounds_completed'] >= 1
    assert result['final_verdict'] in ('PASS', 'CONDITIONAL', 'FAIL')
    assert 'rounds' in result
    print("  iteration_loop: PASS")
    
    # Verify improvement across rounds
    if len(result['rounds']) >= 2:
        scores = [r['composite_score'] for r in result['rounds']]
        print(f"  Scores: {scores}")
        assert scores[-1] >= scores[0], "Should improve over rounds"
        print("  improvement: PASS")
    
    print("  ALL PASS")
    return True


if __name__ == "__main__":
    self_test()
