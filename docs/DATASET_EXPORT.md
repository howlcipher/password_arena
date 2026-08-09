# Public Benchmark Dataset Export

Password Arena can generate a local, round-level public benchmark dataset from a
tournament. This is an explicit `PUBLIC_BENCHMARK` boundary with schema version
`1.0.0`. It does not alter ordinary experiment JSON, Markdown journals, or aggregate
tournament reports.

## Installation and Hugging Face boundary

The exporter itself uses only the Python standard library. Hugging Face model
discovery is a separate optional feature:

```bash
pip install -e ".[dashboard,hf]"
```

The `hf` extra installs `huggingface_hub>=0.27,<2`. The dashboard constructs a Hub
client and reads `HF_TOKEN` only after **Search Hugging Face** is clicked. If the
variable is absent, it passes `token=False` so a persisted machine login is not used
implicitly. Search calls only `HfApi.list_models`; it never calls model detail,
download, snapshot, inference, execution, or upload APIs.

A Hub result is discovery metadata, not an executable provider. Selecting one copies
the ID to the current role's manual model field and retains the already selected
execution provider. `ProviderRegistry` remains the only execution authority.

## Row construction

`build_public_benchmark_dataset` accepts typed `PublicBenchmarkSource` values. Each
source pairs one matchup with all of its full recorded experiments. The builder:

1. Iterates only actual `ExperimentResult.rounds`.
2. Creates one row per recorded round, including non-comparable rounds.
3. Creates no row for a preflight failure or an interrupted round that never reached
   the recorded-round boundary.
4. Copies `comparable` directly from the round.
5. Copies `exclusion_reason` only from a matching existing
   `excluded_round_records` entry. Missing legacy reasons remain null.
6. Builds every row field explicitly. It never calls `ExperimentResult.to_dict()`.

Rows and the dataset summary are frozen dataclasses. The summary reports total,
comparable, and excluded row counts.

## Fixed schema

Columns appear in the order below in both JSONL objects and the CSV header.

| Group | Columns |
| --- | --- |
| Version and provenance | `dataset_schema_version`, `application_version`, `tournament_storage_schema_version`, `event_schema_version`, `replay_schema_version`, `attacker_prompt_version`, `defender_prompt_version`, `capability_registry_version` |
| Experiment | `tournament_id`, `matchup_id`, `experiment_id`, `tournament_timestamp`, `experiment_timestamp`, `seed`, `round_number`, `difficulty`, `generator_mode`, `generator_version` |
| Attacker identity and thinking | `attacker_provider`, `attacker_model`, `attacker_requested_thinking_level`, `attacker_effective_thinking_level` |
| Attacker usage and outcome | `attacker_input_tokens`, `attacker_output_tokens`, `attacker_reasoning_tokens`, `attacker_latency_ms`, `attacker_estimated_cost`, `attacker_guesses_used`, `attacker_winning_strategy`, `attacker_solved`, `attacker_outcome` |
| Defender identity and thinking | `defender_provider`, `defender_model`, `defender_requested_thinking_level`, `defender_effective_thinking_level` |
| Defender usage and target measurements | `defender_input_tokens`, `defender_output_tokens`, `defender_reasoning_tokens`, `defender_latency_ms`, `defender_estimated_cost`, `defender_password_family`, `defender_password_length`, `defender_entropy_bits`, `defender_strength_score` |
| Comparability | `comparable`, `exclusion_reason` |

Requested thinking is sourced from recorded role metadata. Effective thinking comes
from the recorded provider-call usage. If no provider call occurred, effective
thinking and all per-call usage fields remain unavailable rather than being
fabricated.

## Missing values

Unavailable is not zero:

- JSONL writes unavailable values as JSON `null`.
- CSV writes unavailable values as blank cells.
- A numeric zero is retained only when zero was actually recorded.
- A null `exclusion_reason` means no matching reason was recorded; it does not mean
  the round was comparable.

Reasoning-token fields are numeric usage counts. They never contain model reasoning
or chain-of-thought.

## Fail-closed security contract

The public row schema is a scalar allowlist. It excludes source password displays,
successful candidates, attack candidate lists, events, prompts, system prompts,
notes, learning text, model prose, hidden or private reasoning, known-password state,
API and Hugging Face tokens, authorization headers, environment values, credentials,
and breach data.

Immediately before `export_public_dataset_jsonl` or
`export_public_dataset_csv` returns, `validate_public_dataset_payload` checks the
complete proposed payload. It rejects:

- unknown or missing columns;
- forbidden field names;
- nested or container values;
- non-finite numeric values;
- secret-like token and authorization patterns; and
- any source password or candidate value present in an explicitly revealed source
  record if that value appears anywhere in the serialization.

Any failure raises `PublicDatasetSafetyError`. The exporter returns no partial file
and does not silently substitute a redacted-looking value.

## Dataset Card

`generate_dataset_card` returns Hugging Face-compatible Markdown with YAML front
matter. It documents the purpose, synthetic source, methodology, attacker and
defender roles, repeated trials, comparability, solve-rate meaning, entropy and
strength limitations, model and thinking metadata, usage semantics, intended uses,
prohibited uses, limitations, and security guarantees.

The card states that no real credentials are tested, bounded benchmark performance
is not evidence of real-world cracking, hosted models are stochastic, and provider
and model behavior can change over time.

## Saved tournament completeness

Fresh tournament results already hold their complete experiments. A saved tournament
stores links to experiment history, so the dashboard hydrates every linked experiment
for every matchup before enabling public downloads. If any link is missing, the UI
shows the count and disables JSONL, CSV, and Dataset Card downloads. It never
publishes a silently incomplete dataset.

## No-upload policy

All three outputs are generated as local download data. Password Arena has no dataset
upload, repository creation, commit, push, or automatic publication path. Publishing
a reviewed export later is an explicit action outside the application.
