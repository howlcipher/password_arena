import sys
import json
from pathlib import Path

from password_arena.models import RoleConfig, TournamentConfig, MatchupConfig
from password_arena.tournament import run_matchup
from password_arena.tournament_history import TournamentHistoryManager
from password_arena.reporting import tournament_report_markdown
from password_arena.dataset_export import (
    generate_dataset_card,
    build_public_benchmark_dataset,
    export_public_dataset_jsonl,
    export_public_dataset_csv,
    PublicBenchmarkSource,
)

def run_experiment(title, policies, output_dir_name):
    manager = TournamentHistoryManager()
    
    matchups = []
    
    seeds = (42, 43, 44)
    rounds = 5
    max_guesses = 500
    
    attacker = RoleConfig(provider="ollama", model="qwen3:4b", thinking_level="auto")
    defender = RoleConfig(provider="ollama", model="qwen3:4b", thinking_level="auto")
    
    config = TournamentConfig(
        attackers=(attacker,),
        defenders=(defender,),
        seeds=seeds,
        rounds_per_match=rounds,
        max_guesses=max_guesses,
        generator_mode="deterministic-test",
        generator_version="benchmark",
    )
    
    for policy in policies:
        print(f"\nRunning {title} - Policy: {policy}")
        m_config = MatchupConfig(
            attacker=attacker,
            defender=defender,
            rounds=rounds,
            seeds=seeds,
            generator_mode="deterministic-test",
            generator_version="benchmark",
            max_guesses=max_guesses,
            information_policy_id=policy,
        )
        
        result = run_matchup(m_config)
        matchups.append(result)
        
    out_dir = Path(f"results/{output_dir_name}")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    import datetime
    report_md = tournament_report_markdown(
        tournament_id="local",
        timestamp=datetime.datetime.now().isoformat(),
        config=config, 
        matchups=matchups
    )
    (out_dir / "benchmark-summary.md").write_text(report_md, encoding="utf-8")
    
    import datetime
    sources = [PublicBenchmarkSource(matchup=m, experiments=m.experiments) for m in matchups]
    dataset = build_public_benchmark_dataset(
        tournament_id="local",
        tournament_timestamp=datetime.datetime.now().isoformat(),
        sources=sources,
    )
    if dataset:
        (out_dir / "public-dataset.jsonl").write_text(export_public_dataset_jsonl(dataset), encoding="utf-8")
        (out_dir / "public-dataset.csv").write_text(export_public_dataset_csv(dataset), encoding="utf-8")
        
        card = generate_dataset_card(dataset)
        (out_dir / "DATASET_CARD.md").write_text(card, encoding="utf-8")

if __name__ == "__main__":
    policies = [
        "frozen",
        "self_only",
        "attacker_observes_defender",
        "defender_observes_attacker",
        "mutual_bounded",
        "mutual_full",
        "legacy_current",
    ]
    run_experiment("Experiment A (Primary)", policies, "benchmark-004")
    run_experiment("Experiment B (Replication)", policies, "benchmark-005")
