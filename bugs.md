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
**Status:** Open

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

### Status note

Discovered during validation of this sprint's tournament-statistics work. Left
**unfixed and out of scope**: this is an Arena-tab control-flow/UX defect, not a
tournament statistics, comparability, or persistence defect, and fixing it means
changing `render_arena_tab()`'s early-return structure -- exactly the kind of
dashboard/UI change this sprint's brief said to defer. Tracked here so it is not
lost; recommended as the first item for the next UI-focused sprint.
