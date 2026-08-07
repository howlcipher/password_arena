import json
import os
import time
from typing import Any

from anthropic import (
    Anthropic,
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
)

from password_arena.providers import (
    AgentBackend,
    AvailabilityResult,
    AvailabilityState,
    ModelCapabilities,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    ThinkingLevel,
    UsageMetrics,
    parse_and_validate_json,
)

ANTHROPIC_MODEL_REGISTRY: dict[str, ModelCapabilities] = {
    "claude-3-5-sonnet-20241022": ModelCapabilities(
        model_id="claude-3-5-sonnet-20241022",
        thinking_supported=False,
        accepted_thinking_levels=(ThinkingLevel.AUTO,),
        structured_output_supported=False,
        context_limit=200000,
        output_limit=8192,
        token_accounting=True,
        cost_metadata=True,
        local_execution=False,
    ),
    "claude-3-7-sonnet-20250219": ModelCapabilities(
        model_id="claude-3-7-sonnet-20250219",
        thinking_supported=True,
        accepted_thinking_levels=(
            ThinkingLevel.MINIMAL,
            ThinkingLevel.LOW,
            ThinkingLevel.MEDIUM,
            ThinkingLevel.HIGH,
            ThinkingLevel.MAXIMUM,
        ),
        structured_output_supported=False,
        context_limit=200000,
        output_limit=128000,
        token_accounting=True,
        cost_metadata=True,
        local_execution=False,
    ),
    "claude-3-5-haiku-20241022": ModelCapabilities(
        model_id="claude-3-5-haiku-20241022",
        thinking_supported=False,
        accepted_thinking_levels=(ThinkingLevel.AUTO,),
        structured_output_supported=False,
        context_limit=200000,
        output_limit=8192,
        token_accounting=True,
        cost_metadata=True,
        local_execution=False,
    ),
}

ANTHROPIC_PRICING: dict[str, tuple[float, float]] = {
    "claude-3-5-sonnet-20241022": (3.0, 15.0),
    "claude-3-7-sonnet-20250219": (3.0, 15.0),
    "claude-3-5-haiku-20241022": (0.8, 4.0),
}


class AnthropicProvider(AgentBackend):
    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        client: Anthropic | None = None
    ) -> None:
        self.model = model

        if model not in ANTHROPIC_MODEL_REGISTRY:
            self._capabilities = ModelCapabilities(
                model_id=model,
                thinking_supported=False,
                accepted_thinking_levels=(ThinkingLevel.AUTO,),
                structured_output_supported=False,
                context_limit=200000,
                output_limit=4096,
                token_accounting=True,
                cost_metadata=False,
                local_execution=False,
            )
        else:
            self._capabilities = ANTHROPIC_MODEL_REGISTRY[model]

        self.client = client
        self._availability = AvailabilityState.AVAILABLE
        self._check_availability_on_init()

    def _check_availability_on_init(self) -> None:
        if self.client is not None:
            self._availability = AvailabilityState.AVAILABLE
        elif "ANTHROPIC_API_KEY" in os.environ:
            try:
                self.client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
                self._availability = AvailabilityState.AVAILABLE
            except Exception:
                self._availability = AvailabilityState.AUTHENTICATION_FAILED
        else:
            self._availability = AvailabilityState.AUTHENTICATION_FAILED

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def model_id(self) -> str:
        return self.model

    def get_capabilities(self) -> ModelCapabilities:
        return self._capabilities

    def check_availability(self) -> AvailabilityResult:
        return AvailabilityResult(state=self._availability, message=self._availability.value)

    def _map_error(self, e: Exception) -> ProviderError:
        if isinstance(e, AuthenticationError):
            return ProviderError(AvailabilityState.AUTHENTICATION_FAILED, str(e), retryable=False)
        if isinstance(e, RateLimitError):
            msg = str(e).lower()
            if "quota" in msg or "insufficient_quota" in msg:
                return ProviderError(AvailabilityState.QUOTA_EXHAUSTED, str(e), retryable=False)
            return ProviderError(
                AvailabilityState.RATE_LIMITED, str(e), retryable=True, retry_after=10
            )
        if isinstance(e, NotFoundError):
            return ProviderError(AvailabilityState.MODEL_UNAVAILABLE, str(e), retryable=False)
        if isinstance(e, (APITimeoutError, APIConnectionError)):
            return ProviderError(AvailabilityState.PROVIDER_UNAVAILABLE, str(e), retryable=True)
        if isinstance(e, APIError):
            return ProviderError(AvailabilityState.PROVIDER_UNAVAILABLE, str(e), retryable=True)
        return ProviderError(AvailabilityState.UNKNOWN_ERROR, str(e), retryable=False)

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        if self._availability != AvailabilityState.AVAILABLE or not self.client:
            raise ProviderError(self._availability, f"Provider is {self._availability.value}")

        messages: list[dict[str, Any]] = [
            {"role": "user", "content": request.prompt}
        ]
        
        system = request.system_prompt
        
        if request.structured_schema:
            schema_str = json.dumps(request.structured_schema)
            instruction = f"You must output JSON matching this schema: {schema_str}"
            system = f"{system}\n\n{instruction}" if system else instruction

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": request.max_tokens or self._capabilities.output_limit,
        }
        if system:
            kwargs["system"] = system
            
        if request.temperature is not None and not (
            self._capabilities.thinking_supported and request.thinking_level != ThinkingLevel.AUTO
        ):
            kwargs["temperature"] = request.temperature

        effective_thinking = ThinkingLevel.AUTO

        if request.thinking_level != ThinkingLevel.AUTO:
            if not self._capabilities.thinking_supported:
                raise ProviderError(
                    AvailabilityState.UNSUPPORTED_CONFIGURATION,
                    f"Model {self.model} does not support explicit thinking levels."
                )
            if request.thinking_level not in self._capabilities.accepted_thinking_levels:
                raise ProviderError(
                    AvailabilityState.UNSUPPORTED_CONFIGURATION,
                    f"Model {self.model} does not support thinking level "
                    f"{request.thinking_level.value}."
                )
            
            effective_thinking = request.thinking_level
            
            # Map thinking levels to token budgets
            budget_map = {
                ThinkingLevel.MINIMAL: 1024,
                ThinkingLevel.LOW: 2048,
                ThinkingLevel.MEDIUM: 4096,
                ThinkingLevel.HIGH: 8192,
                ThinkingLevel.MAXIMUM: 16384,
            }
            budget = budget_map.get(request.thinking_level, 4096)
            
            # Anthropic thinking parameter
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": budget
            }
            
            # Need to bump max_tokens to accommodate the budget
            if kwargs["max_tokens"] <= budget:
                kwargs["max_tokens"] = budget + 4096

        start_time = time.monotonic()
        try:
            response = self.client.messages.create(**kwargs)
        except Exception as e:
            raise self._map_error(e) from e

        end_time = time.monotonic()
        latency_ms = (end_time - start_time) * 1000.0

        content = ""
        for block in response.content:
            if getattr(block, "type", None) == "text":
                content += getattr(block, "text", "")

        parsed_structured_data, success, error_msg = parse_and_validate_json(
            content, request.structured_schema
        )

        input_tokens = 0
        output_tokens = 0
        estimated_cost = 0.0

        if hasattr(response, "usage") and response.usage:
            input_tokens = getattr(response.usage, "input_tokens", 0)
            output_tokens = getattr(response.usage, "output_tokens", 0)

            if self._capabilities.cost_metadata and self.model in ANTHROPIC_PRICING:
                in_price, out_price = ANTHROPIC_PRICING[self.model]
                cost_in = input_tokens / 1_000_000 * in_price
                cost_out = output_tokens / 1_000_000 * out_price
                estimated_cost = cost_in + cost_out

        metrics = UsageMetrics(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            estimated_cost=estimated_cost,
            retries=0,
            requested_thinking_level=request.thinking_level,
            effective_thinking_level=effective_thinking,
            structured_validation_success=success,
        )

        return ProviderResponse(
            content=content,
            provider_name=self.provider_name,
            model_id=self.model_id,
            parsed_structured_data=parsed_structured_data,
            metrics=metrics
        )
