# Password Arena — Benchmark 002

## What we tested

* Qwen3 4B via local Ollama
* rule-based deterministic baseline
* seeds 42, 43, 44
* 5 rounds each
* 500 guesses
* deterministic-test
* generator version benchmark

## Matchups

We tested three distinct configurations to measure role-specific behavior:
1. `ollama/qwen3:4b` attacker -> `rule_based/v1` defender
2. `rule_based/v1` attacker -> `ollama/qwen3:4b` defender
3. `ollama/qwen3:4b` attacker -> `ollama/qwen3:4b` defender

## Headline results

| Attacker | Defender | Rounds | Comparable | Excluded | Solved | Solve rate | Survival rate | Mean attacker latency | Mean defender latency | Attacker tokens | Defender tokens |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ollama/qwen3:4b` | `rule_based/v1` | 15 | 15 | 0 | 0 | 0.0% | 100.0% | 12903.0 ms | N/A | In: 2017, Out: 6867 | N/A |
| `rule_based/v1` | `ollama/qwen3:4b` | 15 | 15 | 0 | 0 | 0.0% | 100.0% | N/A | 4381.8 ms | N/A | In: 2760, Out: 1718 |
| `ollama/qwen3:4b` | `ollama/qwen3:4b` | 15 | 15 | 0 | 0 | 0.0% | 100.0% | 13115.1 ms | 4344.8 ms | In: 1991, Out: 7201 | In: 2715, Out: 1729 |

*(Note: Rule-based agents operate natively without token or network latency measurements, hence N/A).*

## Resource-constrained environment

This benchmark successfully executed a local LLM under strict isolation to validate the environment constraints.
* **Host CPU:** Ryzen 5 1600
* **Host RAM:** 24 GB
* **Model:** Qwen3 4B via Ollama
* **Isolation:** dedicated resource-limited Distrobox (podman container)
* **Constraints:** 10 GB container memory ceiling enforced; exact peak model footprint not reliably measured due to mmap semantics. CPU limits applied.
* **Context:** 4K
* **Concurrency:** one loaded model, one parallel request

## Most important finding

**All attacks may have been resisted, but survival rate alone does not indicate defender quality.**

During testing, the benchmark exposed an important limitation in relying solely on survival metrics:
A bounded strategy attacker may fail to guess a weak synthetic target.

For instance, the weakest Qwen defender generated this target:
- Length: 2
- Entropy: 6.58 bits
- Family: `cryptographic-random`
- Survived 500 guesses against the Qwen3 4B attacker (and also survived against the rule-based attacker).

This exposes a calibration limitation. A length=2 string is trivial to brute-force, but a bounded agent targeting complex password patterns may entirely omit simple exhaustive searches from its strategy. Therefore solve/survival rate must be interpreted alongside entropy, password length, family, and strategy coverage.

## What Benchmark 002 proves

* Password Arena can run a real local LLM in both roles.
* Ollama integration works end-to-end.
* public dataset export works with real model metrics.
* role-specific tokens and latency are captured.
* local benchmarking can operate under a hard resource ceiling.
* real benchmarking surfaced a methodological limitation.

## What Benchmark 002 does NOT prove

* Qwen3 is not “uncrackable.”
* 100% survival does not mean every generated password was strong (as shown by the weak target finding).
* three seeds are not sufficient for broad model-ranking claims.
* these are synthetic bounded attacks, not real authentication attacks.
* latency reflects a deliberately resource-constrained local environment.
