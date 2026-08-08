import os
import time
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

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


class OllamaProvider:
    def __init__(self, model: str = "llama3", base_url: str | None = None) -> None:
        self.model = model
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self._capabilities = ModelCapabilities(
            model_id=model,
            thinking_supported="deepseek" in model.lower(),
            accepted_thinking_levels=(ThinkingLevel.AUTO,),
            structured_output_supported=True,
            context_limit=8192,
            output_limit=4096,
            token_accounting=True,
            cost_metadata=False,
            local_execution=True,
        )

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_id(self) -> str:
        return self.model

    def get_capabilities(self) -> ModelCapabilities:
        return self._capabilities

    def check_availability(self) -> AvailabilityResult:
        if httpx is None:
            return AvailabilityResult(
                state=AvailabilityState.PROVIDER_UNAVAILABLE,
                message="httpx package is not installed.",
            )
        try:
            with httpx.Client() as client:
                response = client.get(f"{self.base_url}/api/tags", timeout=2.0)
                if response.status_code != 200:
                    return AvailabilityResult(
                        state=AvailabilityState.LOCAL_SERVER_OFFLINE,
                        message="Ollama server returned non-200 status.",
                    )

                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
                if self.model not in models and f"{self.model}:latest" not in models:
                    return AvailabilityResult(
                        state=AvailabilityState.LOCAL_MODEL_NOT_INSTALLED,
                        message=f"Model {self.model} not installed.",
                    )

                return AvailabilityResult(state=AvailabilityState.AVAILABLE, message="available")
        except httpx.RequestError:
            return AvailabilityResult(
                state=AvailabilityState.LOCAL_SERVER_OFFLINE,
                message="Ollama server is offline or unreachable.",
            )
        except Exception as e:
            return AvailabilityResult(state=AvailabilityState.UNKNOWN_ERROR, message=str(e))

    def _map_error(self, e: Exception) -> ProviderError:
        if isinstance(e, httpx.TimeoutException):
            return ProviderError(AvailabilityState.TIMEOUT, str(e), retryable=True)
        if isinstance(e, httpx.NetworkError):
            return ProviderError(AvailabilityState.LOCAL_SERVER_OFFLINE, str(e), retryable=True)
        if isinstance(e, httpx.HTTPStatusError):
            code = e.response.status_code
            if code == 404:
                return ProviderError(
                    AvailabilityState.LOCAL_MODEL_NOT_INSTALLED, str(e), retryable=False
                )
            if code == 400:
                return ProviderError(
                    AvailabilityState.UNSUPPORTED_CONFIGURATION, str(e), retryable=False
                )
            if code in (429,):
                return ProviderError(AvailabilityState.RATE_LIMITED, str(e), retryable=True)
        return ProviderError(AvailabilityState.UNKNOWN_ERROR, str(e), retryable=False)

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        if httpx is None:
            raise ProviderError(
                AvailabilityState.PROVIDER_UNAVAILABLE, "httpx package is not installed."
            )

        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": request.prompt,
            "stream": False,
            "options": {},
        }

        if request.temperature is not None:
            payload["options"]["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["options"]["num_predict"] = request.max_tokens

        if self._capabilities.structured_output_supported and request.structured_schema is not None:
            payload["format"] = request.structured_schema

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
            with httpx.Client() as client:
                response = client.post(f"{self.base_url}/api/generate", json=payload, timeout=60.0)
                response.raise_for_status()
                data = response.json()
                latency_ms = (time.monotonic() - start_time) * 1000.0

                content = data.get("response", "")
                parsed_data, success, error_msg = parse_and_validate_json(
                    content, request.structured_schema
                )

                metrics = UsageMetrics(
                    input_tokens=data.get("prompt_eval_count", 0),
                    output_tokens=data.get("eval_count", 0),
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
        except Exception as e:
            raise self._map_error(e) from e
