from password_arena.models import (
    MatchupConfig,
    ReplayMetadata,
    RoleConfig,
    RoleMetadata,
    TournamentConfig,
)
from password_arena.providers import ThinkingLevel
from password_arena.tournament import aggregate_matchup
from password_arena.tournament_comparison import (
    compare_stored_tournaments,
    compare_tournament_configs,
)
from password_arena.tournament_history import StoredMatchup, StoredTournament


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


def _replay(
    *,
    application: str = "0.1.0",
    schema: str = "1.0",
    attacker_prompt: str = "1.0",
    defender_prompt: str = "1.0",
    capability_registry: str = "1.0",
) -> ReplayMetadata:
    return ReplayMetadata(
        attacker=RoleMetadata("openai", "gpt-4o", ThinkingLevel.AUTO),
        defender=RoleMetadata("anthropic", "claude", ThinkingLevel.AUTO),
        seeds=(1,),
        rounds_per_match=1,
        max_guesses=100,
        generator_mode="deterministic-test",
        generator_version="benchmark",
        application_version=application,
        schema_version=schema,
        deterministic=False,
        attacker_prompt_version=attacker_prompt,
        defender_prompt_version=defender_prompt,
        capability_registry_version=capability_registry,
    )


def _stored(
    replays: tuple[ReplayMetadata | None, ...], *, schema_version: str = "2.1"
) -> StoredTournament:
    config = _config()
    matchup_config = MatchupConfig(
        attacker=config.attackers[0],
        defender=config.defenders[0],
        rounds=1,
        seeds=(1,),
    )
    summary = aggregate_matchup(matchup_config, [], []).summary
    return StoredTournament(
        tournament_id="stored",
        timestamp="2026-08-08T00:00:00+00:00",
        schema_version=schema_version,
        config=config,
        matchups=tuple(
            StoredMatchup(
                matchup_id=f"m{index}",
                config=matchup_config,
                summary=summary,
                is_comparable=False,
                non_comparable_reason="preflight_failed",
                experiment_ids=(),
                replay=replay,
            )
            for index, replay in enumerate(replays)
        ),
    )


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


def test_saved_tournament_comparison_includes_all_replay_versions() -> None:
    a = _stored((_replay(),))
    b = _stored(
        (
            _replay(
                application="0.1.1",
                schema="1.1",
                attacker_prompt="1.1",
                defender_prompt="1.2",
                capability_registry="2.0",
            ),
        )
    )
    result = compare_stored_tournaments(a, b)

    assert result.configuration_identical
    assert not result.identical
    joined = "\n".join(result.metadata_differences)
    assert "Application version: A = {0.1.0}; B = {0.1.1}" in joined
    assert "Experiment/schema version: A = {1.0}; B = {1.1}" in joined
    assert "Attacker prompt version: A = {1.0}; B = {1.1}" in joined
    assert "Defender prompt version: A = {1.0}; B = {1.2}" in joined
    assert "Capability-registry version: A = {1.0}; B = {2.0}" in joined


def test_saved_tournament_comparison_surfaces_mixed_metadata_sets() -> None:
    a = _stored((_replay(attacker_prompt="1.0"), _replay(attacker_prompt="1.1")))
    b = _stored((_replay(attacker_prompt="1.1"),))
    result = compare_stored_tournaments(a, b)

    assert not result.identical
    assert any(
        "Attacker prompt version: A = {1.0, 1.1}; B = {1.1}" in difference
        and "mixed version metadata" in difference
        for difference in result.metadata_differences
    )


def test_saved_tournament_comparison_treats_old_missing_metadata_as_unavailable() -> None:
    old_a = _stored((None,), schema_version="2.0")
    old_b = _stored((None,), schema_version="2.0")
    result = compare_stored_tournaments(old_a, old_b)

    assert result.configuration_identical
    assert not result.identical
    assert len(result.metadata_differences) == 5
    assert all("version metadata unavailable" in item for item in result.metadata_differences)


def test_saved_tournament_comparison_reports_history_schema_separately() -> None:
    result = compare_stored_tournaments(
        _stored((_replay(),), schema_version="2.0"), _stored((_replay(),))
    )
    assert not result.identical
    assert result.metadata_differences == (
        "Tournament history schema version: A = '2.0'; B = '2.1'",
    )


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
