import os
import time
from typing import Any

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore
    types = None  # type: ignore

from password_arena.providers import (
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


class GeminiProvider:
    def __init__(self, model: str = "gemini-2.5-pro", client: Any = None) -> None:
        self.model = model
        self._client = client
        self._capabilities = ModelCapabilities(
            model_id=model,
            thinking_supported="pro" in model or "thinking" in model,
            accepted_thinking_levels=(
                ThinkingLevel.AUTO,
                ThinkingLevel.LOW,
                ThinkingLevel.MEDIUM,
                ThinkingLevel.HIGH,
            ),
            structured_output_supported=True,
            context_limit=1048576,
            output_limit=8192,
            token_accounting=True,
            cost_metadata=False,
            local_execution=False,
        )

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_id(self) -> str:
        return self.model

    def get_capabilities(self) -> ModelCapabilities:
        return self._capabilities

    def _get_client(self) -> Any:
        if self._client:
            return self._client
        if genai is None:
            raise ProviderError(
                AvailabilityState.PROVIDER_UNAVAILABLE, "google-genai package is not installed."
            )
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ProviderError(
                AvailabilityState.AUTHENTICATION_FAILED,
                "GEMINI_API_KEY environment variable is not set.",
            )
        return genai.Client(api_key=api_key)

    def _map_error(self, e: Exception) -> ProviderError:
        if genai is None:
            return ProviderError(
                AvailabilityState.PROVIDER_UNAVAILABLE, "google-genai package is not installed."
            )

        if isinstance(e, genai.errors.APIError):
            code = getattr(e, "code", 500)
            msg = str(e).lower()
            if code in (401, 403):
                return ProviderError(
                    AvailabilityState.AUTHENTICATION_FAILED, str(e), retryable=False
                )
            elif code == 404:
                return ProviderError(AvailabilityState.MODEL_UNAVAILABLE, str(e), retryable=False)
            elif code == 429:
                if "quota" in msg:
                    return ProviderError(AvailabilityState.QUOTA_EXHAUSTED, str(e), retryable=False)
                return ProviderError(
                    AvailabilityState.RATE_LIMITED, str(e), retryable=True, retry_after=5
                )
            elif code in (500, 502, 503, 504):
                return ProviderError(
                    AvailabilityState.PROVIDER_UNAVAILABLE, str(e), retryable=True, retry_after=5
                )
            elif code == 400:
                return ProviderError(
                    AvailabilityState.UNSUPPORTED_CONFIGURATION, str(e), retryable=False
                )

        msg = str(e).lower()
        if "timeout" in msg or "deadline" in msg:
            return ProviderError(AvailabilityState.TIMEOUT, str(e), retryable=True)
        if "connection" in msg or "network" in msg:
            return ProviderError(AvailabilityState.PROVIDER_UNAVAILABLE, str(e), retryable=True)

        return ProviderError(AvailabilityState.UNKNOWN_ERROR, str(e), retryable=False)

    def check_availability(self) -> AvailabilityResult:
        if genai is None:
            return AvailabilityResult(
                state=AvailabilityState.PROVIDER_UNAVAILABLE,
                message="google-genai package is not installed.",
            )
        if not os.environ.get("GEMINI_API_KEY") and self._client is None:
            return AvailabilityResult(
                state=AvailabilityState.AUTHENTICATION_FAILED,
                message="GEMINI_API_KEY environment variable is not set.",
            )

        try:
            client = self._get_client()
            # Verify the model exists and is accessible
            client.models.get(name=f"models/{self.model}")
            return AvailabilityResult(state=AvailabilityState.AVAILABLE, message="available")
        except Exception as e:
            err = self._map_error(e)
            return AvailabilityResult(
                state=err.state,
                message=str(e),
                retryable=err.retryable,
                retry_after_seconds=err.retry_after,
            )

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        client = self._get_client()

        config_kwargs: dict[str, Any] = {}
        if request.temperature is not None:
            config_kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            config_kwargs["max_output_tokens"] = request.max_tokens

        if self._capabilities.structured_output_supported and request.structured_schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = request.structured_schema

        if request.thinking_level != ThinkingLevel.AUTO:
            if not self._capabilities.thinking_supported:
                raise ProviderError(
                    AvailabilityState.UNSUPPORTED_CONFIGURATION,
                    f"Model {self.model} does not support explicit thinking levels.",
                )
            if request.thinking_level not in self._capabilities.accepted_thinking_levels:
                raise ProviderError(
                    AvailabilityState.UNSUPPORTED_CONFIGURATION,
                    f"Model {self.model} does not support thinking level "
                    f"{request.thinking_level.value}.",
                )

        start_time = time.monotonic()
        try:
            config = types.GenerateContentConfig(**config_kwargs) if types else None
            response = client.models.generate_content(
                model=self.model,
                contents=request.prompt,
                config=config,
            )
        except Exception as e:
            raise self._map_error(e) from e
        latency_ms = (time.monotonic() - start_time) * 1000.0

        content = response.text or ""
        parsed_data, success, error_msg = parse_and_validate_json(
            content, request.structured_schema
        )

        metrics = UsageMetrics(
            input_tokens=(
                response.usage_metadata.prompt_token_count if response.usage_metadata else 0
            ),
            output_tokens=(
                response.usage_metadata.candidates_token_count if response.usage_metadata else 0
            ),
            latency_ms=latency_ms,
            requested_thinking_level=request.thinking_level,
            effective_thinking_level=(
                request.thinking_level
                if self._capabilities.thinking_supported
                else ThinkingLevel.AUTO
            ),
            structured_validation_success=success,
        )

        return ProviderResponse(
            content=content,
            provider_name=self.provider_name,
            model_id=self.model_id,
            parsed_structured_data=parsed_data,
            metrics=metrics,
        )
