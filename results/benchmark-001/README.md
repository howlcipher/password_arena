# Password Arena — Benchmark 001

## Purpose

This is a smoke benchmark validating the end-to-end Password Arena benchmarking workflow.

It is not intended as a definitive model leaderboard.

## Environment

* Date: 2026-08-11
* Password Arena Git SHA: 42c7c45d104b492361bae57ef5e9ac2caf790a43
* Python version: 3.14.4
* Password Arena version: 0.1.0
* Ollama version: N/A
* Ollama model: N/A
* Gemini model: N/A

## Configuration

* Seeds: 42, 43, 44
* Rounds: 5
* Max guesses: 500
* Generator mode: deterministic-test
* Generator version: benchmark
* Thinking settings: auto
* Relevant resource budgets: Max guesses = 500, Max tokens = None, Max cost = None

## Participants

* `rule_based`: Available
* Ollama models: Unavailable
* Gemini models: Unavailable

## Matchups

* `rule_based` attacker vs `rule_based` defender

## Results

| Attacker | Defender | Comparable rounds | Excluded rounds | Solve rate | Survival rate | Median guesses | Attacker tokens | Defender tokens | Attacker latency | Defender latency | Estimated cost | Entropy gain | Entropy gain / 1K defender tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `rule_based` | `rule_based` | 15 | 0 | 0.0000 | 1.0000 | N/A | 0 | 0 | N/A | N/A | 0.000000 | 103.97 bits | N/A |

## Integrity

* interruptions: 0
* exclusions: 0
* fallback usage: 0
* provider failures: N/A (no hosted models attempted due to preflight constraints)
* missing metrics: Guesses to solve is N/A because there were no successful solves. Token-based efficiency and latency are N/A because rule-based participants do not invoke models.
* comparability concerns: None.

## Observations

### Benchmark-system observations

* Preflight successfully prevented execution of tests against unavailable models (Ollama not installed, Gemini API not configured).
* Persistence and reload worked correctly, capturing the benchmark in local history.
* Public export validation passed successfully, generating valid JSONL/CSV outputs.
* Real usage confirmed the benchmark system functions end-to-end for the rule-based baseline.

### Model observations

In this three-seed smoke benchmark, the `rule_based` model solved 0/15 comparable rounds against the `rule_based` defender.
This sample is too small to support a broad model-quality claim.

## Safety

* synthetic passwords only
* no real credentials
* no authentication endpoints
* public exports exclude target passwords/candidates/prompts/private reasoning

## Next benchmark

The recommended next campaign is a larger 10-seed matrix comparing an installed Ollama model and a configured Gemini model against the rule-based baseline.
