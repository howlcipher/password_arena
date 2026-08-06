import pytest

from password_arena.models import ArenaConfig


@pytest.mark.parametrize(
    "config",
    [
        ArenaConfig(rounds=0),
        ArenaConfig(start_difficulty=11),
        ArenaConfig(difficulty_step=6),
        ArenaConfig(max_guesses=0),
    ],
)
def test_invalid_config_is_rejected(config: ArenaConfig) -> None:
    with pytest.raises(ValueError):
        config.validate()
