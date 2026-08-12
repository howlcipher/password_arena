# Benchmark 008 — Model Comparison (derived, public-safe aggregates)

Derived aggregates only. No raw prompts, candidate strings, or model prose. See
`README.md` for full interpretation and `public-dataset.csv` / `public-dataset.jsonl`
for the underlying round-level records.

## Headline table

| Scenario | Qwen Solve % | Gemma Solve % | Qwen Mean Entropy | Gemma Mean Entropy |
|---|---|---|---|---|
| Frozen | 0.0 | 0.0 | 80.2 | 43.1 |
| Mutual bounded | 0.0 | 13.3 | 36.3 | 38.9 |
| Mutual full | 0.0 | 0.0 | 36.3 | 38.1 |
| Normal control | 0.0 | 0.0 | 95.6 | 39.2 |
| Attacker privileged | 0.0 | 0.0 | 86.0 | 42.0 |
| Defender privileged | 0.0 | 0.0 | 95.1 | 37.9 |

## Model profile — Qwen3 4B

- **Attack effectiveness:** 0.0% solve rate across all six scenarios in this run.
- **Defender strength:** high and context-sensitive — 80-96 bits mean entropy under
  frozen/normal_control/privileged scenarios, collapsing to ~36 bits under either
  mutual-information scenario.
- **Context efficiency:** negative — additional context tokens correlate with
  measurably weaker defender entropy, with no attacker-side benefit.
- **Structured-output reliability:** 83/90 comparable rounds in the main matrix
  (3/18 trials interrupted by schema-validation failures); 100% valid within
  completed rounds.
- **Privilege response:** modest, mixed entropy shifts; no measurable solve-rate
  change at this sample size.

## Model profile — Gemma 3 4B

- **Attack effectiveness:** 0.0% solve rate in five of six scenarios; 13.3% under
  `mutual_bounded` (2/15 rounds, self-play only — not reproduced in the cross-model
  pilot).
- **Defender strength:** low and stable — 37-43 bits mean entropy across every
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
| Qwen attacks Gemma | 0.0 | 34.3 |
| Gemma attacks Qwen | 0.0 | 94.6 |

Defender identity, not attacker identity, dominates the resulting entropy in both
directions — consistent with the self-vs-self findings above.

No composite "AI score" is reported. Different models lead different categories;
collapsing that into one number would misrepresent the data.
