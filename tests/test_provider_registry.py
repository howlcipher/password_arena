import pytest

from password_arena.models import ArenaConfig, RoleConfig, ThinkingLevel
from password_arena.engine import build_arena_engine, PreflightFailure
from password_arena.openai_provider import OpenAIProvider


def test_build_arena_engine_rule_based() -> None:
    config = ArenaConfig(
        defender_config=RoleConfig(provider="rule_based"),
        attacker_config=RoleConfig(provider="rule_based"),
    )
    result = build_arena_engine(config)
    assert not isinstance(result, PreflightFailure)
    assert result.defender.backend is None
    assert result.attacker.backend is None


def test_build_arena_engine_provider_injection() -> None:
    # Use a dummy provider config to ensure injection attempts to create the provider
    config = ArenaConfig(
        defender_config=RoleConfig(provider="openai", model="gpt-4o"),
        attacker_config=RoleConfig(provider="rule_based"),
    )
    # The preflight check will fail since no API key is set, but it proves we selected openai
    result = build_arena_engine(config)
    assert isinstance(result, PreflightFailure)
    assert result.role == "defender"
    assert result.state == "authentication_failed"


def test_build_arena_engine_unknown_provider() -> None:
    config = ArenaConfig(
        defender_config=RoleConfig(provider="unknown_xyz")
    )
    result = build_arena_engine(config)
    assert isinstance(result, PreflightFailure)
    assert result.state == "unknown_error"
    assert "Unknown provider" in result.message
