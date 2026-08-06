import enum
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
    UNKNOWN_ERROR = "unknown_error"


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
    latency_ms: float = 0.0
    estimated_cost: float = 0.0
    retries: int = 0
    requested_thinking_level: ThinkingLevel = ThinkingLevel.AUTO
    effective_thinking_level: ThinkingLevel = ThinkingLevel.AUTO


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


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    content: str
    parsed_structured_data: dict[str, Any] | None = None
    metrics: UsageMetrics = field(default_factory=UsageMetrics)


class AgentBackend(Protocol):
    def get_capabilities(self) -> ModelCapabilities:
        ...

    def check_availability(self) -> AvailabilityState:
        ...

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        ...


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
        self._availability = availability
        self._canned_response = canned_response
        self._canned_structured_data = canned_structured_data
        self._error = error_to_raise
        self._effective_thinking = effective_thinking

    def get_capabilities(self) -> ModelCapabilities:
        return self._capabilities

    def check_availability(self) -> AvailabilityState:
        return self._availability

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        if self._error:
            raise self._error
        if self._availability != AvailabilityState.AVAILABLE:
            raise ProviderError(self._availability, f"Provider is {self._availability.value}")

        return ProviderResponse(
            content=self._canned_response,
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
