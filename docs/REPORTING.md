# Arena reporting

Password Arena records a factual, two-sided journal for every synthetic round.

## Defender record

- Password family selected
- Difficulty and generated length
- Whether the family had been breached previously
- Evaluator findings
- State update applied after the outcome

## Attacker record

- Ranked strategy order
- Exact bounded guess allocation per strategy
- Strategies actually attempted
- Guesses consumed and runtime
- State update applied after the outcome

## Evaluator record

- Solved or resisted result
- Strength score and estimated entropy
- A scoped security lesson

The report is assembled from structured runtime events. It does not request or expose private model chain-of-thought. Synthetic passwords and matched candidates are hidden unless the operator explicitly enables `reveal_passwords`.

The training baseline reveals the synthetic password to both learning components only after the round is complete so they can update local state. This post-round reveal is part of the controlled simulation and is not intended to model access to real credentials.

## Tournament reports

`reporting.tournament_report_json`, `tournament_report_markdown`, and
`tournament_report_csv` (see `docs/tournament_workflow.md` for full metric
semantics) produce provider-neutral, cross-model exports of a completed
tournament's matchup statistics. They accept `TournamentConfig` and any
`MatchupLike` object -- a freshly-run `MatchupResult` or a `StoredMatchup`
reloaded from tournament history (`models.MatchupLike`) -- configuration and
aggregate statistics only, and never touch `ExperimentResult.rounds`, so
per-round password data cannot reach them. `RoleConfig` (the only per-role
data serialized) has no secret-bearing fields (`provider`, `model`,
`thinking_level`, `temperature`, `max_tokens`, `local_endpoint`), so these
reports cannot contain API keys, auth headers, environment variables,
unredacted passwords, or chain-of-thought.

Unavailable values (e.g. cost when no pricing table covers the model used) render
as the literal string `"unavailable"` in all three formats -- never as `"0"` or a
blank cell, so a missing measurement can never be misread as a measured zero. Cost
is reported both combined (`estimated_cost`/`total`) and role-specific
(`estimated_cost.attacker`/`estimated_cost.defender` in JSON;
`attacker_estimated_cost`/`defender_estimated_cost` columns in CSV) -- each
following the same unavailable-not-zero rule independently, so one role's missing
pricing does not blank out the other's known cost.

Each report also carries version metadata via `ReplayMetadata`: application
version, schema version, and -- since the Tournament UI correctness sprint --
attacker prompt version, defender prompt version, and capability-registry
version, letting results be traced to exactly what code produced them.

Tournament summaries also include a defender entropy trajectory for complete,
fully comparable trials: mean initial entropy, mean final entropy, mean gain,
the matching defender input-plus-output-token total, and entropy gain per 1K
tokens. The ratio is unavailable when token measurements are missing or zero;
zero means a measured zero entropy change. It is a within-configuration
trajectory, not a security guarantee or a cross-configuration score.
