from password_arena.models import RoleConfig, TournamentConfig
from password_arena.providers import ThinkingLevel
from password_arena.tournament_comparison import compare_tournament_configs


def _config(**overrides: object) -> TournamentConfig:
    defaults: dict[str, object] = {
        "attackers": (RoleConfig(provider="openai", model="gpt-4o"),),
        "defenders": (RoleConfig(provider="anthropic", model="claude-3-5-sonnet-20241022"),),
        "seeds": (1, 2, 3),
        "rounds_per_match": 5,
        "generator_version": "benchmark",
        "generator_mode": "deterministic-test",
        "max_guesses": 5000,
        "max_wall_time_s": None,
        "max_tokens": None,
        "max_api_cost": None,
        "max_retries": None,
    }
    defaults.update(overrides)
    return TournamentConfig(**defaults)  # type: ignore[arg-type]


def test_identical_configs_have_no_differences() -> None:
    a = _config()
    b = _config()
    result = compare_tournament_configs(a, b)
    assert result.identical
    assert result.differences == ()


def test_seed_order_does_not_affect_comparability() -> None:
    """Trial order does not affect aggregate comparability -- only the set
    of seeds run matters."""
    a = _config(seeds=(1, 2, 3))
    b = _config(seeds=(3, 1, 2))
    result = compare_tournament_configs(a, b)
    assert result.identical


def test_seed_set_difference_is_reported() -> None:
    a = _config(seeds=(1, 2, 3))
    b = _config(seeds=(1, 2, 4))
    result = compare_tournament_configs(a, b)
    assert not result.identical
    assert any("seeds" in d for d in result.differences)


def test_scalar_budget_differences_are_reported() -> None:
    a = _config(rounds_per_match=5, max_guesses=5000, max_retries=3)
    b = _config(rounds_per_match=10, max_guesses=100, max_retries=5)
    result = compare_tournament_configs(a, b)
    assert not result.identical
    joined = "\n".join(result.differences)
    assert "rounds_per_match" in joined
    assert "max_guesses" in joined
    assert "max_retries" in joined


def test_thinking_level_difference_in_role_config_is_reported() -> None:
    """A handful of matching scalar settings must not be enough to call two
    tournaments directly comparable when the actual model configurations
    differ (e.g. thinking level)."""
    a = _config(attackers=(RoleConfig(provider="openai", model="gpt-4o"),))
    b = _config(
        attackers=(
            RoleConfig(provider="openai", model="gpt-4o", thinking_level=ThinkingLevel.HIGH),
        )
    )
    result = compare_tournament_configs(a, b)
    assert not result.identical
    assert any("attackers" in d for d in result.differences)


def test_provider_or_model_difference_in_role_config_is_reported() -> None:
    a = _config(defenders=(RoleConfig(provider="anthropic", model="claude-3-5-sonnet-20241022"),))
    b = _config(defenders=(RoleConfig(provider="anthropic", model="claude-3-5-haiku-20241022"),))
    result = compare_tournament_configs(a, b)
    assert not result.identical
    assert any("defenders" in d for d in result.differences)


def test_extra_role_in_one_tournament_is_reported() -> None:
    a = _config(
        attackers=(
            RoleConfig(provider="openai", model="gpt-4o"),
            RoleConfig(provider="anthropic", model="claude-3-5-sonnet-20241022"),
        )
    )
    b = _config(attackers=(RoleConfig(provider="openai", model="gpt-4o"),))
    result = compare_tournament_configs(a, b)
    assert not result.identical
    assert any("attackers only in A" in d for d in result.differences)


def test_generator_version_and_mode_differences_are_reported() -> None:
    a = _config(generator_version="benchmark", generator_mode="deterministic-test")
    b = _config(generator_version="1.0", generator_mode="live")
    result = compare_tournament_configs(a, b)
    assert not result.identical
    joined = "\n".join(result.differences)
    assert "generator_version" in joined
    assert "generator_mode" in joined
