import os

from password_arena.dataset_export import (
    PublicBenchmarkSource,
    build_public_benchmark_dataset,
    export_public_dataset_csv,
    export_public_dataset_jsonl,
    generate_dataset_card,
)
from password_arena.history import HistoryManager
from password_arena.reporting import tournament_report_markdown
from password_arena.tournament_history import TournamentHistoryManager


def run_export():
    manager = TournamentHistoryManager()
    h_manager = HistoryManager()
    t_id = "8462ce2fb17b475b9e2dca7c5c7b96a9"
    t_stored = manager.load(t_id, h_manager)

    # Export results
    output_dir = "results/benchmark-003"
    os.makedirs(output_dir, exist_ok=True)

    # Markdown
    md_path = os.path.join(output_dir, "README.md")
    with open(md_path, "w") as f:
        f.write(
            tournament_report_markdown(t_id, t_stored.timestamp, t_stored.config, t_stored.matchups)
        )

    # Dataset
    sources = []
    for m in t_stored.matchups:
        experiments = tuple(h_manager.load(eid) for eid in m.experiment_ids)
        sources.append(PublicBenchmarkSource(matchup=m, experiments=experiments))
    dataset = build_public_benchmark_dataset(t_id, t_stored.timestamp, sources)

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
    run_export()
