"""Benchmark 008 optional cross-model pilot (exploratory, not headline).

qwen3:4b attacker vs gemma3:4b defender, and the reverse, normal_control only.
Run only after both self-vs-self matrices complete (they did). 30 rounds total.
Scratch/one-off per repo convention.
"""

import dataclasses
import json
from pathlib import Path

from password_arena.models import RoleConfig, TournamentConfig
from password_arena.tournament import build_tournament_matrix, run_matchup

SEEDS = (42, 43, 44)
ROUNDS_PER_MATCH = 5
MAX_GUESSES = 500

OUT_DIR = Path("results/benchmark-008/raw")

DIRECTIONS = [
    ("qwen_attacks_gemma", "qwen3:4b", "gemma3:4b"),
    ("gemma_attacks_qwen", "gemma3:4b", "qwen3:4b"),
]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for name, attacker_model, defender_model in DIRECTIONS:
        out_path = OUT_DIR / f"pilot__{name}.json"
        if out_path.exists():
            print(f"[skip] {name} (checkpoint exists)")
            continue

        print(f"Running pilot: {name} (attacker={attacker_model}, defender={defender_model})")
        config = TournamentConfig(
            attackers=[RoleConfig(provider="ollama", model=attacker_model)],
            defenders=[RoleConfig(provider="ollama", model=defender_model)],
            rounds_per_match=ROUNDS_PER_MATCH,
            seeds=SEEDS,
            generator_mode="deterministic-test",
            generator_version="benchmark",
            max_guesses=MAX_GUESSES,
        )
        matrix = build_tournament_matrix(config)
        matchup_config = matrix[0]
        object.__setattr__(matchup_config, "information_policy_id", "legacy_current")
        object.__setattr__(matchup_config, "privilege_mode", "normal_control")

        result = run_matchup(matchup_config)
        print(
            f"  solve_rate={result.summary.solve_rate} "
            f"rounds_completed={result.summary.rounds_completed}"
        )

        with open(out_path, "w") as f:
            json.dump(dataclasses.asdict(result), f, indent=2, default=str)

    print("Pilot finished.")


if __name__ == "__main__":
    main()
