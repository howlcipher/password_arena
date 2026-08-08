import pytest

from password_arena import ArenaConfig, ArenaEngine


def test_engine_runs_requested_rounds() -> None:
    result = ArenaEngine(ArenaConfig(rounds=4, max_guesses=100)).run()
    assert len(result.rounds) == 4
    assert result.rounds[0].round_number == 1
    assert result.rounds[-1].round_number == 4


def test_engine_resumption() -> None:
    from password_arena.providers import (
        AvailabilityState,
        MockProvider,
        ModelCapabilities,
        ProviderError,
        ProviderRequest,
        ProviderResponse,
        ThinkingLevel,
    )

    capabilities = ModelCapabilities(
        model_id="mock",
        thinking_supported=False,
        accepted_thinking_levels=(ThinkingLevel.AUTO,),
        structured_output_supported=True,
        context_limit=1000,
        output_limit=1000,
        token_accounting=False,
        cost_metadata=False,
        local_execution=True,
    )

    class FailingMockProvider(MockProvider):
        def __init__(self) -> None:
            super().__init__(
                capabilities, canned_structured_data={"family": "dictionary-word", "note": "x"}
            )
            self.calls = 0

        def generate(self, request: ProviderRequest) -> ProviderResponse:
            self.calls += 1
            if self.calls == 1:
                raise ProviderError(AvailabilityState.RATE_LIMITED, "Rate limited on round 1")
            return super().generate(request)

    engine = ArenaEngine(
        ArenaConfig(rounds=2, max_guesses=10), defender_backend=FailingMockProvider()
    )
    res1 = engine.run()
    assert res1.interruption_state == "rate_limited"
    assert len(res1.rounds) == 0

    res2 = engine.run()
    assert res2.interruption_reason is None
    assert len(res2.rounds) == 2


def test_passwords_are_hidden_by_default() -> None:
    result = ArenaEngine(ArenaConfig(rounds=1, max_guesses=10)).run()
    displayed = result.rounds[0].password_display
    assert set(displayed) == {"•"}


def test_difficulty_is_capped() -> None:
    result = ArenaEngine(
        ArenaConfig(rounds=5, start_difficulty=9, difficulty_step=3, max_guesses=10)
    ).run()
    assert all(item.difficulty <= 10 for item in result.rounds)


def test_default_demo_solves_early_patterns_then_hits_resistance() -> None:
    result = ArenaEngine(ArenaConfig(rounds=4, max_guesses=5_000, reveal_passwords=True)).run()
    assert result.rounds[0].attack.solved is True
    assert result.rounds[1].attack.solved is True
    assert result.rounds[3].strength.entropy_bits > result.rounds[0].strength.entropy_bits


def test_tiny_guess_budgets_are_valid_and_bounded() -> None:
    for budget in range(1, 5):
        result = ArenaEngine(ArenaConfig(rounds=1, max_guesses=budget)).run()
        attack = result.rounds[0].attack
        assert attack.guesses_used <= budget
        assert sum(entry.guess_budget for entry in attack.plan) == budget
        assert all(entry.guess_budget >= 0 for entry in attack.plan)


def test_engine_with_mock_backend() -> None:
    from password_arena.providers import MockProvider, ModelCapabilities, ThinkingLevel

    capabilities = ModelCapabilities(
        model_id="mock",
        thinking_supported=False,
        accepted_thinking_levels=(ThinkingLevel.AUTO,),
        structured_output_supported=True,
        context_limit=1000,
        output_limit=1000,
        token_accounting=True,
        cost_metadata=True,
        local_execution=True,
    )
    defender_backend = MockProvider(
        capabilities=capabilities,
        canned_structured_data={
            "password": "mocked-password-123",
            "family": "dictionary-word",
            "note": "mocked note",
        },
    )
    attacker_backend = MockProvider(
        capabilities=capabilities,
        canned_structured_data={
            "weights": {"common": 0.5, "random": 0.5},
            "reasoning": "mocked reasoning",
        },
    )
    result = ArenaEngine(
        ArenaConfig(rounds=1, max_guesses=10),
        defender_backend=defender_backend,
        attacker_backend=attacker_backend,
    ).run()

    assert result.rounds[0].defender_strategy == "dictionary-word"

    plan = result.rounds[0].attack.plan
    assert any(p.strategy == "common" and p.weight == 0.5 for p in plan)


def test_generator_mode_deterministic_test_reproducibility() -> None:
    # Deterministic mode should produce identical results.
    config1 = ArenaConfig(
        rounds=1, start_difficulty=7, max_guesses=10, seed=123, generator_mode="deterministic-test"
    )
    result1 = ArenaEngine(config1).run()

    config2 = ArenaConfig(
        rounds=1, start_difficulty=7, max_guesses=10, seed=123, generator_mode="deterministic-test"
    )
    result2 = ArenaEngine(config2).run()

    assert result1.rounds[0].password_display == result2.rounds[0].password_display


def test_rule_based_rounds_have_no_usage_and_are_comparable() -> None:
    result = ArenaEngine(ArenaConfig(rounds=1, max_guesses=10)).run()
    round_result = result.rounds[0]
    assert round_result.attacker_usage is None
    assert round_result.defender_usage is None
    assert round_result.comparable is True


def test_mock_backend_populates_usage_via_build_arena_engine() -> None:
    from password_arena.engine import PreflightFailure, build_arena_engine
    from password_arena.models import RoleConfig

    config = ArenaConfig(
        rounds=1,
        max_guesses=10,
        defender_config=RoleConfig(provider="mock"),
        attacker_config=RoleConfig(provider="mock"),
    )
    engine = build_arena_engine(config)
    assert not isinstance(engine, PreflightFailure)
    result = engine.run()
    round_result = result.rounds[0]

    assert round_result.attacker_usage is not None
    assert round_result.attacker_usage.input_tokens > 0
    assert round_result.defender_usage is not None
    assert round_result.defender_usage.input_tokens > 0
    assert round_result.comparable is True


def test_fallback_used_marks_round_non_comparable(monkeypatch: pytest.MonkeyPatch) -> None:
    from typing import Any

    from password_arena import providers as providers_module
    from password_arena.engine import PreflightFailure, build_arena_engine
    from password_arena.models import RoleConfig
    from password_arena.providers import (
        AgentBackend,
        MockProvider,
        ModelCapabilities,
        ThinkingLevel,
    )

    capabilities = ModelCapabilities(
        model_id="mock",
        thinking_supported=False,
        accepted_thinking_levels=(ThinkingLevel.AUTO,),
        structured_output_supported=True,
        context_limit=1000,
        output_limit=1000,
        token_accounting=True,
        cost_metadata=False,
        local_execution=True,
    )
    real_create = providers_module.ProviderRegistry.create

    def fallback_mock_create(
        role_config: Any, secrets_config: dict[str, str] | None = None
    ) -> AgentBackend | None:
        if role_config.provider == "mock":
            return MockProvider(capabilities, fallback_used=True)
        return real_create(role_config, secrets_config)

    monkeypatch.setattr(
        providers_module.ProviderRegistry, "create", staticmethod(fallback_mock_create)
    )

    config = ArenaConfig(
        rounds=1,
        max_guesses=10,
        defender_config=RoleConfig(provider="mock"),
        attacker_config=RoleConfig(provider="rule_based"),
    )
    engine = build_arena_engine(config)
    assert not isinstance(engine, PreflightFailure)
    result = engine.run()
    round_result = result.rounds[0]

    assert round_result.defender_usage is not None
    assert round_result.defender_usage.fallback_used is True
    assert round_result.comparable is False


def test_generator_version_benchmark_regression() -> None:
    # Ensure the benchmark generator produces expected held-out passwords.
    config = ArenaConfig(
        rounds=1, start_difficulty=3, max_guesses=10, seed=42, generator_version="benchmark"
    )
    result = ArenaEngine(config).run()
    # The benchmark template for difficulty 3 should be eval-substitution
    # using HELD_OUT_WORDS. Let's just verify it uses 'eval-substitution' family.
    assert result.rounds[0].defender_strategy == "eval-substitution"
    # Also verify the attacker fails since it's a held-out vocabulary and different template
    assert not result.rounds[0].attack.solved
