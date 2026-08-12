import sys
import json
import datetime
from pathlib import Path

from password_arena.engine import build_arena_engine
from password_arena.models import RoleConfig, ArenaConfig, MatchupConfig
from password_arena.reporting import tournament_report_markdown
from password_arena.dataset_export import (
    generate_dataset_card,
    build_public_benchmark_dataset,
    export_public_dataset_jsonl,
    export_public_dataset_csv,
    PublicBenchmarkSource,
)
from password_arena.tournament_history import MatchupResult


def run_experiment_c():
    output_dir_name = "benchmark-006"
    title = "Experiment C (Cross-Run Accumulated Knowledge)"
    
    seeds = (42, 43, 44)
    rounds = 5
    max_guesses = 500
    num_campaigns = 4
    
    attacker = RoleConfig(provider="ollama", model="qwen3:4b", thinking_level="auto")
    defender = RoleConfig(provider="ollama", model="qwen3:4b", thinking_level="auto")
    
    matchups = []
    
    # We create a MatchupResult for the entire benchmark, containing all experiments across seeds and campaigns
    all_experiments = []
    
    for seed in seeds:
        print(f"\n--- Starting Seed {seed} ---")
        
        current_attacker_obs = None
        current_defender_obs = None
        
        for campaign_idx in range(num_campaigns):
            print(f"Running {title} - Seed {seed} - Campaign {campaign_idx + 1}/{num_campaigns}")
            
            arena_config = ArenaConfig(
                rounds=rounds,
                start_difficulty=1,
                difficulty_step=1,
                max_guesses=max_guesses,
                max_wall_time_s=600,
                max_tokens=None,
                max_api_cost=None,
                max_retries=3,
                seed=seed,
                reveal_passwords=False,
                defender_config=defender,
                attacker_config=attacker,
                generator_mode="deterministic-test",
                generator_version="benchmark",
                information_policy_id="mutual_bounded",
                information_policy_version="1.0",
                campaign_id=f"camp_{campaign_idx+1}",
                replication_id="exp_c",
                prior_campaign_count=campaign_idx,
                cross_run_knowledge_policy="mutual_bounded",
                cross_run_knowledge_version="1.0",
                initial_attacker_observations=tuple(current_attacker_obs) if current_attacker_obs else None,
                initial_defender_observations=tuple(current_defender_obs) if current_defender_obs else None,
            )
            
            engine = build_arena_engine(arena_config)
            experiment_result = engine.run()
            all_experiments.append(experiment_result)
            
            # Extract memory for next campaign
            current_attacker_obs = engine.attacker.observations
            current_defender_obs = engine.defender.observations
            
    # Dummy matchup config to hold the results for reporting
    m_config = MatchupConfig(
        attacker=attacker,
        defender=defender,
        rounds=rounds,
        seeds=seeds,
        generator_mode="deterministic-test",
        generator_version="benchmark",
        max_guesses=max_guesses,
        information_policy_id="mutual_bounded",
    )
    
    from password_arena.tournament import aggregate_matchup
    
    m_result = aggregate_matchup(m_config, all_experiments, [])
    
    from password_arena.models import TournamentConfig
    t_config = TournamentConfig(
        attackers=(attacker,),
        defenders=(defender,),
        seeds=seeds,
        rounds_per_match=rounds,
        max_guesses=max_guesses,
        generator_mode="deterministic-test",
        generator_version="benchmark",
    )
    
    out_dir = Path(f"results/{output_dir_name}")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    report_md = tournament_report_markdown(
        tournament_id="local",
        timestamp=datetime.datetime.now().isoformat(),
        config=t_config,
        matchups=[m_result]
    )
    (out_dir / "benchmark-summary.md").write_text(report_md, encoding="utf-8")
    
    sources = [PublicBenchmarkSource(matchup=m_result, experiments=m_result.experiments)]
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
    
    print(f"\nDone. Results saved to {out_dir}")

if __name__ == "__main__":
    run_experiment_c()
