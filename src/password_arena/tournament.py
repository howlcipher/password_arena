from __future__ import annotations

import math
import statistics
import uuid

import password_arena
from password_arena.engine import PreflightFailure, build_arena_engine
from password_arena.models import (
    ArenaConfig,
    EfficiencyMetrics,
    ExclusionReason,
    ExclusionRecord,
    ExperimentResult,
    MatchupConfig,
    MatchupResult,
    MatchupSummary,
    ReplayMetadata,
    RoleMetadata,
    TournamentConfig,
)

REPLAY_SCHEMA_VERSION = "1.0"


def calculate_confidence_interval(
    successes: int, trials: int, z: float = 1.96
) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Assumes independent Bernoulli observations. When fed round-level solve counts
    from repeated hosted-model trials, treat this as a standard descriptive
    convention rather than a statistical guarantee: repeated calls to the same
    model can share correlated failure modes and are not necessarily i.i.d.
    """
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


def build_replay_metadata(config: MatchupConfig) -> ReplayMetadata:
    """Enough metadata to reconstruct a matchup's configuration for a re-run.

    `deterministic=True` only when both roles are rule_based AND generator_mode is
    "deterministic-test" -- the only combination where re-running is guaranteed to
    reproduce identical output (see AdaptiveDefender: deterministic-test mode is
    what switches the cryptographic-random family from `secrets.choice` to a seeded
    RNG; every other family already uses the seeded RNG unconditionally). For any
    hosted-model role, this only supports "configuration replay": re-running the
    same configuration, with no claim the model will reproduce prior output.
    """
    deterministic = (
        config.attacker.provider == "rule_based"
        and config.defender.provider == "rule_based"
        and config.generator_mode == "deterministic-test"
    )
    return ReplayMetadata(
        attacker=RoleMetadata.from_role_config(config.attacker),
        defender=RoleMetadata.from_role_config(config.defender),
        seeds=config.seeds,
        rounds_per_match=config.rounds,
        max_guesses=config.max_guesses,
        generator_mode=config.generator_mode,
        generator_version=config.generator_version,
        application_version=password_arena.__version__,
        schema_version=REPLAY_SCHEMA_VERSION,
        deterministic=deterministic,
    )


def compute_efficiency(
    rounds_solved: int,
    rounds_resisted: int,
    attacker_total_tokens: int,
    defender_total_tokens: int,
    attacker_total_latency_ms: float,
    total_estimated_cost: float | None,
) -> EfficiencyMetrics:
    """Transparent per-role efficiency ratios. Never divide by zero or unavailable data."""

    def ratio(numerator: int, denominator: float) -> float | None:
        return numerator / denominator if denominator > 0 else None

    cost_denominator = total_estimated_cost if total_estimated_cost else None

    return EfficiencyMetrics(
        attacker_solved_per_1k_tokens=ratio(rounds_solved, attacker_total_tokens / 1000),
        attacker_solved_per_second=ratio(rounds_solved, attacker_total_latency_ms / 1000),
        attacker_solved_per_dollar=(
            ratio(rounds_solved, cost_denominator) if cost_denominator else None
        ),
        defender_survived_per_1k_tokens=ratio(rounds_resisted, defender_total_tokens / 1000),
        defender_survived_per_dollar=(
            ratio(rounds_resisted, cost_denominator) if cost_denominator else None
        ),
    )


def aggregate_matchup(
    config: MatchupConfig,
    experiments: list[ExperimentResult],
    preflight_exclusions: list[ExclusionRecord],
) -> MatchupResult:
    """Pure aggregation over already-run trials.

    Split out from `run_matchup` so tournament statistics can be unit-tested with
    hand-built `ExperimentResult` fixtures, without exercising the engine.

    Round-level headline stats (solve rate, survival rate, guess metrics, token/
    cost/latency) are computed from every *comparable* round (see
    `RoundResult.comparable`) across ALL trials, including trials later interrupted
    -- their already-recorded, non-fallback rounds are still valid observations.
    Trial-level stats (final-round counts, per-trial guess totals, comparable_trials)
    require the whole trial to be comparable, since they are not decomposable to
    individual rounds.
    """
    trials = len(config.seeds)
    trial_exclusions: list[ExclusionRecord] = list(preflight_exclusions)
    round_exclusions: list[ExclusionRecord] = []

    rounds_completed = 0
    rounds_solved = 0
    rounds_resisted = 0
    guesses_per_round: list[int] = []
    guesses_to_solve: list[int] = []
    total_guesses_per_trial: list[int] = []
    final_round_solved_count = 0
    final_round_resisted_count = 0

    attacker_input_tokens = 0
    attacker_output_tokens = 0
    attacker_reasoning_tokens: int | None = None
    defender_input_tokens = 0
    defender_output_tokens = 0
    defender_reasoning_tokens: int | None = None
    attacker_latencies: list[float] = []
    defender_latencies: list[float] = []
    cost_known = True
    total_cost = 0.0

    for experiment in experiments:
        seed = experiment.config.seed
        trial_comparable = experiment.interruption_reason is None
        if not trial_comparable:
            trial_exclusions.append(
                ExclusionRecord(
                    seed, experiment.experiment_id, None, ExclusionReason.INTERRUPTED_PROVIDER
                )
            )
        else:
            total_guesses_per_trial.append(sum(r.attack.guesses_used for r in experiment.rounds))
            if experiment.rounds:
                last = experiment.rounds[-1]
                if last.attack.solved:
                    final_round_solved_count += 1
                else:
                    final_round_resisted_count += 1

        for r in experiment.rounds:
            if not r.comparable:
                round_exclusions.append(
                    ExclusionRecord(
                        seed,
                        experiment.experiment_id,
                        r.round_number,
                        ExclusionReason.FALLBACK_USED,
                    )
                )
                continue

            rounds_completed += 1
            guesses_per_round.append(r.attack.guesses_used)
            if r.attack.solved:
                rounds_solved += 1
                guesses_to_solve.append(r.attack.guesses_used)
            else:
                rounds_resisted += 1

            if r.attacker_usage is not None:
                attacker_input_tokens += r.attacker_usage.input_tokens
                attacker_output_tokens += r.attacker_usage.output_tokens
                if r.attacker_usage.reasoning_tokens is not None:
                    attacker_reasoning_tokens = (
                        attacker_reasoning_tokens or 0
                    ) + r.attacker_usage.reasoning_tokens
                attacker_latencies.append(r.attacker_usage.latency_ms)
                if r.attacker_usage.estimated_cost is None:
                    cost_known = False
                else:
                    total_cost += r.attacker_usage.estimated_cost

            if r.defender_usage is not None:
                defender_input_tokens += r.defender_usage.input_tokens
                defender_output_tokens += r.defender_usage.output_tokens
                if r.defender_usage.reasoning_tokens is not None:
                    defender_reasoning_tokens = (
                        defender_reasoning_tokens or 0
                    ) + r.defender_usage.reasoning_tokens
                defender_latencies.append(r.defender_usage.latency_ms)
                if r.defender_usage.estimated_cost is None:
                    cost_known = False
                else:
                    total_cost += r.defender_usage.estimated_cost

    comparable_trials = trials - len(trial_exclusions)
    excluded_trials = len(trial_exclusions)
    excluded_rounds = len(round_exclusions)

    solve_rate = rounds_solved / rounds_completed if rounds_completed > 0 else None
    survival_rate = rounds_resisted / rounds_completed if rounds_completed > 0 else None
    ci_lower: float | None
    ci_upper: float | None
    if rounds_completed > 0:
        ci_lower, ci_upper = calculate_confidence_interval(rounds_solved, rounds_completed)
    else:
        ci_lower = ci_upper = None

    total_estimated_cost = total_cost if cost_known else None

    efficiency = compute_efficiency(
        rounds_solved=rounds_solved,
        rounds_resisted=rounds_resisted,
        attacker_total_tokens=attacker_input_tokens + attacker_output_tokens,
        defender_total_tokens=defender_input_tokens + defender_output_tokens,
        attacker_total_latency_ms=sum(attacker_latencies),
        total_estimated_cost=total_estimated_cost,
    )

    summary = MatchupSummary(
        trials=trials,
        comparable_trials=comparable_trials,
        excluded_trials=excluded_trials,
        excluded_rounds=excluded_rounds,
        rounds_completed=rounds_completed,
        rounds_solved=rounds_solved,
        rounds_resisted=rounds_resisted,
        solve_rate=solve_rate,
        survival_rate=survival_rate,
        confidence_interval_lower=ci_lower,
        confidence_interval_upper=ci_upper,
        final_round_solved_count=final_round_solved_count,
        final_round_resisted_count=final_round_resisted_count,
        mean_guesses_per_round=(
            statistics.mean(guesses_per_round) if guesses_per_round else None
        ),
        median_guesses_per_round=(
            statistics.median(guesses_per_round) if guesses_per_round else None
        ),
        std_guesses_per_round=(
            statistics.stdev(guesses_per_round) if len(guesses_per_round) > 1 else None
        ),
        mean_guesses_to_solve=statistics.mean(guesses_to_solve) if guesses_to_solve else None,
        median_guesses_to_solve=(
            statistics.median(guesses_to_solve) if guesses_to_solve else None
        ),
        mean_total_guesses_per_trial=(
            statistics.mean(total_guesses_per_trial) if total_guesses_per_trial else None
        ),
        attacker_input_tokens=attacker_input_tokens,
        attacker_output_tokens=attacker_output_tokens,
        attacker_reasoning_tokens=attacker_reasoning_tokens,
        defender_input_tokens=defender_input_tokens,
        defender_output_tokens=defender_output_tokens,
        defender_reasoning_tokens=defender_reasoning_tokens,
        attacker_mean_latency_ms=(
            statistics.mean(attacker_latencies) if attacker_latencies else None
        ),
        defender_mean_latency_ms=(
            statistics.mean(defender_latencies) if defender_latencies else None
        ),
        total_estimated_cost=total_estimated_cost,
        efficiency=efficiency,
    )

    is_comparable = comparable_trials > 0
    non_comparable_reason = (
        "; ".join(sorted({e.reason.value for e in trial_exclusions})) if trial_exclusions else None
    )

    return MatchupResult(
        matchup_id=uuid.uuid4().hex,
        config=config,
        experiments=tuple(experiments),
        summary=summary,
        is_comparable=is_comparable,
        non_comparable_reason=non_comparable_reason,
        excluded_trial_records=tuple(trial_exclusions),
        excluded_round_records=tuple(round_exclusions),
        replay=build_replay_metadata(config),
    )


def run_matchup(config: MatchupConfig) -> MatchupResult:
    experiments: list[ExperimentResult] = []
    preflight_exclusions: list[ExclusionRecord] = []

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
            preflight_exclusions.append(
                ExclusionRecord(seed, None, None, ExclusionReason.PREFLIGHT_FAILED)
            )
            continue

        engine = result_or_failure
        experiments.append(engine.run())

    return aggregate_matchup(config, experiments, preflight_exclusions)


def replay_matchup(matchup_result: MatchupResult) -> MatchupResult:
    """Re-run a matchup's configuration.

    Exact reproduction is only guaranteed when `matchup_result.replay.deterministic`
    is True. Otherwise this is "configuration replay": the same configuration is
    re-run, with no claim that a hosted model will reproduce prior output.
    """
    return run_matchup(matchup_result.config)


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
