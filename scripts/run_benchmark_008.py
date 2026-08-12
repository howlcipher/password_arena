"""Benchmark 008 runner: matched Qwen3 4B vs Gemma 3 4B self-vs-self comparison.

Modeled directly on scripts/run_experiments.py (Benchmark 007). Runs the same
six-scenario compact matrix for each model, under identical current-generation
code/protocol/prompts/seeds/budgets (IMP-037). Model identity never affects
benchmark behavior -- only the `model` string passed into RoleConfig changes.

Checkpointed per (model, scenario): a completed matchup is written to
results/benchmark-008/raw/<model>__<scenario>.json and skipped on rerun, so an
interrupted run (rate limit, crash, container restart) can resume without
re-running already-completed live-inference work.
"""

import dataclasses
import json
from pathlib import Path

from password_arena.models import RoleConfig, TournamentConfig
from password_arena.tournament import build_tournament_matrix, run_matchup

MODELS = ["qwen3:4b", "gemma3:4b"]

# (scenario name, information_policy_id, privilege_mode)
SCENARIOS = [
    ("frozen", "frozen", "normal_control"),
    ("mutual_bounded", "mutual_bounded", "normal_control"),
    ("mutual_full", "mutual_full", "normal_control"),
    ("normal_control", "legacy_current", "normal_control"),
    ("attacker_privileged", "legacy_current", "attacker_privileged"),
    ("defender_privileged", "legacy_current", "defender_privileged"),
]

SEEDS = (42, 43, 44)
ROUNDS_PER_MATCH = 5
MAX_GUESSES = 500

OUT_DIR = Path("results/benchmark-008/raw")


def checkpoint_path(model: str, scenario_name: str) -> Path:
    safe_model = model.replace(":", "_")
    return OUT_DIR / f"{safe_model}__{scenario_name}.json"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for model in MODELS:
        print(f"=== Model: {model} ===")
        attacker = RoleConfig(provider="ollama", model=model)
        defender = RoleConfig(provider="ollama", model=model)

        for scenario_name, information_policy_id, privilege_mode in SCENARIOS:
            out_path = checkpoint_path(model, scenario_name)
            if out_path.exists():
                print(f"  [skip] {scenario_name} (checkpoint exists)")
                continue

            print(f"  Running scenario: {scenario_name}")
            config = TournamentConfig(
                attackers=[attacker],
                defenders=[defender],
                rounds_per_match=ROUNDS_PER_MATCH,
                seeds=SEEDS,
                generator_mode="deterministic-test",
                generator_version="benchmark",
                max_guesses=MAX_GUESSES,
            )

            matrix = build_tournament_matrix(config)
            matchup_config = matrix[0]
            # build_tournament_matrix does not propagate information_policy_id /
            # privilege_mode from TournamentConfig onto MatchupConfig (same gap
            # scripts/run_experiments.py already works around for Benchmark 007).
            object.__setattr__(matchup_config, "information_policy_id", information_policy_id)
            object.__setattr__(matchup_config, "privilege_mode", privilege_mode)

            result = run_matchup(matchup_config)
            print(
                f"    solve_rate={result.summary.solve_rate} "
                f"rounds_completed={result.summary.rounds_completed}"
            )

            with open(out_path, "w") as f:
                json.dump(dataclasses.asdict(result), f, indent=2, default=str)

    print(f"Finished. Raw results in {OUT_DIR}/")


if __name__ == "__main__":
    main()
