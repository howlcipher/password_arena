import pytest

from password_arena.providers import (
    AvailabilityState,
    MockProvider,
    ModelCapabilities,
    ProviderError,
    ProviderRequest,
    ThinkingLevel,
)


def test_thinking_levels() -> None:
    levels = [
        ThinkingLevel.AUTO,
        ThinkingLevel.MINIMAL,
        ThinkingLevel.LOW,
        ThinkingLevel.MEDIUM,
        ThinkingLevel.HIGH,
        ThinkingLevel.MAXIMUM,
    ]
    assert len(levels) == 6
    assert ThinkingLevel("auto") == ThinkingLevel.AUTO
    assert ThinkingLevel("maximum") == ThinkingLevel.MAXIMUM


def test_availability_states() -> None:
    states = [
        AvailabilityState.AVAILABLE,
        AvailabilityState.RATE_LIMITED,
        AvailabilityState.QUOTA_EXHAUSTED,
        AvailabilityState.AUTHENTICATION_FAILED,
        AvailabilityState.MODEL_UNAVAILABLE,
        AvailabilityState.UNSUPPORTED_CONFIGURATION,
        AvailabilityState.PROVIDER_UNAVAILABLE,
        AvailabilityState.LOCAL_SERVER_OFFLINE,
        AvailabilityState.LOCAL_MODEL_NOT_INSTALLED,
        AvailabilityState.UNKNOWN_ERROR,
        AvailabilityState.TIMEOUT,
        AvailabilityState.INVALID_RESPONSE,
    ]
    assert len(states) == 12
    assert AvailabilityState("rate_limited") == AvailabilityState.RATE_LIMITED


def test_mock_provider_success() -> None:
    capabilities = ModelCapabilities(
        model_id="mock-1",
        thinking_supported=True,
        accepted_thinking_levels=(ThinkingLevel.AUTO, ThinkingLevel.HIGH),
        structured_output_supported=True,
        context_limit=8000,
        output_limit=1000,
        token_accounting=True,
        cost_metadata=True,
        local_execution=False,
    )
    provider = MockProvider(
        capabilities=capabilities,
        availability=AvailabilityState.AVAILABLE,
        canned_response="mock response",
        effective_thinking=ThinkingLevel.HIGH,
    )

    assert provider.get_capabilities() == capabilities
    assert provider.check_availability().state == AvailabilityState.AVAILABLE

    request = ProviderRequest(prompt="hello")
    response = provider.generate(request)
    assert response.content == "mock response"
    assert response.metrics.effective_thinking_level == ThinkingLevel.HIGH


@pytest.mark.parametrize(
    "state",
    [
        AvailabilityState.RATE_LIMITED,
        AvailabilityState.QUOTA_EXHAUSTED,
        AvailabilityState.AUTHENTICATION_FAILED,
        AvailabilityState.MODEL_UNAVAILABLE,
        AvailabilityState.UNSUPPORTED_CONFIGURATION,
        AvailabilityState.PROVIDER_UNAVAILABLE,
        AvailabilityState.LOCAL_SERVER_OFFLINE,
        AvailabilityState.LOCAL_MODEL_NOT_INSTALLED,
        AvailabilityState.UNKNOWN_ERROR,
        AvailabilityState.TIMEOUT,
        AvailabilityState.INVALID_RESPONSE,
    ],
)
def test_mock_provider_unavailable(state: AvailabilityState) -> None:
    capabilities = ModelCapabilities(
        model_id="mock-1",
        thinking_supported=False,
        accepted_thinking_levels=(),
        structured_output_supported=False,
        context_limit=1000,
        output_limit=1000,
        token_accounting=False,
        cost_metadata=False,
        local_execution=False,
    )
    provider = MockProvider(capabilities=capabilities, availability=state)
    assert provider.check_availability().state == state

    with pytest.raises(ProviderError) as exc:
        provider.generate(ProviderRequest(prompt="test"))

    assert exc.value.state == state
