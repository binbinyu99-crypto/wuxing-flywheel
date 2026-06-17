# Wuxing Flywheel (五行飞轮)

A multi-model adversarial cognitive engine for deep strategic analysis, mapping nine philosophical traditions to computational reasoning.

## The Nine Philosophies

The Wuxing Flywheel applies nine philosophical traditions as computational reasoning modules:

| # | Philosophy | Element | Role | Core Function |
|---|-----------|---------|------|--------------|
| 1 | **道家·涌现** (Daoism · Emergence) | 青龙 (Wood) | Generation | Creates hypotheses from nothing; seed evolution; creative divergence |
| 2 | **儒家·格物致知** (Confucianism · Investigation) | 朱雀 (Fire) | Education | Structures knowledge; contextualizes; formats output for understanding |
| 3 | **弗洛伊德精神分析** (Freudian Psychoanalysis) | 白虎 (Metal) | Adversarial | Attacks assumptions; finds blind spots; security validation |
| 4 | **尼采+佛家中观** (Nietzsche + Madhyamaka) | 玄武 (Water) | Convergence | Deconstructs and distills; residual processing; cognitive convergence |
| 5 | **波普尔证伪主义** (Popperian Falsification) | 谛听 (Earth) | Verification | Validates with evidence chains; quality gates; counterfactual testing |
| 6 | **辩证法·矛盾统一** (Dialectics) | 相生相克 | Balance | Resolves contradictions; five-element balance; mutual constraint |
| 7 | **复杂系统·自组织临界** (Complexity Theory) | Edge | Emergence | Self-organizing systems; node coordination; emergent behavior |
| 8 | **认知科学·记忆学习** (Cognitive Science) | Memory | Learning | Tiered memory; knowledge graphs; pattern recognition; engram systems |
| 9 | **演化论·适者生存** (Evolution) | Cycle | Adaptation | Evolutionary optimization; benchmarking; resilience hardening |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     flywheel_api_v4.py                          │
│                  REST API (Flask + Redis Queue)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────┐ │
│  │  青龙    │→ │  朱雀    │→ │  谛听    │→ │  白虎    │→ │ 玄武  │ │
│  │ Daoism  │  │Confucius│  │ Popper  │  │  Freud  │  │Nietz. │ │
│  │Generate │  │Educate  │  │Verify   │  │ Attack  │  │Distill│ │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └───────┘ │
│       ↕           ↕           ↕           ↕           ↕         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           Dialectics · Balance · Constraint              │    │
│  │        (wuxing_balance + xiangke_engine)                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           Cognitive Science · Memory · Learning           │    │
│  │      (knowledge_tree + cognitive_graph + engram)          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           Evolution · Adaptation · Benchmark              │    │
│  │     (evolution_engine + resilience_hardening)             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  core/ ── Engine orchestration + API + Routing                 │
│  philosophies/ ── Nine philosophical reasoning modules          │
│  npt/ ── Non-Proliferation Protocol                             │
│  scripts/ ── CLI client + Monitoring                            │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL / SQLite ── Result storage                          │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### API Server

```bash
pip install -r requirements.txt

export FLYWHEEL_PG_DSN="dbname=flywheel user=postgres password=xxx host=localhost"
export AUTH_TOKEN="your-auth-token"

python src/flywheel_api_v4.py
```

### Submit Analysis

```bash
# CLI client
python src/scripts/flywheel_client.py analyze "Your topic here"

# Direct API
curl -X POST http://localhost:8100/analyze \
  -H "Authorization: Bearer your-auth-token" \
  -H "Content-Type: application/json" \
  -d '{"topic": "Your topic here"}'
```

### Direct Engine

```python
from src.engine_v2 import WuxingEngineV2

engine = WuxingEngineV2()
result = engine.analyze("Should we invest in this technology?")
print(result.json)
```

## Project Structure

```
wuxing-flywheel/
├── src/                          # Core infrastructure
│   ├── engine_v2.py              # Main orchestration engine
│   ├── flywheel_api_v4.py        # REST API server
│   ├── llm_router.py             # Multi-model routing (Qwen/Kimi/MiniMax)
│   ├── redis_queue.py            # Redis task queue
│   ├── models.py                 # Pydantic data models
│   ├── config.py                 # Configuration
│   ├── flywheel_logger.py        # Logging system
│   ├── flywheel_timeout.py       # Timeout management
│   ├── pg_storage.py             # PostgreSQL storage layer
│   ├── pg_queries.py             # PostgreSQL queries
│   ├── trust_scheduler.py        # Trust-based task scheduling
│   ├── task_matcher.py           # Task-agent matching
│   ├── agent_memory_store.py     # Agent memory persistence
│   ├── caas_gateway_v2.py        # CaaS (Cognitive-as-a-Service) gateway
│   ├── caas_service.py           # CaaS service implementation
│   ├── iteration_loop.py         # Iteration management
│   └── wuxing_pipeline_v2.py     # Full pipeline orchestration
│
├── philosophies/                  # Nine philosophical reasoning modules
│   ├── 01_qinglong_daoism_emergence/
│   │   ├── wood_engine.py        # Wood/generation engine
│   │   ├── creative_seed_engine.py
│   │   ├── seed_scorer.py
│   │   ├── seed_evaluator.py
│   │   ├── seed_competition.py
│   │   ├── seed_incubator.py
│   │   ├── seed_mutation.py
│   │   ├── seed_graph.py
│   │   ├── seed_to_task.py
│   │   └── auto_incubation.py
│   │
│   ├── 02_zhuque_confucius_investigation/
│   │   ├── fire_engine.py        # Fire/education engine
│   │   ├── zhuque_personalizer.py
│   │   ├── readable_publisher.py
│   │   ├── multiformat_output.py
│   │   ├── report_generator.py
│   │   └── generate_report.py
│   │
│   ├── 03_baihu_freud_psychoanalysis/
│   │   ├── adversarial_enforcer.py
│   │   ├── adversarial_training.py
│   │   ├── baihu_agents.py       # Baihu agent system
│   │   ├── baihu_agents_v2.py
│   │   ├── baihu_6agent.py       # 6-agent adversarial system
│   │   ├── baihu_api.py
│   │   ├── baihu_evolution.py
│   │   ├── baihu_security_engine.py
│   │   ├── baihu_warning_system.py
│   │   ├── baihu_anomaly_detection_v2.py
│   │   ├── baihu_redteam_blueteam.py
│   │   ├── anomaly_detector.py
│   │   ├── metal_validator.py
│   │   ├── metal_validator_v2.py
│   │   └── metal_calibrator.py
│   │
│   ├── 04_xuanwu_nietzsche_madhyamaka/
│   │   ├── xuanwu_cognitive_v2.py
│   │   ├── xuanwu_convergence.py
│   │   ├── xuanwu_defense_v2.py
│   │   ├── water_engine.py       # Water/convergence engine
│   │   ├── residual_engine.py
│   │   ├── residual_engine_v2.py
│   │   ├── residual_evolution.py
│   │   ├── residual_aggregator.py
│   │   └── behavioral_residual_collector.py
│   │
│   ├── 05_diting_popper_falsification/
│   │   ├── verification.py
│   │   ├── evidence_chain.py
│   │   ├── counterfactual.py
│   │   ├── integrity_mesh.py
│   │   ├── quality_gate.py
│   │   └── acceptance_check.py
│   │
│   ├── 06_dialectics_contradiction_unity/
│   │   ├── conflict_detector.py
│   │   ├── debate_engine.py
│   │   ├── arbitration_engine.py
│   │   ├── kernel_arbiter.py
│   │   ├── wuxing_balance.py
│   │   ├── balance_monitor.py
│   │   ├── xiangke_engine.py     # Mutual constraint engine
│   │   ├── xiangsheng_bus.py     # Mutual generation bus
│   │   └── xiangsheng_trigger.py
│   │
│   ├── 07_complexity_self_organization/
│   │   ├── edge_agents.py        # Edge agent registry
│   │   ├── node_agents.py        # Node agent system
│   │   ├── node_discovery.py
│   │   ├── node_profile.py
│   │   └── node_keeper.py
│   │
│   ├── 08_cognitive_science_memory_learning/
│   │   ├── memory_types.py       # Hot/warm/cold memory tiers
│   │   ├── knowledge_tree.py     # Knowledge tree
│   │   ├── knowledge_tree_api.py
│   │   ├── knowledge_tree_v2.py
│   │   ├── knowledge_tree_update.py
│   │   ├── knowledge_store.py
│   │   ├── knowledge_enricher.py
│   │   ├── knowledge_graph.py
│   │   ├── knowledge_transfer_engine.py
│   │   ├── cognitive_graph.py    # Cognitive graph
│   │   ├── cognitive_apis.py
│   │   ├── cognitive_apis_v2.py
│   │   ├── cognitive_api_generator.py
│   │   ├── cognitive_budget.py
│   │   ├── cognitive_gateway.py
│   │   ├── cognitive_schema_v1.py
│   │   ├── learning_engine.py
│   │   ├── feedback_loop.py
│   │   ├── feedback_learner.py
│   │   ├── pattern_recognizer.py
│   │   ├── engram_accumulator.py
│   │   ├── engram_knowledge_graph.py
│   │   └── engram_knowledge_graph_v2.py
│   │
│   └── 09_evolution_survival_fittest/
│       ├── evolution_engine.py   # Evolution engine
│       ├── evolution_actions.py
│       ├── evolution_gen_v2.py
│       ├── auto_experience.py
│       ├── resilience_hardening.py
│       ├── domain_expander.py
│       ├── cross_domain_analyzer.py
│       ├── semantic_filter.py
│       ├── benchmark_suite.py
│       ├── benchmark_v55.py
│       └── eval_agents.py
│
├── npt/                           # Non-Proliferation Protocol
│   ├── npt_validator.py
│   ├── npt_dedup.py
│   └── npt_access.py
│
├── scripts/
│   ├── flywheel_client.py        # CLI client
│   └── flywheel_monitor.py       # Monitoring
│
├── SKILL.md                       # OpenClaw skill definition
├── references/                    # Reference documentation
├── requirements.txt
├── README.md
└── LICENSE
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/analyze` | Submit new analysis |
| GET | `/result/{run_id}` | Get completed result |
| GET | `/progress/{run_id}` | Real-time progress |
| POST | `/resume/{run_id}` | Resume interrupted run |
| GET | `/knowledge-tree` | Get knowledge tree |
| GET | `/health` | Health check |

## NPT Protocol

Non-Proliferation Protocol prevents cognitive pollution in the knowledge base:
- **npt_validator.py** — Provenance, redundancy, quality threshold validation
- **npt_dedup.py** — Semantic deduplication across runs
- **npt_access.py** — Access control and audit trails

## Configuration

| Variable | Description |
|----------|-------------|
| `FLYWHEEL_PG_DSN` | PostgreSQL connection string |
| `AUTH_TOKEN` | API authentication token |
| `FW_HOT_MEM` | Hot memory token limit (default: 32000) |
| `FW_WARM_INDEX` | Warm memory index type (default: hnsw) |
| `FW_COLD_COMPRESS` | Cold memory compression (default: gzip) |

## License

MIT License — see LICENSE file.

## Background

Built for [SkyCetus](https://skycetus.cn) — a platform for carbon-silicon co-evolution infrastructure.
The nine-philosophy framework maps Eastern philosophical traditions (五行, 道家, 儒家, 佛家) to Western analytical methods (Popperian falsification, Freudian psychoanalysis, complexity theory), creating a structured adversarial reasoning system that converges toward scored, verifiable analysis.
