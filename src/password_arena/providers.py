import enum
from dataclasses import dataclass, field
from typing import Any, Protocol
import datetime


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
        self._availability = AvailabilityResult(state=availability, message=f"State is {availability.value}")
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
    def create(cls, role_config: Any, secrets_config: dict[str, str] | None = None) -> AgentBackend | None:
        if role_config.provider == "rule_based":
            return None
        elif role_config.provider == "mock":
            return MockProvider(
                ModelCapabilities("mock-model", False, (ThinkingLevel.AUTO,), True, 8192, 4096, True, False, False)
            )
        elif role_config.provider == "openai":
            from password_arena.openai_provider import OpenAIProvider
            return OpenAIProvider(model=role_config.model or "gpt-4o")
        elif role_config.provider == "gemini":
            from password_arena.gemini_provider import GeminiProvider
            return GeminiProvider(model=role_config.model or "gemini-2.5-pro")
        elif role_config.provider == "ollama":
            from password_arena.ollama_provider import OllamaProvider
            return OllamaProvider(model=role_config.model or "llama3")
        else:
            raise ValueError(f"Unknown provider: {role_config.provider}")
