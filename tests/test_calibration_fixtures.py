import random

from password_arena.attacker import AdaptiveAttacker


def test_exhaustive_short_strategy_solves_length_2_target() -> None:
    # A generic target of length 2
    target = "z9"
    attacker = AdaptiveAttacker(random.Random())
    # It should solve it in fewer than 100,000 guesses, easily
    result = attacker.attack(target, difficulty=1, max_guesses=100000)
    assert result.solved
    assert result.candidate == target
