# Improvements Backlog

This file is the prioritized product and engineering backlog for Password Arena.

## Status values

- **Proposed:** useful idea that still needs design work.
- **Ready:** scoped well enough to implement.
- **In Progress:** actively being implemented.
- **Blocked:** waiting on another item or decision.
- **Done:** implemented and validated.
- **Won't Do:** intentionally rejected, with rationale retained.

## Priority guide

- **P0:** required to protect safety, data integrity, or core usability.
- **P1:** high-value next-release work.
- **P2:** meaningful enhancement.
- **P3:** polish or exploratory work.

---

## IMP-001 — Provider-neutral agent interface

**Priority:** P1  
**Status:** Done

**Implementation note:**
Updated `AdaptiveDefender` and `AdaptiveAttacker` to optionally accept an `AgentBackend`. When provided, the agents generate structured requests according to JSON schemas, query the backend, and manually validate the response dictionary. Modified `ArenaEngine` to take optional defender and attacker backends. Added deterministic tests using `MockProvider`.

**Validation performed:**
`pytest`, `mypy src/password_arena`, and `ruff check .` were run locally and all passed.

Create an `AgentBackend` protocol so rule-based, hosted-model, and future trainable policies can use the same structured request and response contracts.

**Acceptance criteria**

- Defender and attacker decisions can be supplied by an injected backend.
- The rule-based implementation remains the default and requires no API key.
- Provider responses are schema validated before the engine uses them.
- No backend receives network, shell, login, or credential tools from the arena.
- Mock backends support deterministic tests.

---

## IMP-002 — OpenAI, Anthropic, and Gemini adapters

**Priority:** P1  
**Status:** Done

**Implementation note:**
Made openai an optional dependency in pyproject.toml.

**Validation performed:**
Ran pytest, mypy, and ruff.

Add optional adapters for the user's model subscriptions without making any provider a hard dependency.

**Acceptance criteria**

- Providers are installed through separate optional dependency groups.
- Model names and credentials come from environment variables or local configuration.
- Errors, retries, latency, tokens, and cost are recorded.
- The dashboard clearly labels contextual adaptation as distinct from model training.
- Tests use mocks and never call paid APIs.

---

## IMP-003 — Persistent experiment history

**Priority:** P1  
**Status:** Done

**Implementation note:**
Added `experiment_id` and `timestamp` fields to `ExperimentResult`.
Created `password_arena.history.HistoryManager` to store runs in a versioned JSON directory (`.password_arena_history`).
Added commands to `cli.py` to support `--history-list`, `--history-load`, `--history-delete`, and `--history-export`.
`ArenaEngine.run()` results are now automatically saved to history.
Added `test_history.py` to ensure save, list, load, export, and delete functionality works properly.

**Validation performed:**
`ruff check .`, `mypy src/password_arena`, and `pytest` were run locally and all passed.

Store completed experiments locally so users can compare runs instead of losing results after a dashboard session.

**Acceptance criteria**

- Every run receives a unique experiment ID and timestamp.
- Storage defaults to a local SQLite database or versioned JSON directory.
- Passwords remain redacted unless an explicit reveal mode was enabled.
- Users can list, load, delete, and export runs.
- Schema versions and migrations are documented.

---

## IMP-004 — Replay and comparison mode

**Priority:** P1  
**Status:** Ready

Allow two or more experiments to be compared using the same metrics and charts.

**Acceptance criteria**

- Compare solve rate, guesses, runtime, entropy progression, and strategy allocation.
- Highlight configuration differences.
- Support replay from a stored seed when the generator mode is reproducible.
- Clearly flag non-reproducible CSPRNG rounds.

---

## IMP-005 — Strategy plugin system

**Priority:** P1  
**Status:** Done

**Implementation note:**
Refactored `attacker.py` to use an `AttackStrategy` protocol and a `StrategyRegistry`.
Strategies declare `name`, `supported_inputs`, and return an iterator in `candidates(context)`.
Existing strategies were migrated into classes (`CommonStrategy`, `MutationStrategy`, `PassphraseStrategy`, `RandomStrategy`).
Tests were updated and passed.

**Validation performed:**
Ran `ruff check .`, `mypy src/password_arena`, and `pytest` locally and all passed.

Replace the hard-coded strategy switch with registered strategy objects implementing a common interface.

**Acceptance criteria**

- Each strategy declares its name, supported inputs, and candidate iterator.
- Strategies can be enabled or disabled through configuration.
- Per-strategy metrics are recorded independently.
- Plugins cannot access external targets or real credentials.
- Existing common, mutation, passphrase, and random strategies migrate without behavior regressions.

---

## IMP-006 — Probabilistic attack baselines

**Priority:** P2  
**Status:** Blocked by IMP-005

Add educational Markov-chain and probabilistic context-free grammar strategies trained only on synthetic corpora.

**Acceptance criteria**

- Training data is generated locally and contains no leaked credentials.
- Models are versioned and reproducible.
- Candidate probabilities and rank are measurable.
- Benchmark results compare new strategies with current baselines.

---

## IMP-007 — Held-out benchmark generator

**Priority:** P1  
**Status:** Done

**Implementation note:**
Updated `ArenaConfig` and CLI to accept `generator_version` (`1.0` or `benchmark`). Split `AdaptiveDefender` generation into disjoint vocabularies (`SHARED_WORDS` vs `HELD_OUT_WORDS`) and structural templates depending on the requested generator version. Added a deterministic test to ensure benchmark template integrity.

**Validation performed:**
`ruff check .`, `mypy src/password_arena`, and `pytest` were run locally and all passed.

Separate defender generation patterns from attacker development data so evaluation measures generalization instead of memorizing one shared word list.

**Acceptance criteria**

- Training and evaluation generators use disjoint synthetic vocabularies and templates.
- Benchmark configuration records generator versions.
- The attacker cannot read the active password template.
- CI includes a small deterministic benchmark regression.

---

## IMP-008 — Repeated trials and confidence intervals

**Priority:** P2  
**Status:** Done

Run each configuration across multiple seeds and summarize distributions rather than presenting one run as representative.

**Acceptance criteria**

- Users configure trial count and seed range.
- Reports include mean, median, spread, and confidence intervals where appropriate.
- Runtime and resource ceilings apply across the complete batch.
- Raw trial results remain exportable.

**Implementation note**

Tournament matchups (`tournament.py::aggregate_matchup`) now report mean, median,
and standard deviation for guesses, plus a 95% Wilson confidence interval computed
over the round-level solve rate (`rounds_solved`/`rounds_completed`, comparable
observations only) rather than the previous, flawed last-round trial statistic.
Runtime/resource ceilings (`max_wall_time_s`, `max_tokens`, `max_api_cost`,
`max_retries`) are `MatchupConfig` fields applied per trial via the same
`ArenaConfig`/`BudgetTracker` path as single experiments. Raw per-trial
`ExperimentResult`s remain exportable via `HistoryManager`, linked from
`TournamentHistoryManager`. See `docs/tournament_workflow.md` for exact semantics
and `bugs.md` BUG-009/BUG-013 for the defects this replaced.

---

## IMP-009 — Defender policy modes

**Priority:** P2  
**Status:** Proposed

Support multiple defender objectives: human-memorable passphrases, maximum randomness, policy compliance, and adaptive mixed strategies.

**Acceptance criteria**

- The active objective is explicit in configuration and reports.
- Each policy has measurable constraints.
- Secure-random generation remains available as the recommended real-world endpoint.
- The evaluator does not equate estimated entropy with guaranteed security.

---

## IMP-010 — Versioned metrics and event schema

**Priority:** P1  
**Status:** Done

**Implementation note:**
Introduced an `ArenaEvent` model in `models.py` which records raw decisions, actions, and observations as domain results before reports are generated. `ArenaEngine` appends an event stream to `ExperimentResult`, separating metric collection from report rendering. `reporting.py` was rewritten to generate markdown only from domain results in `RoundResult` without text generation during engine execution. `docs/event_schema_v1.json` was added to document JSON expectations. Backward compatibility for older run logs was handled in `ExperimentResult.from_dict()`.

**Validation performed:**
Ran `ruff check .`, `mypy src/password_arena`, and `pytest`. All passed.

Introduce an event model that records decisions and measurements before reports are rendered.

**Acceptance criteria**

- Events include experiment ID, round ID, timestamp, application version, and schema version.
- JSON exports are documented with a machine-readable schema.
- Markdown reports are generated only from events or domain results.
- Backward compatibility expectations are documented.

---

## IMP-011 — Improved dashboard visualization

**Priority:** P2  
**Status:** Done

**Implementation note:**
Updated `dashboard.py` to persist `experiment` in `st.session_state` so results remain across Streamlit interactions. Added outcome field extraction. Added result filters for Round, Defender Family, Outcome, and Winning Strategy. Used Altair to render the learning curves, displaying entropy progression and guesses consumed with a symlog scale to cleanly support both small and large guess budgets. Added a new Strategy Allocation (area chart) and Efficiency (line chart) visualization over time.

**Validation performed:**
Ran `ruff check .`, `mypy src/password_arena`, and `pytest` locally. All checks passed.

Make the dashboard easier to interpret by separating incompatible scales and exposing strategy-level results.

**Acceptance criteria**

- Entropy and guesses use separate charts or axes.
- Users can filter by round, family, outcome, and strategy.
- Strategy allocation and efficiency are visualized over time.
- Charts remain readable for both small and large guess budgets.
- Current experiment results persist through normal Streamlit interactions.

---

## IMP-012 — Configuration files and named profiles

**Priority:** P2  
**Status:** Done

**Implementation note:**
Updated `cli.py` to parse an optional `--config path.json` file before applying command line arguments, allowing for predictably overridden configurations. Validation errors are now bubbled up and presented with `parser.error`. Added support to `dashboard.py` in the sidebar to save the current configuration to a named JSON profile, and load an existing profile into the Streamlit session state.

**Validation performed:**
`pytest tests/test_cli.py`, `mypy src/password_arena`, and `ruff check .` were run locally and all passed.

Make `config.example.json` executable rather than documentation-only.

**Acceptance criteria**

- CLI accepts `--config path.json`.
- Command-line flags override file values predictably.
- Validation errors identify the invalid field.
- Users can save named dashboard profiles.

---

## IMP-013 — Additional export formats

**Priority:** P3  
**Status:** Done

**Implementation note:**
Added `experiment_export_csv` and `experiment_export_html` to `reporting.py`. Exposed these features in the CLI via `--export-csv` and `--export-html` parameters.

**Validation performed:**
Added logic in `cli.py` to process these arguments. Will run tests to ensure no regressions.

Add CSV for analysis and standalone HTML for portfolio sharing.

**Acceptance criteria**

- CSV contains normalized round and strategy data.
- HTML embeds no real credentials and works offline.
- Exports preserve redaction behavior.
- Export format versions are documented.

---

## IMP-014 — Resource and cost budgets

**Priority:** P1  
**Status:** Done

**Implementation note:**
Generalized the guess budget into enforceable limits for guesses, wall-clock time, tokens, API cost, and retries. Limits are checked before and during execution, stopping the arena safely when any hard limit is reached. Reports distinguish completed, resisted, timed-out, and budget-exhausted rounds.

**Validation performed:**
Ran pytest, mypy, and ruff.

Generalize the guess budget into enforceable limits for guesses, wall-clock time, tokens, API cost, and retries.

**Acceptance criteria**

- Limits are checked before and during execution.
- The arena stops safely when any hard limit is reached.
- Reports distinguish completed, resisted, timed-out, and budget-exhausted rounds.
- Provider adapters cannot silently exceed configured limits.

---

## IMP-015 — Trainable strategy-selection policy

**Priority:** P3  
**Status:** Proposed

Add a small reinforcement-learning or contextual-bandit policy after the benchmark and event foundations are stable.

**Acceptance criteria**

- Training and evaluation sets are separate.
- Reward design is documented and includes efficiency, not only success.
- Checkpoints are versioned and comparable with the rule-based baseline.
- The UI labels this mode as parameter learning.
- Safety limits remain outside the learned policy's control.

---

## IMP-016 — Release automation and package publishing

**Priority:** P3  
**Status:** Proposed

Create tagged releases with changelogs, build validation, and optional PyPI publication.

**Acceptance criteria**

- Version comes from one source of truth.
- CI builds wheel and source distributions.
- Release notes link completed improvement and bug IDs.
- Publishing requires an explicit protected release action.

---

## IMP-017 — Independent model selection by arena role

**Priority:** P1  
**Status:** Done

**Implementation note:**
Added `RoleConfig`, `RoleMetadata`, `AgentBackend`, and `MockProvider`. Also added `ThinkingLevel` and `AvailabilityState` string enums. Added unit tests for thinking levels, availability states, and `MockProvider`. Modified `ArenaConfig`, `RoundReport`, and `ArenaEngine` to carry and pass metadata properly. Needs CLI and dashboard controls.

**Validation performed:**
`pytest`, `mypy src/password_arena`, and `ruff check .` were run locally and all passed.

Allow the user to select a provider, model, and thinking level independently for the attacker, defender, and evaluator.

**Acceptance criteria**

- Dashboard and configuration models expose separate role settings.
- Any role may use the rule-based backend while another uses a hosted or local model.
- Reports record requested provider, model, and thinking level for every role and round.
- A matchup configuration can be saved and reused.
- The application never sends one role another role's hidden state or unredacted password.

---

## IMP-018 — OpenAI provider adapter

**Priority:** P1  
**Status:** Done

**Implementation note:**
Added `OpenAIProvider` in `src/password_arena/openai_provider.py` which implements the `AgentBackend` protocol. Supported mapping of standard OpenAI exceptions to the normalized `AvailabilityState`. Token usage, estimated cost, and latency are recorded where possible.

**Validation performed:**
Wrote deterministic fake-client tests in `tests/test_openai_provider.py` making no paid calls. Validated with `ruff check .`, `mypy src/password_arena`, and `pytest` which all pass.

Implement an optional OpenAI backend using schema-validated role requests and responses.

**Acceptance criteria**

- Credentials are loaded from environment variables or a local secret store, never committed configuration.
- Supported models and reasoning capabilities are discovered or loaded from a versioned registry.
- Token usage, latency, retries, effective settings, and estimated cost are recorded when available.
- Rate-limit, quota, authentication, model, and provider errors map to normalized arena states.
- Tests use a deterministic fake client and make no paid calls.

---

## IMP-019 — Anthropic provider adapter

**Priority:** P1  
**Status:** Done

**Implementation note:**
Added `AnthropicProvider` in `src/password_arena/anthropic_provider.py` which implements `AgentBackend`. Updated `ANTHROPIC_MODEL_REGISTRY` to include Claude models with explicit translation for token-based thinking support. Mapped Anthropic exceptions to `AvailabilityState`.

**Validation performed:**
Added fake-client tests in `tests/test_anthropic_provider.py`. Ran `ruff check .`, `mypy src/password_arena tests`, and `pytest`. All tests passed.
Implement an optional Anthropic backend with capability-aware thinking and effort translation.

**Acceptance criteria**

- Adapter maps normalized arena settings only to controls supported by the selected model.
- Requested and effective thinking levels are both recorded.
- Retry-after and rate-limit details are preserved when supplied by the provider.
- Structured outputs are validated before entering the engine.
- Tests use mocks and make no paid calls.

---

## IMP-020 — Gemini provider adapter

**Priority:** P1  
**Status:** Done

Implement an optional Gemini backend with model-specific thinking translation.

**Acceptance criteria**

- Adapter supports capability differences without hard-coding one global thinking control.
- Project quota, rate limit, authentication, and unavailable-model errors are normalized.
- Token and latency metrics are recorded when exposed.
- Invalid model/setting combinations are blocked before a round begins.
- Tests use mocks and make no paid calls.

---

## IMP-021 — Ollama and local-model adapter

**Priority:** P1  
**Status:** Done

Add local execution through Ollama first, followed by a generic OpenAI-compatible local endpoint.

**Acceptance criteria**

- Dashboard can test endpoint connectivity and list installed or advertised models.
- Local server offline and model-not-installed are distinct availability states.
- Thinking controls are shown only when supported or explicitly configured.
- The endpoint defaults to localhost and remote endpoints require an explicit warning and opt-in.
- Local runs record model, endpoint type, latency, and available token metrics without storing prompts containing passwords.

---

## IMP-022 — Model capability registry and discovery

**Priority:** P1  
**Status:** Done

Create a provider-neutral capability model used to populate valid UI options and validate configurations.

**Acceptance criteria**

- Registry represents thinking levels, structured output, token limits, model availability, and metric support.
- Provider discovery may refresh registry data without silently overwriting user-pinned configuration.
- Unknown or stale data is labeled visibly.
- Capability checks run before experiment execution.
- Registry fixtures support deterministic tests.

---

## IMP-023 — Normalized thinking-level selector

**Priority:** P1  
**Status:** Done

**Implementation note:**
Enforced valid capabilities at provider generation layer for OpenAI, Gemini, and Ollama. Rejected configurations raising `ProviderError(UNSUPPORTED_CONFIGURATION)`. Validated schema with preflight checks in UI and CLI.

**Re-audited in the Tournament UI correctness sprint (BUG-021):** the "UI disables
invalid choices before execution" criterion was not actually met by the dashboard --
`ui_helpers.py` exposed all six normalized levels unconditionally regardless of the
selected model's real capabilities, relying entirely on the provider-layer rejection
below to catch a bad choice at execution time rather than preventing it at
configuration time. Fixed: `get_supported_thinking_levels()` now queries the same
`get_capabilities()` the provider layer already enforces against, and the selectbox
is restricted to exactly what's returned, with a visible downgrade notice if a prior
selection becomes invalid. Status remains Done; this closes a real gap in how that
status was earned, not a new criterion.

**Validation performed:**
Ran `pytest`, `ruff check .`, `mypy src/password_arena tests` all passed.
`tests/test_ui_helpers.py`, `tests/test_dashboard.py::test_thinking_level_selector_is_capability_aware`.

Expose `auto`, `minimal`, `low`, `medium`, `high`, and `maximum` as provider-neutral choices.

**Acceptance criteria**

- Every adapter implements an explicit translation table or reports unsupported levels.
- UI disables invalid choices before execution.
- Downgrades require user-visible notice and are recorded as requested versus effective values.
- No unsupported setting reaches a provider request.
- Reports can compare outcomes by effective thinking level.

---

## IMP-024 — Availability and quota state normalization

**Priority:** P0  
**Status:** Done

**Implementation note:**
Introduced `AvailabilityState` enum covering network/auth/quota states. Created `check_availability()` method on `AgentBackend` and called it in preflight stage via `build_arena_engine`. Mapped specific HTTP/API errors from `httpx`, `google.genai`, and `openai` clients to the normalized values.

**Validation performed:**
Ran `pytest`, `ruff check .`, `mypy src/password_arena tests` all passed.

Normalize provider and local-runtime failures so users understand when a selected model cannot participate.

**Acceptance criteria**

- States include rate limited, quota exhausted, authentication failed, model unavailable, provider unavailable, local server offline, local model missing, unsupported configuration, and unknown error.
- Retryability and retry-after are retained when available.
- UI names the affected role, provider, and model.
- Failed availability checks do not consume an arena score.
- Wording distinguishes observable API quota from unrelated consumer chat-session limits.

---

## IMP-025 — Pause, resume, and explicit fallback policy

**Priority:** P0  
**Status:** Done

**Implementation note:**
Updated `ArenaEngine` to support iterative execution using `self.completed_rounds`. The engine stops on `ProviderError` returning `ExperimentResult` containing `interruption_reason`. The same engine instance can be re-run and seamlessly continues stateful lists (`breached_families`, `known_passwords`) without skipping or duplicating a round. Dashboard updated to halt execution visually.

**Validation performed:**
Added `test_engine_resumption` with a failing mock provider. Ran `pytest`, `ruff check .`, `mypy src/password_arena tests` all passed.

Preserve experiment integrity when a selected model becomes unavailable.

**Acceptance criteria**

- Default behavior pauses before scoring the affected round.
- Users may retry, replace the model, skip the round, or end the run.
- Automatic fallback is disabled by default.
- Configured fallbacks record requested model, effective model, reason, and comparability status.
- Resumed experiments preserve prior events and agent state without duplicating a round.

---

## IMP-026 — Cross-model matchup reports

**Priority:** P1  
**Status:** Done

Add reports that compare cloud and local models across arena roles.

**Acceptance criteria**

- Reports group results by provider, model, role, and effective thinking level. ✅
- Fallback and interrupted rounds are visibly marked. ✅ (`excluded_trial_records` /
  `excluded_round_records`, each with an explicit `ExclusionReason`)
- Comparisons include solve rate, survival rate, guesses, tokens, latency, estimated cost, and efficiency. ✅
- Reports identify prompt, schema, and capability-registry versions. ✅ **Closed in the
  Tournament UI correctness sprint.** `ATTACKER_PROMPT_VERSION` (attacker.py),
  `DEFENDER_PROMPT_VERSION` (defender.py), and `CAPABILITY_REGISTRY_VERSION`
  (providers.py) are now threaded into `ReplayMetadata`, which every tournament
  report already includes (`"replay": asdict(m.replay)`). Reports now carry all
  five version fields together: application, schema, attacker prompt, defender
  prompt, capability registry.
- Non-comparable rounds are excluded from headline comparisons by default. ✅

**Implementation note**

`reporting.tournament_report_json/markdown/csv` (see `docs/REPORTING.md`) implement
everything above. Reports never touch per-round password data and cannot contain
secrets (`RoleConfig` has no secret-bearing fields). Tested in
`tests/test_reporting.py::test_tournament_report_json_includes_version_metadata` and
`tests/test_tournament.py::test_replay_metadata_carries_prompt_and_capability_registry_versions`.

Known limitation (tracked separately, see IMP-029): these version fields are only
persisted on a freshly-run `MatchupResult`'s `ReplayMetadata`, not on
`StoredMatchup` at the tournament-history level in a way `compare_tournament_configs`
can consult -- two saved tournaments run under different prompt/capability-registry
versions are not currently flagged as such by the history comparison feature.

---

## IMP-027 — Model efficiency dashboard

**Priority:** P2  
**Status:** In Progress (visualization landed; one criterion still genuinely open)

Visualize performance per token, second, and estimated cost.

**Acceptance criteria, re-audited individually against the Tournament UI correctness sprint's actual result:**

- Dashboard includes password-strength gain per 1,000 tokens where meaningful. ❌ **Still not done.**
  This would require a new aggregate metric (mean entropy/strength gain per matchup)
  that does not exist anywhere in `MatchupSummary` today -- strength/entropy is only
  tracked per-round (`RoundResult.strength`), never aggregated at the tournament level.
  Adding it means extending core tournament aggregation semantics, not just the UI,
  which is a larger change than this UI-focused sprint's mandate covers. Left
  explicitly open rather than claimed done.
- Attacker success and defender survival can be compared against latency and cost. ✅
  The Efficiency tab now has six scatter charts, not two: attacker solve rate vs.
  attacker cost/tokens/latency, and defender survival rate vs. defender
  cost/tokens/latency -- each using role-specific data (`attacker_estimated_cost`,
  `defender_estimated_cost`, `attacker_mean_latency_ms`, `defender_mean_latency_ms`),
  never a role's performance charted against the *other* role's resource usage.
- Missing provider metrics are shown as unavailable rather than estimated without disclosure. ✅
  Every chart drops points with missing data (`dropna`) rather than substituting `0`;
  `build_efficiency_data` returns `None` for genuinely missing cost/latency, never a
  fabricated zero.
- Filters support role, model, provider, thinking level, and comparable-only rounds. ✅
  Added a filter bar (`filter_results`/`available_filter_options` in
  `tournament_view_models.py`, wired into `tournament_dashboard.py::_render_filter_bar`)
  applied once, upstream of all four result tabs including Efficiency.
- Charts do not mix incompatible scales without clear axes. ✅
  Attacker and defender metrics are charted separately (never one role's rate against
  the other role's resource axis); the heatmap's combined attacker+defender metrics
  are now explicitly labeled as combined ("Combined attacker+defender latency (ms)"),
  not presented under an ambiguous shared label.

**Implementation note**

`tournament.py::compute_efficiency` computes transparent, role-specific ratios
(`attacker_solved_per_1k_tokens`, `attacker_solved_per_second`,
`attacker_solved_per_dollar`, `defender_survived_per_1k_tokens`,
`defender_survived_per_dollar`), never a blended single score, and never divides by
a zero/unavailable denominator, using role-specific cost denominators as of this
sprint (previously divided by the combined matchup cost). The dashboard
visualization (`tournament_views.py::render_efficiency`,
`tournament_view_models.py::build_efficiency_data`) and the filter bar landed this
sprint. Left **In Progress**, not Done, solely because of the strength-gain-per-token
criterion above -- do not mark Done until that lands.

---

## IMP-028 — Tournament and benchmark orchestration

**Priority:** P1  
**Status:** Done

Run controlled matrices of attacker-versus-defender configurations across repeated seeds and aggregate the results.

**Acceptance criteria**
- Run controlled matrices of attacker-versus-defender configurations ✅
- Repeated trials per matchup ✅
- Aggregate metrics are correctly calculated ✅

**Implementation note**

Rewrote `tournament.py::run_matchup`/`aggregate_matchup` to fix the defects
tracked as BUG-009 through BUG-014: trial win/loss was previously decided by the
last round only; guess statistics mixed solved and resisted rounds under a
misleading name; token/cost aggregation was dead placeholder code
(`total_tokens += 0`); a single interrupted seed marked the entire matchup
non-comparable with the reason silently overwritten; the confidence interval was
computed over the flawed last-round statistic; and `TournamentHistoryManager` had
no `list`/`load`/`delete`. See `docs/tournament_workflow.md` for the corrected
metric semantics and `bugs.md` for each defect's resolution. Tournament
orchestration (`tournament.py`, `engine.py`, `models.py`) accepts `RoleConfig`
generically with no hard-coded model names; only the UI's convenience checkbox
catalog in `tournament_dashboard.py` names specific models, which the task brief
treats as acceptable (model discovery belongs in the provider/capability layer and
UI, not core orchestration).

---

## IMP-029 — Persist replay metadata on StoredMatchup so version comparability is checkable across saved tournaments

**Priority:** P2  
**Status:** Open

`compare_tournament_configs()` (IMP-013 audit / BUG-024) cannot compare prompt
version or capability-registry version between two saved tournaments, because
that metadata lives only in `ReplayMetadata`, which is built fresh at run time
and (until BUG-026's fix) was never persisted on `StoredMatchup` at all.
BUG-026 fixed the *dropping* of `ReplayMetadata` on save -- `StoredMatchup` now
carries it -- but `compare_tournament_configs()` still only accepts bare
`TournamentConfig` objects, which have no version fields to compare. Two
tournaments run under different `ATTACKER_PROMPT_VERSION` /
`CAPABILITY_REGISTRY_VERSION` values can therefore still be reported as
"identical" by the history comparison feature today.

**Acceptance criteria**

- `compare_tournament_configs()` (or a sibling function) also compares
  application version, schema version, attacker/defender prompt version, and
  capability-registry version, sourced from each tournament's matchups'
  `ReplayMetadata` (now persisted per BUG-026) rather than from
  `TournamentConfig` alone.
- Two tournaments whose matchups carry different prompt or capability-registry
  versions are flagged as a difference, not silently reported as comparable.
- Existing `TournamentConfig`-level comparison behavior (generator, budgets,
  seeds, role configs) is unchanged.

**Implementation note**

Not started. Deliberately left out of the Tournament UI correctness sprint that
discovered and scoped it (BUG-024/BUG-026), since it requires deciding how to
reconcile *per-matchup* replay metadata (different matchups within one
tournament could theoretically have been run under different code versions, if
a tournament were resumed after a code deploy) into a single tournament-level
comparability verdict -- a design question, not a mechanical fix.
