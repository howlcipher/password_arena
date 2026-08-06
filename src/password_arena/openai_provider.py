import json
import os
import time
from typing import Any

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    NotFoundError,
    OpenAI,
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

# Registry of supported OpenAI models
# In a real app this might be loaded from a config file.
OPENAI_MODEL_REGISTRY: dict[str, ModelCapabilities] = {
    "gpt-4o": ModelCapabilities(
        model_id="gpt-4o",
        thinking_supported=False,
        accepted_thinking_levels=(ThinkingLevel.AUTO,),
        structured_output_supported=True,
        context_limit=128000,
        output_limit=4096,
        token_accounting=True,
        cost_metadata=True,
        local_execution=False,
    ),
    "o1-preview": ModelCapabilities(
        model_id="o1-preview",
        thinking_supported=True,
        accepted_thinking_levels=(ThinkingLevel.LOW, ThinkingLevel.MEDIUM, ThinkingLevel.HIGH),
        structured_output_supported=False,
        context_limit=128000,
        output_limit=32768,
        token_accounting=True,
        cost_metadata=True,
        local_execution=False,
    ),
    "gpt-4o-mini": ModelCapabilities(
        model_id="gpt-4o-mini",
        thinking_supported=False,
        accepted_thinking_levels=(ThinkingLevel.AUTO,),
        structured_output_supported=True,
        context_limit=128000,
        output_limit=16384,
        token_accounting=True,
        cost_metadata=True,
        local_execution=False,
    ),
}

# Pricing per 1m tokens (input, output)
OPENAI_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (5.0, 15.0),
    "o1-preview": (15.0, 60.0),
    "gpt-4o-mini": (0.15, 0.60),
}


class OpenAIProvider(AgentBackend):
    def __init__(self, model: str = "gpt-4o", client: OpenAI | None = None) -> None:
        self.model = model

        if model not in OPENAI_MODEL_REGISTRY:
            # Fallback for unknown models
            self._capabilities = ModelCapabilities(
                model_id=model,
                thinking_supported=False,
                accepted_thinking_levels=(ThinkingLevel.AUTO,),
                structured_output_supported=False,
                context_limit=8192,
                output_limit=4096,
                token_accounting=True,
                cost_metadata=False,
                local_execution=False,
            )
        else:
            self._capabilities = OPENAI_MODEL_REGISTRY[model]

        self.client = client
        self._availability = AvailabilityState.AVAILABLE
        self._check_availability_on_init()

    def _check_availability_on_init(self) -> None:
        # Check if client was provided or credentials exist
        if self.client is not None:
            self._availability = AvailabilityState.AVAILABLE
        elif "OPENAI_API_KEY" in os.environ:
            try:
                self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
                self._availability = AvailabilityState.AVAILABLE
            except Exception:
                self._availability = AvailabilityState.AUTHENTICATION_FAILED
        else:
            self._availability = AvailabilityState.AUTHENTICATION_FAILED

    @property
    def provider_name(self) -> str:
        return "openai"

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
            # Check if it's quota or rate limit
            # Often quota errors are labeled with 'insufficient_quota'
            msg = str(e).lower()
            if "quota" in msg or "exceeded your current quota" in msg:
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

        messages: list[dict[str, Any]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        messages.append({"role": "user", "content": request.prompt})

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }

        if request.temperature is not None and not self._capabilities.thinking_supported:
            kwargs["temperature"] = request.temperature

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
            kwargs["reasoning_effort"] = request.thinking_level.value

        if request.max_tokens is not None:
            # o1 uses max_completion_tokens
            if self.model.startswith("o1"):
                kwargs["max_completion_tokens"] = request.max_tokens
            else:
                kwargs["max_tokens"] = request.max_tokens

        # structured outputs
        if request.structured_schema and self._capabilities.structured_output_supported:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_response",
                    "schema": request.structured_schema,
                    "strict": True,
                },
            }
        elif request.structured_schema:
            # fallback to JSON mode or standard text if structured outputs not natively supported
            kwargs["response_format"] = {"type": "json_object"}
            schema_str = json.dumps(request.structured_schema)
            messages.append(
                {
                    "role": "system",
                    "content": f"You must output JSON matching this schema: {schema_str}",
                }
            )

        start_time = time.monotonic()
        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as e:
            raise self._map_error(e) from e

        end_time = time.monotonic()
        latency_ms = (end_time - start_time) * 1000.0

        content = response.choices[0].message.content or ""

        parsed_structured_data, success, error_msg = parse_and_validate_json(
            content, request.structured_schema
        )

        input_tokens = 0
        output_tokens = 0
        estimated_cost = 0.0

        if response.usage:
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens

            if self._capabilities.cost_metadata and self.model in OPENAI_PRICING:
                in_price, out_price = OPENAI_PRICING[self.model]
                cost_in = input_tokens / 1_000_000 * in_price
                cost_out = output_tokens / 1_000_000 * out_price
                estimated_cost = cost_in + cost_out

        metrics = UsageMetrics(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            estimated_cost=estimated_cost,
            retries=0,
            requested_thinking_level=ThinkingLevel.AUTO,
            effective_thinking_level=ThinkingLevel.AUTO,
            structured_validation_success=success,
        )

        return ProviderResponse(
            content=content,
            provider_name=self.provider_name,
            model_id=self.model_id,
            parsed_structured_data=parsed_structured_data,
            metrics=metrics
        )
