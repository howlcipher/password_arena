from typing import Any

import pytest

from password_arena.history import HistoryManager
from password_arena.models import ArenaConfig, ExperimentResult, RoleConfig
from password_arena.providers import ThinkingLevel


def test_history_manager_save_load_list_delete(tmp_path: Any) -> None:
    hm = HistoryManager(storage_dir=tmp_path)

    config = ArenaConfig(rounds=2)
    exp = ExperimentResult(config=config)

    hm.save(exp)
    runs = hm.list_runs()
    assert len(runs) == 1
    assert runs[0]["experiment_id"] == exp.experiment_id

    loaded = hm.load(exp.experiment_id)
    assert loaded.experiment_id == exp.experiment_id
    assert loaded.config.rounds == 2

    export_path = tmp_path / "exports" / "export.json"
    hm.export(exp.experiment_id, export_path)
    assert export_path.exists()

    hm.delete(exp.experiment_id)
    assert len(hm.list_runs()) == 0
    with pytest.raises(FileNotFoundError):
        hm.load(exp.experiment_id)


def test_loaded_experiment_role_config_thinking_level_is_a_real_enum(tmp_path: Any) -> None:
    """Regression: ThinkingLevel is a StrEnum, so `to_dict()` -> `json.dumps()`
    -> `json.load()` leaves thinking_level as a bare `str`; without
    ExperimentResult.from_dict re-wrapping it, any later
    `.thinking_level.value` access on a loaded experiment's role config would
    raise AttributeError."""
    hm = HistoryManager(storage_dir=tmp_path)

    config = ArenaConfig(
        rounds=1,
        attacker_config=RoleConfig(
            provider="openai", model="gpt-4o", thinking_level=ThinkingLevel.HIGH
        ),
    )
    exp = ExperimentResult(config=config)
    hm.save(exp)

    loaded = hm.load(exp.experiment_id)
    assert isinstance(loaded.config.attacker_config.thinking_level, ThinkingLevel)
    assert loaded.config.attacker_config.thinking_level == ThinkingLevel.HIGH
    assert loaded.config.attacker_config.thinking_level.value == "high"


def test_role_usage_thinking_levels_round_trip_through_history(tmp_path: Any) -> None:
    from password_arena.engine import PreflightFailure, build_arena_engine

    hm = HistoryManager(storage_dir=tmp_path)
    config = ArenaConfig(
        rounds=1,
        max_guesses=10,
        attacker_config=RoleConfig(provider="mock"),
        defender_config=RoleConfig(provider="mock"),
    )
    engine = build_arena_engine(config)
    assert not isinstance(engine, PreflightFailure)
    result = engine.run()
    hm.save(result)

    loaded = hm.load(result.experiment_id)
    attacker_usage = loaded.rounds[0].attacker_usage
    defender_usage = loaded.rounds[0].defender_usage
    assert attacker_usage is not None
    assert defender_usage is not None
    assert attacker_usage.requested_thinking_level == ThinkingLevel.AUTO
    assert attacker_usage.effective_thinking_level == ThinkingLevel.AUTO
    assert defender_usage.requested_thinking_level == ThinkingLevel.AUTO
    assert defender_usage.effective_thinking_level == ThinkingLevel.AUTO
