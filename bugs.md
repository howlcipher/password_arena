# Bugs Backlog

This file tracks confirmed defects and behavioral mismatches. Product ideas belong in `improvements.md`.

## Severity guide

- **P0:** unsafe behavior, credential exposure, or unusable core system.
- **P1:** major incorrect behavior or broken primary workflow.
- **P2:** meaningful defect with a workaround.
- **P3:** minor display, reporting, or edge-case issue.

## Status values

- **Open**
- **In Progress**
- **Blocked**
- **Resolved**
- **Won't Fix**

---

## BUG-001 — Guess budgets below four can create negative allocations

**Priority:** P1  
**Status:** Resolved  
**Resolved in:** Initial repository setup

### Previous behavior

The allocator forced at least one guess into all four strategies and then subtracted the excess from the highest-ranked strategy. With budgets of one or two, the highest allocation became negative and `itertools.islice` raised `ValueError`. A budget of three could assign zero guesses to the highest-ranked strategy.

### Resolution

The allocator now uses largest-remainder distribution. Allocations are non-negative, sum exactly to the configured budget, and zero-budget strategies are skipped.

### Regression coverage

`test_tiny_guess_budgets_are_valid_and_bounded` validates budgets one through four.

---

## BUG-002 — Seeded high-difficulty runs are not fully reproducible

**Priority:** P1  
**Status:** Resolved  
**Resolved in:** BUG-002 Fix

### Reproduction

1. Run two experiments with the same seed, `reveal_passwords=True`, and a difficulty of seven or higher.
2. Compare the generated cryptographic-random passwords.
3. The values differ because `secrets.choice` intentionally ignores the experiment seed.

### Impact

The README describes the baseline as reproducible, but secure-random defender rounds are intentionally nondeterministic. This also prevents exact replay of complete experiments.

### Resolution

- Added `generator_mode` to `ArenaConfig` and `AdaptiveDefender` with `"secure"` and `"deterministic-test"` as valid options.
- The `generator_mode` defaults to `"secure"` to maintain secure generation for the password-manager endpoint.
- Updated `AdaptiveDefender` to use `self.rng.choice` when `generator_mode` is `"deterministic-test"`, ensuring full reproducibility, while continuing to use `secrets.choice` for `"secure"` mode.
- Exposed `--generator-mode` parameter in the CLI.

### Validation performed

Run `ruff check .`, `mypy src/password_arena`, and `pytest`. All passed.

---

## BUG-003 — Attacker passphrase grammar does not match all defender passphrases

**Priority:** P1  
**Status:** Resolved
**Resolved in:** BUG-003 Fix

### Reproduction

Run difficulty five or six rounds. The defender emits three- or four-word passphrases with arbitrary three-digit suffixes. The attacker generates at most three words and mostly two-digit suffixes, plus only `123` and `2026` as longer suffixes.

### Impact

Some rounds are structurally unreachable by the intended passphrase strategy regardless of a reasonable budget. The experiment can therefore measure grammar mismatch rather than adaptive strategy quality.

### Resolution

- Created `src/password_arena/grammars.py` to separate password grammar and training data.
- Split words into `SHARED_WORDS` (known to attacker and defender) and `HELD_OUT_WORDS` (known only to defender).
- Added up to four-word passphrases generation for the attacker.
- Modified suffix generation for the attacker to include 0-999.
- Added `tests/test_grammars.py` to prove benchmark cases are reachable, while held-out cases remain genuinely novel.

### Validation performed

Run `ruff check .`, `mypy src/password_arena`, and `pytest`. All passed.

---

## BUG-004 — Failed attacks report a strategy as though it solved the password

**Priority:** P2  
**Status:** Resolved  
**Resolved in:** BUG-004 Fix

### Previous behavior

Run a resistant round and inspect `AttackResult.strategy` or the dashboard's “Attack strategy” column. The field contains the highest-priority strategy even though no strategy succeeded and several may have been attempted.

### Resolution

- Renamed `AttackResult.strategy` to `AttackResult.winning_strategy` and set it to `None` on failure.
- Updated `cli.py`, `dashboard.py`, `reporting.py`, and `attacker.py` to use `winning_strategy`.

### Validation performed

Run `ruff check .`, `mypy src/password_arena`, and `pytest`. All passed.

---

## BUG-005 — Reusing one ArenaEngine instance carries state into a second run

**Priority:** P2  
**Status:** Resolved  
**Resolved in:** BUG-005 Fix

### Reproduction

1. Construct one `ArenaEngine` instance.
2. Call `run()` twice.
3. The second call starts with defender breach memory, attacker learned words, strategy scores, and advanced random state from the first call.

### Impact

A caller may expect `run()` to represent a fresh experiment because the configuration is unchanged. The current lifecycle is not documented.

### Expected resolution

Choose and document one contract:

- make `run()` single-use and raise on a second call;
- reset agents at the start of each run; or
- rename the operation to make continued training explicit and introduce a separate fresh-run API.

### Resolution

- Initialized a `_has_run` boolean to `False` in the `ArenaEngine.__init__` method.
- Updated the `run()` method to check this boolean. If `_has_run` is `True`, it now raises a `RuntimeError`.
- Set `_has_run = True` immediately after the check to prevent any subsequent runs.

### Validation performed

Added `test_engine_single_use` in `tests/test_engine.py`. Ran `ruff check .`, `mypy src/password_arena`, and `pytest`. All tests passed successfully.

---

## BUG-006 — Invalid CLI configuration produces a Python traceback

**Priority:** P2  
**Status:** Resolved
**Resolved in:** CLI validation update

### Reproduction

Run `password-arena --rounds 0` or another value rejected by `ArenaConfig.validate()`.

### Impact

The CLI exposes an implementation traceback instead of a concise usage error, which makes normal input validation look like an application crash.

### Expected resolution

Catch validation errors at the CLI boundary and pass them to `argparse.ArgumentParser.error()` or return a concise non-zero error message. Add subprocess-level CLI tests.

### Resolution

Added a call to `config.validate()` in `src/password_arena/cli.py` and caught the `ValueError`, passing the error message to `argparse.ArgumentParser.error()`. Added `test_cli_invalid_config` in `tests/test_cli.py` to assert the CLI outputs a concise error message without tracebacks.

---

## BUG-007 — Entropy and guess counts share one chart scale

**Priority:** P2  
**Status:** Resolved  
**Resolved in:** BUG-007 Fix

### Reproduction

Run the Streamlit dashboard with a guess budget in the thousands. The “Learning curves” chart plots entropy bits and guesses on the same numeric scale.

### Impact

The entropy line appears almost flat and the chart can imply that strength is not changing.

### Expected resolution

Render separate charts or use a clearly labeled dual-axis visualization. Add strategy efficiency and solve outcome overlays only when they remain readable.

### Resolution

- Updated `src/password_arena/dashboard.py` to display two separate line charts side-by-side using `st.columns(2)` for "Entropy bits" and "Guesses" to resolve the scale discrepancy.

### Validation performed

Ran `ruff check .`, `mypy src/password_arena`, and `pytest`. All tests passed successfully.

---

## BUG-008 — Rounded strategy weights may not display as exactly 100 percent

**Priority:** P3  
**Status:** Resolved  
**Resolved in:** BUG-008 Fix

### Reproduction

Inspect serialized `StrategyBudget.weight` values. Weights are rounded to four decimal places before storage, so displayed percentages can sum slightly above or below 100 percent.

### Impact

The exact integer guess budgets remain authoritative, but the report can look internally inconsistent.

### Expected resolution

Store full-precision normalized weights and round only in presentation layers, or derive displayed percentages directly from integer allocations.

### Resolution

- Updated `src/password_arena/attacker.py` to store exact, full-precision weight for `StrategyBudget` without rounding to 4 decimal places.

### Validation performed

Ran `ruff check .`, `mypy src/password_arena`, and `pytest`. All tests passed successfully.

---

## BUG-009 — Tournament trial outcome ignores every round but the last

**Priority:** P1  
**Status:** Resolved  
**Resolved in:** Tournament aggregation rewrite

### Reproduction

Run a tournament matchup with `rounds > 1`. `run_matchup()` determined whether the attacker "won" a trial by inspecting only `experiment.rounds[-1].attack.solved` (`tournament.py:88-94`, pre-fix), discarding the outcome of every other round in the trial.

### Impact

A trial where the attacker solved 7 of 8 rounds and an otherwise-identical trial where the attacker solved only the final round were indistinguishable in the headline statistic. Solve rate could not be trusted as a summary of attacker performance.

### Expected resolution

Define an explicit, round-level headline metric and keep any retained trial-level binary statistic narrowly scoped and separately labeled.

### Resolution

- `tournament.py::aggregate_matchup` now computes `solve_rate`/`survival_rate` as round-level Bernoulli statistics (`rounds_solved`/`rounds_completed`, comparable observations only).
- The old last-round check is retained only as an explicitly narrow, separately labeled `final_round_solved_count`/`final_round_resisted_count` -- never presented as the headline.

### Validation performed

`tests/test_tournament.py::test_one_solved_one_resisted_round`, `test_all_solved`, `test_none_solved`. Ran `ruff check .`, `mypy src/password_arena tests`, and `pytest`.

---

## BUG-010 — Tournament guess statistic mixes solved and resisted rounds under a misleading name

**Priority:** P2  
**Status:** Resolved  
**Resolved in:** Tournament aggregation rewrite

### Reproduction

`mean_guesses` (pre-fix) summed `guesses_used` across every round of a trial, including rounds the attacker never solved, which still consume up to `max_guesses` guesses.

### Impact

A number that reads as "guesses to solve" was actually a blended, always-larger total-guess-volume figure, understating attacker efficiency and misleading anyone comparing models.

### Expected resolution

Separate "guesses to solve" (solved rounds only) from "guesses per round" (all rounds) and "total guesses per trial."

### Resolution

- `MatchupSummary` now reports `mean_guesses_to_solve`/`median_guesses_to_solve` (solved rounds only), `mean_guesses_per_round`/`median_guesses_per_round`/`std_guesses_per_round` (all comparable rounds), and `mean_total_guesses_per_trial` (per-trial sums) as distinct fields.

### Validation performed

`tests/test_tournament.py::test_guess_statistics_hand_calculated`. Ran `pytest`.

---

## BUG-011 — Tournament token and cost aggregation is dead placeholder code

**Priority:** P1  
**Status:** Resolved  
**Resolved in:** Tournament aggregation rewrite

### Reproduction

`run_matchup()` executed `total_tokens += 0` and `total_estimated_cost += 0.0` unconditionally every loop iteration (`tournament.py:96-97`, pre-fix), even though `engine.py`'s `BudgetTracker` already accumulated real usage per trial. `MatchupSummary.total_tokens`/`total_estimated_cost` were always zero regardless of actual LLM usage. Separately, every provider adapter defaulted `estimated_cost` to `0.0` even when the model's price was unknown, so a genuinely-unpriced call was indistinguishable from a genuinely-free one.

### Impact

Any tournament involving hosted models reported zero tokens and zero cost, making cost/efficiency comparisons meaningless and silently misleading.

### Expected resolution

Wire real per-role usage into round/trial/matchup results, and represent unknown cost as `None`, never a fabricated `0.0`.

### Resolution

- `providers.py::UsageMetrics.estimated_cost` is now `float | None` (`None` = unavailable). `openai_provider.py`/`anthropic_provider.py` only set a float when their pricing table covers the model; `gemini_provider.py`/`ollama_provider.py` never fabricated a cost and now correctly default to `None`. `engine.py::BudgetTracker.add_metrics` guards the `None` case.
- `engine.py::BoundBackend` now records `last_metrics` per call; `ArenaEngine.run()` captures per-role `RoleUsage` (tokens, latency, cost, fallback flag) onto each `RoundResult`.
- `tournament.py::aggregate_matchup` sums real per-role tokens/latency and propagates `total_estimated_cost=None` if any contributing call had unknown cost, rather than silently treating it as zero.
- `gemini_provider.py`/`ollama_provider.py` also gained real latency measurement (previously always `0.0`, a fabricated measurement for a network call).

### Validation performed

`tests/test_tournament.py::test_role_specific_token_and_latency_aggregation`, `test_unavailable_cost_propagates_as_none`, `test_known_cost_sums_including_rule_based_zero`; `tests/test_openai_provider.py::test_openai_provider_unpriced_model_cost_is_unavailable`; `tests/test_anthropic_provider.py` equivalent; `tests/test_engine.py::test_mock_backend_populates_usage_via_build_arena_engine`. Ran `ruff check .`, `mypy src/password_arena tests`, and `pytest`.

---

## BUG-012 — One interrupted seed marks an entire matchup non-comparable and loses prior exclusion reasons

**Priority:** P1  
**Status:** Resolved  
**Resolved in:** Tournament aggregation rewrite

### Reproduction

`run_matchup()` used a single matchup-wide `is_comparable`/`non_comparable_reason` pair (pre-fix). Any preflight failure or interruption set `is_comparable = False` and overwrote `non_comparable_reason`, so if seed A failed for one reason and seed B failed for another, only B's reason survived, and every trial in the matchup -- including ones that completed cleanly -- was excluded from headline statistics.

### Impact

A single rate-limited seed could discard an entire matchup's worth of valid observations, and the recorded failure reason could be wrong for part of the run.

### Expected resolution

Track comparability at the smallest meaningful unit (round and trial), record every exclusion with its own reason, and compute headline statistics only from comparable observations while preserving excluded ones for inspection.

### Resolution

- Added `ExclusionRecord`/`ExclusionReason` (`models.py`). `MatchupResult` now carries `excluded_trial_records` (preflight failures, interruptions) and `excluded_round_records` (per-round provider fallback) as complete, unabridged lists -- never overwritten or discarded.
- `RoundResult.comparable` is a new round-level flag (false only when that round's provider call used a fallback). Round-level headline statistics use every comparable round from every trial, including trials later interrupted -- their already-recorded, non-fallback rounds are still valid observations.
- `MatchupResult.is_comparable` is now `comparable_trials > 0` rather than "zero failures anywhere."

### Validation performed

`tests/test_tournament.py::test_interrupted_trial_completed_rounds_still_count_for_headline`, `test_preflight_failure_is_excluded_and_recorded`, `test_fallback_round_excluded_but_trial_stays_comparable`. Ran `pytest`.

---

## BUG-013 — Confidence interval computed over the flawed last-round trial statistic

**Priority:** P2  
**Status:** Resolved  
**Resolved in:** Tournament aggregation rewrite

### Reproduction

`calculate_confidence_interval(attacker_wins, completed_trials)` (pre-fix) fed the Wilson score formula the same last-round-only win count described in BUG-009. The formula itself was correct; its input was not.

### Impact

The reported confidence interval implied statistical precision around a trial-level statistic that did not honestly summarize a trial's rounds.

### Expected resolution

Re-point the (already-correct) Wilson interval at the round-level solve rate, and document the independence assumption.

### Resolution

- `tournament.py::aggregate_matchup` now calls `calculate_confidence_interval(rounds_solved, rounds_completed)`. The function's docstring documents that it assumes independent Bernoulli observations and that repeated hosted-model trials may not be strictly independent.

### Validation performed

`tests/test_tournament.py::test_confidence_interval_exact_value`, `test_confidence_interval_edge_cases`. Ran `pytest`.

---

## BUG-014 — TournamentHistoryManager has no list, load, or delete

**Priority:** P2  
**Status:** Resolved  
**Resolved in:** Tournament history lifecycle

### Reproduction

`tournament_history.py` (pre-fix) implemented only `save()`. No caller anywhere in the codebase could list, reload, or delete a saved tournament.

### Impact

Saved tournaments were effectively write-only; the persistence feature described in documentation did not exist in practice.

### Expected resolution

Complete the lifecycle to match the existing single-experiment `HistoryManager` (save/list/load/delete), with schema versioning and backward-compatible parsing for files saved before the change.

### Resolution

- Added `TOURNAMENT_SCHEMA_VERSION`, `list_runs()`, `load()` (returns `StoredTournament`/`StoredMatchup`, defensively parsed field-by-field so old-format JSON loads without crashing), `delete()`, and `hydrate_experiments()` (joins a stored matchup back to its full `ExperimentResult`s in `HistoryManager`, tolerating a dangling linked id rather than raising).

### Validation performed

`tests/test_tournament_history.py` (save/list/load/delete round trip, old-format tolerance, dangling-id hydration). Ran `pytest`.

---

## BUG-015 — Streamlit "Save profile" is vulnerable to path traversal

**Priority:** P1  
**Status:** Resolved  
**Resolved in:** Profile export hardening

### Reproduction

`dashboard.py` (pre-fix) built `Path(f"{profile_name}.json")` directly from an unsanitized `st.text_input` and called `.write_text()` on it, with no containment check. A `profile_name` of `../../outside` or an absolute path was honored as-is.

### Impact

A user (or anyone with access to the running dashboard) could write a JSON file to an arbitrary path reachable by the server process, limited only by OS permissions.

### Expected resolution

Either confine writes to a fixed directory with a validated filename, or avoid the server-side filesystem write entirely via a browser download.

### Resolution

- Replaced the filesystem write with `st.download_button`, matching the pattern already used elsewhere in the same file for JSON/Markdown exports. No server-side path is ever constructed from user input; the suggested browser filename is sanitized to `[A-Za-z0-9_-]` as a hygiene measure only, since no traversal is possible once there is no filesystem write.

### Validation performed

`tests/test_dashboard.py::test_save_profile_never_writes_to_filesystem`, parametrized over `../../outside`, `../foo`, and `C:\temp\thing`, asserting no file is created anywhere in the test's working directory. Ran `pytest`.

---

## BUG-016 — Tournament tab is unreachable until an Arena experiment has been run

**Priority:** P1  
**Status:** Resolved  
**Resolved in:** Tournament UI correctness sprint

### Reproduction

Load the dashboard fresh (`password-arena --ui`) and click straight to the **Tournament** tab without first running anything on the **Arena** tab.

### Impact

`render_dashboard()` renders `tab1` (`render_arena_tab()`) before `tab2`
(`render_tournament_tab()`). `render_arena_tab()` calls `st.stop()` whenever
`st.session_state.experiment` is unset (i.e., on every first load), and
`st.stop()` halts the *entire* script run, not just the current tab's container.
Confirmed via `streamlit.testing.v1.AppTest`: on a fresh session, `at.button`
only contains `"Run arena"` -- no tournament widgets exist in the tree at all
until after an Arena experiment has been run once, moving `st.session_state`
past the `st.stop()` guard on a later rerun. A user who only wants Tournament
Mode currently cannot reach it without first running an unrelated single-arena
experiment.

### Expected resolution

Move the "no experiment yet" early-return out of the shared script path -- e.g.
guard only the Arena tab's results section, not the whole script, or check
`st.session_state.experiment` before calling `st.stop()` in a way that does not
also block sibling tabs from rendering.

### Resolution

Replaced all three `st.stop()` calls in `render_arena_tab()` with `return`.
`st.stop()` halts the entire script run (both tabs); `return` only exits the
Arena tab's own render function, leaving `render_tournament_tab()` (called
afterward in the same script run) unaffected. Also removed the duplicate
`st.set_page_config()` call that used to live inside `render_arena_tab()` --
`render_dashboard()` now makes the single application-level call, since the
Arena tab is no longer guaranteed to always run first without side effects.

### Validation performed

`tests/test_dashboard.py::test_tournament_tab_accessible_without_arena_run`:
fresh `AppTest` session, asserts both Arena controls ("Run arena") and
Tournament controls ("Run Tournament", "Add Attacker", "Add Defender", the
"Tournament Configuration" header) exist without ever running Arena. Ran
`pytest`.

---

## BUG-017 — Tournament Overview understated total cost by treating unknown per-matchup cost as zero

**Priority:** P1  
**Status:** Resolved  
**Resolved in:** Tournament UI correctness sprint

### Reproduction

Run or load a tournament containing at least one matchup with known cost and at least one matchup using a provider without cost metadata (e.g. `gemini`/`ollama`, or any comparable round with `RoleUsage.estimated_cost=None`). Open the Overview tab.

### Impact

`tournament_views.py::render_overview` computed `cost_known = any(r.summary.total_estimated_cost is not None for r in results)` and `total_cost = sum((r.summary.total_estimated_cost or 0.0) for r in results)`. Because `cost_known` only required *one* matchup to have a known cost, and the sum silently substituted `0.0` for every unpriced matchup, the Overview displayed a confident dollar figure that was actually missing an unknown amount -- directly contradicting the documented invariant (`docs/tournament_workflow.md`): "a missing cost is `None`, never `0.0`."

### Expected resolution

A cross-matchup cost rollup must require *every* contributing matchup's cost to be known before showing a sum; otherwise it must render as unavailable, matching the same discipline `tournament.py::aggregate_matchup` already applies within a single matchup.

### Resolution

Added `aggregate_tournament_cost()` (`tournament_view_models.py`), a pure function using `all()`-known semantics: sums `total_estimated_cost` across the given matchups only if none are `None`; otherwise returns `None`. `render_overview` now calls this instead of the inline `any()`/`or 0.0` logic. Also fixed the same-shaped bug in the solve/survival rate computation, which used to silently render `0.0` (not "no data") when there were zero comparable rounds.

### Validation performed

`tests/test_tournament_view_models.py::test_aggregate_tournament_cost_known_zero`,
`::test_aggregate_tournament_cost_unknown_when_any_matchup_unknown`,
`::test_aggregate_tournament_cost_empty_is_none_not_zero`,
`::test_build_overview_cost_unknown_not_zero_substituted`,
`::test_build_overview_no_comparable_rounds_returns_none_not_zero`. Ran `pytest`.

---

## BUG-018 — Attacker leaderboard "Cost" column showed combined attacker+defender matchup cost

**Priority:** P1  
**Status:** Resolved  
**Resolved in:** Tournament UI correctness sprint

### Reproduction

Run a tournament where attacker and defender both use priced hosted providers. Open the Leaderboards tab and inspect the attacker table's "Cost" column.

### Impact

`tournament_views.py::render_leaderboards` populated the attacker "Cost" column from `r.summary.total_estimated_cost` -- the whole matchup's combined attacker+defender spend -- with an inline comment self-acknowledging the shortcut ("Fallback: per role not separated"). This inflated apparent attacker cost by however much the defender spent, and the defender leaderboard had no Cost column at all, so defender spend was invisible.

### Expected resolution

Either compute real per-role cost from the data already available (`RoleUsage.estimated_cost` is role-separated at the round level), or mark attacker/defender cost unavailable rather than presenting combined cost as attacker-only.

### Resolution

Extended the data model cleanly: added `attacker_estimated_cost`/`defender_estimated_cost` to `MatchupSummary`, computed in `tournament.py::aggregate_matchup` with the same all-known-or-`None` discipline as the existing combined total (per role, not the whole matchup). `compute_efficiency` now divides `attacker_solved_per_dollar` by the attacker's own cost and `defender_survived_per_dollar` by the defender's own cost, not the combined total. The attacker leaderboard reads `attacker_estimated_cost`; the defender leaderboard gained a "Cost" column reading `defender_estimated_cost`.

### Validation performed

`tests/test_tournament.py::test_role_specific_cost_is_not_combined_matchup_cost`,
`::test_role_specific_cost_unknown_for_only_the_affected_role`,
`::test_role_specific_cost_zero_when_role_never_calls_llm`,
`::test_efficiency_uses_role_specific_cost_not_combined`;
`tests/test_tournament_view_models.py::test_defender_leaderboard_is_weighted_and_has_cost_column`. Ran `pytest`.

---

## BUG-019 — Leaderboard and thinking-level comparisons used an unweighted mean of per-matchup rates

**Priority:** P1  
**Status:** Resolved  
**Resolved in:** Tournament UI correctness sprint

### Reproduction

Build fixtures where one attacker played matchup A (100 comparable rounds, 100% solve rate) and matchup B (2 comparable rounds, 0% solve rate) against different defenders. Check the attacker leaderboard's aggregate solve rate.

### Impact

`tournament_views.py::render_leaderboards` and `render_thinking_comparison` built a per-matchup row per attacker/defender/thinking-level, then called `df.groupby(...).mean(numeric_only=True)` -- an unweighted arithmetic mean of each matchup's own percentage. With the fixture above, this produced 50% (mean of 100% and 0%) rather than the statistically correct 100/102 ≈ 98.0% (ratio of summed counts). A matchup with 2 comparable rounds carried equal statistical weight to one with 100.

### Expected resolution

Aggregate as a ratio of summed counts (`sum(rounds_solved) / sum(rounds_completed)`), matching how `tournament.py` itself defines solve/survival rate, not a mean of already-normalized percentages.

### Resolution

`build_attacker_leaderboard`/`build_defender_leaderboard`/`build_thinking_comparison_data` (`tournament_view_models.py`) now aggregate rates as ratios of summed counts. Latency and guesses-to-solve are reconstructed as weighted means using each contributing matchup's own count (`rounds_completed`/`rounds_solved`) as the weight -- an exact reconstruction of the pooled mean, documented in the module docstring alongside why medians are *not* recombined the same way (a "median of medians" isn't a valid reconstruction without the raw per-round data).

### Validation performed

`tests/test_tournament_view_models.py::test_attacker_leaderboard_is_weighted_not_unweighted_mean`
(the 100-round-vs-2-round fixture, asserting the weighted result differs from the unweighted mean),
`::test_defender_leaderboard_is_weighted_and_has_cost_column`,
`::test_leaderboard_latency_is_weighted_mean_reconstruction`,
`::test_thinking_comparison_is_weighted_across_matchups`. Ran `pytest`.

---

## BUG-020 — Heatmap combined attacker+defender latency/tokens under an ambiguous label, relying on color alone

**Priority:** P2  
**Status:** Resolved  
**Resolved in:** Tournament UI correctness sprint

### Reproduction

Open the Matchup Heatmap tab and select "Latency ms" or "Tokens" as the metric.

### Impact

`tournament_views.py::render_heatmap`'s "Latency ms" and "Tokens" metrics summed the attacker and defender values with no indication the displayed number was combined, under a generic label that reads as if it were a single role's figure. The heatmap also had no "Cost" metric at all, and conveyed its value only through cell color (`viridis` color scale), with no accessible text alternative, and tooltips omitted comparable/excluded round counts, trial counts, and confidence intervals.

### Expected resolution

Label combined metrics explicitly as combined; add a Cost metric; add a visible value alongside color; extend tooltips with the full context.

### Resolution

`HEATMAP_METRICS` now reads `"Combined attacker+defender latency (ms)"` / `"Combined attacker+defender tokens"` instead of the ambiguous originals, plus a new `"Cost"` option (using the matchup-level `total_estimated_cost`, which is legitimately a whole-matchup figure at that granularity, not mislabeled). `render_heatmap` layers a `mark_text` value label on top of the `mark_rect` color cells so the metric is never conveyed by color alone. Tooltips now include attacker/defender provider, model, thinking level, comparable rounds, excluded rounds, trials, excluded trials, and the confidence interval bounds.

### Validation performed

`tests/test_tournament_view_models.py::test_heatmap_combined_metrics_are_explicitly_labeled`,
`::test_heatmap_data_missing_latency_is_none_not_zero`,
`::test_heatmap_data_tooltip_payload_is_complete`,
`::test_heatmap_data_rejects_unknown_metric`. Ran `pytest`.

---

## BUG-021 — Thinking-level selector exposed all six levels regardless of the selected model's actual capability

**Priority:** P2  
**Status:** Resolved  
**Resolved in:** Tournament UI correctness sprint

### Reproduction

In either the Arena or Tournament role configuration UI, select `openai` / `gpt-4o` (which only accepts `auto`) or `o1-preview` (which only accepts `low`/`medium`/`high`) and inspect the "Thinking level" dropdown.

### Impact

`ui_helpers.py::render_role_config` built the thinking-level selectbox from `[t.value for t in ThinkingLevel]` unconditionally -- all six normalized levels, for every provider/model, ignoring the real per-model capability registry (`ModelCapabilities.accepted_thinking_levels`) that provider adapters already enforce at request time. Users could select and run with a level the provider would reject or silently coerce, discovered only at preflight/execution time rather than at configuration time.

### Expected resolution

Query the existing capability registry (already IMP-023's source of truth for enforcement) before rendering the selector; restrict options to what the selected model actually accepts; never silently downgrade.

### Resolution

Added `get_supported_thinking_levels(provider, model)` (`ui_helpers.py`), which asks the provider adapter's own `get_capabilities()` -- the same source execution itself consults. The thinking-level selectbox is now restricted to exactly what's returned. If a previously valid selection becomes invalid after switching provider/model, it is downgraded with a visible `st.warning` naming both the rejected and the new level, never silently.

### Validation performed

`tests/test_ui_helpers.py::test_get_supported_thinking_levels_narrow_model`,
`::test_get_supported_thinking_levels_auto_only_model`,
`::test_get_supported_thinking_levels_unknown_manual_model_falls_back_to_auto`;
`tests/test_dashboard.py::test_thinking_level_selector_is_capability_aware` (end-to-end AppTest
proving the downgrade-with-warning path). Ran `pytest`.

---

## BUG-022 — mypy exclude regex unanchored, silently hiding real type errors in two files never intended to be excluded

**Priority:** P2  
**Status:** Resolved  
**Resolved in:** Tournament UI correctness sprint

### Reproduction

Run `mypy src/password_arena tests` on `main` before this fix, then re-run with `--verbose` and diff the "Found source" file list against every `.py` file under `src/password_arena/` and `tests/`.

### Impact

`pyproject.toml`'s `[tool.mypy] exclude = ["dashboard\\.py", "tournament_views\\.py"]` used unanchored regexes, which mypy matches with `re.search` (substring match). `"dashboard\.py"` therefore also matched `tournament_dashboard.py` and `tests/test_dashboard.py` -- neither was ever intended to be excluded (only `src/password_arena/dashboard.py` was), but both were silently skipped by strict mypy in every CI run. This masked 5 real strict-mode errors once corrected, including a genuine type mismatch between `_render_results()`'s declared `list` parameter and the `tuple[StoredMatchup, ...]` it was actually called with for loaded tournaments.

### Expected resolution

Anchor the exclude patterns so they only match the exact intended filenames.

### Resolution

Changed to `exclude = ["(^|/)dashboard\\.py$", "(^|/)tournament_views\\.py$"]`, verified against the full file list to exclude exactly those two files and no others. Fixed the 5 real errors this surfaced by moving the `MatchupLike` Protocol (introduced in the earlier view-model extraction) to `models.py` and typing `_render_results`, `_render_filter_bar`, and `reporting.py`'s three `tournament_report_*` functions against `Sequence[MatchupLike]` instead of a bare/mismatched `list`.

### Validation performed

Diffed the full `.py` file list against `mypy --verbose`'s "Found source" list before and after -- confirmed exactly 2 files excluded (down from 4), both intended. Ran `mypy src/password_arena tests` (41 files, clean) and `pytest`.

---

## BUG-023 — Provider preflight network calls fired on every Streamlit rerun, not just explicit checks

**Priority:** P1  
**Status:** Resolved  
**Resolved in:** Tournament UI correctness sprint

### Reproduction

Select a hosted provider (e.g. `openai`) for a role in either the Arena or Tournament tab, then interact with any unrelated widget on the page (a slider, another selectbox).

### Impact

`dashboard.py::render_arena_tab` called `build_arena_engine(config)` (which internally calls `check_availability()` for both roles) unconditionally on every script rerun, and `tournament_dashboard.py::render_tournament_tab` ran an equivalent `check_availability()` loop over every unique role, also unconditionally. Since any widget interaction anywhere on a Streamlit page triggers a full script rerun, every keystroke or slider drag fired provider network calls -- wasteful, and risked hitting rate limits or unexpected spend signals from repeated availability checks.

### Expected resolution

Cache preflight status, invalidate the cache on configuration change, and only perform the actual network check in response to an explicit user action ("Test connections"). Rule-based configurations should remain immediately available with no network check.

### Resolution

Added `preflight.py`: `compute_role_fingerprint()` (pure, no I/O, cheap to call every rerun) plus `check_role_availability()`/`check_roles_availability()` (the actual network-calling checks). `ui_helpers.render_preflight_gate()` wraps these with session-state caching keyed by the fingerprint -- a configuration change invalidates the cache and shows "Configuration changed. Status: Not checked." with a "Test connections" button; the check only runs in response to that click. `Run arena`/`Run Tournament` stay disabled until the cached result for the *current* configuration is all-available. `build_arena_engine()` (which re-verifies availability while constructing the engine) now only runs when "Run arena" is actually clicked.

### Validation performed

`tests/test_preflight.py` (fingerprinting, dedup, error wrapping -- all with fakes, no network calls);
`tests/test_dashboard.py::test_preflight_not_checked_automatically_for_non_rule_based_provider`,
`::test_test_connections_caches_result_until_config_changes`,
`::test_tournament_preflight_gate_disables_run_for_unchecked_hosted_provider` (end-to-end AppTests
using OpenAI's real, network-free `check_availability()` behavior when no API key is set). Ran `pytest`.

---

## BUG-024 — Tournament comparison declared "directly comparable" after checking only 4 scalar fields

**Priority:** P1  
**Status:** Resolved  
**Resolved in:** Tournament UI correctness sprint

### Reproduction

Save two tournaments with identical `rounds_per_match`/`seeds`/`max_guesses`/`generator_version` but different attacker/defender provider, model, or thinking-level configurations, or different budgets. Select both in Tournament History and click "Compare Tournaments".

### Impact

`tournament_dashboard.py::render_tournament_history` only compared `rounds_per_match`, `seeds`, `max_guesses`, and `generator_version`; if those four matched, it printed "Tournaments share identical core parameters and are directly comparable" even when the actual role configurations (provider/model/thinking level) or budgets (tokens/cost/time/retries) differed -- a materially false claim.

### Expected resolution

Compare every field that plausibly affects comparability: generator version/mode, seed set, rounds per match, all budget fields, and every attacker/defender role configuration present in either tournament. Return a structured diff, not a single boolean.

### Resolution

Added `compare_tournament_configs()` (`tournament_comparison.py`), a pure function comparing generator_version, generator_mode, seeds (as a set -- trial order doesn't affect comparability), rounds_per_match, max_guesses, max_tokens, max_api_cost, max_wall_time_s, max_retries, and per-role signatures (provider/model/thinking_level/temperature/max_tokens) for every attacker/defender present in either tournament. Returns a `ConfigComparison` with a full list of named differences, not a bare bool. Wired into the "Compare Tournaments" flow, replacing the old 4-field check. Storage schema-version mismatches are also flagged separately.

Known, documented limitation: prompt version and capability-registry version are *not* compared, because neither is part of `TournamentConfig` nor persisted at the tournament level (only per-matchup `ReplayMetadata` at run time, which `StoredMatchup` did not carry at all until BUG-026 below). See IMP-029.

### Validation performed

`tests/test_tournament_comparison.py` (8 cases: identical configs, seed-order independence, seed-set differences, scalar budget differences, thinking-level differences, provider/model differences, extra-role differences, generator differences);
`tests/test_dashboard.py::test_compare_two_tournaments_renders_without_error` (end-to-end AppTest). Ran `pytest`.

---

## BUG-025 — RoleConfig.thinking_level deserialized as a bare string, not a ThinkingLevel enum, after loading from disk

**Priority:** P1  
**Status:** Resolved  
**Resolved in:** Tournament UI correctness sprint

### Reproduction

Save any tournament or single-arena experiment involving a non-`rule_based` role with a non-default thinking level, then load it back and access `role_config.thinking_level.value` (e.g. via the Tournament leaderboard, heatmap, or the new comparison feature).

### Impact

`ThinkingLevel` is a `StrEnum`; `dataclasses.asdict()` does not convert it, but `json.dumps()` serializes it as a plain string (StrEnum inherits from `str`). Neither `tournament_history.py::_role_config_from_dict` nor `models.py::ExperimentResult.from_dict` re-wrapped the loaded value, so `RoleConfig.thinking_level` on anything loaded from disk was actually a bare `str`, not a `ThinkingLevel` member -- despite the field's declared type. Any code calling `.thinking_level.value` on a loaded config raised `AttributeError: 'str' object has no attribute 'value'`. Discovered while manually exercising the new tournament-comparison feature end to end (BUG-024) against two saved tournaments -- this crashed the entire Tournament tab render for *any* loaded tournament, predating this sprint's changes entirely.

### Expected resolution

Re-wrap `thinking_level` with `ThinkingLevel(...)` in both deserialization paths.

### Resolution

Fixed in both `tournament_history.py::_role_config_from_dict` and `models.py::ExperimentResult.from_dict`.

### Validation performed

`tests/test_tournament_history.py::test_loaded_role_config_thinking_level_is_a_real_enum_not_a_string`;
`tests/test_history.py::test_loaded_experiment_role_config_thinking_level_is_a_real_enum`. Ran `pytest`.

---

## BUG-026 — StoredMatchup silently dropped replay metadata and exclusion records on save

**Priority:** P1  
**Status:** Resolved  
**Resolved in:** Tournament UI correctness sprint

### Reproduction

Save any tournament, then load it back and attempt to download a JSON/Markdown/CSV report for it (or compare it against another saved tournament).

### Impact

`TournamentHistoryManager.save()` never persisted `replay`, `excluded_trial_records`, or `excluded_round_records` -- `StoredMatchup` didn't carry those fields at all. `reporting.py::_matchup_payload` unconditionally accesses `m.replay`/`m.excluded_trial_records`/`m.excluded_round_records`, so generating any report for a loaded tournament raised `AttributeError`. This also violated the documented invariant in `docs/tournament_workflow.md` that exclusion records are "never dropped." Discovered while manually exercising the new tournament-comparison feature end to end (BUG-024) -- predates this sprint's changes entirely.

### Expected resolution

Persist and reconstruct `replay`/`excluded_trial_records`/`excluded_round_records` on `StoredMatchup`, with backward-compatible defaults for tournaments saved before the fix.

### Resolution

Added the three fields to `StoredMatchup` (defaulting to `None`/`()`), persisted them in `save()`, and reconstructed them on load via new `_replay_metadata_from_dict`/`_exclusion_record_from_dict` helpers (which also re-wrap the `ThinkingLevel`/`ExclusionReason` StrEnum fields nested inside them -- see BUG-025). Bumped `TOURNAMENT_SCHEMA_VERSION` to `"2.1"`; tournaments saved under `"2.0"` or earlier load with `None`/`()` defaults for the new fields rather than raising.

### Validation performed

`tests/test_tournament_history.py::test_save_list_load_delete_round_trip` (extended with replay/exclusion-record round-trip assertions),
`::test_load_tolerates_old_format_missing_replay_and_exclusion_records`;
`tests/test_dashboard.py::test_load_saved_tournament_from_history_renders_without_error`,
`::test_compare_two_tournaments_renders_without_error`. Ran `pytest`.

---

## BUG-027 — Comparing two tournaments side by side crashed with a duplicate Streamlit element ID

**Priority:** P2  
**Status:** Resolved  
**Resolved in:** Tournament UI correctness sprint

### Reproduction

Save two tournaments, select both in Tournament History, and click "Compare Tournaments".

### Impact

`tournament_views.py::render_heatmap`'s metric `st.selectbox` had no explicit `key`. Streamlit auto-generates widget IDs from element type, label, and options; rendering two tournaments side by side in the same script run (the comparison view calls `_render_results` twice) produced two heatmap selectboxes with an identical auto-ID, raising `StreamlitDuplicateElementId` and crashing the whole comparison. Discovered while manually exercising BUG-024's comparison feature end to end -- predates this sprint's changes entirely (the side-by-side comparison code path already existed and was simply never exercised by any prior test).

### Expected resolution

Give the metric selectbox an explicit, per-tournament-unique key.

### Resolution

`render_heatmap()` now takes a required `key_prefix` parameter, keyed by the calling `tournament_id`, and passes `key=f"{key_prefix}_heatmap_metric"` to the selectbox.

### Validation performed

`tests/test_dashboard.py::test_compare_two_tournaments_renders_without_error`. Ran `pytest`.

---

## BUG-028 — Missing type arguments for generic type `list` in tournament_views.py

**Priority:** P2  
**Status:** Resolved  
**Resolved in:** Benchmark smoke-test sprint

### Reproduction

Run `mypy src/password_arena tests` on `main`.

### Impact

The `list` type hint in several function signatures inside `tournament_views.py` caused five `mypy` strict-mode errors (`Missing type arguments for generic type "list" [type-arg]`). This caused the pre-flight test suite checks to fail, blocking benchmarking workflows which strictly require tests to pass before proceeding.

### Expected resolution

Use `Sequence[MatchupLike]` instead of `list` to satisfy both the type constraints expected by `build_overview` and mypy's generic type requirements.

### Resolution

Changed `results: list` to `results: Sequence[MatchupLike]` in the signatures of `render_overview`, `render_leaderboards`, `render_heatmap`, `render_efficiency`, and `render_thinking_comparison` within `tournament_views.py`. Added corresponding imports.

### Validation performed

Ran `mypy src/password_arena tests`. It passed with "Success: no issues found in 45 source files".

---

## BUG-029 — test_information_policies.py has mypy strict-mode errors

**Priority:** P2  
**Status:** Resolved  
**Resolved in:** Benchmark test sprint

### Reproduction

Run `mypy src/password_arena tests` on `main`.

### Impact

The tests in `test_information_policies.py` lacked return type annotations (`-> None`) and didn't check for `PreflightFailure` when instantiating `ArenaEngine`. This caused 31 `mypy` strict-mode errors. Since GitHub Actions runs `mypy src/password_arena tests`, this caused the CI pipeline to fail, blocking merges.

### Expected resolution

Add `-> None` return type annotations to all test functions. Add `assert not isinstance(engine, tuple)` after `build_arena_engine()` calls to narrow the type and appease mypy.

### Resolution

Added `-> None` to all test functions in `tests/test_information_policies.py` and inserted type-narrowing assertions.

### Validation performed

Ran `mypy src/password_arena tests`. It passed with "Success: no issues found in 50 source files". CI pipeline is green.
