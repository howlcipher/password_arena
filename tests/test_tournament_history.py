import json
from typing import Any

import pytest

from password_arena.history import HistoryManager
from password_arena.models import MatchupConfig, MatchupResult, RoleConfig, TournamentConfig
from password_arena.tournament import run_matchup
from password_arena.tournament_history import (
    TOURNAMENT_SCHEMA_VERSION,
    TournamentHistoryManager,
    hydrate_experiments,
)


def _config(seeds: tuple[int, ...] = (1, 2)) -> TournamentConfig:
    return TournamentConfig(
        attackers=(RoleConfig(provider="rule_based"),),
        defenders=(RoleConfig(provider="rule_based"),),
        seeds=seeds,
        rounds_per_match=2,
        max_guesses=50,
    )


def _matchup_result(seeds: tuple[int, ...] = (1, 2)) -> MatchupResult:
    config = MatchupConfig(
        attacker=RoleConfig(provider="rule_based"),
        defender=RoleConfig(provider="rule_based"),
        rounds=2,
        seeds=seeds,
        max_guesses=50,
    )
    return run_matchup(config)


def test_save_list_load_delete_round_trip(tmp_path: Any) -> None:
    tourney_mgr = TournamentHistoryManager(storage_dir=tmp_path)
    history_mgr = HistoryManager(storage_dir=tmp_path / "experiments")

    tournament_config = _config()
    matchup = _matchup_result()
    for exp in matchup.experiments:
        history_mgr.save(exp)

    tournament_id, timestamp = tourney_mgr.save(tournament_config, [matchup])

    runs = tourney_mgr.list_runs()
    assert len(runs) == 1
    assert runs[0]["tournament_id"] == tournament_id
    assert runs[0]["timestamp"] == timestamp
    assert runs[0]["schema_version"] == TOURNAMENT_SCHEMA_VERSION
    assert runs[0]["matchup_count"] == 1

    stored = tourney_mgr.load(tournament_id, history_mgr=history_mgr)
    assert stored.tournament_id == tournament_id
    assert stored.schema_version == TOURNAMENT_SCHEMA_VERSION
    assert len(stored.matchups) == 1
    assert stored.matchups[0].summary.comparable_trials == matchup.summary.comparable_trials
    assert stored.missing_experiment_ids == ()

    experiments, missing = hydrate_experiments(stored.matchups[0], history_mgr)
    assert len(experiments) == len(matchup.experiments)
    assert missing == ()

    tourney_mgr.delete(tournament_id)
    assert tourney_mgr.list_runs() == []
    with pytest.raises(FileNotFoundError):
        tourney_mgr.load(tournament_id)


def test_delete_missing_raises(tmp_path: Any) -> None:
    tourney_mgr = TournamentHistoryManager(storage_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        tourney_mgr.delete("does-not-exist")


def test_load_missing_raises(tmp_path: Any) -> None:
    tourney_mgr = TournamentHistoryManager(storage_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        tourney_mgr.load("does-not-exist")


def test_load_tolerates_old_format_missing_new_fields(tmp_path: Any) -> None:
    """Simulates JSON saved by the pre-rewrite tournament code: no schema_version,
    and MatchupSummary using the old, narrower field set."""
    tourney_mgr = TournamentHistoryManager(storage_dir=tmp_path)
    history_mgr = HistoryManager(storage_dir=tmp_path / "experiments")

    old_format = {
        "tournament_id": "legacy-id",
        "timestamp": "2025-01-01T00:00:00+00:00",
        "config": {
            "attackers": [{"provider": "rule_based"}],
            "defenders": [{"provider": "rule_based"}],
            "seeds": [1, 2],
            "rounds_per_match": 2,
        },
        "matchups": [
            {
                "matchup_id": "legacy-matchup",
                "config": {
                    "attacker": {"provider": "rule_based"},
                    "defender": {"provider": "rule_based"},
                    "rounds": 2,
                    "seeds": [1, 2],
                },
                "summary": {
                    "trials": 2,
                    "completed_trials": 2,
                    "interrupted_trials": 0,
                    "attacker_wins": 1,
                    "defender_survives": 1,
                    "solve_rate": 0.5,
                    "mean_guesses": 12.0,
                    "median_guesses": 12.0,
                    "std_guesses": 1.0,
                    "mean_latency_ms": 5.0,
                    "total_tokens": 0,
                    "total_estimated_cost": 0.0,
                    "confidence_interval_lower": 0.1,
                    "confidence_interval_upper": 0.9,
                },
                "is_comparable": True,
                "non_comparable_reason": None,
                "experiment_ids": [],
            }
        ],
    }
    file_path = tmp_path / "legacy-id.json"
    file_path.write_text(json.dumps(old_format), encoding="utf-8")

    runs = tourney_mgr.list_runs()
    assert len(runs) == 1
    assert runs[0]["schema_version"] == "1.0"

    stored = tourney_mgr.load("legacy-id", history_mgr=history_mgr)
    assert stored.schema_version == "1.0"
    assert len(stored.matchups) == 1
    m = stored.matchups[0]
    # Old field names are mapped onto their nearest new-field equivalent.
    assert m.summary.comparable_trials == 2
    assert m.summary.rounds_completed == 2
    assert m.summary.rounds_solved == 1
    assert m.summary.excluded_rounds == 0
    assert m.summary.mean_guesses_per_round == 12.0


def test_hydrate_experiments_skips_dangling_id(tmp_path: Any) -> None:
    history_mgr = HistoryManager(storage_dir=tmp_path / "experiments")
    matchup = _matchup_result(seeds=(1,))
    real_experiment = matchup.experiments[0]
    history_mgr.save(real_experiment)

    from password_arena.tournament_history import StoredMatchup

    stored_matchup = StoredMatchup(
        matchup_id="m1",
        config=matchup.config,
        summary=matchup.summary,
        is_comparable=matchup.is_comparable,
        non_comparable_reason=matchup.non_comparable_reason,
        experiment_ids=(real_experiment.experiment_id, "dangling-id-does-not-exist"),
    )

    experiments, missing = hydrate_experiments(stored_matchup, history_mgr)
    assert len(experiments) == 1
    assert experiments[0].experiment_id == real_experiment.experiment_id
    assert missing == ("dangling-id-does-not-exist",)
