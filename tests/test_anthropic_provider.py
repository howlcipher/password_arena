import os
from typing import Any
from unittest.mock import Mock, patch

import pytest
from anthropic import AuthenticationError, NotFoundError, RateLimitError

from password_arena.anthropic_provider import AnthropicProvider
from password_arena.providers import (
    AvailabilityState,
    ProviderError,
    ProviderRequest,
)


@pytest.fixture
def mock_client() -> Any:
    client = Mock()
    mock_response = Mock()
    mock_block = Mock()
    mock_block.type = "text"
    mock_block.text = '{"key": "value"}'
    mock_response.content = [mock_block]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    client.messages.create.return_value = mock_response
    return client


def test_anthropic_provider_initialization(mock_client: Any) -> None:
    provider = AnthropicProvider(model="claude-3-5-sonnet-20241022", client=mock_client)
    assert provider.check_availability().state == AvailabilityState.AVAILABLE
    caps = provider.get_capabilities()
    assert caps.model_id == "claude-3-5-sonnet-20241022"
    assert caps.structured_output_supported is False


def test_anthropic_provider_no_credentials() -> None:
    with patch.dict(os.environ, {}, clear=True):
        provider = AnthropicProvider(model="claude-3-5-sonnet-20241022")
        assert provider.check_availability().state == AvailabilityState.AUTHENTICATION_FAILED


def test_anthropic_provider_generate(mock_client: Any) -> None:
    provider = AnthropicProvider(model="claude-3-5-sonnet-20241022", client=mock_client)
    request = ProviderRequest(
        prompt="hello",
        structured_schema={"type": "object", "properties": {"key": {"type": "string"}}},
    )

    response = provider.generate(request)
    assert response.content == '{"key": "value"}'
    assert response.parsed_structured_data == {"key": "value"}
    assert response.metrics.input_tokens == 100
    assert response.metrics.output_tokens == 50
    assert response.metrics.estimated_cost is not None
    assert response.metrics.estimated_cost > 0.0


def test_anthropic_provider_unpriced_model_cost_is_unavailable(mock_client: Any) -> None:
    provider = AnthropicProvider(model="some-future-model", client=mock_client)
    response = provider.generate(ProviderRequest(prompt="hello"))
    assert response.metrics.input_tokens == 100
    assert response.metrics.estimated_cost is None


def test_anthropic_provider_error_mapping(mock_client: Any) -> None:
    mock_client.messages.create.side_effect = AuthenticationError(
        message="Invalid token", response=Mock(), body=None
    )
    provider = AnthropicProvider(model="claude-3-5-sonnet-20241022", client=mock_client)

    with pytest.raises(ProviderError) as exc:
        provider.generate(ProviderRequest(prompt="hello"))

    assert exc.value.state == AvailabilityState.AUTHENTICATION_FAILED

    # Rate Limit
    mock_client.messages.create.side_effect = RateLimitError(
        message="Rate limited", response=Mock(), body=None
    )
    with pytest.raises(ProviderError) as exc:
        provider.generate(ProviderRequest(prompt="hello"))
    assert exc.value.state == AvailabilityState.RATE_LIMITED

    # Quota
    mock_client.messages.create.side_effect = RateLimitError(
        message="You exceeded your current quota", response=Mock(), body=None
    )
    with pytest.raises(ProviderError) as exc:
        provider.generate(ProviderRequest(prompt="hello"))
    assert exc.value.state == AvailabilityState.QUOTA_EXHAUSTED

    # Not Found
    mock_client.messages.create.side_effect = NotFoundError(
        message="Model not found", response=Mock(), body=None
    )
    with pytest.raises(ProviderError) as exc:
        provider.generate(ProviderRequest(prompt="hello"))
    assert exc.value.state == AvailabilityState.MODEL_UNAVAILABLE
