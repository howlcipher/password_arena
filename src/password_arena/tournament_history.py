from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from password_arena.history import HistoryManager
from password_arena.models import (
    EfficiencyMetrics,
    ExclusionReason,
    ExclusionRecord,
    ExperimentResult,
    MatchupConfig,
    MatchupResult,
    MatchupSummary,
    ReplayMetadata,
    RoleConfig,
    RoleMetadata,
    TournamentConfig,
)
from password_arena.providers import ThinkingLevel

# 2.1 adds replay/excluded_trial_records/excluded_round_records to
# StoredMatchup. 2.2 adds the optional defender entropy-trajectory summary
# fields. `_stored_matchup_from_dict` defaults both additions so older saved
# tournaments remain loadable.
TOURNAMENT_SCHEMA_VERSION = "2.2"


@dataclass(frozen=True, slots=True)
class StoredMatchup:
    """A matchup as reconstructed from disk. Full ExperimentResult data is not
    embedded -- only the linking `experiment_ids` (see `hydrate_experiments`)."""

    matchup_id: str
    config: MatchupConfig
    summary: MatchupSummary
    is_comparable: bool
    non_comparable_reason: str | None
    experiment_ids: tuple[str, ...]
    replay: ReplayMetadata | None = None
    excluded_trial_records: tuple[ExclusionRecord, ...] = ()
    excluded_round_records: tuple[ExclusionRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class StoredTournament:
    tournament_id: str
    timestamp: str
    schema_version: str
    config: TournamentConfig
    matchups: tuple[StoredMatchup, ...]
    missing_experiment_ids: tuple[str, ...] = ()


def _role_config_from_dict(d: dict[str, Any] | None) -> RoleConfig:
    d = d or {}
    # ThinkingLevel is a StrEnum, so `asdict()` -> `json.dumps()` serializes it
    # as a plain string; without re-wrapping it here, thinking_level would
    # deserialize as a bare `str` instead of a `ThinkingLevel` member, and any
    # later `.thinking_level.value` access (leaderboards, heatmap, comparison)
    # would raise AttributeError for every tournament loaded from disk.
    return RoleConfig(
        provider=d.get("provider", "rule_based"),
        model=d.get("model"),
        thinking_level=ThinkingLevel(d.get("thinking_level", ThinkingLevel.AUTO)),
        temperature=d.get("temperature"),
        max_tokens=d.get("max_tokens"),
        local_endpoint=d.get("local_endpoint"),
    )


def _matchup_config_from_dict(d: dict[str, Any]) -> MatchupConfig:
    return MatchupConfig(
        attacker=_role_config_from_dict(d.get("attacker")),
        defender=_role_config_from_dict(d.get("defender")),
        rounds=d.get("rounds", 0),
        seeds=tuple(d.get("seeds", ())),
        generator_version=d.get("generator_version", "benchmark"),
        generator_mode=d.get("generator_mode", "deterministic-test"),
        max_guesses=d.get("max_guesses", 5000),
        max_wall_time_s=d.get("max_wall_time_s"),
        max_tokens=d.get("max_tokens"),
        max_api_cost=d.get("max_api_cost"),
        max_retries=d.get("max_retries"),
    )


def _tournament_config_from_dict(d: dict[str, Any]) -> TournamentConfig:
    return TournamentConfig(
        attackers=tuple(_role_config_from_dict(x) for x in d.get("attackers", ())),
        defenders=tuple(_role_config_from_dict(x) for x in d.get("defenders", ())),
        seeds=tuple(d.get("seeds", ())),
        rounds_per_match=d.get("rounds_per_match", 0),
        generator_version=d.get("generator_version", "benchmark"),
        generator_mode=d.get("generator_mode", "deterministic-test"),
        max_guesses=d.get("max_guesses", 5000),
        max_wall_time_s=d.get("max_wall_time_s"),
        max_tokens=d.get("max_tokens"),
        max_api_cost=d.get("max_api_cost"),
        max_retries=d.get("max_retries"),
    )


def _efficiency_from_dict(d: dict[str, Any] | None) -> EfficiencyMetrics:
    d = d or {}
    return EfficiencyMetrics(
        attacker_solved_per_1k_tokens=d.get("attacker_solved_per_1k_tokens"),
        attacker_solved_per_second=d.get("attacker_solved_per_second"),
        attacker_solved_per_dollar=d.get("attacker_solved_per_dollar"),
        defender_survived_per_1k_tokens=d.get("defender_survived_per_1k_tokens"),
        defender_survived_per_dollar=d.get("defender_survived_per_dollar"),
        defender_entropy_gain_per_1k_tokens=d.get("defender_entropy_gain_per_1k_tokens"),
    )


def _matchup_summary_from_dict(d: dict[str, Any]) -> MatchupSummary:
    """Reconstruct a MatchupSummary, tolerating JSON saved by the pre-rewrite
    tournament code (schema_version < "2.0"), which used a narrower field set:
    trials/completed_trials/interrupted_trials/attacker_wins/defender_survives/
    mean_guesses/median_guesses/std_guesses/mean_latency_ms/total_tokens/
    total_estimated_cost/confidence_interval_lower/confidence_interval_upper.
    """
    return MatchupSummary(
        trials=d.get("trials", 0),
        comparable_trials=d.get("comparable_trials", d.get("completed_trials", 0)),
        excluded_trials=d.get("excluded_trials", d.get("interrupted_trials", 0)),
        excluded_rounds=d.get("excluded_rounds", 0),
        rounds_completed=d.get("rounds_completed", d.get("completed_trials", 0)),
        rounds_solved=d.get("rounds_solved", d.get("attacker_wins", 0)),
        rounds_resisted=d.get("rounds_resisted", d.get("defender_survives", 0)),
        solve_rate=d.get("solve_rate"),
        survival_rate=d.get("survival_rate"),
        confidence_interval_lower=d.get("confidence_interval_lower"),
        confidence_interval_upper=d.get("confidence_interval_upper"),
        final_round_solved_count=d.get("final_round_solved_count", d.get("attacker_wins", 0)),
        final_round_resisted_count=d.get(
            "final_round_resisted_count", d.get("defender_survives", 0)
        ),
        mean_guesses_per_round=d.get("mean_guesses_per_round", d.get("mean_guesses")),
        median_guesses_per_round=d.get("median_guesses_per_round", d.get("median_guesses")),
        std_guesses_per_round=d.get("std_guesses_per_round", d.get("std_guesses")),
        mean_guesses_to_solve=d.get("mean_guesses_to_solve"),
        median_guesses_to_solve=d.get("median_guesses_to_solve"),
        mean_total_guesses_per_trial=d.get("mean_total_guesses_per_trial"),
        attacker_input_tokens=d.get("attacker_input_tokens", 0),
        attacker_output_tokens=d.get("attacker_output_tokens", 0),
        attacker_reasoning_tokens=d.get("attacker_reasoning_tokens"),
        defender_input_tokens=d.get("defender_input_tokens", 0),
        defender_output_tokens=d.get("defender_output_tokens", 0),
        defender_reasoning_tokens=d.get("defender_reasoning_tokens"),
        attacker_mean_latency_ms=d.get("attacker_mean_latency_ms"),
        defender_mean_latency_ms=d.get("defender_mean_latency_ms"),
        total_estimated_cost=d.get("total_estimated_cost"),
        attacker_estimated_cost=d.get("attacker_estimated_cost"),
        defender_estimated_cost=d.get("defender_estimated_cost"),
        entropy_gain_trials=d.get("entropy_gain_trials", 0),
        mean_initial_entropy_bits=d.get("mean_initial_entropy_bits"),
        mean_final_entropy_bits=d.get("mean_final_entropy_bits"),
        mean_entropy_gain_bits=d.get("mean_entropy_gain_bits"),
        defender_entropy_gain_tokens=d.get("defender_entropy_gain_tokens"),
        efficiency=_efficiency_from_dict(d.get("efficiency")),
    )


def _role_metadata_from_dict(d: dict[str, Any] | None) -> RoleMetadata:
    d = d or {}
    return RoleMetadata(
        provider=d.get("provider", "rule_based"),
        model=d.get("model"),
        thinking_level=ThinkingLevel(d.get("thinking_level", ThinkingLevel.AUTO)),
    )


def _replay_metadata_from_dict(d: dict[str, Any] | None) -> ReplayMetadata | None:
    if not d:
        return None
    return ReplayMetadata(
        attacker=_role_metadata_from_dict(d.get("attacker")),
        defender=_role_metadata_from_dict(d.get("defender")),
        seeds=tuple(d.get("seeds", ())),
        rounds_per_match=d.get("rounds_per_match", 0),
        max_guesses=d.get("max_guesses", 0),
        generator_mode=d.get("generator_mode", "deterministic-test"),
        generator_version=d.get("generator_version", "benchmark"),
        application_version=d.get("application_version", ""),
        schema_version=d.get("schema_version", ""),
        deterministic=d.get("deterministic", False),
        attacker_prompt_version=d.get("attacker_prompt_version", ""),
        defender_prompt_version=d.get("defender_prompt_version", ""),
        capability_registry_version=d.get("capability_registry_version", ""),
    )


def _exclusion_record_from_dict(d: dict[str, Any]) -> ExclusionRecord:
    return ExclusionRecord(
        seed=d.get("seed", 0),
        experiment_id=d.get("experiment_id"),
        round_number=d.get("round_number"),
        reason=ExclusionReason(d.get("reason", ExclusionReason.UNSUPPORTED_CONFIGURATION)),
    )


def _stored_matchup_from_dict(d: dict[str, Any]) -> StoredMatchup:
    return StoredMatchup(
        matchup_id=d.get("matchup_id", ""),
        config=_matchup_config_from_dict(d.get("config", {})),
        summary=_matchup_summary_from_dict(d.get("summary", {})),
        is_comparable=d.get("is_comparable", True),
        non_comparable_reason=d.get("non_comparable_reason"),
        experiment_ids=tuple(d.get("experiment_ids", ())),
        # Absent on tournaments saved before schema 2.1 -- default to "no
        # replay metadata"/"no recorded exclusions" rather than raising, same
        # backward-compat tolerance as _matchup_summary_from_dict.
        replay=_replay_metadata_from_dict(d.get("replay")),
        excluded_trial_records=tuple(
            _exclusion_record_from_dict(r) for r in d.get("excluded_trial_records", ())
        ),
        excluded_round_records=tuple(
            _exclusion_record_from_dict(r) for r in d.get("excluded_round_records", ())
        ),
    )


def _parse_stored_tournament(
    data: dict[str, Any], history_mgr: HistoryManager
) -> StoredTournament:
    matchups = tuple(_stored_matchup_from_dict(m) for m in data.get("matchups", []))
    missing: list[str] = []
    for m in matchups:
        for experiment_id in m.experiment_ids:
            if not (history_mgr.storage_dir / f"{experiment_id}.json").exists():
                missing.append(experiment_id)
    return StoredTournament(
        tournament_id=data.get("tournament_id", ""),
        timestamp=data.get("timestamp", ""),
        schema_version=data.get("schema_version", "1.0"),
        config=_tournament_config_from_dict(data.get("config", {})),
        matchups=matchups,
        missing_experiment_ids=tuple(missing),
    )


class TournamentHistoryManager:
    def __init__(self, storage_dir: str | Path = ".password_arena_tournaments"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, config: TournamentConfig, matchups: list[MatchupResult]) -> tuple[str, str]:
        """Persist matchup metadata and links to full experiments in single-run
        history (see HistoryManager). Returns (tournament_id, timestamp)."""
        tournament_id = uuid.uuid4().hex
        timestamp = datetime.now(UTC).isoformat()

        matchup_data = []
        for m in matchups:
            m_dict = {
                "matchup_id": m.matchup_id,
                "config": asdict(m.config),
                "summary": asdict(m.summary),
                "is_comparable": m.is_comparable,
                "non_comparable_reason": m.non_comparable_reason,
                "experiment_ids": [exp.experiment_id for exp in m.experiments],
                "replay": asdict(m.replay) if m.replay else None,
                "excluded_trial_records": [asdict(r) for r in m.excluded_trial_records],
                "excluded_round_records": [asdict(r) for r in m.excluded_round_records],
            }
            matchup_data.append(m_dict)

        data = {
            "tournament_id": tournament_id,
            "timestamp": timestamp,
            "schema_version": TOURNAMENT_SCHEMA_VERSION,
            "config": asdict(config),
            "matchups": matchup_data,
        }

        file_path = self.storage_dir / f"{tournament_id}.json"
        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return tournament_id, timestamp

    def list_runs(self) -> list[dict[str, Any]]:
        runs = []
        for file_path in self.storage_dir.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                matchups = data.get("matchups", [])
                runs.append(
                    {
                        "tournament_id": data.get("tournament_id", file_path.stem),
                        "timestamp": data.get("timestamp", ""),
                        "schema_version": data.get("schema_version", "1.0"),
                        "matchup_count": len(matchups),
                    }
                )
            except Exception:
                continue
        runs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return runs

    def load(
        self, tournament_id: str, history_mgr: HistoryManager | None = None
    ) -> StoredTournament:
        file_path = self.storage_dir / f"{tournament_id}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Tournament {tournament_id} not found.")
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return _parse_stored_tournament(data, history_mgr or HistoryManager())

    def delete(self, tournament_id: str) -> None:
        file_path = self.storage_dir / f"{tournament_id}.json"
        if file_path.exists():
            file_path.unlink()
        else:
            raise FileNotFoundError(f"Tournament {tournament_id} not found.")


def hydrate_experiments(
    stored: StoredMatchup, history_mgr: HistoryManager
) -> tuple[tuple[ExperimentResult, ...], tuple[str, ...]]:
    """Load a stored matchup's full experiments from single-run history.

    Returns (experiments, missing_experiment_ids). A linked experiment may have
    been deleted independently via HistoryManager.delete() -- that must not raise
    here, only be reported.
    """
    experiments = []
    missing = []
    for experiment_id in stored.experiment_ids:
        try:
            experiments.append(history_mgr.load(experiment_id))
        except FileNotFoundError:
            missing.append(experiment_id)
    return tuple(experiments), tuple(missing)
