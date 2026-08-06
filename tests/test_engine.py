from password_arena import ArenaConfig, ArenaEngine


def test_engine_runs_requested_rounds() -> None:
    result = ArenaEngine(ArenaConfig(rounds=4, max_guesses=100)).run()
    assert len(result.rounds) == 4
    assert result.rounds[0].round_number == 1
    assert result.rounds[-1].round_number == 4


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
    result = ArenaEngine(
        ArenaConfig(rounds=4, max_guesses=5_000, reveal_passwords=True)
    ).run()
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
            "family": "mocked-family",
            "note": "mocked note"
        }
    )
    attacker_backend = MockProvider(
        capabilities=capabilities,
        canned_structured_data={
            "weights": {"common": 0.5, "random": 0.5},
            "reasoning": "mocked reasoning"
        }
    )
    result = ArenaEngine(
        ArenaConfig(rounds=1, max_guesses=10),
        defender_backend=defender_backend,
        attacker_backend=attacker_backend,
    ).run()
    
    assert result.rounds[0].defender_strategy == "mocked-family"
    
    plan = result.rounds[0].attack.plan
    assert any(p.strategy == "common" and p.weight == 0.5 for p in plan)

