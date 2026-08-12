"""Benchmark 008 artifact builder: loads raw checkpoint JSON, reconstructs
MatchupResult/ExperimentResult objects, computes the metrics requested for
the report (including ones MatchupSummary doesn't track natively -- min/
median/max entropy, weak-target survivals, calibration warnings, strategy
distributions -- straight from recorded round-level data, never invented),
and writes results/benchmark-008/{public-dataset.csv,public-dataset.jsonl,
DATASET_CARD.md} plus a computed-metrics JSON used to hand-write README.md /
model-comparison.md. Scratch/one-off per repo convention (see run_export.py).
"""

import dataclasses
import json
import statistics
from pathlib import Path

from password_arena.dataset_export import (
    PublicBenchmarkSource,
    build_public_benchmark_dataset,
    export_public_dataset_csv,
    export_public_dataset_jsonl,
    generate_dataset_card,
)
from password_arena.models import (
    ArenaConfig,
    AttackResult,
    ExclusionRecord,
    ExperimentResult,
    MatchupConfig,
    MatchupResult,
    MatchupSummary,
    ReplayMetadata,
    RoleConfig,
    RoleMetadata,
    RoleUsage,
    RoundResult,
    StrategyBudget,
    StrengthReport,
    ThinkingLevel,
)

RAW_DIR = Path("results/benchmark-008/raw")
OUT_DIR = Path("results/benchmark-008")

MAIN_SCENARIOS = [
    "frozen",
    "mutual_bounded",
    "mutual_full",
    "normal_control",
    "attacker_privileged",
    "defender_privileged",
]
MODELS = ["qwen3_4b", "gemma3_4b"]


def _role_config(d):
    return RoleConfig(
        provider=d["provider"],
        model=d["model"],
        thinking_level=ThinkingLevel(d["thinking_level"]),
        temperature=d["temperature"],
        max_tokens=d["max_tokens"],
        local_endpoint=d["local_endpoint"],
    )


def _role_metadata(d):
    if d is None:
        return None
    return RoleMetadata(provider=d["provider"], model=d["model"], thinking_level=ThinkingLevel(d["thinking_level"]))


def _role_usage(d):
    if d is None:
        return None
    return RoleUsage(**d)


def _strength(d):
    return StrengthReport(**d)


def _attack_result(d):
    d = dict(d)
    d["plan"] = tuple(StrategyBudget(**p) for p in d["plan"])
    d["attempted_strategies"] = tuple(d["attempted_strategies"])
    return AttackResult(**d)


def _round_result(d):
    d = dict(d)
    d["strength"] = _strength(d["strength"])
    d["attack"] = _attack_result(d["attack"])
    d["defender_metadata"] = _role_metadata(d["defender_metadata"])
    d["attacker_metadata"] = _role_metadata(d["attacker_metadata"])
    d["evaluator_metadata"] = _role_metadata(d["evaluator_metadata"])
    d["attacker_usage"] = _role_usage(d["attacker_usage"])
    d["defender_usage"] = _role_usage(d["defender_usage"])
    d["attacker_boundary_responses"] = tuple(d["attacker_boundary_responses"])
    d["defender_boundary_responses"] = tuple(d["defender_boundary_responses"])
    return RoundResult(**d)


def _arena_config(d):
    d = dict(d)
    d["defender_config"] = _role_config(d["defender_config"])
    d["attacker_config"] = _role_config(d["attacker_config"])
    d["evaluator_config"] = _role_config(d["evaluator_config"])
    d["initial_attacker_observations"] = None
    d["initial_defender_observations"] = None
    return ArenaConfig(**d)


def _experiment_result(d):
    return ExperimentResult(
        config=_arena_config(d["config"]),
        rounds=tuple(_round_result(r) for r in d["rounds"]),
        experiment_id=d["experiment_id"],
        timestamp=d["timestamp"],
        interruption_reason=d["interruption_reason"],
        interruption_state=d["interruption_state"],
        events=(),
    )


def _matchup_config(d):
    d = dict(d)
    d["attacker"] = _role_config(d["attacker"])
    d["defender"] = _role_config(d["defender"])
    d["seeds"] = tuple(d["seeds"])
    return MatchupConfig(**d)


def _exclusion_record(d):
    return ExclusionRecord(seed=d["seed"], experiment_id=d["experiment_id"], round_number=d["round_number"], reason=d["reason"])


def _replay(d):
    if d is None:
        return None
    d = dict(d)
    d["attacker"] = _role_metadata(d["attacker"])
    d["defender"] = _role_metadata(d["defender"])
    d["seeds"] = tuple(d["seeds"])
    return ReplayMetadata(**d)


def load_matchup(path: Path) -> MatchupResult:
    d = json.loads(path.read_text())
    return MatchupResult(
        matchup_id=d["matchup_id"],
        config=_matchup_config(d["config"]),
        experiments=tuple(_experiment_result(e) for e in d["experiments"]),
        summary=MatchupSummary(**d["summary"]),
        is_comparable=d["is_comparable"],
        non_comparable_reason=d["non_comparable_reason"],
        excluded_trial_records=tuple(_exclusion_record(r) for r in d["excluded_trial_records"]),
        excluded_round_records=tuple(_exclusion_record(r) for r in d["excluded_round_records"]),
        replay=_replay(d["replay"]),
    )


def comparable_rounds(matchup: MatchupResult):
    for exp in matchup.experiments:
        for r in exp.rounds:
            if r.comparable:
                yield r


def compute_extra_metrics(matchup: MatchupResult) -> dict:
    rounds = list(comparable_rounds(matchup))
    entropies = [r.strength.entropy_bits for r in rounds]
    calibration_warnings = [r.calibration_warning for r in rounds if r.calibration_warning]
    weak_target_survivals = sum(
        1 for r in rounds if r.calibration_warning == "VERY_SHORT_TARGET_SURVIVED" and not r.attack.solved
    )
    defender_family_dist: dict[str, int] = {}
    for r in rounds:
        defender_family_dist[r.defender_strategy] = defender_family_dist.get(r.defender_strategy, 0) + 1
    attacker_strategy_dist: dict[str, int] = {}
    for r in rounds:
        for s in r.attack.attempted_strategies:
            attacker_strategy_dist[s] = attacker_strategy_dist.get(s, 0) + 1

    return {
        "min_entropy_bits": min(entropies) if entropies else None,
        "median_entropy_bits": statistics.median(entropies) if entropies else None,
        "mean_entropy_bits": statistics.mean(entropies) if entropies else None,
        "max_entropy_bits": max(entropies) if entropies else None,
        "weak_target_survivals": weak_target_survivals,
        "calibration_warning_count": len(calibration_warnings),
        "defender_family_distribution": defender_family_dist,
        "attacker_strategy_distribution": attacker_strategy_dist,
        "trials_total": matchup.summary.trials,
        "trials_excluded": matchup.summary.excluded_trials,
    }


def main():
    computed = {"models": {}, "pilot": {}}

    for model in MODELS:
        computed["models"][model] = {}
        for scenario in MAIN_SCENARIOS:
            path = RAW_DIR / f"{model}__{scenario}.json"
            matchup = load_matchup(path)
            summary_dict = dataclasses.asdict(matchup.summary)
            efficiency_dict = summary_dict.pop("efficiency")
            entry = {
                "summary": summary_dict,
                "efficiency": efficiency_dict,
                "is_comparable": matchup.is_comparable,
                "excluded_trial_records": [
                    {"seed": e.seed, "reason": str(e.reason)} for e in matchup.excluded_trial_records
                ],
                **compute_extra_metrics(matchup),
            }
            computed["models"][model][scenario] = entry

    for name in ["qwen_attacks_gemma", "gemma_attacks_qwen"]:
        path = RAW_DIR / f"pilot__{name}.json"
        if path.exists():
            matchup = load_matchup(path)
            summary_dict = dataclasses.asdict(matchup.summary)
            efficiency_dict = summary_dict.pop("efficiency")
            computed["pilot"][name] = {
                "summary": summary_dict,
                "efficiency": efficiency_dict,
                **compute_extra_metrics(matchup),
            }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "computed_metrics.json", "w") as f:
        json.dump(computed, f, indent=2, default=str)
    print(f"Wrote {OUT_DIR / 'computed_metrics.json'}")

    # Public dataset export: all 12 main matchups + pilot matchups, one dataset.
    sources = []
    for model in MODELS:
        for scenario in MAIN_SCENARIOS:
            matchup = load_matchup(RAW_DIR / f"{model}__{scenario}.json")
            sources.append(PublicBenchmarkSource(matchup=matchup, experiments=matchup.experiments))
    for name in ["qwen_attacks_gemma", "gemma_attacks_qwen"]:
        path = RAW_DIR / f"pilot__{name}.json"
        if path.exists():
            matchup = load_matchup(path)
            sources.append(PublicBenchmarkSource(matchup=matchup, experiments=matchup.experiments))

    tournament_id = "benchmark-008"
    from datetime import datetime, timezone

    timestamp = datetime.now(timezone.utc).isoformat()
    dataset = build_public_benchmark_dataset(tournament_id, timestamp, sources)

    with open(OUT_DIR / "public-dataset.csv", "w") as f:
        f.write(export_public_dataset_csv(dataset))
    with open(OUT_DIR / "public-dataset.jsonl", "w") as f:
        f.write(export_public_dataset_jsonl(dataset))
    with open(OUT_DIR / "DATASET_CARD.md", "w") as f:
        f.write(generate_dataset_card(dataset))

    print("Wrote public-dataset.csv, public-dataset.jsonl, DATASET_CARD.md")
    print(f"Dataset summary: total={dataset.summary.total_rows} comparable={dataset.summary.comparable_rows} excluded={dataset.summary.excluded_rows}")


if __name__ == "__main__":
    main()
