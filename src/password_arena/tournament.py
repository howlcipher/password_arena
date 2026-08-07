import math
import statistics
import uuid

from password_arena.engine import PreflightFailure, build_arena_engine
from password_arena.models import (
    ArenaConfig,
    ExperimentResult,
    MatchupConfig,
    MatchupResult,
    MatchupSummary,
    TournamentConfig,
)


def calculate_confidence_interval(
    successes: int, trials: int, z: float = 1.96
) -> tuple[float, float]:
    if trials == 0:
        return (0.0, 0.0)
    p = successes / trials
    # Wilson score interval for binomial proportion
    denominator = 1 + z**2 / trials
    center = p + z**2 / (2 * trials)
    spread = z * math.sqrt((p * (1 - p) + z**2 / (4 * trials)) / trials)
    lower = (center - spread) / denominator
    upper = (center + spread) / denominator
    return max(0.0, lower), min(1.0, upper)


def run_matchup(config: MatchupConfig) -> MatchupResult:
    matchup_id = uuid.uuid4().hex
    experiments: list[ExperimentResult] = []

    interrupted_trials = 0
    completed_trials = 0
    attacker_wins = 0
    defender_survives = 0
    total_guesses_list: list[int] = []
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    total_estimated_cost: float = 0.0

    is_comparable = True
    non_comparable_reason = None

    for seed in config.seeds:
        arena_config = ArenaConfig(
            rounds=config.rounds,
            start_difficulty=1,
            difficulty_step=1,
            max_guesses=config.max_guesses,
            max_wall_time_s=config.max_wall_time_s,
            max_tokens=config.max_tokens,
            max_api_cost=config.max_api_cost,
            max_retries=config.max_retries,
            seed=seed,
            reveal_passwords=False,
            defender_config=config.defender,
            attacker_config=config.attacker,
            generator_mode=config.generator_mode,
            generator_version=config.generator_version,
        )

        result_or_failure = build_arena_engine(arena_config)
        if isinstance(result_or_failure, PreflightFailure):
            # Record a failed preflight trial
            is_comparable = False
            non_comparable_reason = f"Preflight failed: {result_or_failure.message}"
            interrupted_trials += 1
            continue

        engine = result_or_failure
        experiment = engine.run()
        experiments.append(experiment)

        if experiment.interruption_reason:
            interrupted_trials += 1
            is_comparable = False
            non_comparable_reason = "Trial interrupted during execution"
        else:
            completed_trials += 1

            # Aggregate stats
            guesses_for_this_trial = sum(r.attack.guesses_used for r in experiment.rounds)
            total_guesses_list.append(guesses_for_this_trial)

            # Determine win
            if experiment.rounds:
                last_round = experiment.rounds[-1]
                if last_round.attack.solved:
                    attacker_wins += 1
                else:
                    defender_survives += 1

        total_tokens += 0
        total_estimated_cost += 0.0

        # Calculate latency
        for r in experiment.rounds:
            total_latency_ms += r.attack.elapsed_ms

    trials = len(config.seeds)
    solve_rate = attacker_wins / completed_trials if completed_trials > 0 else 0.0
    mean_guesses = statistics.mean(total_guesses_list) if total_guesses_list else None
    median_guesses = statistics.median(total_guesses_list) if total_guesses_list else None
    std_guesses = statistics.stdev(total_guesses_list) if len(total_guesses_list) > 1 else None

    ci_lower, ci_upper = calculate_confidence_interval(attacker_wins, completed_trials)

    summary = MatchupSummary(
        trials=trials,
        completed_trials=completed_trials,
        interrupted_trials=interrupted_trials,
        attacker_wins=attacker_wins,
        defender_survives=defender_survives,
        solve_rate=solve_rate,
        mean_guesses=mean_guesses,
        median_guesses=median_guesses,
        std_guesses=std_guesses,
        mean_latency_ms=total_latency_ms / max(1, sum(len(e.rounds) for e in experiments)),
        total_tokens=total_tokens,
        total_estimated_cost=total_estimated_cost,
        confidence_interval_lower=ci_lower if completed_trials > 0 else None,
        confidence_interval_upper=ci_upper if completed_trials > 0 else None,
    )

    return MatchupResult(
        matchup_id=matchup_id,
        config=config,
        experiments=tuple(experiments),
        summary=summary,
        is_comparable=is_comparable,
        non_comparable_reason=non_comparable_reason,
    )


def build_tournament_matrix(
    config: TournamentConfig, exclude_self: bool = False
) -> list[MatchupConfig]:
    matchups = []
    for attacker in config.attackers:
        for defender in config.defenders:
            if exclude_self and attacker == defender:
                continue

            matchup = MatchupConfig(
                attacker=attacker,
                defender=defender,
                rounds=config.rounds_per_match,
                seeds=config.seeds,
                generator_version=config.generator_version,
                generator_mode=config.generator_mode,
                max_guesses=config.max_guesses,
                max_wall_time_s=config.max_wall_time_s,
                max_tokens=config.max_tokens,
                max_api_cost=config.max_api_cost,
                max_retries=config.max_retries,
            )
            matchups.append(matchup)

    return matchups
