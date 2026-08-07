import datetime
import enum
import json
import math
from dataclasses import dataclass, field
from typing import Any, Protocol


class ThinkingLevel(enum.StrEnum):
    AUTO = "auto"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAXIMUM = "maximum"


class AvailabilityState(enum.StrEnum):
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXHAUSTED = "quota_exhausted"
    AUTHENTICATION_FAILED = "authentication_failed"
    MODEL_UNAVAILABLE = "model_unavailable"
    UNSUPPORTED_CONFIGURATION = "unsupported_configuration"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    LOCAL_SERVER_OFFLINE = "local_server_offline"
    LOCAL_MODEL_NOT_INSTALLED = "local_model_not_installed"
    TIMEOUT = "timeout"
    INVALID_RESPONSE = "invalid_response"
    UNKNOWN_ERROR = "unknown_error"


@dataclass(frozen=True, slots=True)
class AvailabilityResult:
    state: AvailabilityState
    message: str
    retryable: bool = False
    retry_after_seconds: int | None = None
    checked_at: datetime.datetime | None = None


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    model_id: str
    thinking_supported: bool
    accepted_thinking_levels: tuple[ThinkingLevel, ...]
    structured_output_supported: bool
    context_limit: int
    output_limit: int
    token_accounting: bool
    cost_metadata: bool
    local_execution: bool


@dataclass(frozen=True, slots=True)
class UsageMetrics:
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int | None = None
    latency_ms: float = 0.0
    estimated_cost: float = 0.0
    retries: int = 0
    requested_thinking_level: ThinkingLevel = ThinkingLevel.AUTO
    effective_thinking_level: ThinkingLevel = ThinkingLevel.AUTO
    request_id: str | None = None
    structured_validation_success: bool = True
    fallback_used: bool = False


class ProviderError(Exception):
    def __init__(
        self,
        state: AvailabilityState,
        message: str,
        retryable: bool = False,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.state = state
        self.retryable = retryable
        self.retry_after = retry_after


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    prompt: str
    system_prompt: str | None = None
    structured_schema: dict[str, Any] | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    thinking_level: ThinkingLevel = ThinkingLevel.AUTO


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    content: str
    provider_name: str
    model_id: str
    parsed_structured_data: dict[str, Any] | None = None
    metrics: UsageMetrics = field(default_factory=UsageMetrics)


class AgentBackend(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def model_id(self) -> str: ...

    def get_capabilities(self) -> ModelCapabilities: ...

    def check_availability(self) -> AvailabilityResult: ...

    def generate(self, request: ProviderRequest) -> ProviderResponse: ...


def parse_and_validate_json(
    content: str, schema: dict[str, Any] | None
) -> tuple[dict[str, Any] | None, bool, str | None]:
    if not schema:
        return None, True, None

    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return None, False, f"Malformed JSON: {e}"

    if not isinstance(data, dict):
        return None, False, "JSON root must be an object"

    required = schema.get("required", [])
    for key in required:
        if key not in data:
            return None, False, f"Missing required key: {key}"

    properties = schema.get("properties", {})
    for key, value in data.items():
        if key in properties:
            expected_type = properties[key].get("type")
            if expected_type == "string" and not isinstance(value, str):
                return None, False, f"Key {key} must be a string"
            elif expected_type == "number":
                if type(value) is bool or not isinstance(value, (int, float)):
                    return None, False, f"Key {key} must be a number"
            elif expected_type == "object" and not isinstance(value, dict):
                return None, False, f"Key {key} must be an object"

    if "weights" in data and isinstance(data["weights"], dict):
        weights = data["weights"]
        total = 0.0
        for strat, w in weights.items():
            if type(w) is bool or not isinstance(w, (int, float)):
                return None, False, f"Weight for {strat} must be a number"
            if math.isnan(w) or math.isinf(w):
                return None, False, f"Weight for {strat} cannot be NaN or infinity"
            if w < 0:
                return None, False, f"Weight for {strat} cannot be negative"
            total += float(w)
        if total <= 0:
            return None, False, "Total weight must be positive"

    return data, True, None


class MockProvider:
    def __init__(
        self,
        capabilities: ModelCapabilities,
        availability: AvailabilityState = AvailabilityState.AVAILABLE,
        canned_response: str = "mocked response",
        canned_structured_data: dict[str, Any] | None = None,
        error_to_raise: ProviderError | None = None,
        effective_thinking: ThinkingLevel = ThinkingLevel.AUTO,
    ) -> None:
        self._capabilities = capabilities
        self._availability = AvailabilityResult(
            state=availability, message=f"State is {availability.value}"
        )
        if isinstance(availability, AvailabilityResult):
            self._availability = availability
        self._canned_response = canned_response
        self._canned_structured_data = canned_structured_data
        self._error = error_to_raise
        self._effective_thinking = effective_thinking

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_id(self) -> str:
        return self._capabilities.model_id

    def get_capabilities(self) -> ModelCapabilities:
        return self._capabilities

    def check_availability(self) -> AvailabilityResult:
        return self._availability

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        if self._error:
            raise self._error
        if self._availability.state != AvailabilityState.AVAILABLE:
            raise ProviderError(self._availability.state, self._availability.message)

        return ProviderResponse(
            content=self._canned_response,
            provider_name=self.provider_name,
            model_id=self.model_id,
            parsed_structured_data=self._canned_structured_data,
            metrics=UsageMetrics(
                input_tokens=10,
                output_tokens=20,
                latency_ms=100.0,
                estimated_cost=0.0,
                retries=0,
                requested_thinking_level=ThinkingLevel.AUTO,
                effective_thinking_level=self._effective_thinking,
            ),
        )


class ProviderRegistry:
    @classmethod
    def create(
        cls, role_config: Any, secrets_config: dict[str, str] | None = None
    ) -> AgentBackend | None:
        if role_config.provider == "rule_based":
            return None
        elif role_config.provider == "mock":
            return MockProvider(
                ModelCapabilities(
                    "mock-model", False, (ThinkingLevel.AUTO,), True, 8192, 4096, True, False, False
                )
            )
        elif role_config.provider == "openai":
            from password_arena.openai_provider import OpenAIProvider

            return OpenAIProvider(model=role_config.model or "gpt-4o")
        elif role_config.provider == "gemini":
            from password_arena.gemini_provider import GeminiProvider

            return GeminiProvider(model=role_config.model or "gemini-2.5-pro")
        elif role_config.provider == "anthropic":
            from password_arena.anthropic_provider import AnthropicProvider

            return AnthropicProvider(model=role_config.model or "claude-3-5-sonnet-20241022")
        elif role_config.provider == "ollama":
            from password_arena.ollama_provider import OllamaProvider

            return OllamaProvider(model=role_config.model or "llama3")
        else:
            raise ValueError(f"Unknown provider: {role_config.provider}")
