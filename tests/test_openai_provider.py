import os
from typing import Any
from unittest.mock import Mock, patch

import pytest
from openai import AuthenticationError, NotFoundError, RateLimitError

from password_arena.openai_provider import OpenAIProvider
from password_arena.providers import (
    AvailabilityState,
    ProviderError,
    ProviderRequest,
)


@pytest.fixture
def mock_client() -> Any:
    client = Mock()
    mock_response = Mock()
    mock_choice = Mock()
    mock_choice.message.content = '{"key": "value"}'
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50
    client.chat.completions.create.return_value = mock_response
    return client


def test_openai_provider_initialization(mock_client: Any) -> None:
    provider = OpenAIProvider(model="gpt-4o", client=mock_client)
    assert provider.check_availability().state == AvailabilityState.AVAILABLE
    caps = provider.get_capabilities()
    assert caps.model_id == "gpt-4o"
    assert caps.structured_output_supported is True


def test_openai_provider_no_credentials() -> None:
    with patch.dict(os.environ, {}, clear=True):
        provider = OpenAIProvider(model="gpt-4o")
        assert provider.check_availability().state == AvailabilityState.AUTHENTICATION_FAILED


def test_openai_provider_generate(mock_client: Any) -> None:
    provider = OpenAIProvider(model="gpt-4o", client=mock_client)
    request = ProviderRequest(
        prompt="hello",
        structured_schema={"type": "object", "properties": {"key": {"type": "string"}}},
    )

    response = provider.generate(request)
    assert response.content == '{"key": "value"}'
    assert response.parsed_structured_data == {"key": "value"}
    assert response.metrics.input_tokens == 100
    assert response.metrics.output_tokens == 50
    assert response.metrics.estimated_cost > 0.0


def test_openai_provider_error_mapping(mock_client: Any) -> None:
    mock_client.chat.completions.create.side_effect = AuthenticationError(
        message="Invalid token", response=Mock(), body=None
    )
    provider = OpenAIProvider(model="gpt-4o", client=mock_client)

    with pytest.raises(ProviderError) as exc:
        provider.generate(ProviderRequest(prompt="hello"))

    assert exc.value.state == AvailabilityState.AUTHENTICATION_FAILED

    # Rate Limit
    mock_client.chat.completions.create.side_effect = RateLimitError(
        message="Rate limited", response=Mock(), body=None
    )
    with pytest.raises(ProviderError) as exc:
        provider.generate(ProviderRequest(prompt="hello"))
    assert exc.value.state == AvailabilityState.RATE_LIMITED

    # Quota
    mock_client.chat.completions.create.side_effect = RateLimitError(
        message="You exceeded your current quota", response=Mock(), body=None
    )
    with pytest.raises(ProviderError) as exc:
        provider.generate(ProviderRequest(prompt="hello"))
    assert exc.value.state == AvailabilityState.QUOTA_EXHAUSTED

    # Not Found
    mock_client.chat.completions.create.side_effect = NotFoundError(
        message="Model not found", response=Mock(), body=None
    )
    with pytest.raises(ProviderError) as exc:
        provider.generate(ProviderRequest(prompt="hello"))
    assert exc.value.state == AvailabilityState.MODEL_UNAVAILABLE
