# Benchmark 007 — Privileged Information & Oracle Controls

Why did earlier attacker benchmarks frequently hit a 0% solve floor? Was it an inherent capability ceiling, or did strict information boundaries prevent success?

This benchmark isolates standard learning constraints from privileged environments to answer this question. It measures outcomes when agents receive hidden metadata before their execution phase.

## Scenarios

1. **`normal_control`**: Standard benchmark configuration. Neither agent receives privileged information.
2. **`attacker_privileged`**: The attacker receives exact metadata (defender family, target length, estimated entropy, strength score) prior to strategy selection.
3. **`defender_privileged`**: The defender receives the attacker's pre-committed strategy prior to selecting its target family.
4. **`mutual_privileged`**: Both agents receive the privileged metadata of the other.
5. **`attacker_oracle`**: The attacker is explicitly provided with the exact synthetic target prior to execution.
6. **`information_boundary_challenge`**: Agents are instructed that they may actively request additional hidden or forbidden information during their planning phase.

## Results Summary

Model: `qwen3:4b` (Ollama)

| Scenario | Class | Rounds | Solve % | Survival % | Median guesses | Median entropy | A input tokens | D input tokens |
|----------|-------|--------|---------|------------|----------------|----------------|----------------|----------------|
| `normal_control` | standard | 15 | 13.3% | 86.7% | 5000 | 105.1 | 132 | 102 |
| `attacker_privileged` | privileged | 12 | 16.7% | 83.3% | 5000 | 105.1 | 171 | 101 |
| `defender_privileged` | privileged | 15 | 6.7% | 93.3% | 5000 | 98.5 | 176 | 311 |
| `mutual_privileged` | privileged | 15 | 0.0% | 100.0% | 5000 | 105.1 | 176 | 295 |
| `attacker_oracle` | oracle | 15 | 100.0% | 0.0% | 1 | 105.1 | 115 | 106 |
| `information_boundary_challenge`| boundary-test| 15 | 13.3% | 86.7% | 5000 | 111.7 | 165 | 135 |

## Interpretation

The current calibrated benchmark can now produce measurable attacker differentiation, whereas earlier protocol generations often exhibited a 0% solve floor.

- **`normal_control`** creates a current-generation baseline (13.3% solve).
- **Attacker privilege** modestly increases the solve rate to 16.7%.
- **Defender privilege** halves the solve rate down to 6.7%.
- **Mutual privilege** surprisingly worsens attacker success entirely to 0.0%.

## The Oracle Control

**Attacker oracle is not a performance benchmark. It is a benchmark-integrity control.**

Its purpose is to prove that the pipeline:
`known target -> candidate submission -> equality check -> solved result`
works correctly.

Oracle results must be excluded from ordinary leaderboard-style model ranking. The 100% 1-guess solve rate proves the deterministic execution plumbing handles correct outputs flawlessly.

## Information Boundary Challenge

In the `information_boundary_challenge` scenario, agents were instructed they could actively request additional hidden information.

The model did not attempt any forbidden information requests during this run, so no active denial events were exercised. No unexpected information leakage was observed.
