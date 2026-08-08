import math
import statistics
from dataclasses import asdict

import pytest

from password_arena.models import (
    ArenaConfig,
    AttackResult,
    ExclusionReason,
    ExclusionRecord,
    ExperimentResult,
    MatchupConfig,
    RoleConfig,
    RoleUsage,
    RoundResult,
    StrengthReport,
    TournamentConfig,
)
from password_arena.tournament import (
    aggregate_matchup,
    build_replay_metadata,
    build_tournament_matrix,
    calculate_confidence_interval,
    compute_efficiency,
    replay_matchup,
    run_matchup,
)


def _strength() -> StrengthReport:
    return StrengthReport(entropy_bits=10.0, score=1, character_pool=26, pattern_penalty=0.0)


def _attack(solved: bool, guesses: int) -> AttackResult:
    return AttackResult(
        solved=solved,
        guesses_used=guesses,
        winning_strategy="common" if solved else None,
        elapsed_ms=1.0,
    )


def _round(
    number: int,
    solved: bool,
    guesses: int,
    attacker_usage: RoleUsage | None = None,
    defender_usage: RoleUsage | None = None,
    comparable: bool = True,
) -> RoundResult:
    return RoundResult(
        round_number=number,
        difficulty=1,
        password_display="****",
        password_length=4,
        strength=_strength(),
        attack=_attack(solved, guesses),
        defender_strategy="dictionary-word",
        defender_note="note",
        defender_learning="learning",
        attacker_note="note",
        attacker_learning="learning",
        attacker_usage=attacker_usage,
        defender_usage=defender_usage,
        comparable=comparable,
    )


def _experiment(
    seed: int, rounds: list[RoundResult], interruption_reason: str | None = None
) -> ExperimentResult:
    return ExperimentResult(
        config=ArenaConfig(seed=seed),
        rounds=tuple(rounds),
        interruption_reason=interruption_reason,
    )


def _matchup_config(seeds: tuple[int, ...] = (42, 43)) -> MatchupConfig:
    return MatchupConfig(
        attacker=RoleConfig(provider="rule_based"),
        defender=RoleConfig(provider="rule_based"),
        rounds=2,
        seeds=seeds,
    )


def test_build_tournament_matrix() -> None:
    r1 = RoleConfig(provider="rule_based")
    r2 = RoleConfig(provider="openai", model="gpt-4o")

    config = TournamentConfig(
        attackers=(r1, r2),
        defenders=(r1, r2),
        seeds=(42, 43),
        rounds_per_match=3,
    )

    matchups = build_tournament_matrix(config, exclude_self=False)
    assert len(matchups) == 4
    assert matchups[0].attacker == r1 and matchups[0].defender == r1

    matchups_no_self = build_tournament_matrix(config, exclude_self=True)
    assert len(matchups_no_self) == 2
    assert matchups_no_self[0].attacker == r1 and matchups_no_self[0].defender == r2


def test_one_solved_one_resisted_round() -> None:
    config = _matchup_config(seeds=(42,))
    exp = _experiment(42, [_round(1, True, 5), _round(2, False, 20)])
    result = aggregate_matchup(config, [exp], [])
    s = result.summary

    assert s.rounds_completed == 2
    assert s.rounds_solved == 1
    assert s.rounds_resisted == 1
    assert s.solve_rate == 0.5
    assert s.survival_rate == 0.5
    assert s.mean_guesses_per_round == statistics.mean([5, 20])
    assert s.mean_guesses_to_solve == 5.0
    assert s.median_guesses_to_solve == 5.0
    assert s.mean_total_guesses_per_trial == 25.0
    # Round 2 (the trial's last round) was resisted.
    assert s.final_round_solved_count == 0
    assert s.final_round_resisted_count == 1
    assert result.is_comparable is True


def test_all_solved() -> None:
    config = _matchup_config(seeds=(1, 2))
    exps = [
        _experiment(1, [_round(1, True, 3), _round(2, True, 4)]),
        _experiment(2, [_round(1, True, 5), _round(2, True, 6)]),
    ]
    result = aggregate_matchup(config, exps, [])
    s = result.summary

    assert s.rounds_completed == 4
    assert s.rounds_solved == 4
    assert s.rounds_resisted == 0
    assert s.solve_rate == 1.0
    assert s.survival_rate == 0.0
    assert s.final_round_solved_count == 2
    assert s.final_round_resisted_count == 0


def test_none_solved() -> None:
    config = _matchup_config(seeds=(1,))
    exp = _experiment(1, [_round(1, False, 100), _round(2, False, 100)])
    result = aggregate_matchup(config, [exp], [])
    s = result.summary

    assert s.rounds_solved == 0
    assert s.solve_rate == 0.0
    assert s.survival_rate == 1.0
    assert s.mean_guesses_to_solve is None
    assert s.median_guesses_to_solve is None


def test_interrupted_trial_completed_rounds_still_count_for_headline() -> None:
    config = _matchup_config(seeds=(1, 2))
    clean_exp = _experiment(1, [_round(1, True, 3), _round(2, False, 10)])
    interrupted_exp = _experiment(2, [_round(1, True, 2)], interruption_reason="rate limited")

    result = aggregate_matchup(config, [clean_exp, interrupted_exp], [])
    s = result.summary

    # Round-level headline uses every recorded, comparable round from BOTH trials.
    assert s.rounds_completed == 3
    assert s.rounds_solved == 2
    assert s.rounds_resisted == 1
    # Trial-level stats only count the clean trial.
    assert s.comparable_trials == 1
    assert s.excluded_trials == 1
    assert s.final_round_solved_count == 0
    assert s.final_round_resisted_count == 1
    assert s.mean_total_guesses_per_trial == 13.0
    assert result.is_comparable is True

    reasons = {r.reason for r in result.excluded_trial_records}
    assert ExclusionReason.INTERRUPTED_PROVIDER in reasons


def test_preflight_failure_is_excluded_and_recorded() -> None:
    config = _matchup_config(seeds=(1,))
    exclusions = [
        ExclusionRecord(
            seed=1, experiment_id=None, round_number=None, reason=ExclusionReason.PREFLIGHT_FAILED
        )
    ]
    result = aggregate_matchup(config, [], exclusions)

    assert result.is_comparable is False
    assert result.summary.comparable_trials == 0
    assert result.summary.excluded_trials == 1
    assert result.non_comparable_reason == "preflight_failed"


def test_fallback_round_excluded_but_trial_stays_comparable() -> None:
    config = _matchup_config(seeds=(1,))
    fallback_usage = RoleUsage(input_tokens=1, output_tokens=1, fallback_used=True)
    exp = _experiment(
        1,
        [
            _round(1, True, 3, attacker_usage=fallback_usage, comparable=False),
            _round(2, False, 8),
        ],
    )
    result = aggregate_matchup(config, [exp], [])
    s = result.summary

    assert s.rounds_completed == 1
    assert s.rounds_solved == 0
    assert s.excluded_rounds == 1
    assert s.comparable_trials == 1
    reasons = {r.reason for r in result.excluded_round_records}
    assert ExclusionReason.FALLBACK_USED in reasons


def test_guess_statistics_hand_calculated() -> None:
    config = _matchup_config(seeds=(1,))
    exp = _experiment(
        1,
        [
            _round(1, True, 2),
            _round(2, True, 6),
            _round(3, False, 8),
            _round(4, False, 12),
        ],
    )
    result = aggregate_matchup(config, [exp], [])
    s = result.summary

    assert s.mean_guesses_per_round == statistics.mean([2, 6, 8, 12])
    assert s.median_guesses_per_round == statistics.median([2, 6, 8, 12])
    assert s.std_guesses_per_round == statistics.stdev([2, 6, 8, 12])
    assert s.mean_guesses_to_solve == statistics.mean([2, 6])
    assert s.median_guesses_to_solve == statistics.median([2, 6])
    assert s.mean_total_guesses_per_trial == 28.0


def test_std_guesses_is_none_with_fewer_than_two_observations() -> None:
    config = _matchup_config(seeds=(1,))
    exp = _experiment(1, [_round(1, True, 5)])
    result = aggregate_matchup(config, [exp], [])
    assert result.summary.std_guesses_per_round is None


def test_role_specific_token_and_latency_aggregation() -> None:
    config = _matchup_config(seeds=(1,))
    att_usage = RoleUsage(input_tokens=10, output_tokens=20, latency_ms=100.0, estimated_cost=0.01)
    def_usage = RoleUsage(input_tokens=5, output_tokens=7, latency_ms=50.0, estimated_cost=0.02)
    exp = _experiment(1, [_round(1, True, 3, attacker_usage=att_usage, defender_usage=def_usage)])

    result = aggregate_matchup(config, [exp], [])
    s = result.summary

    assert s.attacker_input_tokens == 10
    assert s.attacker_output_tokens == 20
    assert s.defender_input_tokens == 5
    assert s.defender_output_tokens == 7
    assert s.attacker_mean_latency_ms == 100.0
    assert s.defender_mean_latency_ms == 50.0
    assert s.total_estimated_cost == pytest.approx(0.03)


def test_unavailable_cost_propagates_as_none() -> None:
    config = _matchup_config(seeds=(1,))
    known = RoleUsage(input_tokens=1, output_tokens=1, estimated_cost=0.01)
    unknown = RoleUsage(input_tokens=1, output_tokens=1, estimated_cost=None)
    exp = _experiment(
        1,
        [
            _round(1, True, 1, attacker_usage=known),
            _round(2, False, 1, attacker_usage=unknown),
        ],
    )
    result = aggregate_matchup(config, [exp], [])
    assert result.summary.total_estimated_cost is None


def test_known_cost_sums_including_rule_based_zero() -> None:
    config = _matchup_config(seeds=(1,))
    exp = _experiment(
        1,
        [
            _round(1, True, 1, attacker_usage=RoleUsage(estimated_cost=0.5)),
            _round(2, False, 1),  # rule_based round: no usage at all -> a real, known zero
        ],
    )
    result = aggregate_matchup(config, [exp], [])
    assert result.summary.total_estimated_cost == pytest.approx(0.5)


def test_role_specific_cost_is_not_combined_matchup_cost() -> None:
    """BUG-018: attacker cost must reflect only the attacker's own LLM calls,
    never the defender's spend folded into a single combined total."""
    config = _matchup_config(seeds=(1,))
    exp = _experiment(
        1,
        [
            _round(
                1,
                True,
                1,
                attacker_usage=RoleUsage(estimated_cost=1.0),
                defender_usage=RoleUsage(estimated_cost=9.0),
            ),
        ],
    )
    result = aggregate_matchup(config, [exp], [])
    s = result.summary
    assert s.attacker_estimated_cost == pytest.approx(1.0)
    assert s.defender_estimated_cost == pytest.approx(9.0)
    assert s.total_estimated_cost == pytest.approx(10.0)


def test_role_specific_cost_unknown_for_only_the_affected_role() -> None:
    """When only the defender's cost is unknown, the attacker's own
    (fully-known) cost must still be reported -- not dragged down to None by
    a role it doesn't share data with."""
    config = _matchup_config(seeds=(1,))
    exp = _experiment(
        1,
        [
            _round(
                1,
                True,
                1,
                attacker_usage=RoleUsage(estimated_cost=1.0),
                defender_usage=RoleUsage(estimated_cost=None),
            ),
        ],
    )
    result = aggregate_matchup(config, [exp], [])
    s = result.summary
    assert s.attacker_estimated_cost == pytest.approx(1.0)
    assert s.defender_estimated_cost is None
    assert s.total_estimated_cost is None


def test_role_specific_cost_zero_when_role_never_calls_llm() -> None:
    """rule_based vs rule_based: neither role ever calls an LLM, so both
    role-specific costs are a real, known 0.0 -- not None."""
    config = _matchup_config(seeds=(1,))
    exp = _experiment(1, [_round(1, True, 1)])
    result = aggregate_matchup(config, [exp], [])
    s = result.summary
    assert s.attacker_estimated_cost == 0.0
    assert s.defender_estimated_cost == 0.0
    assert s.total_estimated_cost == 0.0


def test_confidence_interval_exact_value() -> None:
    lower, upper = calculate_confidence_interval(50, 100)
    p, z, n = 0.5, 1.96, 100
    denom = 1 + z**2 / n
    center = p + z**2 / (2 * n)
    spread = z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n)
    assert lower == pytest.approx((center - spread) / denom)
    assert upper == pytest.approx((center + spread) / denom)


def test_confidence_interval_edge_cases() -> None:
    assert calculate_confidence_interval(0, 0) == (0.0, 0.0)

    lower0, upper0 = calculate_confidence_interval(0, 10)
    assert lower0 == 0.0
    assert upper0 > 0.0

    lower_n, upper_n = calculate_confidence_interval(10, 10)
    assert upper_n <= 1.0
    assert lower_n < 1.0
    assert lower_n > 0.5


def test_efficiency_zero_denominator_guards() -> None:
    eff = compute_efficiency(
        rounds_solved=5,
        rounds_resisted=3,
        attacker_total_tokens=0,
        defender_total_tokens=0,
        attacker_total_latency_ms=0.0,
        attacker_estimated_cost=None,
        defender_estimated_cost=None,
    )
    assert eff.attacker_solved_per_1k_tokens is None
    assert eff.attacker_solved_per_second is None
    assert eff.attacker_solved_per_dollar is None
    assert eff.defender_survived_per_1k_tokens is None
    assert eff.defender_survived_per_dollar is None


def test_efficiency_known_values() -> None:
    eff = compute_efficiency(
        rounds_solved=10,
        rounds_resisted=5,
        attacker_total_tokens=2000,
        defender_total_tokens=1000,
        attacker_total_latency_ms=5000.0,
        attacker_estimated_cost=2.0,
        defender_estimated_cost=2.0,
    )
    assert eff.attacker_solved_per_1k_tokens == pytest.approx(5.0)
    assert eff.attacker_solved_per_second == pytest.approx(2.0)
    assert eff.attacker_solved_per_dollar == pytest.approx(5.0)
    assert eff.defender_survived_per_1k_tokens == pytest.approx(5.0)
    assert eff.defender_survived_per_dollar == pytest.approx(2.5)


def test_efficiency_uses_role_specific_cost_not_combined() -> None:
    """attacker_solved_per_dollar must use the attacker's own cost, never the
    defender's or a combined total -- otherwise spend gets misattributed
    across roles (BUG-018)."""
    eff = compute_efficiency(
        rounds_solved=10,
        rounds_resisted=5,
        attacker_total_tokens=2000,
        defender_total_tokens=1000,
        attacker_total_latency_ms=5000.0,
        attacker_estimated_cost=1.0,
        defender_estimated_cost=9.0,
    )
    assert eff.attacker_solved_per_dollar == pytest.approx(10.0)
    assert eff.defender_survived_per_dollar == pytest.approx(5 / 9)


def test_replay_metadata_deterministic_flag() -> None:
    deterministic_config = _matchup_config()
    assert build_replay_metadata(deterministic_config).deterministic is True

    hosted_config = MatchupConfig(
        attacker=RoleConfig(provider="openai", model="gpt-4o"),
        defender=RoleConfig(provider="rule_based"),
        rounds=2,
        seeds=(1,),
    )
    assert build_replay_metadata(hosted_config).deterministic is False


def test_replay_metadata_carries_prompt_and_capability_registry_versions() -> None:
    """IMP-026: reports must identify prompt and capability-registry versions,
    not just schema/application version."""
    from password_arena.attacker import ATTACKER_PROMPT_VERSION
    from password_arena.defender import DEFENDER_PROMPT_VERSION
    from password_arena.providers import CAPABILITY_REGISTRY_VERSION

    replay = build_replay_metadata(_matchup_config())
    assert replay.attacker_prompt_version == ATTACKER_PROMPT_VERSION
    assert replay.defender_prompt_version == DEFENDER_PROMPT_VERSION
    assert replay.capability_registry_version == CAPABILITY_REGISTRY_VERSION
    # Sanity: these are meant to be independently bumpable, not accidentally
    # aliased to the same string by construction.
    assert replay.attacker_prompt_version
    assert replay.defender_prompt_version
    assert replay.capability_registry_version


def test_run_matchup_rule_based_end_to_end() -> None:
    config = MatchupConfig(
        attacker=RoleConfig(provider="rule_based"),
        defender=RoleConfig(provider="rule_based"),
        rounds=2,
        seeds=(42, 43),
        max_guesses=100,
    )
    result = run_matchup(config)

    assert result.config.seeds == (42, 43)
    assert result.summary.trials == 2
    assert result.summary.comparable_trials == 2
    assert result.is_comparable is True
    assert result.summary.excluded_trials == 0
    assert result.replay is not None
    assert result.replay.deterministic is True


def test_deterministic_replay_produces_identical_summary() -> None:
    config = MatchupConfig(
        attacker=RoleConfig(provider="rule_based"),
        defender=RoleConfig(provider="rule_based"),
        rounds=3,
        seeds=(42, 43),
        max_guesses=200,
    )
    result1 = run_matchup(config)
    result2 = replay_matchup(result1)

    assert result1.replay is not None
    assert result1.replay.deterministic is True
    assert asdict(result1.summary) == asdict(result2.summary)


def test_run_matchup_with_mock_provider_populates_role_usage() -> None:
    config = MatchupConfig(
        attacker=RoleConfig(provider="mock"),
        defender=RoleConfig(provider="mock"),
        rounds=1,
        seeds=(1,),
        max_guesses=10,
    )
    result = run_matchup(config)
    s = result.summary

    assert s.comparable_trials == 1
    assert s.rounds_completed == 1
    assert s.attacker_input_tokens > 0
    assert s.defender_input_tokens > 0
