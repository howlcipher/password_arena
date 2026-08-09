from password_arena.anthropic_provider import ANTHROPIC_MODEL_REGISTRY
from password_arena.openai_provider import OPENAI_MODEL_REGISTRY
from password_arena.providers import ThinkingLevel
from password_arena.ui_helpers import (
    _known_models_for_provider,
    get_huggingface_execution_status,
    get_supported_thinking_levels,
)


def test_get_supported_thinking_levels_narrow_model() -> None:
    """o1-preview only accepts LOW/MEDIUM/HIGH per OPENAI_MODEL_REGISTRY --
    the UI must restrict to exactly that set, not offer all six levels."""
    levels = get_supported_thinking_levels("openai", "o1-preview")
    assert levels == (ThinkingLevel.LOW, ThinkingLevel.MEDIUM, ThinkingLevel.HIGH)


def test_get_supported_thinking_levels_auto_only_model() -> None:
    """gpt-4o does not support thinking at all -- only AUTO should be offered."""
    levels = get_supported_thinking_levels("openai", "gpt-4o")
    assert levels == (ThinkingLevel.AUTO,)


def test_get_supported_thinking_levels_unknown_manual_model_falls_back_to_auto() -> None:
    """A manually-entered, unrecognized OpenAI model ID must mirror exactly
    what OpenAIProvider itself falls back to at execution time (AUTO only)
    -- the UI must not guess something different from what will actually run."""
    levels = get_supported_thinking_levels("openai", "some-future-model-nobody-registered")
    assert levels == (ThinkingLevel.AUTO,)


def test_get_supported_thinking_levels_none_for_rule_based() -> None:
    assert get_supported_thinking_levels("rule_based", None) is None


def test_get_supported_thinking_levels_none_when_no_model_chosen_yet() -> None:
    assert get_supported_thinking_levels("openai", None) is None
    assert get_supported_thinking_levels("openai", "") is None


def test_get_supported_thinking_levels_sourced_from_anthropic_registry() -> None:
    for model_id, capabilities in ANTHROPIC_MODEL_REGISTRY.items():
        assert get_supported_thinking_levels("anthropic", model_id) == (
            capabilities.accepted_thinking_levels
        )


def test_known_models_for_openai_and_anthropic_match_their_registries() -> None:
    """The dropdown's "known models" must be sourced directly from each
    provider's own registry, never a separately hand-maintained list that
    can silently drift out of sync with it."""
    assert set(_known_models_for_provider("openai")) == set(OPENAI_MODEL_REGISTRY)
    assert set(_known_models_for_provider("anthropic")) == set(ANTHROPIC_MODEL_REGISTRY)


def test_known_models_empty_for_providers_without_a_static_registry() -> None:
    """gemini/ollama derive capabilities heuristically from the model string
    rather than a curated per-model registry -- there is nothing honest to
    enumerate here, so manual entry (or, for Ollama, live discovery) is the
    only correct source."""
    assert _known_models_for_provider("gemini") == []
    assert _known_models_for_provider("ollama") == []


def test_huggingface_execution_status_uses_exact_capability_registry_match() -> None:
    assert get_huggingface_execution_status("rule_based", "anything/model") == "NO"
    assert get_huggingface_execution_status("openai", "gpt-4o") == "YES"
    assert get_huggingface_execution_status("openai", "org/gpt-4o") == "UNKNOWN"
    assert get_huggingface_execution_status("gemini", "gemini-2.5-pro") == "UNKNOWN"
