import os

from password_arena.dataset_export import (
    PublicBenchmarkSource,
    build_public_benchmark_dataset,
    export_public_dataset_csv,
    export_public_dataset_jsonl,
    generate_dataset_card,
)
from password_arena.history import HistoryManager
from password_arena.models import MatchupConfig, RoleConfig, ThinkingLevel, TournamentConfig
from password_arena.reporting import tournament_report_markdown
from password_arena.tournament import run_matchup
from password_arena.tournament_history import TournamentHistoryManager


def run_benchmark_003():
    print("Starting Benchmark 003...")

    seeds = (42, 43, 44)
    rounds = 5
    max_guesses = 500

    attackers = (
        RoleConfig(provider="ollama", model="qwen3:4b", thinking_level=ThinkingLevel.AUTO),
        RoleConfig(provider="rule_based", model="v1", thinking_level=ThinkingLevel.AUTO),
    )

    defenders = (
        RoleConfig(provider="ollama", model="qwen3:4b", thinking_level=ThinkingLevel.AUTO),
        RoleConfig(provider="rule_based", model="v1", thinking_level=ThinkingLevel.AUTO),
    )

    matchup_configs = [
        MatchupConfig(
            attacker=attackers[0],
            defender=defenders[1],
            seeds=seeds,
            rounds=rounds,
            max_guesses=max_guesses,
            generator_mode="deterministic-test",
            generator_version="benchmark",
        ),
        MatchupConfig(
            attacker=attackers[1],
            defender=defenders[0],
            seeds=seeds,
            rounds=rounds,
            max_guesses=max_guesses,
            generator_mode="deterministic-test",
            generator_version="benchmark",
        ),
        MatchupConfig(
            attacker=attackers[0],
            defender=defenders[0],
            seeds=seeds,
            rounds=rounds,
            max_guesses=max_guesses,
            generator_mode="deterministic-test",
            generator_version="benchmark",
        ),
    ]

    history_mgr = HistoryManager()
    manager = TournamentHistoryManager()

    stored_matchups = []
    for config in matchup_configs:
        print(
            f"Running Matchup: Attacker {config.attacker.provider}/"
            f"{config.attacker.model} vs Defender {config.defender.provider}/"
            f"{config.defender.model}"
        )
        matchup_result = run_matchup(config)

        # Save experiments to disk
        for exp in matchup_result.experiments:
            history_mgr.save(exp)

        stored_matchups.append(matchup_result)
        print(
            f"Finished. Rounds: {matchup_result.summary.rounds_completed}, "
            f"Solved: {matchup_result.summary.rounds_solved}"
        )

    # Create tournament record
    t_config = TournamentConfig(
        attackers=attackers,
        defenders=defenders,
        seeds=seeds,
        rounds_per_match=rounds,
        max_guesses=max_guesses,
        generator_mode="deterministic-test",
        generator_version="benchmark",
    )

    t_id, timestamp = manager.save(t_config, stored_matchups)
    print(f"Saved tournament {t_id}")

    # Export results
    output_dir = "results/benchmark-003"
    os.makedirs(output_dir, exist_ok=True)

    # Markdown
    md_path = os.path.join(output_dir, "README.md")
    with open(md_path, "w") as f:
        f.write(tournament_report_markdown(t_id, timestamp, t_config, stored_matchups))

    # Dataset
    sources = [PublicBenchmarkSource(matchup=m, experiments=m.experiments) for m in stored_matchups]
    dataset = build_public_benchmark_dataset(t_id, timestamp, sources)

    csv_path = os.path.join(output_dir, "benchmark-003.csv")
    with open(csv_path, "w") as f:
        f.write(export_public_dataset_csv(dataset))

    jsonl_path = os.path.join(output_dir, "benchmark-003.jsonl")
    with open(jsonl_path, "w") as f:
        f.write(export_public_dataset_jsonl(dataset))

    card_path = os.path.join(output_dir, "DATASET_CARD.md")
    with open(card_path, "w") as f:
        f.write(generate_dataset_card(dataset))

    print("Done writing exports.")


if __name__ == "__main__":
    run_benchmark_003()
