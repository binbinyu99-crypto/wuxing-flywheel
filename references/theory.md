# Five-Phase Flywheel — Theoretical Foundation

## Why Five? Mathematical Proof

Five is the minimum number where mutual-generation (相生) and mutual-restraint (相克) chains are both complete AND non-overlapping.

### Graph Theory Proof

- N nodes on a cycle. 相生 = adjacent edges (skip-0). 相克 = skip-2 edges.
- For 相克 to form an independent cycle (not overlapping 相生): need skip-2 on N nodes to visit all N before returning.
- N=3: skip-2 = skip-1 backwards → 相克 = reverse of 相生. Not independent.
- N=4: skip-2 → {0,2,0} — only visits 2 nodes. Incomplete.
- N=5: skip-2 → {0,2,4,1,3,0} — visits all 5. ✅ First complete independent cycle.
- N=6+: Works but adds unnecessary complexity.

**Conclusion: 5 is the minimum for dual independent complete cycles.**

### Cross-Disciplinary Convergence

| Discipline | Why 5 |
|-----------|-------|
| Thermodynamics | Dissipative structures need ≥5 coupled subsystems for sustained far-from-equilibrium stability |
| Information Theory | Shannon model: source + encoder + channel + decoder + destination = 5 |
| Control Theory | Sensor + controller + actuator + plant + feedback = 5 irreducible components |
| Biology | Minimal cell: membrane + genome + metabolism + signaling + division = 5 |
| Chinese Philosophy | 木火土金水 — 2000+ years of empirical validation in medicine, agriculture, governance |

## The 1+4 Architecture

土 (Earth) is NOT the 5th wheel — it's the central hub.

```
        木
       / \
      水   火
       \ /
        金

    All four connect through 土 (center)
```

This is a star topology, not a ring. Earth provides:
- Data exchange between all four phases
- External signal injection point (real-world feedback)
- Residual collection from all phases
- State synchronization

## Residual Field Theory Connection

The flywheel's cognitive output follows a residual pattern:

```
Knowledge(t+1) = Knowledge(t) + Residual(t)
```

Where Residual = gap between expected and actual outcome. Each flywheel cycle reduces residuals but never eliminates them — this is the engine of continuous learning.

## Self-Bootstrap Limits

The flywheel can self-improve up to Level 3 (Gödel's incompleteness theorem):
- L1: Execute given tasks → automatable
- L2: Generate own tasks → requires 木 phase
- L3: Evaluate own output → requires 金 phase
- L4: Discover own blind spots → requires external signal (土)

L3→L4 leap is impossible without 土 (external reality). This is why 土 is the center, not a peripheral wheel.
