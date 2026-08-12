import dataclasses
import json
from pathlib import Path

from password_arena.models import RoleConfig, TournamentConfig
from password_arena.tournament import build_tournament_matrix, run_matchup


def main():
    scenarios = [
        "normal_control",
        "attacker_privileged",
        "defender_privileged",
        "mutual_privileged",
        "attacker_oracle",
        "information_boundary_challenge",
    ]

    seeds = [42, 100, 2026]
    rounds_per_match = 5

    attacker = RoleConfig(provider="ollama", model="qwen3:4b")
    defender = RoleConfig(provider="ollama", model="qwen3:4b")

    results = {}

    for scenario in scenarios:
        print(f"Running scenario: {scenario}")
        config = TournamentConfig(
            attackers=[attacker],
            defenders=[defender],
            rounds_per_match=rounds_per_match,
            seeds=seeds,
        )

        matrix = build_tournament_matrix(config)
        matchup_config = matrix[0]
        # Inject scenario variables
        object.__setattr__(matchup_config, "privilege_mode", scenario)
        object.__setattr__(matchup_config, "privilege_mode_version", "1.0")

        result = run_matchup(matchup_config)
        print(f"  Completed! Solve rate: {result.summary.solve_rate}")
        results[scenario] = dataclasses.asdict(result)

    out_dir = Path("results/benchmark-privilege")
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"Finished writing to {out_dir}/results.json")


if __name__ == "__main__":
    main()
