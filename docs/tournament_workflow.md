# Multi-Model Tournament Workflow

Password Arena includes a Tournament and Benchmark mode with round-level statistics,
persistence (save/list/load/delete), replay, and cross-model reports. This document
describes exactly what is measured and what its limitations are -- do not rely on
older descriptions of this feature that predate the statistics rewrite (see BUG-009
through BUG-015 in `bugs.md`).

## Features
- **Fair Comparisons:** Runs identical difficulty progression, seeds, and guess
  budgets across multiple models.
- **Repeated Trials:** Each matchup executes across a designated number of seeds.
  The headline solve/survival rate is a round-level statistic (see below), not a
  per-trial win/loss count.
- **Matrix Orchestration:** Compare `N` attackers versus `M` defenders efficiently.
- **Persistence lifecycle:** Matchup summaries are saved to `.password_arena_tournaments`
  (see `TournamentHistoryManager`: `save`/`list_runs`/`load`/`delete`), linked to full
  round logs saved in single-experiment history (`HistoryManager`).
- **Replay:** Deterministic replay for rule_based-vs-rule_based, deterministic-test
  configurations; configuration replay (re-running the same config, no reproducibility
  claim) for any hosted-model configuration.
- **Cross-model reports:** JSON, Markdown, and CSV exports (`reporting.tournament_report_*`).

## How to use the Tournament Dashboard
1. Run `password-arena --ui` to start the Streamlit application.
2. Navigate to the **Tournament** tab.
3. Select any combination of attacker roles and defender roles.
4. Configure standard constraints: rounds per match, trials (seeds), and max guesses.
5. Click **Run Tournament**.

The UI automatically filters out self-play matches (e.g. a model defending against
itself) if selected, and executes the complete matchup matrix in sequence.

## Metric semantics

### Solve rate and survival rate (headline)

The headline metric is a **round-level** Bernoulli statistic, not a per-trial
win/loss count:

```
solve rate     = comparable rounds solved   / comparable rounds completed
survival rate  = comparable rounds resisted / comparable rounds completed
```

A round counts if it belongs to a trial that ran (even a trial later interrupted
contributes its already-completed, non-fallback rounds) and the round itself did
not require a provider fallback (see Comparability below).

A narrower, explicitly-labeled statistic is also reported: `final_round_solved_count`
/ `final_round_resisted_count` -- whether the attacker solved the *last* (typically
hardest) round of each comparable trial. This is not the headline number; it exists
because difficulty escalates per round, so "did it solve the peak-difficulty round"
has standalone meaning.

### Guesses

Three distinct guess metrics are reported, and they are not interchangeable:
- `mean_guesses_per_round` / `median_guesses_per_round`: guesses consumed across
  every comparable round, solved or resisted.
- `mean_guesses_to_solve` / `median_guesses_to_solve`: guesses consumed on
  **solved rounds only**. This is the only metric that should be called
  "guesses to solve."
- `mean_total_guesses_per_trial`: total guesses summed across all rounds of each
  comparable trial.

### Tokens, latency, and cost

Tracked separately per role (attacker/defender): input tokens, output tokens,
reasoning tokens (when exposed by the provider), and mean latency. Estimated cost
is tracked both ways: a combined `total_estimated_cost: float | None` and, since
this sprint, role-specific `attacker_estimated_cost` / `defender_estimated_cost`.
Efficiency ratios (`attacker_solved_per_dollar`, `defender_survived_per_dollar`)
use the matching role-specific cost as their denominator, never the combined
total -- otherwise the other role's spend would be misattributed.

**A missing cost is `None`, never `0.0`.** If any comparable round used an LLM call
whose provider could not price the model, the affected scope's cost is `None` --
`total_estimated_cost` is `None` if either role has any unknown-cost round;
`attacker_estimated_cost`/`defender_estimated_cost` are `None` only for the
affected role, so one role's missing pricing does not blank out the other's known
cost. All are rendered as `"unavailable"` in reports, never as a zero. A role that
made no LLM calls at all (rule_based) reports a real, known `0.0` for that role.

As of this writing, `gemini` and `ollama` providers have no pricing table, so any
matchup using them will report the affected role's (and therefore the combined)
cost as unavailable.

The Tournament dashboard's cross-matchup rollups (tournament totals, per-attacker/
per-defender leaderboard costs) apply the same rule at their own granularity: a
sum is only shown when **every** contributing matchup's cost for that role/scope
is known; otherwise the rollup is `None`/"unavailable", never silently summed as
if the unknown contributors were zero. See `tournament_view_models.py`.

### Comparability

Comparability is tracked at the smallest meaningful unit, with exclusion reasons
recorded (never silently discarded):
- **Trial-level:** a trial (one seed) is excluded if its preflight check failed
  (`preflight_failed`) or it was interrupted mid-run (`interrupted_provider`).
  Trial-level statistics (`final_round_*`, `mean_total_guesses_per_trial`,
  `comparable_trials`) only use comparable trials.
- **Round-level:** an individual round is excluded (`fallback_used`) if either
  role's provider call fell back to a different model/config for that round. This
  can happen inside an otherwise-clean trial -- the round-level headline
  (solve/survival rate, guess metrics, token/latency/cost totals) is computed from
  every comparable round across *all* trials, including trials later interrupted.

`MatchupResult.excluded_trial_records` / `excluded_round_records` hold the full,
unabridged list of exclusions (seed, experiment id, round number, reason) for
inspection -- headline statistics exclude them by default, they are never dropped.

### Confidence intervals

The 95% confidence interval is a Wilson score interval computed over the
round-level solve rate: `successes = rounds_solved`, `trials = rounds_completed`
(comparable observations only). This assumes independent Bernoulli round outcomes.
**Repeated hosted-model trials are stochastic and may not be strictly independent**
in the statistical sense -- treat the interval as a standard descriptive convention,
not a rigorous guarantee.

### Efficiency

Transparent, role-specific ratios -- never a single blended "AI score":
`attacker_solved_per_1k_tokens`, `attacker_solved_per_second`,
`attacker_solved_per_dollar`, `defender_survived_per_1k_tokens`,
`defender_survived_per_dollar`. Each is `None` (never a fabricated value) when its
denominator is zero or unavailable.

## Persistence

`TournamentHistoryManager` supports the full lifecycle: `save`, `list_runs`, `load`,
`delete`. Only matchup metadata and links to full experiments (`experiment_ids`) are
saved directly; full round logs live in single-experiment history (`HistoryManager`).
`load()` tolerates JSON saved before this rewrite (schema version < `"2.0"`) by
mapping old field names onto their nearest new equivalent, and reports any linked
experiment that can no longer be found (`missing_experiment_ids`) rather than raising.

## Replay

`replay_matchup()` re-runs a matchup's stored configuration. Exact reproduction is
only guaranteed when `MatchupResult.replay.deterministic` is `True` (both roles
`rule_based`, `generator_mode == "deterministic-test"`). For any hosted-model
configuration this is "configuration replay" only: the same configuration is
re-run, with no claim that a hosted model will reproduce prior output.

## Reports

`reporting.tournament_report_json/markdown/csv` produce provider-neutral exports
covering: tournament ID, timestamp, provider/model/thinking level per role, seed
set, rounds, guess budget, comparable/excluded observation counts and reasons,
solve/survival rate, guess metrics, token/latency/cost, confidence interval, and
efficiency. They operate only on configuration and aggregate statistics -- never on
per-round password data -- so they cannot contain API keys, auth headers,
environment variables, unredacted passwords, or chain-of-thought.
