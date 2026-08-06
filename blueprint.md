# Password Arena Blueprint

**Status:** Active MVP blueprint  
**Current release:** 0.1.0  
**Primary goal:** Build a safe, measurable adversarial-learning arena where a defender improves synthetic password construction and an attacker improves bounded guessing strategy selection.

## 1. Product thesis

Password Arena is not a real credential-cracking utility. It is an educational simulation for studying how two constrained agents adapt when they receive structured feedback from repeated synthetic experiments.

The project should answer four questions:

1. Which predictable password structures are discovered by each attack strategy?
2. How does a defender progress from human patterns toward password-manager-style randomness?
3. How efficiently does an attacker allocate a fixed guess, time, token, or cost budget?
4. Can every decision and adaptation be explained from recorded events without exposing private chain-of-thought?

## 2. Safety contract

These constraints are architectural requirements, not optional documentation:

- Only synthetic passwords generated inside the arena may be tested.
- The application must not accept credential files, browser exports, breach dumps, or real user passwords.
- Attackers operate only against in-memory equality checks.
- No login endpoints, identity providers, websites, sockets, browser automation, or authentication APIs may be attack targets.
- Every attack has a hard, validated resource budget.
- Passwords and successful candidates are redacted by default.
- Provider-backed agents must not receive network, shell, authentication, or credential-store tools.
- Reports must describe recorded actions and outputs, not request hidden model reasoning.

Any change that weakens these constraints requires a security review and an explicit update to `SECURITY.md`.

## 3. Intended users

### Builder

A developer experimenting with agent orchestration, evaluation, observability, and AI-assisted security education.

### Learner

A student exploring why human-generated patterns differ from cryptographically secure randomness.

### Evaluator

A researcher or hiring manager reviewing reproducible experiments, metrics, architecture, and engineering decisions.

## 4. Core arena model

```text
Experiment configuration
        |
        v
+------------------+       synthetic password       +------------------+
| Defender policy  | ------------------------------> | Attacker policy  |
+------------------+                                 +------------------+
        |                                                     |
        | strategy + metadata                                 | guesses + plan
        v                                                     v
+--------------------------------------------------------------------------+
| Evaluator: strength heuristics, bounded outcome, runtime, cost, accuracy |
+--------------------------------------------------------------------------+
        |
        v
+------------------+       +------------------+       +------------------+
| Defender update  |       | Attacker update  |       | Arena journal    |
+------------------+       +------------------+       +------------------+
        |
        +-------------------------- next round ---------------------------->
```

The defender and attacker communicate only through the arena engine. Neither role directly controls the other role, the evaluator, storage, or external systems.

## 5. Current components

| Component | Responsibility | Current implementation |
|---|---|---|
| `ArenaEngine` | Coordinates rounds and state updates | Deterministic orchestration with one intentional CSPRNG exception |
| `AdaptiveDefender` | Selects password family and records breached families | Rule-based progression from words to secure random strings |
| `AdaptiveAttacker` | Ranks strategies and allocates bounded guesses | Weighted rule-based policy with synthetic token memory |
| Strength evaluator | Produces comparative structural metrics | Heuristic entropy and pattern penalties |
| Reporter | Produces factual two-sided documentation | Structured Markdown and JSON exports |
| CLI | Runs repeatable local experiments | `password-arena` command |
| Dashboard | Configures and visualizes experiments | Streamlit application |

## 6. Domain objects

The stable domain boundary should remain serializable and provider-neutral:

- `ArenaConfig`: experiment controls and resource limits.
- `StrategyBudget`: planned guess allocation for one strategy.
- `AttackResult`: observed attack outcome and execution metrics.
- `StrengthReport`: comparative password measurements.
- `AgentReport`: decision, actions, observation, and state update.
- `RoundResult`: complete auditable record for one round.
- `ExperimentResult`: configuration, summary, and ordered rounds.

Future schema changes should include a schema version and migration plan before persistent storage is introduced.

## 7. Learning modes

Password Arena must label learning accurately.

### Mode A — Rule-based adaptation

The current baseline changes strategy scores and remembers synthetic structures. No model weights are trained.

### Mode B — Contextual agent adaptation

Provider-backed agents receive approved summaries of prior rounds and return schema-validated decisions. This is contextual adaptation, not training.

### Mode C — Persistent policy learning

A local policy or model updates parameters from reward signals. Training and evaluation data must be separated, checkpoints versioned, and regressions measured.

The UI and reports must always identify the active mode.

## 8. Metrics

### Required per round

- Difficulty and password family
- Password length and redacted display
- Estimated entropy and structural findings
- Strategy order and exact budget allocation
- Strategies attempted
- Solved or resisted result
- Guesses consumed
- Runtime
- Defender and attacker state updates

### Required per experiment

- Solve rate
- Total guesses and runtime
- Success by password family
- Success and efficiency by attack strategy
- Strength progression
- Configuration, seed, application version, and schema version

### Provider-backed additions

- Input and output tokens
- Provider latency
- Estimated API cost
- Parse or validation failures
- Retry count
- Model, provider, endpoint, and capability identifiers
- Requested and effective thinking level
- Availability, quota, retry-after, and fallback events

## 9. Multi-model provider design

The attacker, defender, and evaluator must be independently configurable. A user may run the same model on all three roles or compare different cloud and local models in one experiment.

### Role configuration

Each role configuration includes:

- provider: `rule_based`, `openai`, `anthropic`, `gemini`, `ollama`, or another registered backend;
- model identifier;
- normalized thinking level: `auto`, `minimal`, `low`, `medium`, `high`, or `maximum`;
- temperature or equivalent sampling controls when supported;
- token, latency, retry, and cost limits;
- optional local endpoint for OpenAI-compatible or Ollama servers.

The provider adapter translates normalized settings into the selected model's supported controls. Unsupported settings must be rejected or visibly downgraded before a round starts. The requested and effective values must both be recorded.

### Capability discovery

The dashboard should show only valid combinations. Each adapter reports capabilities such as:

- available model IDs;
- thinking support and accepted levels;
- structured-output support;
- context and output limits;
- token accounting availability;
- cost metadata availability;
- local installation or server status.

Capability data may be discovered from a provider, loaded from a versioned registry, or both. Stale or unknown capability data must be labeled rather than guessed.

### Availability states

All provider errors are normalized into one of these states:

- `available`;
- `rate_limited`;
- `quota_exhausted`;
- `authentication_failed`;
- `model_unavailable`;
- `unsupported_configuration`;
- `provider_unavailable`;
- `local_server_offline`;
- `local_model_not_installed`;
- `unknown_error`.

A provider response may include whether the condition is retryable and a retry-after value. The UI must say which role and model are unavailable and whether the current round was paused, skipped, or ended.

### No silent substitution

A model failure must never silently switch a role to another model because that invalidates model-to-model comparisons. The default behavior is to pause the round, preserve state, and ask the user to retry, select a replacement, or end the experiment.

Optional fallback chains may be configured explicitly. Any fallback round must record the originally requested model, the effective model, the reason for substitution, and an `is_comparable=false` flag unless the user intentionally defined the fallback as part of the benchmark.

### Session-limit wording

The arena reports only conditions observable through the configured API or local runtime. It must distinguish API rate limits, quota exhaustion, missing credits, authentication failures, and local availability. It must not claim to know the status of an unrelated consumer chat subscription or web-session allowance unless an official provider interface exposes that status.

### Execution boundary

Models choose or explain strategies through schema-validated messages. Deterministic arena code remains responsible for generating synthetic passwords, executing bounded guesses, enforcing budgets, redacting secrets, and recording events. Provider-generated prose is never the source of truth for what occurred.

## 10. Reporting requirements

Every round must expose three factual views:

- **Defender:** selected family, actions, observed outcome, and state update.
- **Attacker:** selected plan, budget allocation, attempts, outcome, and state update.
- **Evaluator:** measured result, limitations, and scoped security lesson.

Reports must be derived from structured runtime events. Free-form model prose may summarize those events, but it may not replace them as the source of truth.

## 11. Delivery phases

### Phase 0 — Baseline MVP

- Safe synthetic generator
- Bounded attacker strategies
- Stateful adaptation
- CLI and dashboard
- JSON and Markdown reports
- Tests, type checks, linting, Docker, and CI

### Phase 1 — Experiment platform

- Versioned experiment IDs
- Persistent run history
- Replay and comparison
- Separate metric charts
- Configuration profiles
- CSV and HTML exports

### Phase 2 — Multi-model provider arena

- Provider-neutral `AgentBackend`
- Independent attacker, defender, and evaluator model selection
- OpenAI, Anthropic, Gemini, Ollama, and OpenAI-compatible local adapters
- Capability-aware normalized thinking levels
- Structured output validation
- Token, latency, retry, availability, and cost metrics
- Explicit pause/resume and opt-in fallback behavior
- Offline mock provider for tests

### Phase 3 — Stronger evaluation

- Plugin-based attack strategies
- Markov and probabilistic context-free grammar baselines
- Held-out synthetic pattern generators
- Repeated seeded runs and confidence intervals
- Strategy ablations and benchmark suites

### Phase 4 — Genuine learning

- Trainable strategy-selection policy
- Reward definition and safety limits
- Checkpointing and evaluation splits
- Baseline comparisons and regression gates

## 12. Non-goals

- Recovering real passwords
- Testing accounts or authentication systems
- Estimating exact real-world crack time
- Replacing password managers or established password-strength libraries
- Claiming model training when only prompts or memory changed
- Maximizing raw guesses at the expense of interpretability

## 13. Definition of done

A feature is complete only when:

1. Safety boundaries remain intact.
2. Behavior is represented in the domain model.
3. Tests cover success, failure, and boundary conditions.
4. `ruff check .`, `mypy src/password_arena`, and `pytest` pass.
5. User-facing behavior is documented.
6. The corresponding entry in `improvements.md` or `bugs.md` is updated.
7. Reports remain redacted by default and auditable from structured events.

## 14. Backlog governance

- Product and engineering work lives in `improvements.md`.
- Confirmed defects live in `bugs.md`.
- Each item has an ID, priority, status, rationale, and acceptance criteria.
- Coding agents must follow `AGENTS.md` and update the item they worked on.
- Completed items remain in the file as project history rather than being deleted.
