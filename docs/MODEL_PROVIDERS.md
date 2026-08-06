# Model Provider Design

This document defines the planned multi-model layer for Password Arena. The current MVP remains rule-based and requires no API key.

## Goals

- Select providers and models independently for attacker, defender, and evaluator roles.
- Compare cloud and local models under the same arena budgets.
- Normalize thinking controls without pretending every provider exposes identical capabilities.
- Make rate limits, quota exhaustion, provider failures, and local-model failures visible.
- Preserve experiment validity by preventing silent model substitution.

## Role configuration

Each role uses a provider-neutral configuration:

```json
{
  "provider": "openai | anthropic | gemini | ollama | openai_compatible | rule_based",
  "model": "provider-specific-model-id",
  "thinking_level": "auto | minimal | low | medium | high | maximum",
  "max_output_tokens": 2048,
  "timeout_seconds": 60,
  "max_retries": 2,
  "max_cost_usd": 0.25
}
```

The JSON above is a design example, not yet accepted by the current CLI.

## Backend contract

A backend should implement operations equivalent to:

```python
class AgentBackend(Protocol):
    def list_models(self) -> list[ModelCapability]: ...
    def check_availability(self, model_id: str) -> AvailabilityResult: ...
    def decide(self, request: AgentRequest) -> AgentDecision: ...
    def normalize_error(self, error: Exception) -> ProviderError: ...
```

The arena engine owns all password generation, guess execution, budget enforcement, redaction, state transitions, and event recording. Backends return schema-validated decisions only.

## Normalized thinking levels

The UI exposes:

- `auto`
- `minimal`
- `low`
- `medium`
- `high`
- `maximum`

Adapters translate these values according to the selected model. A capability registry determines whether a level is supported. The application must record both the requested level and the effective provider setting.

Unsupported combinations are handled before execution:

1. disable the invalid option in the dashboard when capability data is known;
2. reject the configuration with a clear message when no valid mapping exists; or
3. offer a visible downgrade that requires user acceptance and is recorded in the report.

## Availability model

```text
available
rate_limited
quota_exhausted
authentication_failed
model_unavailable
unsupported_configuration
provider_unavailable
local_server_offline
local_model_not_installed
unknown_error
```

An availability result may also include `retryable`, `retry_after_seconds`, provider request ID, and a safe user-facing message.

The arena reports only limits observable through the configured API or local runtime. It should not describe a consumer chat subscription as exhausted unless an official interface explicitly provides that information.

## Interruption behavior

When a selected model is unavailable:

1. stop before scoring the round;
2. record an availability event;
3. preserve experiment and role state;
4. display the affected role, provider, model, and reason;
5. allow retry, model replacement, round skip, or experiment termination.

Fallback is opt-in. A fallback round records:

- requested provider and model;
- effective provider and model;
- fallback reason;
- whether the round is comparable with the original benchmark definition.

## Local models

Ollama is the first planned local backend. A later generic adapter can support OpenAI-compatible local servers.

Local configuration must distinguish:

- server unreachable;
- model not installed or not advertised;
- unsupported thinking mode;
- generation timeout;
- malformed structured output.

Local endpoints default to loopback addresses. Remote endpoints require explicit configuration and should display a warning because prompts and experiment data may leave the machine.

## Metrics

Every provider-backed round should record, when available:

- provider, model, role, endpoint type;
- requested and effective thinking level;
- input, cached, reasoning, and output tokens;
- latency and retries;
- estimated cost and pricing-version metadata;
- availability events;
- parse and schema-validation failures;
- prompt and schema versions.

Provider metrics that are not exposed must remain `null` or unavailable. They should not be silently invented.

## Security rules

- API keys are read from environment variables or an OS/local secret store.
- Keys are never written to reports, logs, exports, prompts, or repository files.
- Models receive synthetic experiment context only.
- Models do not receive shell, browser, credential-store, authentication, or arbitrary network tools.
- Passwords stay redacted from model-facing summaries unless a narrowly scoped role operation requires the current synthetic value and the provider-risk setting explicitly allows it.
- The evaluator summarizes recorded events; it does not request private chain-of-thought.

## Implementation order

1. `IMP-001` provider-neutral interface and mock backend.
2. `IMP-022` capability registry.
3. `IMP-023` normalized thinking selector.
4. `IMP-024` availability normalization.
5. `IMP-025` pause/resume and fallback integrity.
6. Hosted and local adapters (`IMP-018` through `IMP-021`).
7. Role selection, matchup reports, and efficiency dashboard.
