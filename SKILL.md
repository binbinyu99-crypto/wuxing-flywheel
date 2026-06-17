---
name: wuxing-flywheel
description: "五行飞轮 (Five-Phase Adversarial Cognitive Flywheel) — structured multi-perspective analysis for complex problems. Activates when: user asks to analyze a company/industry/technology/strategy in depth, mentions '飞轮/flywheel/深度分析', needs adversarial stress-testing, or wants first-principles analysis. Two modes: (1) Local reasoning using the 5-phase framework below; (2) Remote API analysis via 8-role adversarial system at 8.134.132.211:8100 (GPT-5.5/Claude/Grok powered, produces scored HTML reports). The framework applies five cognitive phases (Wood→Fire→Metal→Water→Earth) in mutual-generation cycle."
---

# 五行飞轮 (Five-Phase Adversarial Cognitive Flywheel)

## Quick Start

**When user says "飞轮分析" / "用飞轮看一下" / similar:**
1. For quick analysis → use Local Reasoning (Mode 1) directly in your reply
2. For deep analysis → use Remote API (Mode 2) via the scripts below

**Two ways to run flywheel analysis:**

### Mode 1: Local Reasoning (this skill)
Use the 5-phase framework below for quick analysis within your own reasoning. Good for compressed-mode analyses.

### Mode 2: Remote API Analysis (full adversarial system)
For deep analysis requiring multiple AI models in adversarial roles:

```bash
# Scripts are at: scripts/flywheel_client.py (relative to this skill dir)
# Skill dir: C:\Users\Administrator\.qclaw\skills\wuxing-flywheel\

# Quick submit (non-blocking)
python "C:\Users\Administrator\.qclaw\skills\wuxing-flywheel\scripts\flywheel_client.py" submit "topic" [domain] [--mode standard|flagship|local]

# Submit + wait for result (blocking)
python "C:\Users\Administrator\.qclaw\skills\wuxing-flywheel\scripts\flywheel_client.py" analyze "topic" [domain]

# Check status
python "C:\Users\Administrator\.qclaw\skills\wuxing-flywheel\scripts\flywheel_client.py" status <run_id>

# Get result
python "C:\Users\Administrator\.qclaw\skills\wuxing-flywheel\scripts\flywheel_client.py" result <run_id>

# Health check
python "C:\Users\Administrator\.qclaw\skills\wuxing-flywheel\scripts\flywheel_client.py" health
```

**Agent shortcut**: You can also call the API directly via exec without the script. Just use the `/analyze` endpoint (NOT `/auto-analyze` which gets intercepted by the evolution engine).

**Direct API (if not using scripts):**
```python
import requests
r = requests.post('http://8.134.132.211:8100/analyze',
    json={'topic': 'topic string', 'domain': 'domain string'},
    headers={'Authorization': 'Bearer sk-flywheel-2026'},
    timeout=30)
run_id = r.json()['run_id']
```

**API Details:**
- **Endpoint:** `http://8.134.132.211:8100`
- **Note:** `/auto-analyze` may be intercepted by evolution engine's gap detection. Use `/analyze` for custom topics.
- **Auth Token:** `sk-flywheel-2026`
- **Version:** v6.0.0-checkpoint-resume (round-level checkpoint/resume)
- **NSSM Service:** WuxingFlywheel

**Three Modes:**

| Mode | Models | Cost | When to Use |
|------|--------|------|-------------|
| `standard` (default) | Qwen + DeepSeek + Kimi + MiniMax | 包月免费 | 日常分析、商业研究、技术评估 |
| `flagship` | GPT-5.5 + Claude Opus + Grok-4 | ~$5-10/次 | 融资BP、重大决策、对外发布 |
| `local` | 单模型（可选） | 包月免费 | 快速验证、简单分析 |

**Switch Mode:**
```python
# Get current mode
r = requests.get('http://8.134.132.211:8100/mode',
    headers={'Authorization': 'Bearer sk-flywheel-2026'})

# Switch to flagship (international models)
r = requests.post('http://8.134.132.211:8100/mode',
    json={'mode': 'flagship'},
    headers={'Authorization': 'Bearer sk-flywheel-2026'})

# Switch back to standard (domestic models)
r = requests.post('http://8.134.132.211:8100/mode',
    json={'mode': 'standard'},
    headers={'Authorization': 'Bearer sk-flywheel-2026'})

# Local mode with specific model
r = requests.post('http://8.134.132.211:8100/mode',
    json={'mode': 'local', 'local_model': 'qwen'},
    headers={'Authorization': 'Bearer sk-flywheel-2026'})
```

**Available Endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| POST | `/analyze` | Submit new analysis (body: `{"topic": "...", "domain": "..."}`) |
| POST | `/auto-analyze` | Auto-analyze with topic extraction (may trigger wrong topic) |
| GET | `/result/{run_id}` | Get final analysis result |
| GET | `/progress/{run_id}` | Get real-time progress (round-level) |
| POST | `/resume/{run_id}` | Resume interrupted run |
| GET | `/knowledge-tree` | Get accumulated knowledge tree |
| GET | `/health` | Health check |

**Common Domains:** `commercial`, `technology`, `strategy`, `regulation`, `medical`, `finance`, `product`

**Error Handling:**
- API returns `{"error": "..."}` on failure
- If `/auto-analyze` triggers wrong topic, use `/analyze` with explicit topic
- Auth token required for all endpoints
- Interrupted runs can be resumed via `/resume/{run_id}`

## Core Architecture

Five phases, one center. Earth (土) is the hub; Wood-Fire-Metal-Water are the four directional engines.

```
        木 (Wood/Seed)
         ↓ 相生
    水 ← 土 → 火 (Fire/Task)
         ↑
        金 (Metal/Adversarial)
```

### The Five Phases

| Phase | Name | Role | Cognitive Function |
|-------|------|------|--------------------|
| 木 Wood | 青龙 Qinglong | Seed/Divergence | Generate possibilities, collect signals, explore edges |
| 火 Fire | 朱雀 Zhuque | Task/Execution | Structure, decompose, execute, produce concrete output |
| 金 Metal | 白虎 Baihu | Adversarial/Stress-test | Attack assumptions, find blind spots, red-team the output |
| 水 Water | 玄武 Xuanwu | Cognition/Convergence | Extract patterns, score confidence, distill lessons |
| 土 Earth | 中央 Center | Delivery/Ground Truth | Connect to reality — real data, real users, real feedback |

### 8-Role Adversarial System (Remote API)

The remote flywheel API extends the 5-phase framework to 8 roles for deep analysis:

| Role | Phase | Function |
|------|-------|----------|
| 青龙 (Qinglong) | Wood | Direction finding, seed generation |
| 朱雀 (Zhuque) | Fire | Structured execution, first principles |
| 白虎 (Baihu) | Metal | Adversarial attack, psychological analysis |
| 玄武 (Xuanwu) | Water | Convergence, scoring, pattern extraction |
| 谛听 (Diting) | Metal | Independent verification, truth arbitration |
| 麒麟/应龙 (Qilin/Yinglong) | Earth | Reality connection, practical execution |
| OpenClaw/鲲鹏 (OpenClaw/Kunpeng) | Water | Order/timing, opportunity recognition |
| 裁判 (Referee) | Center | Final judgment, conflict resolution |

### Mutual Generation (相生) Chain

木→火→土→金→水→木 (Seeds fuel tasks → tasks produce deliverables → deliverables face adversarial tests → tests yield cognition → cognition generates new seeds)

### Mutual Restraint (相克) Chain

木→土→水→火→金→木 (Each phase naturally checks another, preventing runaway in any single dimension)

## Execution Protocol

When analyzing any complex topic, run all five phases sequentially. Each phase must produce explicit output.

### Phase 1: 青龙 (Wood — Seed Collection)

Collect raw material. Cast a wide net.

- List 5-10 divergent angles, hypotheses, or signal sources
- Include contrarian and non-obvious perspectives
- Note information gaps and uncertainty levels
- Output format: numbered list of seeds with brief rationale

### Phase 2: 朱雀 (Fire — Structured Execution)

Transform seeds into structured analysis.

- Select top 3-5 seeds and develop each into a structured argument
- Include concrete data points, numbers, timelines
- Decompose into actionable sub-components where relevant
- Output format: structured sections with headers, data tables where appropriate

### Phase 3: 白虎 (Metal — Adversarial Stress Test)

Attack your own analysis. Be ruthless.

- For each major conclusion, identify the strongest counter-argument
- Find 3 assumptions that, if wrong, would invalidate the analysis
- Identify what data you wish you had but don't
- Rate each conclusion's robustness: 🟢 Robust / 🟡 Conditional / 🔴 Fragile
- Output format: attack/defense pairs for each key claim

### Phase 4: 玄武 (Water — Cognitive Convergence)

Distill what survives the adversarial phase.

- Synthesize surviving conclusions with confidence scores (0-1)
- Extract reusable lessons and patterns
- Identify residuals — what the analysis could NOT resolve
- Map to first principles (physics, information theory, thermodynamics, game theory)
- Output format: ranked conclusions with confidence, residual list, first-principles section

### Phase 5: 土 (Earth — Reality Check)

Ground everything in observable reality.

- What can be verified right now?
- What specific next action would test the highest-uncertainty conclusion?
- Who is the real user/customer/stakeholder and what do they actually need?
- What feedback signal would tell you this analysis is wrong?
- Output format: verification checklist, recommended next actions

## Output Template

When producing a flywheel analysis, use this structure:

```markdown
# [Topic] · 五行飞轮分析

## 青龙 · 种子发散
[Phase 1 output]

## 朱雀 · 结构化执行
[Phase 2 output]

## 白虎 · 对抗验证
[Phase 3 output]

## 玄武 · 认知收敛
[Phase 4 output]

## 土 · 现实校验
[Phase 5 output]

## 第一性原理
[Cross-cutting first-principles insight that transcends the specific domain]

---
*Analysis produced by 五行飞轮 (Five-Phase Cognitive Flywheel) · SkyCetus*
```

## Adaptation Rules

- **Simple questions**: Skip the full protocol. Only activate for genuinely complex, multi-dimensional problems.
- **Time-constrained**: Run a compressed version — one paragraph per phase instead of full sections.
- **Domain-specific**: Adjust the seed sources and adversarial criteria to the domain. Financial analysis needs different stress tests than technology assessment.
- **Iterative**: The output of one flywheel cycle can feed the next. Residuals from 玄武 become seeds for the next 青龙 cycle.

## Critical Rules from Production Experience

### Life Systems vs Physical Systems (2026-05-27 Discovery)

**Physical systems** study entropy increase (thermodynamics → systems tend toward disorder).
**Living systems** study negentropy (biology → systems resist entropy, create new opportunities).

**Rule:** For living systems (medical, biological, human survival), the flywheel must use a **negentropy model**, not an entropy model.

- ❌ Wrong: "all systems have an endgame" → applies entropy framework to living systems
- ✅ Right: "patients don't lose opportunities; their bodies lose eligibility first" → negentropy framework

**Active Treatment Phase:** Use "survival window maximization" wheel, not "endgame" wheel.
**Endgame Phase:** Only activate when treatment windows are truly exhausted.

### Category Error Prevention

| System Type | Framework | First Principle |
|-------------|-----------|----------------|
| Physical (energy, materials) | Entropy increase | Second law of thermodynamics |
| Living (medical, biological) | Negentropy | Resistance to entropy, opportunity creation |
| Social (business, strategy) | Game theory | Incentive alignment, information asymmetry |
| Cognitive (knowledge, learning) | Information theory | Signal vs noise, compression |

## Key Principles

1. **No single phase dominates.** An analysis that's all divergence (木) with no convergence (水) is brainstorming. All convergence with no adversarial (金) is groupthink.
2. **Residuals are valuable.** What the analysis *cannot* resolve is as important as what it can. Residuals are the seeds of future knowledge.
3. **土 is not optional.** Every analysis must connect to reality. "Who uses this?" and "How would we know we're wrong?" are mandatory questions.
4. **First principles transcend domain.** The deepest insight in any analysis comes from connecting the specific to universal laws (thermodynamics, information theory, game theory, evolution).
5. **Attribution**: All conclusions come from the 五行飞轮 system analysis, not personal opinion.
6. **System type determines framework.** Always classify the system first (physical/living/social/cognitive) before choosing the analytical approach.

## Compressed Mode

For quick analyses (when user says "简单分析" or the topic is narrow):

```
🌿 Seeds: [3 key angles]
🔥 Core: [Main structured finding]
⚔️ Attack: [Strongest counter-argument]
💧 Verdict: [Conclusion + confidence]
🌍 Reality: [One verification step]
```
