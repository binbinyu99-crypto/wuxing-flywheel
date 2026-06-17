"""
wuxing_pipeline_v2.py - Optimized Five Elements Pipeline
Wood+Fire parallel, PG persistence, Hub integration.
"""

import json
import time
import subprocess
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import dim_annotator
    DIM_ANNOTATOR = True
except ImportError:
    DIM_ANNOTATOR = False

VERSION = "v8.4.0-autoprefeed"  # V7.9: Multi-round iteration

# Import shared LLM router
from llm_router import call_llm, MODEL_CONFIG, PHASE_MODEL, strip_code_fences as _strip_code_fences

# === V6.0 Defense Integration ===
try:
    from agent_sandbox import SandboxManager
    from cascade_limiter import CascadeLimiter
    from behavioral_profiler import BehavioralProfiler
    from adaptive_thresholds import AdaptiveThresholds
    DEFENSE_AVAILABLE = True

except ImportError as e:
    print(f'[WARN] Defense modules not available: {e}')
    DEFENSE_AVAILABLE = False

# === V6.2 Extensions ===
try:
    from semantic_filter import SemanticFilter
    from domain_keywords_v2 import detect_domain as detect_domain_v2
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False

# === V6.3 Memory Security ===
try:
    from memory_security import MemorySecurityLayer
    MEMORY_SECURITY = True
except ImportError:
    MEMORY_SECURITY = False

# === V6.4 PG Security Wrapper ===
try:
    from pg_security_wrapper import SecurePGWrapper, integrate_with_pipeline
    PG_SECURITY = True
except ImportError:
    PG_SECURITY = False

# === V7.3 Edge Agents (15-Agent Architecture) ===
try:
    from edge_agents import EdgeAgentRegistry
    _EDGE_REGISTRY = EdgeAgentRegistry(call_llm)
    EDGE_AGENTS = True
    print('[V7.3] Edge agents loaded: 5 generation + 5 control')
except ImportError:
    _EDGE_REGISTRY = None
    EDGE_AGENTS = False

# === V7.4 Node Agents (Stateful 5-Element Agents) ===
try:
    from node_agents import NodeAgentRegistry
    _NODE_REGISTRY = NodeAgentRegistry()
    NODE_AGENTS = True
    print('[V7.4] Node agents loaded: 5 stateful element agents')
except ImportError:
    _NODE_REGISTRY = None
    NODE_AGENTS = False

# === V7.6 Sovereign Scheduler (天鲸 SkyCetus) ===
try:
    from trust_scheduler import get_sovereign
    SOVEREIGN_AVAILABLE = True
    print('[V7.6] SkyCetus Sovereign loaded')
except ImportError:
    SOVEREIGN_AVAILABLE = False


# v8.0: Kernel Arbiter
try:
    from kernel_arbiter import get_kernel
    from memory_types import MemoryItem, MemoryType
    KERNEL_AVAILABLE = True
except ImportError:
    KERNEL_AVAILABLE = False




def defense_check_transfer(defense_ctx, src_phase, tgt_phase, data):
    """V6.0: Validate data transfer between phases"""
    if not defense_ctx.get('enabled'):
        return True, data
    try:
        cascade = defense_ctx['cascade']
        profiler = defense_ctx['profiler']
        adaptive = defense_ctx['adaptive']
        cascade_id = f'pipeline_{src_phase}_{tgt_phase}'
        if not cascade.start_cascade(cascade_id, src_phase):
            print(f'[V6.0 BLOCK] Cascade limit: {src_phase} -> {tgt_phase}')
            return False, data
        profiler.register_agent(src_phase)
        profiler.record_event(src_phase, 'transfer', {'target': tgt_phase, 'size': len(str(data))})
        anomaly_score = min(1.0, len(str(data)) / 100000)
        is_anomaly, threshold = adaptive.detect(anomaly_score)
        if is_anomaly:
            print(f'[V6.0 WARN] Anomaly: {src_phase}->{tgt_phase} score={anomaly_score:.2f}')
            adaptive.feedback(True)
        return True, data
    except Exception as e:
        print(f'[V6.0] Defense check error: {e}')
        return True, data

def init_defense_context():
    """Initialize V6.0 defense layers + V6.3 memory security"""
    msl = MemorySecurityLayer() if MEMORY_SECURITY else None
    
    if not DEFENSE_AVAILABLE:
        return {"enabled": False, "memory_security": msl}
    try:
        sandbox = SandboxManager()
        cascade = CascadeLimiter(max_depth=3, max_concurrent=5)
        profiler = BehavioralProfiler(quarantine_threshold=0.5, min_events_for_classification=3)
        adaptive = AdaptiveThresholds(initial_threshold=0.6)
        for phase in ["wood", "fire", "earth", "metal", "water"]:
            sandbox.create_sandbox(phase)
        xiangsheng = [("wood","fire"),("fire","earth"),("earth","metal"),("metal","water"),("water","wood")]
        for src, tgt in xiangsheng:
            sandbox.register_allowed_communication(src, tgt)
        print("[V6.0] Defense layers initialized")
        return {"sandbox": sandbox, "cascade": cascade, "profiler": profiler, "adaptive": adaptive, "enabled": True, "memory_security": msl}
    except Exception as e:
        print(f"[V6.0] Defense init failed: {e}")
        return {"enabled": False, "memory_security": msl}


def _strip_code_fences_legacy(text):
    """Strip markdown code fences from LLM responses."""
    import re
    if not text:
        return text
    text = text.strip()
    match = re.search(r'''```(?:json)?\s*\n?(\{.*?\})\s*\n?```''', text, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r'''```(?:json)?\s*(\{.*?\})\s*```''', text, re.DOTALL)
    if match:
        return match.group(1)
    return text


try:
    import pg_storage
    PG = True
except:
    PG = False

try:
    import hub_connector
    HUB = True
except:
    HUB = False

try:
    import cognitive_graph
    CG = True
except:
    CG = False

try:
    import eval_agents
    EVAL = True
except:
    EVAL = False

try:
    import verification
    VERIFY = True
except:
    VERIFY = False

try:
    import residual_engine
    RESIDUAL = True
except:
    RESIDUAL = False

try:
    import iteration_loop
    LOOP = True
except:
    LOOP = False

try:
    import water_seed_bridge
    WATER_BRIDGE = True
except:
    WATER_BRIDGE = False

try:
    import report_generator
    REPORT = True
except:
    REPORT = False

# v5.5: Post-processing integration
try:
    from pipeline_integrator import post_process_pipeline
    _POST_PROCESS = True
except ImportError:
    _POST_PROCESS = False


# Model configuration and call_llm are imported from llm_router.py
# (Local shadows removed in v8.3.0 to enable PsyLabs routing)

def _pg_safe(func, *args, **kwargs):
    """Safely call a pg_storage function, ignoring errors."""
    if not PG:
        return None
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"[PG] Warning: {e}")
        return None

def phase_wood(topic, domain="general"):
    """Wood/Qinglong: Enhanced seed generation with search + creative techniques."""
    t0 = time.time()
    
    # Gather search context and creative angles
    search_context = ""
    search_data = {}  # Will be populated by search
    creative_context = ""
    try:
        from smart_search import search_for_seeds
        search_data = search_for_seeds(topic, seed_count=5)
        if search_data.get("web_results"):
            titles = [r.get("title","") for r in search_data["web_results"][:5] if r.get("title")]
            snippets = [r.get("snippet","")[:120] for r in search_data["web_results"][:3] if r.get("snippet")]
            if titles:
                search_context = "\nRelevant sources: " + "; ".join(titles)
            if snippets:
                search_context += "\nKey data points: " + " | ".join(snippets)
            print("[Wood] Search: {} results via {}".format(
                len(search_data["web_results"]), search_data.get("search_strategy", "?")))
        if search_data.get("seed_angles"):
            angles = [s.get("angle","")[:60] for s in search_data["seed_angles"][:4]]
            creative_context = "\nCreative thinking prompts: " + "; ".join(angles)
            print("[Wood] Creative angles: {}".format(len(search_data["seed_angles"])))
    except Exception as e:
        print("[Wood] Search enhancement skipped: {}".format(e))
    

    # V7.9: Load prior Water seeds from PG for multi-round iteration
    prior_seed_context = ""
    try:
        if WATER_BRIDGE:
            prior_seeds = water_seed_bridge.get_prior_seeds(domain, limit=3)
            if prior_seeds:
                prior_angles = [s.get('angle', s.get('direction', str(s)))[:120] for s in prior_seeds[:8]]
                prior_seed_context = "\nPrior research directions (from previous analysis rounds - build on these, don't repeat): " + "; ".join(prior_angles)
                print(f"[Wood V7.9] Loaded {len(prior_seeds)} prior seeds from Water bridge")
    except Exception as e:
        print(f"[Wood V7.9] Prior seed loading skipped: {e}")
    
    prompt = ("As a seed generator for industry analysis, generate 5-8 diverse research angles for: {}\n"
              "Domain: {}\n"
              "{}\n"
              "{}\n"
              "{}\n"
              "Requirements:\n"
              "1. Each angle should be specific and actionable\n"
              "2. Cover different dimensions: market size, technology, competition, policy, supply chain, risk\n"
              "3. Include at least one contrarian/non-obvious angle\n"
              "4. Output as JSON array of objects with 'angle' and 'priority' (high/medium/low) fields.").format(
                  topic, domain, search_context, creative_context, prior_seed_context)
    

    # V7.4: Node Agent adaptation
    if NODE_AGENTS:
        prompt = _NODE_REGISTRY.wood.adapt_prompt(prompt, topic, domain)
        strategy = _NODE_REGISTRY.wood.current_strategy
        print(f'[V7.4 Wood] strategy={strategy}, signals={len(_NODE_REGISTRY.wood.active_signals)}')
    result = call_llm(prompt, model=PHASE_MODEL["wood"], thinking_budget=200)
    elapsed = time.time() - t0
    
    seeds = []
    if result:
        try:
            start = result.find('[')
            end = result.rfind(']') + 1
            if start >= 0 and end > start:
                seeds = json.loads(result[start:end])
        except:
            seeds = [{"angle": result[:200], "priority": "medium"}]
    
    output = {"phase": "wood", "seeds": seeds, "elapsed": elapsed, "raw_length": len(result or ""),
              "search_enhanced": bool(search_context), "creative_enhanced": bool(creative_context),
              "search_sources": [{"title": r.get("title",""), "snippet": r.get("snippet","")[:200], "source": r.get("source","")} for r in search_data.get("web_results", [])[:8]]}
    
    for s in seeds:
        sid = hashlib.md5(s.get("angle", "")[:50].encode()).hexdigest()[:12]
        _pg_safe(pg_storage.wood_save_seed, f"seed-{sid}", s.get("angle", ""), domain)
    

    # V7.4: Node Agent post-run
    if NODE_AGENTS:
        _NODE_REGISTRY.wood.post_run(seeds, topic, domain)
    return output


def phase_fire(topic, seeds=None, domain="general"):
    """Fire/Zhuque: Deep execution analysis using all Wood seeds."""
    t0 = time.time()
    
    seed_text = ""
    if seeds:
        # Use ALL seeds, not just first 3
        seed_lines = []
        for i, s in enumerate(seeds):
            angle = s.get("angle", str(s)) if isinstance(s, dict) else str(s)
            priority = s.get("priority", "medium") if isinstance(s, dict) else "medium"
            seed_lines.append("{}. [{}] {}".format(i+1, priority, angle))
        seed_text = "\n".join(seed_lines)
    
    # Check if we have residual seeds (from iteration R2+)
    has_residuals = any(
        isinstance(s, dict) and s.get("source") == "residual" 
        for s in (seeds or [])
    )
    deepening_instruction = ""
    if has_residuals:
        deepening_instruction = ("\nIMPORTANT: This is an iteration round. The research angles marked [high] "
                                  "are gaps identified from a previous analysis round. Focus on FILLING THESE GAPS "
                                  "with specific data, evidence, and deeper analysis. Do not repeat general information.\n")
    
    # V8.5: Upgraded Fire/朱雀 prompt — cognitive identity + structured output
    prompt = ("You are 朱雀 (Zhuque), the Fire agent of the 五行飞轮 cognitive engine.\n"
              "Your role: TRANSFORM raw research seeds into deep, actionable analysis.\n"
              "Like fire, you burn away surface-level thinking and forge insights from raw material.\n\n"
              "## TOPIC\n{}\n\n"
              "## DOMAIN\n{}\n\n"
              "{}\n"
              "## RESEARCH ANGLES FROM WOOD PHASE\n{}\n\n"
              "## YOUR MISSION\n"
              "For EACH research angle, produce a structured analysis block:\n\n"
              "### [Angle Title]\n"
              "**Evidence Layer** (what is verifiably true):\n"
              "- Cite specific numbers, dates, sources. No vague claims.\n"
              "- Distinguish VERIFIED data (with source) from ESTIMATES (with reasoning).\n\n"
              "**Mechanism Layer** (why/how it works):\n"
              "- Causal chain: A causes B because C.\n"
              "- Identify the driving forces, not just correlations.\n\n"
              "**Tension Layer** (what conflicts or could go wrong):\n"
              "- Internal contradictions in the data\n"
              "- Competing forces that could reverse the trend\n"
              "- What the consensus is missing\n\n"
              "**Actionability Layer** (so what?):\n"
              "- Concrete implications for decision-makers\n"
              "- Time horizon: is this a 3-month or 3-year dynamic?\n"
              "- Confidence: HIGH (multiple sources agree) / MEDIUM (plausible but gaps) / LOW (speculative)\n\n"
              "## OUTPUT RULES\n"
              "1. NEVER start with generic overviews. Jump straight into specific findings.\n"
              "2. Every claim must have either a data source or explicit 'ESTIMATE:' prefix.\n"
              "3. If you don't know something, say 'DATA GAP:' — do not fabricate.\n"
              "4. Prioritize non-obvious insights over well-known facts.\n"
              "5. End with a SYNTHESIS: 2-3 sentences connecting the most important cross-cutting themes.\n"
              "6. Output in Chinese (中文输出).").format(
                  topic, domain, deepening_instruction, seed_text or "Cover: market size, key players, tech trends, risks, supply chain, policy")
    

    # V7.4: Node Agent adaptation
    if NODE_AGENTS:
        prompt = _NODE_REGISTRY.fire.adapt_prompt(prompt, topic, domain)
        print(f'[V7.4 Fire] depth={_NODE_REGISTRY.fire.depth_preference}, signals={len(_NODE_REGISTRY.fire.active_signals)}')
    result = call_llm(prompt, model=PHASE_MODEL["fire"], thinking_budget=500)
    elapsed = time.time() - t0
    
    output = {"phase": "fire", "analysis": result or "", "elapsed": elapsed,
              "seeds_used": len(seeds) if seeds else 0}
    _pg_safe(pg_storage.fire_save_execution, f"fire-{int(time.time())}", topic, seeds or [], result or "", 0.7, elapsed, PHASE_MODEL.get("fire", "unknown"))

    # V7.4: Node Agent post-run
    if NODE_AGENTS:
        _NODE_REGISTRY.fire.post_run(result or '', topic, domain)
    return output


def phase_earth(wood_result, fire_result, topic):
    """Earth/Hub (土): Ground truth synthesis center.
    
    The CENTER of 五行飞轮. Synthesizes Wood seeds and Fire analysis
    into a coherent, structured deliverable document.
    Model: Qwen/Bailian (通义千问)
    
    Outputs:
    - Executive summary (3 sentences max)
    - Key findings with confidence levels
    - Data gaps and assumptions made
    - Actionable recommendations
    - Residual questions for next cycle
    """
    t0 = time.time()
    
    seeds = wood_result.get("seeds", [])
    analysis = fire_result.get("analysis", "")
    seed_angles = [(s.get("angle", s.get("seed", "")) if isinstance(s, dict) else str(s))[:100] for s in seeds[:5]]
    
    prompt = f"""You are the Ground Truth Synthesizer (土/Earth) in a five-element analysis system.

Your role: Take raw research seeds and deep analysis, and produce a STRUCTURED DELIVERABLE.

TOPIC: {topic}

RESEARCH SEEDS (from Wood/青龙):
{json.dumps(seed_angles, ensure_ascii=False, indent=2)}

DEEP ANALYSIS (from Fire/朱雀):
{analysis[:1800]}

Produce a JSON response with this exact structure:
{{
    "executive_summary": "3 sentences max. The core insight.",
    "key_findings": [
        {{"finding": "...", "confidence": "high/medium/low", "evidence": "..."}},
        ...
    ],
    "data_gaps": ["What we don't know but assumed", ...],
    "recommendations": [
        {{"action": "...", "priority": "P0/P1/P2", "rationale": "..."}},
        ...
    ],
    "residual_questions": ["Questions for the next analysis cycle", ...],
    "synthesis_quality": {{
        "seed_coverage": 0.0-1.0,
        "analysis_grounding": 0.0-1.0,
        "actionability": 0.0-1.0
    }}
}}

Rules:
- Every finding must cite evidence from the analysis
- Recommendations must be specific and actionable (who/what/when)
- Residual questions feed the Water phase for next-cycle seeds
- Be honest about confidence levels - low confidence is fine
- Output ONLY valid JSON, no other text"""


    # V7.4: Node Agent adaptation
    if NODE_AGENTS:
        prompt = _NODE_REGISTRY.earth.adapt_prompt(prompt, topic, domain if 'domain' in dir() else 'general')
        print(f'[V7.4 Earth] style={_NODE_REGISTRY.earth.synthesis_style}, signals={len(_NODE_REGISTRY.earth.active_signals)}')
    result = call_llm(prompt, model=PHASE_MODEL["earth"], timeout=90, thinking_budget=0, max_tokens=4000)
    elapsed = time.time() - t0
    
    # Parse structured synthesis
    synthesis = {}
    if result:
        cleaned = _strip_code_fences(result)
        try:
            synthesis = json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find JSON in response
            import re
            json_match = re.search(r'\{[\s\S]*\}', cleaned)
            if json_match:
                try:
                    synthesis = json.loads(json_match.group())
                except:
                    synthesis = {"raw_output": cleaned[:2000], "parse_failed": True}
            else:
                synthesis = {"raw_output": cleaned[:2000], "parse_failed": True}
    
    # Ensure required fields exist
    synthesis.setdefault("executive_summary", "Synthesis incomplete")
    synthesis.setdefault("key_findings", [])
    synthesis.setdefault("data_gaps", [])
    synthesis.setdefault("recommendations", [])
    synthesis.setdefault("residual_questions", [])
    synthesis.setdefault("synthesis_quality", {})
    
    # Add metadata
    synthesis["topic"] = topic
    synthesis["seed_count"] = len(seeds)
    synthesis["analysis_length"] = len(analysis)
    synthesis["model"] = PHASE_MODEL.get("earth", "bailian")
    
    # Persist to PG knowledge store
    _pg_safe(pg_storage.knowledge_store,
        key=f"earth-{topic[:30]}-{int(time.time())}",
        content=json.dumps(synthesis, ensure_ascii=False)[:4000],
        domain="synthesis",
        source="pipeline-earth",
        residual_score=synthesis.get("synthesis_quality", {}).get("actionability", 0.5)
    )


    # V7.4: Node Agent post-run
    if NODE_AGENTS:
        _NODE_REGISTRY.earth.post_run(synthesis, topic, 'general')
        # V8.1: Three-layer dimensional annotation (dim3/dim2/dim1)
    try:
        synthesis = dim_annotator.annotate_synthesis(synthesis)
        _dd = synthesis.get("dim_distribution", {})
        _dg = synthesis.get("dim_gaps", [])
        if _dg:
            print(f"[Earth V8.1] Dim gaps: {_dg}")
        else:
            print(f"[Earth V8.1] Dims: d3={_dd.get('dim3',0)}% d2={_dd.get('dim2',0)}% d1={_dd.get('dim1',0)}%")
    except Exception as _de:
        print(f"[Earth V8.1] dim error: {_de}")

    return {"phase": "earth", "synthesis": synthesis, "elapsed": elapsed}


def phase_metal(earth_result, topic, round_info=None):
    """Metal/White Tiger verification phase — delegates to verification.py."""
    t0 = time.time()
    
    # Extract analysis text from Earth synthesis
    synthesis = earth_result.get("synthesis", {})
    # Build full_analysis from synthesis components
    parts = []
    exec_summary = synthesis.get("executive_summary", "")
    if exec_summary:
        parts.append(exec_summary)
    key_findings = synthesis.get("key_findings", [])
    if key_findings:
        for kf in key_findings:
            if isinstance(kf, dict):
                parts.append(kf.get("finding", str(kf)))
            else:
                parts.append(str(kf))
    recommendations = synthesis.get("recommendations", [])
    if recommendations:
        for rec in recommendations:
            if isinstance(rec, dict):
                parts.append(rec.get("action", str(rec)))
            else:
                parts.append(str(rec))
    data_gaps = synthesis.get("data_gaps", [])
    if data_gaps:
        parts.append("Data gaps: " + "; ".join(str(g)[:100] for g in data_gaps[:5]))
    full_analysis = "\n".join(parts)
    # Fallback: try raw_output or any string content
    if not full_analysis:
        full_analysis = synthesis.get("raw_output", "")
    if not full_analysis:
        full_analysis = str(synthesis)[:3000]
    
    # Extract metadata
    seed_count = synthesis.get("seed_count", 0)
    research_angles = synthesis.get("residual_questions", [])
    if not seed_count:
        seed_count = len(earth_result.get("seeds_used", earth_result.get("wood_seeds", [])))
    analysis_length = len(full_analysis)
    
    # Determine domain
    domain = "general"
    finance_kw = ["stock", "fund", "option", "hedge", "trade", "portfolio",
                  "\u80a1\u7968", "\u57fa\u91d1", "\u671f\u6743", "\u5bf9\u51b2", "\u4ea4\u6613"]
    tech_kw = ["AI", "chip", "semiconductor", "software", "cloud",
               "\u82af\u7247", "\u534a\u5bfc\u4f53", "\u4eba\u5de5\u667a\u80fd"]
    mat_kw = ["material", "alloy", "composite", "polymer",
              "\u6750\u6599", "\u5408\u91d1", "\u590d\u5408\u6750\u6599"]
    topic_lower = topic.lower()
    if any(kw in topic_lower for kw in finance_kw):
        domain = "finance"
    elif any(kw in topic_lower for kw in tech_kw):
        domain = "technology"
    elif any(kw in topic_lower for kw in mat_kw):
        domain = "materials"
    
    # Create engine with LLM and eval agents
    engine = verification.VerificationEngine(
        domain=domain,
        llm_fn=call_llm,
        eval_module=eval_agents if EVAL else None,
    )
    
    # Build metadata with round context
    meta = {"seed_count": seed_count, "analysis_length": analysis_length}
    if round_info:
        meta["round_num"] = round_info.get("round_num", 1)
        meta["prev_score"] = round_info.get("prev_score", None)
        meta["prev_weak_dims"] = round_info.get("prev_weak_dims", [])
        # Tell Metal this is a refinement round
        if round_info.get("round_num", 1) > 1:
            full_analysis = f"[ROUND {round_info['round_num']} REFINEMENT - Previous score: {round_info.get('prev_score', 'N/A'):.3f}, Weak areas: {', '.join(round_info.get('prev_weak_dims', []))}]\n\n" + full_analysis

    # Run verification
    result = engine.verify(
        analysis=full_analysis,
        topic=topic,
        seed_count=seed_count,
        research_angles=research_angles,
        metadata=meta,
    )
    
    # Map to legacy format for backward compatibility
    dims = result["dimensions"]
    elapsed = time.time() - t0
    
    metal_result = {
        "verdict": result["verdict"],
        "composite_score": result["composite_score"],
        "dimensions": {
            "data_completeness": dims.get("data_completeness", 0),
            "coverage_breadth": dims.get("coverage_breadth", 0),
            "analysis_depth": dims.get("analysis_depth", 0),
            "seed_utilization": dims.get("seed_utilization", 0),
            "cross_validation": dims.get("cross_validation", 0),
            "devil_advocate": dims.get("devil_advocate", 0),
            "fact_checker": dims.get("fact_checker", 0),
            "agent_composite": dims.get("agent_eval", 0),
        },
        "adversarial": {
            "devil_critique": result["critiques"].get("devil", ""),
            "fact_critique": result["critiques"].get("fact", ""),
        },
        "agent_eval": result.get("agent_eval", {}),
        "elapsed_s": round(elapsed, 1),
        "full_analysis": full_analysis[:500],
        "verification_version": verification.VERSION,
    }
    
    # Save to PG
    _pg_safe(pg_storage.metal_save_audit,
        input_hash=hashlib.md5(full_analysis[:500].encode()).hexdigest(),
        content_preview=full_analysis[:200],
        scores=metal_result["dimensions"],
        verdict=result["verdict"],
        final_score=result["composite_score"],
        adversarial_results=metal_result["adversarial"],
    )
    
    print(f"[Metal] {result['verdict']} {result['composite_score']:.2f} Grade {result['grade']}({result['agent_score']}/10) [{elapsed:.1f}s] domain={domain}")

    # V7.4: Node Agent post-run
    if NODE_AGENTS:
        _NODE_REGISTRY.metal.post_run(result['verdict'], result['composite_score'], topic, domain)
    return metal_result

def phase_water(fire_result, metal_result, topic, domain="general", earth_result=None, cg_result=None):
    """Water/Xuanwu: Knowledge distillation and next-cycle seed generation.
    
    Uses Earth's residual questions + Metal's critique to generate
    high-quality seeds for the next analysis cycle.
    Direction constrainer (Superego layer in psyche model).
    """
    t0 = time.time()
    analysis = fire_result.get("analysis", "")
    
    # Gather Earth residuals if available
    earth_residuals = []
    earth_gaps = []
    if earth_result:
        synth = earth_result.get("synthesis", {})
        earth_residuals = synth.get("residual_questions", [])
        earth_gaps = synth.get("data_gaps", [])
    
    # Metal critique
    devil_critique = metal_result.get("devil_critique", "")
    metal_verdict = metal_result.get("verdict", "")
    metal_dims = metal_result.get("dimensions", {})
    weak_dims = [k for k, v in metal_dims.items() if isinstance(v, (int, float)) and v < 0.5]
    
    # Cognitive graph enrichment
    cg_residuals = []
    cg_patterns = []
    cg_path_weights = None
    if cg_result:
        cg_residuals = cg_result.get("residuals", [])
        cg_patterns = cg_result.get("patterns", [])
        cg_path_weights = cg_result.get("path_weights", {}).get("updated", {})

    new_seeds = []
    if metal_verdict in ("PASS", "CONDITIONAL"):
        residual_section = ""
        if earth_residuals:
            residual_section = "\nEARTH RESIDUAL QUESTIONS:\n" + "\n".join(f"- {q}" for q in earth_residuals[:5])
        if earth_gaps:
            residual_section += "\nDATA GAPS:\n" + "\n".join(f"- {g}" for g in earth_gaps[:5])
        if weak_dims:
            residual_section += f"\nWEAK DIMENSIONS: {', '.join(weak_dims)}"
        if devil_critique:
            residual_section += f"\nADVERSARIAL CRITIQUE: {devil_critique[:300]}"
        
        # Add cognitive graph insights
        if cg_residuals:
            high_sev = sorted(cg_residuals, key=lambda x: x.get("severity",0), reverse=True)[:5]
            residual_section += "\nCOGNITIVE GRAPH RESIDUALS (highest severity):\n"
            residual_section += "\n".join(f"- [{r.get('type','?')}] sev={r.get('severity',0):.1f}: {r.get('label','')[:80]}" for r in high_sev)
        if cg_patterns:
            residual_section += "\nDETECTED PATTERNS:\n"
            residual_section += "\n".join(f"- [{p.get('type','')}] {p.get('description','')[:100]}" for p in cg_patterns[:3])
        if cg_path_weights:
            residual_section += f"\nEXPLORATION WEIGHTS: A(exploit)={cg_path_weights.get('A',65)}% B(adjacent)={cg_path_weights.get('B',25)}% C(paradigm)={cg_path_weights.get('C',10)}%"
        
        prompt = f"""You are Water/玄武: knowledge distillation and direction setting.

TOPIC: {topic}
ANALYSIS: {analysis[:500]}
{residual_section}

Generate 3-5 follow-up research seeds that:
1. Fill identified data gaps (from Earth + Cognitive Graph)
2. Address weak dimensions and high-severity residuals
3. Explore missed angles identified by pattern detection
4. Balance exploitation vs exploration per path weights (A/B/C)
5. Target paradigm gaps where evaluation framework has blind spots

Output JSON array: [{{"angle": "question", "priority": "high/medium/low", "rationale": "why"}}]
Only output JSON array."""
        

    # V7.4: Node Agent adaptation
    if NODE_AGENTS:
        prompt = _NODE_REGISTRY.water.adapt_prompt(prompt, topic, domain)
        print(f'[V7.4 Water] explore={_NODE_REGISTRY.water.exploration_weight:.2f}, signals={len(_NODE_REGISTRY.water.active_signals)}')
        result = call_llm(prompt, model=PHASE_MODEL["water"], thinking_budget=0)
        if result:
            cleaned = _strip_code_fences(result)
            # Strip any reasoning/thinking prefix before JSON array
            import re as _re
            json_match = _re.search(r'\[\s*\{', cleaned)
            if json_match:
                cleaned = cleaned[json_match.start():]
            try:
                start = cleaned.find('[')
                end = cleaned.rfind(']') + 1
                if start >= 0 and end > start:
                    parsed = json.loads(cleaned[start:end])
                    for item in parsed:
                        if isinstance(item, dict):
                            new_seeds.append({
                                "angle": item.get("angle", item.get("question", str(item))),
                                "priority": item.get("priority", "medium"),
                                "rationale": item.get("rationale", ""),
                                "source": "water-distill"
                            })
                        elif isinstance(item, str):
                            new_seeds.append({"angle": item, "priority": "medium", "source": "water-distill"})
            except:
                pass

    elapsed = time.time() - t0

    for s in new_seeds:
        _pg_safe(pg_storage.water_upsert_atom, s.get("angle", "")[:100], domain, source="pipeline")


    # V7.4: Node Agent post-run
    if NODE_AGENTS:
        _NODE_REGISTRY.water.post_run(new_seeds, topic, domain)
    return {"phase": "water", "new_seeds": new_seeds, "elapsed": elapsed}


def _auto_distribute_lux(pipeline_result, executor_id="pipeline"):
    """Auto-distribute Lux rewards after pipeline completion.
    
    Maps pipeline phases to Lux roles:
    - Wood seeds -> creator credit
    - Fire analysis -> executor credit
    - Metal validation -> validator credit
    - Water residuals -> knowledge credit
    - Earth synthesis -> hub credit
    """
    try:
        from lux_engine import distribute_lux
    except ImportError:
        print("[Lux] lux_engine not available, skipping distribution")
        return None
    
    metal = pipeline_result.get("phases", {}).get("metal", {})
    verdict = metal.get("verdict", "FAIL")
    composite = metal.get("composite_score", 0)
    
    # Only distribute if validation passed
    if verdict == "FAIL":
        print("[Lux] Metal verdict FAIL - no Lux distributed")
        return {"distributed": False, "reason": "metal_fail"}
    
    # Determine complexity from analysis depth
    analysis_len = pipeline_result.get("phases", {}).get("fire", {}).get("analysis", "")
    if len(analysis_len) > 3000:
        complexity = "complex"
    elif len(analysis_len) > 1000:
        complexity = "standard"
    else:
        complexity = "simple"
    
    # Determine quality from metal score
    if composite >= 0.85:
        quality = "excellent"
    elif composite >= 0.7:
        quality = "good"
    elif composite >= 0.4:
        quality = "acceptable"
    else:
        quality = "poor"
    
    topic = pipeline_result.get("topic", "unknown")
    task_id = f"pipeline-{hashlib.md5(topic.encode()).hexdigest()[:8]}-{int(time.time())}"
    
    # Knowledge contributors from water seeds
    water_seeds = pipeline_result.get("phases", {}).get("water", {}).get("new_seeds", [])
    knowledge_ids = [f"water-{i}" for i in range(len(water_seeds))] if water_seeds else None
    
    result = distribute_lux(
        task_id=task_id,
        executor_id=executor_id,
        creator_id="wood-generator",
        validator_id="metal-validator",
        knowledge_contributors=knowledge_ids,
        complexity=complexity,
        quality=quality,
        metadata={"topic": topic, "verdict": verdict, "score": composite}
    )
    
    total = result.get("total_lux", result.get("total_distributed", 0))
    print(f"[Lux] Distributed: {total} Lux for {task_id} (quality={quality})")
    return result

def run_pipeline(topic, domain="general", depth="compressed", round_info=None):
    """Run full wuxing pipeline: Wood+Fire parallel -> Earth -> Metal -> Water."""
    t_start = time.time()
    results = {"topic": topic, "domain": domain, "depth": depth, "phases": {}}

    # V7.6: 天鲸 SkyCetus Sovereign Scheduler
    sovereign_decision = None
    if SOVEREIGN_AVAILABLE:
        try:
            sovereign = get_sovereign()
            sovereign.observe(domain=domain)
            sovereign_decision = sovereign.decide(topic, domain=domain)
            if _NODE_REGISTRY and sovereign_decision:
                sovereign.apply_to_node_agents(_NODE_REGISTRY, sovereign_decision)
        except Exception as e:
            print(f'[Sovereign] Pre-run error: {e}')
    
    # Phase 1: Wood + Fire in PARALLEL
    with ThreadPoolExecutor(max_workers=2) as executor:
        wood_future = executor.submit(phase_wood, topic, domain)
        fire_future = executor.submit(phase_fire, topic, None, domain)
        
        wood_result = wood_future.result(timeout=120)
        fire_result = fire_future.result(timeout=120)
    
    results["phases"]["wood"] = wood_result
    results["phases"]["fire"] = fire_result

    # === V7.3: Edge Agent -- Wood generates Fire (Seed Compiler) ===
    if EDGE_AGENTS:
        edge_wf = _EDGE_REGISTRY.wood_fire.transfer(wood_result, topic, domain)
        if not edge_wf.get('blocked'):
            fire_result['seeds_filtered_by_edge'] = edge_wf['stats']
            _s = edge_wf['stats']
            print(f'[V7.3 WoodFire] {_s["input"]}>{_s["output"]} seeds (dedup:{_s["deduplicated"]}, filtered:{_s["quality_filtered"]})')
        else:
            print(f'[V7.3 WoodFire] BLOCKED: {edge_wf.get("reason")}')
        results['edge_agents'] = results.get('edge_agents', {})
        results['edge_agents']['wood_fire'] = edge_wf.get('stats', {})

    # === V7.3: Edge Agent -- Wood controls Earth (Hallucination Detector) ===
    if EDGE_AGENTS:
        edge_we_ctrl = _EDGE_REGISTRY.wood_earth_ctrl.check(wood_result, {})
        if edge_we_ctrl.get('intervention'):
            print(f'[V7.3 WoodCtrlEarth] WARNING: {len(edge_we_ctrl.get("risks",[]))} hallucination risks')
        results['edge_agents'] = results.get('edge_agents', {})
        results['edge_agents']['wood_earth_ctrl'] = edge_we_ctrl

    # === V7.4: Route edge signals to node agents ===
    if NODE_AGENTS and EDGE_AGENTS:
        # WoodEarth ctrl signal -> Earth node
        if edge_we_ctrl.get('intervention'):
            _NODE_REGISTRY.earth.receive_control_signal('wood_controls_earth', edge_we_ctrl)
        print('[V7.4] Edge->Node signals routed')
    
    # Phase 2: Earth (synthesis)
    earth_result = phase_earth(wood_result, fire_result, topic)
    results["phases"]["earth"] = earth_result
    
    # Phase 3: Metal (validation)

    # v8.0: Wire fire_earth + earth_metal
    if EDGE_AGENTS:
        try:
            edge_fe = _EDGE_REGISTRY.process_generation('fire', 'earth', fire_result)
            results['edge_agents'] = results.get('edge_agents', {})
            results['edge_agents']['fire_earth'] = edge_fe.get('stats', {})
        except Exception as e:
            print(f'[Edge] fire_earth: {e}')
        try:
            edge_em = _EDGE_REGISTRY.process_generation('earth', 'metal', earth_result)
            results['edge_agents']['earth_metal'] = edge_em.get('stats', {})
        except Exception as e:
            print(f'[Edge] earth_metal: {e}')

    metal_result = phase_metal(earth_result, topic, round_info=round_info)
    results["phases"]["metal"] = metal_result

    # Phase 3.5: Cognitive Graph Analysis
    cg_result = None
    if CG:
        try:
            run_id = f"run-{hashlib.md5(topic.encode()).hexdigest()[:8]}-{int(time.time())}"
            cg_result = cognitive_graph.run_cognitive_analysis(metal_result, earth_result, topic, run_id)
            results["cognitive_graph"] = {
                "residuals": len(cg_result.get("residuals", [])),
                "patterns": len(cg_result.get("patterns", [])),
                "graph": cg_result.get("graph", {}),
                "path_weights": cg_result.get("path_weights", {}),
                "evolution": cg_result.get("evolution_report", {}),
            }
            print(f"[CG] {len(cg_result.get('residuals',[]))} residuals, {len(cg_result.get('patterns',[]))} patterns, graph: {cg_result.get('graph',{}).get('nodes',0)} nodes")
        except Exception as e:
            print(f"[CG] Error: {e}")
            results["cognitive_graph"] = {"error": str(e)}


    # === V7.3: Edge Agent -- Fire controls Metal (Skepticism Suppressor) ===
    if EDGE_AGENTS:
        edge_fm_ctrl = _EDGE_REGISTRY.fire_metal_ctrl.check(metal_result)
        if edge_fm_ctrl.get('intervention'):
            print(f'[V7.3 FireCtrlMetal] WARNING: {edge_fm_ctrl.get("reason","over-skepticism")}')
        results['edge_agents'] = results.get('edge_agents', {})
        results['edge_agents']['fire_metal_ctrl'] = edge_fm_ctrl

    # === V7.3: Edge Agent -- Metal generates Water (Residual Collector) ===
    if EDGE_AGENTS:
        edge_mw = _EDGE_REGISTRY.metal_water.transfer(metal_result, earth_result, topic)
        _sig = edge_mw.get('signal','?')
        _sev = edge_mw.get('severity','?')
        _wd = len(edge_mw.get('weak_dimensions',{}))
        print(f'[V7.3 MetalWater] signal={_sig} severity={_sev} weak_dims={_wd}')
        results['edge_agents'] = results.get('edge_agents', {})
        results['edge_agents']['metal_water'] = {'signal': _sig, 'severity': _sev, 'weak_dims': _wd}

    # === V7.4: Route edge signals to node agents + feedback ===
    if NODE_AGENTS and EDGE_AGENTS:
        _NODE_REGISTRY.water.receive_generation_signal('metal_generates_water', edge_mw)
        # Metal score -> feedback to all upstream nodes
        metal_score = metal_result.get('composite_score', 0.5)
        _NODE_REGISTRY.feedback_all(metal_score)
        _NODE_REGISTRY.save_all_to_pg()  # V7.8: Persist feedback to PG
        print(f'[V7.8] Metal score {metal_score:.2f} fed back + persisted to PG')

    # Phase 4: Water (distillation) - enriched with CG
    if metal_result.get("verdict") != "FAIL":
        water_result = phase_water(fire_result, metal_result, topic, domain, earth_result, cg_result)
        results["phases"]["water"] = water_result

        # V7.8: Save Water seeds to bridge for next-round Wood
        if WATER_BRIDGE and water_result.get("new_seeds"):
            metal_score = metal_result.get("composite_score", 0)
            water_seed_bridge.save_water_seeds(domain, topic, water_result["new_seeds"], metal_score)
    else:
        results["phases"]["water"] = {"phase": "water", "skipped": True, "reason": "metal_fail"}

    total_elapsed = time.time() - t_start
    results["total_elapsed"] = total_elapsed
    results["pipeline_version"] = VERSION
    
    _pg_safe(pg_storage.job_create, f"pipeline-{int(time.time())}", {"topic": topic, "domain": domain})
    
    # Auto-distribute Lux rewards
    lux_result = _auto_distribute_lux(results)
    if lux_result:
        lux_result["total_distributed"] = lux_result.get("total_lux", 0)
    results["lux_distribution"] = lux_result

    # Auto-generate report (Phase 5: Zhuque output)
    if REPORT:
        try:
            report = report_generator.generate_report(results) if isinstance(results, dict) else None
            results["report"] = {
                "markdown_length": len(report.get("markdown", "")) if report else 0,
                "html_length": report.get("html_length", 0),
                "files": report.get("files", {}),
                "timing": report.get("timing", {}),
            }
        except Exception as e:
            print("[Report] Error: {}".format(e))
            results["report"] = {"error": str(e)}
    

    # v5.5: Post-processing
    if _POST_PROCESS:
        try:
            results = post_process_pipeline(results, topic)
            cal = results.get("calibration", {})
            print("[PostProcess] type={}, verdict={}, score={}".format(
                cal.get("analysis_type", "?"), cal.get("verdict", "?"),
                cal.get("calibrated_composite", "?")))
        except Exception as e:
            print("[PostProcess] Error: {}".format(e))


    # v8.0: Wire remaining edges
    if EDGE_AGENTS:
        try:
            ew = _EDGE_REGISTRY.process_control('earth', 'water', earth_result, water_result)
            results['edge_agents']['earth_water_ctrl'] = ew
        except Exception as e:
            print(f'[Edge] earth_water_ctrl: {e}')
        try:
            wf = _EDGE_REGISTRY.process_control('water', 'fire', water_result, fire_result)
            results['edge_agents']['water_fire_ctrl'] = wf
        except Exception as e:
            print(f'[Edge] water_fire_ctrl: {e}')
        try:
            mwc = _EDGE_REGISTRY.process_control('metal', 'wood', metal_result, wood_result)
            results['edge_agents']['metal_wood_ctrl'] = mwc
        except Exception as e:
            print(f'[Edge] metal_wood_ctrl: {e}')
        try:
            ww = _EDGE_REGISTRY.process_generation('water', 'wood', water_result)
            results['edge_agents']['water_wood'] = ww.get('stats', {})
        except Exception as e:
            print(f'[Edge] water_wood: {e}')

    # === V7.3: Edge Agent Summary ===
    if EDGE_AGENTS:
        results['edge_agents'] = results.get('edge_agents', {})
        results['edge_agents']['registry_summary'] = _EDGE_REGISTRY.summary()

    # V7.4: Node agent summary
    if NODE_AGENTS:
        results['node_agents'] = _NODE_REGISTRY.summary()
        print('[V7.4] Node agents: ' + ', '.join(f'{n}({d["memory"]["total_runs"]})' for n,d in results['node_agents'].items()))
        _ea_count = len([k for k in results['edge_agents'] if k != 'registry_summary'])
        print(f'[V7.3] Edge agents: {_ea_count} agents processed this run')


    # V7.6: Sovereign post-run learning
    if SOVEREIGN_AVAILABLE and sovereign_decision:
        try:
            metal_result = results.get('phases', {}).get('metal', {})
            metal_score = metal_result.get('composite_score', 0)
            sovereign = get_sovereign()
            sovereign.post_run_learn(metal_score, domain=domain)
            results['sovereign'] = {
                'decision': sovereign_decision.to_dict(),
                'trust_report': sovereign.get_trust_report(),
            }
        except Exception as e:
            print(f'[Sovereign] Post-run error: {e}')
    return results

# v5.7.2: Alias for iteration_loop compatibility
def phase_lux(pipeline_result, executor_id="pipeline"):
    """Alias for _auto_distribute_lux for iteration_loop compatibility."""
    return _auto_distribute_lux(pipeline_result, executor_id)


def self_test():
    results = []
    
    # Test parallel execution
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(lambda: time.sleep(0.1) or "a")
        f2 = executor.submit(lambda: time.sleep(0.1) or "b")
        r1, r2 = f1.result(), f2.result()
    elapsed = time.time() - t0
    results.append(("parallel_exec", f"PASS ({elapsed:.2f}s)" if elapsed < 0.3 else f"FAIL ({elapsed:.2f}s)"))
    
    if PG:
        try:
            pg_storage.health_check()
            results.append(("pg_storage", "PASS"))
        except Exception as e:
            results.append(("pg_storage", f"FAIL: {e}"))
    else:
        results.append(("pg_storage", "SKIP (not available)"))
    
    if HUB:
        hub = hub_connector.check_hub()
        results.append(("hub_connector", f"PASS (connected={hub['connected']})" ))
    else:
        results.append(("hub_connector", "SKIP (not available)"))
    
    # Auto-generate report (Phase 5: Zhuque output)
    if REPORT:
        try:
            report = report_generator.generate_report(results) if isinstance(results, dict) else None
            results["report"] = {
                "markdown_length": len(report.get("markdown", "")) if report else 0,
                "html_length": report.get("html_length", 0),
                "files": report.get("files", {}),
                "timing": report.get("timing", {}),
            }
        except Exception as e:
            print("[Report] Error: {}".format(e))
            results["report"] = {"error": str(e)}

    return results



# ============================================================
# V8.2: Deep Pipeline — IterationLoop v2.1 integration
# ============================================================

def run_pipeline_deep(topic, domain="general", max_rounds=3,
                      convergence_threshold=0.75, timeout_s=600):
    """Run deep analysis pipeline using IterationLoop v2.1.
    
    Integrates 5 cognitive modules:
    - Counterfactual analysis (robustness testing)
    - Evidence chain tracking (grounding verification)
    - Confidence engine (belief convergence)
    - Debate engine (adversarial final round)
    - Policy shift tracking (strategy evolution)
    
    Args:
        topic: analysis topic
        domain: "general", "finance", "technology", "materials", "proptech"
        max_rounds: max iteration rounds (default 3)
        convergence_threshold: stop when score >= this
        timeout_s: total time budget in seconds
    
    Returns:
        IterationLoop result dict with rounds, cognitive analysis, etc.
    """
    try:
        from iteration_loop import IterationLoop
    except ImportError as e:
        print(f"[DeepPipeline] Cannot import IterationLoop: {e}")
        print("[DeepPipeline] Falling back to run_pipeline_multi")
        return run_pipeline_multi(topic, domain=domain, max_rounds=max_rounds,
                                  convergence_threshold=convergence_threshold)
    
    import importlib
    modules = {}
    for name in ['verification', 'residual_engine', 'cognitive_graph', 'pg_storage']:
        try:
            modules[name] = importlib.import_module(name)
        except ImportError:
            modules[name] = None
    
    # Create LLM function wrapper for cognitive modules
    def llm_fn(prompt, **kwargs):
        """LLM function for cognitive modules (counterfactual, debate)."""
        model = kwargs.get("model", PHASE_MODEL.get("earth", "bailian"))
        timeout = kwargs.get("timeout", 60)
        return call_llm(prompt, model=model, timeout=timeout, thinking_budget=0)
    
    # Create pipeline proxy (IterationLoop expects a module with phase_* functions)
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    pipeline_proxy = sys.modules[__name__]  # this module itself
    
    loop = IterationLoop(
        pipeline_module=pipeline_proxy,
        verification_module=modules.get('verification'),
        residual_module=modules.get('residual_engine'),
        cg_module=modules.get('cognitive_graph'),
        pg_module=modules.get('pg_storage'),
        max_rounds=max_rounds,
        convergence_threshold=convergence_threshold,
        timeout_s=timeout_s,
        llm_fn=llm_fn,
    )
    
    result = loop.run(topic, domain=domain)
    
    # Persist to PG
    try:
        if modules.get('pg_storage'):
            modules['pg_storage'].knowledge_store(
                key=f"deep-{topic[:30]}-{int(time.time())}",
                content=json.dumps({
                    "topic": topic,
                    "rounds": result.get("rounds_completed"),
                    "final_verdict": result.get("final_verdict"),
                    "final_composite": result.get("final_composite"),
                    "converged": result.get("converged"),
                    "confidence": result.get("confidence_label"),
                }, ensure_ascii=False)[:4000],
                domain="deep_analysis",
                source="pipeline-deep",
                residual_score=result.get("final_composite", 0)
            )
    except Exception as e:
        print(f"[DeepPipeline] PG save error: {e}")
    
    return result




# ============================================================
# V8.2.2: Unified entry point
# ============================================================

def analyze(topic, domain="general", depth="deep", max_rounds=3):
    """Unified pipeline entry point.
    
    Args:
        topic: analysis topic
        domain: "general", "finance", "technology", "materials", "proptech"
        depth: "single" (1 round), "multi" (old multi-round), "deep" (full cognitive)
        max_rounds: max iterations (for multi/deep)
    
    Returns:
        Pipeline result dict
    """
    # V8.4: Auto-prefeed search data before pipeline runs
    try:
        from search_prefeed import prefeed_topic
        _pf = prefeed_topic(topic, domain=domain, queries=3, verbose=True)
        if _pf.get("total_fed", 0) > 0:
            print(f"[Analyze] Pre-fed {_pf['total_fed']} search results")
    except Exception as _e:
        print(f"[Analyze] Prefeed skipped: {_e}")
    
    if depth == "single":
        return run_pipeline(topic, domain=domain)
    elif depth == "multi":
        return run_pipeline_multi(topic, domain=domain, max_rounds=max_rounds)
    else:  # "deep" (default)
        return run_pipeline_deep(topic, domain=domain, max_rounds=max_rounds)


if __name__ == "__main__":
    print(f"wuxing_pipeline_v2.py v{VERSION} self-test")
    print("=" * 40)
    results = self_test()
    for name, status in results:
        print(f"  {name}: {status}")
    passed = sum(1 for _, s in results if s.startswith("PASS"))
    print(f"\n{passed}/{len(results)} tests passed")


# ============================================================
# Iterative Pipeline (N-round loop)
# ============================================================

def run_iterative(topic, domain="general", max_rounds=3, initial_seeds=None):
    """Run N-round iterative pipeline with verification-driven convergence.
    
    Usage:
        result = run_iterative("lithium battery recycling", max_rounds=3)
    """
    import sys as _sys

    this = _sys.modules[__name__]
    
    loop = iteration_loop.IterationLoop(
        pipeline_module=this,
        verification_module=verification if VERIFY else None,
        residual_module=residual_engine if RESIDUAL else None,
        cg_module=cognitive_graph if CG else None,
        pg_module=pg_storage if PG else None,
        max_rounds=max_rounds,
    )
    return loop.run(topic, domain=domain, initial_seeds=initial_seeds)


# ============================================================
# V7.9: Multi-Round Iteration
# ============================================================

def run_pipeline_multi(topic, domain="general", max_rounds=3,  # DEPRECATED: use run_pipeline_deep 
                       convergence_threshold=0.75, depth="compressed"):
    """Run multi-round pipeline with Water->Wood seed feedback loop.
    
    Each round runs the full 16+1 agent pipeline. Water seeds from
    round N are saved to PG and loaded by Wood in round N+1.
    
    Convergence: stops when Metal score stabilizes (delta < 0.05)
    or exceeds convergence_threshold, or max_rounds reached.
    
    Args:
        topic: analysis topic
        domain: domain key for PG seed storage
        max_rounds: maximum iteration rounds (default 3)
        convergence_threshold: stop if Metal score >= this
        depth: "compressed" or "deep"
    
    Returns:
        {
            "topic": str,
            "domain": str,
            "rounds": [{round_result}, ...],
            "rounds_completed": int,
            "final_verdict": str,
            "final_score": float,
            "score_trajectory": [float, ...],
            "converged": bool,
            "stop_reason": str,
            "total_elapsed_s": float,
            "seed_evolution": [{...}, ...],
        }
    """
    import time as _time
    t0 = _time.time()
    
    print(f"\n{'='*60}")
    print(f"[MultiRound] Starting: topic='{topic[:50]}...' domain={domain} max_rounds={max_rounds}")
    print(f"{'='*60}")
    
    rounds = []
    score_trajectory = []
    seed_evolution = []
    stop_reason = f"max_rounds ({max_rounds})"
    
    for round_num in range(1, max_rounds + 1):
        round_t0 = _time.time()
        
        print(f"\n{'='*40}")
        print(f"[MultiRound] === ROUND {round_num}/{max_rounds} ===")
        print(f"{'='*40}")
        
        # Run full pipeline (Wood will auto-load prior seeds from PG via V7.9 patch)
        # Build round context for Metal
        _round_info = {"round_num": round_num}
        if round_num > 1 and score_trajectory:
            _round_info["prev_score"] = score_trajectory[-1]
            # Get weak dims from previous round
            prev_metal = rounds[-1].get("metal_dims", {}) if rounds else {}
            _round_info["prev_weak_dims"] = [k for k, v in prev_metal.items() 
                                              if isinstance(v, (int, float)) and v < 0.5]
        result = run_pipeline(topic, domain=domain, depth=depth, round_info=_round_info)
        
        metal = result.get('phases', {}).get('metal', {})
        water = result.get('phases', {}).get('water', {})
        score = metal.get('composite_score', 0)
        verdict = metal.get('verdict', 'FAIL')
        water_seeds = water.get('new_seeds', [])
        
        round_elapsed = _time.time() - round_t0
        
        round_info = {
            'round': round_num,
            'verdict': verdict,
            'score': score,
            'water_seeds_count': len(water_seeds),
            'elapsed_s': round(round_elapsed, 1),
            'metal_dims': metal.get('dimensions', {}),
        }
        rounds.append(round_info)
        score_trajectory.append(score)
        
        # Track seed evolution
        seed_texts = [s.get('angle', str(s))[:80] for s in water_seeds[:5]]
        seed_evolution.append({
            'round': round_num,
            'seeds': seed_texts,
            'count': len(water_seeds),
        })
        
        print(f"\n[MultiRound] R{round_num} RESULT: {verdict} {score:.3f} | "
              f"Water seeds: {len(water_seeds)} | {round_elapsed:.1f}s")
        
        # Convergence check
        if score >= convergence_threshold:
            stop_reason = f"Score {score:.3f} >= threshold {convergence_threshold}"
            print(f"[MultiRound] CONVERGED: {stop_reason}")
            break
        
        if round_num >= 2:
            prev_score = score_trajectory[-2]
            delta = abs(score - prev_score)
            improvement = score - prev_score
            
            # Only stabilize if NOT declining
            if delta < 0.05 and improvement >= 0:
                stop_reason = f"Score stabilized (delta={delta:.3f} < 0.05)"
                print(f"[MultiRound] STABILIZED: {stop_reason}")
                break
            elif delta < 0.05 and improvement < 0:
                # Score slightly declined — don't stop, try another round
                print(f"[MultiRound] Score slightly declined ({prev_score:.3f} -> {score:.3f}), continuing...")
                # Don't break — give it another chance
            
            # Score declining check
            if score < prev_score - 0.05:
                print(f"[MultiRound] WARNING: Score declining ({prev_score:.3f} -> {score:.3f})")
                if KERNEL_AVAILABLE:
                    kernel = get_kernel()
                    _ov, _reason, _action = kernel.should_override_agent("pipeline", score, score_trajectory)
                    print(f"[Kernel] Override={_ov}, Action={_action}: {_reason}")
                    if _action == "FORCE_STRATEGY_SWITCH" and NODE_AGENTS:
                        for _ag in [_NODE_REGISTRY.wood, _NODE_REGISTRY.fire, _NODE_REGISTRY.earth, _NODE_REGISTRY.metal, _NODE_REGISTRY.water]:
                            _old_s = getattr(_ag, "current_strategy", "N/A")
                            if hasattr(_ag, "select_strategy"): _ag.current_strategy = _ag.select_strategy(domain)
                            print(f"[Kernel] {_ag.element}: {_old_s} -> {_ag.current_strategy}")
                    elif _action == "RETRY_WITH_DIFFERENT_STRATEGY":
                        stop_reason = f"Kernel stopped: {_reason}"
                        break
        
        if round_num >= max_rounds:
            stop_reason = f"Max rounds ({max_rounds}) reached"
            break
        
        # Water seeds are already saved to PG by the pipeline (water_seed_bridge)
        # Next round's Wood will pick them up automatically via V7.9 patch
        print(f"[MultiRound] Seeds saved to PG, proceeding to round {round_num + 1}...")
    
    total_elapsed = _time.time() - t0
    final = rounds[-1] if rounds else {}
    
    result = {
        'topic': topic,
        'domain': domain,
        'rounds': rounds,
        'rounds_completed': len(rounds),
        'final_verdict': final.get('verdict', 'FAIL'),
        'final_score': final.get('score', 0),
        'score_trajectory': score_trajectory,
        'converged': final.get('score', 0) >= convergence_threshold,
        'stop_reason': stop_reason,
        'total_elapsed_s': round(total_elapsed, 1),
        'seed_evolution': seed_evolution,
        'pipeline_version': VERSION,
    }
    
    print(f"\n{'='*60}")
    print(f"[MultiRound] COMPLETE: {len(rounds)} rounds | "
          f"Trajectory: {' -> '.join(f'{s:.3f}' for s in score_trajectory)} | "
          f"{stop_reason} | {total_elapsed:.1f}s")
    print(f"{'='*60}")
    
    return result

