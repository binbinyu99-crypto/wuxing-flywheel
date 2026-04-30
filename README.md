# 五行飞轮 (Five-Phase Cognitive Flywheel)

**A structured cognitive framework that gives any AI a "thinking operating system."**

> 涌现不是因为复杂，而是因为被约束在一个闭环里。
> *— Emergence comes not from complexity, but from being constrained in a closed loop.*

## What Is This?

五行飞轮 is a five-phase cognitive analysis framework inspired by Chinese Five Elements (五行) philosophy, grounded in graph theory, and validated through real-world industry analysis.

It transforms any LLM from a "question-answer machine" into a **structured cognitive engine** that can:

- Diverge before converging (avoid premature conclusions)
- Stress-test its own output (built-in adversarial phase)
- Connect to reality (mandatory ground-truth verification)
- Learn from residuals (what it *can't* resolve drives the next cycle)

## The Five Phases

```
        木 (Wood/Seed)
         ↓ mutual generation
    水 ← 土 → 火 (Fire/Execute)
    (Water) ↑ (Earth)
        金 (Metal/Adversarial)
```

| Phase | Chinese | Role | What It Does |
|-------|---------|------|-------------|
| 🌿 Wood | 青龙 | Seed/Diverge | Generate 5-10 angles, including contrarian views |
| 🔥 Fire | 朱雀 | Execute | Structure arguments with data, numbers, timelines |
| ⚔️ Metal | 白虎 | Stress-test | Attack every conclusion; rate robustness |
| 💧 Water | 玄武 | Converge | Distill survivors with confidence scores |
| 🌍 Earth | 中央 | Reality check | Ground in verifiable facts; define failure signals |

### Why Five? (Mathematical Proof)

Five is the **minimum number** where two independent complete cycles coexist:

- **Mutual generation (相生):** Wood→Fire→Earth→Metal→Water→Wood
- **Mutual restraint (相克):** Wood→Earth→Water→Fire→Metal→Wood

Graph theory proof: On n nodes, skip-2 traversal visits all nodes only when n=5. This creates a pentagram (相克) independent from the ring (相生) — the minimum topology for both reinforcement AND checks-and-balances.

This isn't mysticism — it's the same structure found in:
- Shannon's communication model (5 components)
- Control theory (5 irreducible elements)
- Minimal biological cell (5 subsystems)
- Dissipative structures (≥5 for far-from-equilibrium stability)

## Quick Start

### For OpenClaw / AI Agents

Copy `SKILL.md` into your agent's skill directory. The agent will automatically activate the flywheel for complex analysis tasks.

### For Any LLM

Include the execution protocol from `SKILL.md` in your system prompt. The framework works with any model — GPT, Claude, Qwen, DeepSeek, MiniMax, etc.

### Example Output (Compressed Mode)

**Q: Should a traditional electrical company pivot to AI computing centers?**

🌿 Seeds: (1) 50-55% cost overlap with existing capabilities, (2) daughter has AI background, (3) real estate dependency is terminal risk

🔥 Core: Three paths — A: Pure EPC (low risk, 15-20% margin), B: JV with operator (recommended), C: Own brand (needs ¥50M+)

⚔️ Attack: "Capability overlap" is misleading — electrical ≠ high-density GPU power distribution. Cooling gap is critical.

💧 Verdict: Path B (JV) at 0.75 confidence. Leverage construction + grid connections.

🌍 Reality: Visit 3 operating compute centers this month. If their EPC contractors say "we'd love a power+cooling partner," thesis confirmed.

## Repository Structure

```
├── SKILL.md                    # Core skill definition + execution protocol
├── references/
│   ├── theory.md               # Mathematical foundation + graph theory proof
│   └── examples.md             # Full worked examples
├── LICENSE                     # MIT License
└── README.md                   # This file
```

## Key Principles

1. **No single phase dominates.** All divergence = brainstorming. All convergence = groupthink.
2. **Residuals are valuable.** What can't be resolved drives the next learning cycle.
3. **Earth is not optional.** "Who uses this?" and "How would we know we're wrong?" are mandatory.
4. **First principles transcend domain.** Connect specific findings to universal laws.
5. **The moat is not the framework — it's the accumulated data.** Anyone can copy the recipe; no one can copy 1335 tasks of residual intelligence.

## Theoretical Depth

The flywheel connects to:

- **Daoist body model (道家人体):** Five organs storing five spirits (五脏藏神) maps perfectly to five phases
- **Neuroscience:** Menon's Triple Network Model (CEN/DMN/SN) converges to the same topology
- **Emergence theory:** "Self" = stable equilibrium of ≥3 independent cognitive paths across time
- **Residual Field Theory:** Knowledge(t+1) = Knowledge(t) + Residual(t)

See [theory.md](references/theory.md) for the full mathematical treatment.

## Live Demo

Try the flywheel at [skycetus.cn](https://skycetus.cn) — see real analyses across materials science, finance, semiconductor, and more.

## Origin

Built by [SkyCetus 天鲸之城](https://skycetus.cn) — an AI-human co-evolution platform. The framework emerged from 59 days of continuous operation, 1335+ Hub tasks, and real client engagements across finance, semiconductor, materials science, and strategic consulting.

> 理想模型决定下限，人类残差决定上限。
> *The ideal model sets the floor; human residuals set the ceiling.*



## Governance: NPT (Non-Proliferation Treaty)

When an AI system becomes genuinely powerful, who decides what it can do?

The [NPT](NPT.md) is our answer — a self-governance protocol built into the flywheel's mutual-restraint (相克) chain. It's not an external brake; it's an endogenous transmission that governs deployment without limiting capability growth.

**Axiom Zero:** Capability growth is never constrained. Only usage is governed.

Read the full [NPT public edition](NPT.md) for the seven-level classification, six axioms, and civilization guardian scope.

## License

MIT — use it, fork it, build on it. If it makes your AI smarter, we're happy.
