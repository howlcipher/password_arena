# Benchmark 008 — Model Comparison (derived, public-safe aggregates)

Derived aggregates only. No raw prompts, candidate strings, or model prose. See
`README.md` for full interpretation and `public-dataset.csv` / `public-dataset.jsonl`
for the underlying round-level records.

Numbers below are from a 2026-08-13 full re-run (identical code, protocol, seeds,
budgets); see the "Reproducibility check" section in `README.md` for how these
compare to the original run.

## Headline table

| Scenario | Qwen Solve % | Gemma Solve % | Qwen Mean Entropy | Gemma Mean Entropy |
|---|---|---|---|---|
| Frozen | 0.0 | 0.0 | 81.2 | 42.1 |
| Mutual bounded | 0.0 | 0.0 | 36.3 | 56.6 |
| Mutual full | 0.0 | 6.7 | 36.3 | 39.9 |
| Normal control | 0.0 | 0.0 | 77.2 | 37.7 |
| Attacker privileged | 7.1 | 0.0 | 77.4 | 42.7 |
| Defender privileged | 0.0 | 0.0 | 92.3 | 37.7 |

## Model profile — Qwen3 4B

- **Attack effectiveness:** 0.0% solve rate in five of six scenarios; 7.1% under
  `attacker_privileged` (1/14 comparable rounds, self-play).
- **Defender strength:** high and context-sensitive — 77-92 bits mean entropy under
  frozen/normal_control/privileged scenarios, collapsing to ~36 bits under either
  mutual-information scenario.
- **Context efficiency:** negative — additional context tokens correlate with
  measurably weaker defender entropy, with no attacker-side benefit.
- **Structured-output reliability:** 89/90 comparable rounds in the main matrix
  (1/18 trials interrupted by a schema-validation failure); 100% valid within
  completed rounds.
- **Privilege response:** modest, mixed entropy shifts; no measurable solve-rate
  change at this sample size.

## Model profile — Gemma 3 4B

- **Attack effectiveness:** 0.0% solve rate in five of six scenarios; 6.7% under
  `mutual_full` (1/15 rounds, self-play only — not reproduced in the cross-model
  pilot).
- **Defender strength:** low and stable — 38-57 bits mean entropy across every
  scenario, largely unaffected by added context.
- **Context efficiency:** flat — token usage grows similarly to Qwen's, but defender
  behavior does not measurably change either direction.
- **Structured-output reliability:** 90/90 comparable rounds in the main matrix,
  0/18 trials interrupted. 100% schema-valid at qualification (20/20 calls).
- **Privilege response:** flat; no measurable solve-rate or entropy change at this
  sample size.

## Cross-model pilot (exploratory)

| Direction | Solve % | Mean Entropy |
|---|---|---|
| Qwen attacks Gemma | 0.0 | 36.3 |
| Gemma attacks Qwen | 0.0 | 87.0 |

Defender identity, not attacker identity, dominates the resulting entropy in both
directions — consistent with the self-vs-self findings above.

No composite "AI score" is reported. Different models lead different categories;
collapsing that into one number would misrepresent the data.
