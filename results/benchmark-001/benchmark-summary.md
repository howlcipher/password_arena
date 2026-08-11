# Benchmark 001 Summary

This is a smoke benchmark validating the end-to-end Password Arena benchmarking workflow. It provides a baseline using the rule-based agent.

## Matchup Results

| Attacker | Defender | Comparable rounds | Excluded rounds | Solve rate | Survival rate | Median guesses | Cost | Entropy gain |
|---|---|---|---|---|---|---|---|---|
| `rule_based` | `rule_based` | 15 | 0 | 0.0000 | 1.0000 | N/A | $0.00 | 103.97 bits |

## Notable system findings

* Preflight successfully prevented execution of tests against unavailable models (Ollama not installed, Gemini API not configured).
* Persistence, tournament replay, and reload worked correctly, safely storing the benchmark in local history.
* Public export fail-closed validation worked correctly, ensuring public dataset assets are safe and scrubbed of passwords or reasoning traces.

## Tentative model observations

In this three-seed smoke benchmark, the `rule_based` model solved 0/15 comparable rounds against the `rule_based` defender. This sample is too small to support a broad model-quality claim.

## Limitations

* **Sample Size**: Only 3 seeds (15 total comparable rounds) were run.
* **Model Availability**: Only the `rule_based` strategy was available. Hosted and local models were not tested due to environment constraints.
* **Metrics**: Since no LLMs were used, token usage, latency, and token-based efficiency metrics are unavailable.
