# Wuxing Flywheel (五行飞轮)

A multi-model adversarial cognitive engine for deep strategic analysis.

## What is it?

The Wuxing Flywheel is a cognitive analysis system that applies five adversarial perspectives (inspired by Chinese 五行 philosophy) to complex problems:

| Element | Role | Philosophical Mapping | Function |
|---------|------|----------------------|----------|
| 青龙 (Wood) | Generation | Daoism · 涌现 | Creates hypotheses from nothing |
| 朱雀 (Fire) | Education | Confucianism · 格物致知 | Structures and contextualizes |
| 白虎 (Metal) | Adversarial | Freudian analysis | Attacks assumptions, finds blind spots |
| 玄武 (Water) | Convergence | Nietzsche + Buddhist Madhyamaka | Deconstructs and distills |
| 谛听 (Earth) | Verification | Popperian falsification | Validates with evidence chains |

The engine runs these elements in a mutual-generation cycle (相生), with each round's residuals feeding into the next. Multiple rounds converge toward scored, structured analysis.

## Architecture

```
┌─────────────────────────────────────────────────┐
│              flywheel_api_v4.py                  │
│         REST API (Flask + Redis Queue)           │
├─────────────────────────────────────────────────┤
│                                                 │
│   青龙 → 朱雀 → 谛听 → 白虎 → 玄武             │
│   (Generation → Education → Verification →      │
│    Adversarial → Convergence)                   │
│                    ↕ residuals                   │
│              Next Round (N+1)                    │
│                                                 │
├─────────────────────────────────────────────────┤
│  engine_v2.py ─ Core orchestration              │
│  llm_router.py ─ Multi-model routing            │
│  npt_*.py ─ Non-Proliferation Protocol          │
│  integrity_mesh.py ─ Output validation           │
│  verification.py ─ Evidence chain scoring       │
│  edge_agents.py ─ Edge agent registry           │
│  memory_types.py ─ Tiered memory (hot/warm/cold)│
│  conflict_detector.py ─ Contradiction detection │
├─────────────────────────────────────────────────┤
│  PostgreSQL / SQLite ─ Result storage           │
└─────────────────────────────────────────────────┘
```

## Quick Start

### API Server

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export FLYWHEEL_PG_DSN="dbname=flywheel user=postgres password=xxx host=localhost"
export AUTH_TOKEN="your-auth-token"

# Start server
python src/flywheel_api_v4.py
```

### Submit Analysis

```bash
# Using the client
python src/scripts/flywheel_client.py analyze "Your topic here"

# Or via API directly
curl -X POST http://localhost:8100/analyze \
  -H "Authorization: Bearer your-auth-token" \
  -H "Content-Type: application/json" \
  -d '{"topic": "Your topic here"}'
```

### Direct Engine Usage

```python
from src.engine_v2 import WuxingEngineV2

engine = WuxingEngineV2()
result = engine.analyze("Should we invest in this technology?")
print(result.json)
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/analyze` | Submit new analysis |
| GET | `/result/{run_id}` | Get completed result |
| GET | `/progress/{run_id}` | Real-time progress (round-level) |
| POST | `/resume/{run_id}` | Resume interrupted run |
| GET | `/knowledge-tree` | Get accumulated knowledge tree |
| GET | `/health` | Health check |

## Configuration

Key environment variables:

| Variable | Description |
|----------|-------------|
| `FLYWHEEL_PG_DSN` | PostgreSQL connection string |
| `AUTH_TOKEN` | API authentication token |
| `FW_HOT_MEM` | Hot memory token limit (default: 32000) |
| `FW_WARM_INDEX` | Warm memory index type (default: hnsw) |
| `FW_COLD_COMPRESS` | Cold memory compression (default: gzip) |

## NPT Protocol

The Non-Proliferation Protocol (NPT) system prevents cognitive pollution — ensuring that low-quality or redundant analysis doesn't accumulate in the knowledge base.

- **npt_validator.py** — Core validation (provenance, redundancy, quality threshold)
- **npt_dedup.py** — Semantic deduplication across runs
- **npt_access.py** — Access control and audit trails

## Project Structure

```
wuxing-flywheel/
├── src/
│   ├── engine_v2.py          # Core engine
│   ├── flywheel_api_v4.py    # REST API server
│   ├── llm_router.py         # Multi-model routing
│   ├── npt_validator.py      # NPT protocol
│   ├── npt_dedup.py          # Semantic dedup
│   ├── npt_access.py         # Access control
│   ├── integrity_mesh.py     # Output validation
│   ├── verification.py       # Evidence scoring
│   ├── edge_agents.py        # Agent registry
│   ├── memory_types.py       # Tiered memory
│   ├── conflict_detector.py  # Contradiction detection
│   ├── water_engine.py       # Residual/water element
│   ├── residual_engine.py    # Residual processing
│   ├── wuxing_balance.py     # Five-element balance
│   ├── xiangke_engine.py     # Mutual constraint
│   ├── knowledge_tree.py     # Knowledge tree
│   ├── trust_scheduler.py    # Trust-based scheduling
│   ├── task_matcher.py       # Task matching
│   ├── agent_memory_store.py # Agent memory
│   ├── node_agents.py        # Node agents
│   ├── knowledge_tree_api.py # Knowledge tree API
│   ├── flywheel_logger.py    # Logging
│   ├── wuxing_pipeline_v2.py # Pipeline orchestration
│   ├── iteration_loop.py     # Iteration management
│   ├── caas_gateway_v2.py    # CaaS gateway
│   ├── caas_service.py       # CaaS service
│   ├── cognitive_apis.py     # Cognitive API interfaces
│   ├── pg_storage.py         # PostgreSQL storage
│   ├── pg_queries.py         # PostgreSQL queries
│   ├── models.py             # Data models
│   ├── config.py             # Configuration
│   └── scripts/
│       ├── flywheel_client.py  # CLI client
│       └── flywheel_monitor.py # Monitoring
├── requirements.txt
├── README.md
└── LICENSE
```

## License

MIT License — see LICENSE file.

## Background

Built for SkyCetus (skycetus.cn) — a platform for carbon-silicon co-evolution infrastructure.
The five-element framework maps Eastern philosophical traditions to Western analytical methods,
creating a structured adversarial reasoning system that converges toward scored, verifiable analysis.
