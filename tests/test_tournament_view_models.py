import pytest

from password_arena.models import (
    ArenaConfig,
    AttackResult,
    ExperimentResult,
    MatchupConfig,
    MatchupResult,
    RoleConfig,
    RoleUsage,
    RoundResult,
    StrengthReport,
)
from password_arena.providers import ThinkingLevel
from password_arena.tournament import aggregate_matchup
from password_arena.tournament_history import StoredMatchup
from password_arena.tournament_view_models import (
    HEATMAP_METRICS,
    aggregate_tournament_cost,
    build_attacker_leaderboard,
    build_defender_leaderboard,
    build_efficiency_data,
    build_heatmap_data,
    build_overview,
    build_thinking_comparison_data,
)


def _strength() -> StrengthReport:
    return StrengthReport(entropy_bits=10.0, score=1, character_pool=26, pattern_penalty=0.0)


def _round(
    number: int,
    solved: bool,
    attacker_usage: RoleUsage | None = None,
    defender_usage: RoleUsage | None = None,
) -> RoundResult:
    return RoundResult(
        round_number=number,
        difficulty=1,
        password_display="****",
        password_length=4,
        strength=_strength(),
        attack=AttackResult(
            solved=solved,
            guesses_used=10 if solved else 5000,
            winning_strategy="common" if solved else None,
            elapsed_ms=1.0,
        ),
        defender_strategy="dictionary-word",
        defender_note="",
        defender_learning="",
        attacker_note="",
        attacker_learning="",
        attacker_usage=attacker_usage,
        defender_usage=defender_usage,
    )


def _matchup(
    *,
    attacker: RoleConfig,
    defender: RoleConfig,
    round_outcomes: list[bool],
    attacker_usage: RoleUsage | None = None,
    defender_usage: RoleUsage | None = None,
) -> MatchupResult:
    config = MatchupConfig(
        attacker=attacker,
        defender=defender,
        rounds=len(round_outcomes),
        seeds=(1,),
    )
    rounds = [
        _round(i + 1, solved, attacker_usage=attacker_usage, defender_usage=defender_usage)
        for i, solved in enumerate(round_outcomes)
    ]
    experiment = ExperimentResult(config=ArenaConfig(seed=1), rounds=tuple(rounds))
    return aggregate_matchup(config, [experiment], [])


def _attacker(name: str = "attacker-model") -> RoleConfig:
    return RoleConfig(provider="openai", model=name, thinking_level=ThinkingLevel.HIGH)


def _defender(name: str = "defender-model") -> RoleConfig:
    return RoleConfig(provider="anthropic", model=name, thinking_level=ThinkingLevel.AUTO)


# --- aggregate_tournament_cost ---------------------------------------------


def test_aggregate_tournament_cost_known_zero() -> None:
    m = _matchup(attacker=_attacker(), defender=_defender(), round_outcomes=[True, False])
    assert m.summary.total_estimated_cost == 0.0
    assert aggregate_tournament_cost([m]) == 0.0


def test_aggregate_tournament_cost_unknown_when_any_matchup_unknown() -> None:
    priced = _matchup(
        attacker=_attacker(),
        defender=_defender(),
        round_outcomes=[True],
        attacker_usage=RoleUsage(estimated_cost=1.0),
    )
    unpriced = _matchup(
        attacker=_attacker("other"),
        defender=_defender(),
        round_outcomes=[True],
        attacker_usage=RoleUsage(estimated_cost=None),
    )
    assert priced.summary.total_estimated_cost == 1.0
    assert unpriced.summary.total_estimated_cost is None
    assert aggregate_tournament_cost([priced, unpriced]) is None
    # A single known-cost matchup rolls up correctly on its own.
    assert aggregate_tournament_cost([priced]) == 1.0


def test_aggregate_tournament_cost_empty_is_none_not_zero() -> None:
    assert aggregate_tournament_cost([]) is None


# --- build_overview ----------------------------------------------------------


def test_build_overview_basic() -> None:
    m = _matchup(attacker=_attacker(), defender=_defender(), round_outcomes=[True, False])
    overview = build_overview([m])
    assert overview.comparable_rounds == 2
    assert overview.total_solved == 1
    assert overview.total_resisted == 1
    assert overview.solve_rate == pytest.approx(0.5)
    assert overview.survival_rate == pytest.approx(0.5)
    assert overview.total_cost == 0.0


def test_build_overview_no_comparable_rounds_returns_none_not_zero() -> None:
    """A tournament with zero comparable rounds must report solve/survival
    rate as None ("no data"), not 0.0 -- 0.0 would misleadingly imply a
    measured 0% solve rate."""
    overview = build_overview([])
    assert overview.solve_rate is None
    assert overview.survival_rate is None
    assert overview.comparable_rounds == 0


def test_build_overview_cost_unknown_not_zero_substituted() -> None:
    """Regression for BUG-017: previously `sum(cost or 0.0)` silently treated
    an unpriced matchup's cost as $0 when combined with a priced one."""
    priced = _matchup(
        attacker=_attacker(),
        defender=_defender(),
        round_outcomes=[True],
        attacker_usage=RoleUsage(estimated_cost=5.0),
    )
    unpriced = _matchup(
        attacker=_attacker("other"),
        defender=_defender(),
        round_outcomes=[True],
        attacker_usage=RoleUsage(estimated_cost=None),
    )
    overview = build_overview([priced, unpriced])
    assert overview.total_cost is None


# --- weighted leaderboards ----------------------------------------------------


def test_attacker_leaderboard_is_weighted_not_unweighted_mean() -> None:
    """Core fixture proving a 2-round matchup cannot carry the same
    statistical weight as a 100-round matchup: matchup A has 100 comparable
    rounds all solved (100% solve rate), matchup B has 2 comparable rounds
    both resisted (0% solve rate), same attacker, different defenders.

    An unweighted mean of per-matchup percentages gives 50%. The correct,
    weighted (ratio-of-sums) aggregate is 100/102 =~ 98.0%.
    """
    attacker = _attacker("shared-attacker")
    matchup_a = _matchup(
        attacker=attacker, defender=_defender("defender-a"), round_outcomes=[True] * 100
    )
    matchup_b = _matchup(
        attacker=attacker, defender=_defender("defender-b"), round_outcomes=[False] * 2
    )

    df = build_attacker_leaderboard([matchup_a, matchup_b])
    assert len(df) == 1
    row = df.iloc[0]
    assert row["Comparable Rounds"] == 102

    weighted_rate = row["Solve Rate"]
    unweighted_mean = (1.0 + 0.0) / 2  # what the old groupby(...).mean() produced
    assert weighted_rate == pytest.approx(100 / 102)
    assert weighted_rate != pytest.approx(unweighted_mean)
    assert weighted_rate > 0.9  # the 100-round matchup should dominate


def test_defender_leaderboard_is_weighted_and_has_cost_column() -> None:
    defender = _defender("shared-defender")
    matchup_a = _matchup(
        attacker=_attacker("attacker-a"), defender=defender, round_outcomes=[False] * 100
    )
    matchup_b = _matchup(
        attacker=_attacker("attacker-b"), defender=defender, round_outcomes=[True] * 2
    )

    df = build_defender_leaderboard([matchup_a, matchup_b])
    assert len(df) == 1
    row = df.iloc[0]
    assert row["Survival Rate"] == pytest.approx(100 / 102)
    assert "Cost" in df.columns  # previously absent entirely (BUG-018 audit)


def test_leaderboard_latency_is_weighted_mean_reconstruction() -> None:
    attacker = _attacker("latency-attacker")
    fast = _matchup(
        attacker=attacker,
        defender=_defender("d1"),
        round_outcomes=[True] * 10,
        attacker_usage=RoleUsage(latency_ms=100.0),
    )
    slow = _matchup(
        attacker=attacker,
        defender=_defender("d2"),
        round_outcomes=[True] * 2,
        attacker_usage=RoleUsage(latency_ms=1000.0),
    )
    df = build_attacker_leaderboard([fast, slow])
    row = df.iloc[0]
    # Weighted by rounds_completed (10 vs 2): (100*10 + 1000*2) / 12
    assert row["Latency ms"] == pytest.approx((100.0 * 10 + 1000.0 * 2) / 12)


# --- heatmap -------------------------------------------------------------------


def test_heatmap_combined_metrics_are_explicitly_labeled() -> None:
    assert "Combined attacker+defender latency (ms)" in HEATMAP_METRICS
    assert "Combined attacker+defender tokens" in HEATMAP_METRICS
    assert "Latency ms" not in HEATMAP_METRICS  # the old ambiguous label
    assert "Tokens" not in HEATMAP_METRICS
    assert "Cost" in HEATMAP_METRICS  # was entirely missing before


def test_heatmap_data_missing_latency_is_none_not_zero() -> None:
    m = _matchup(attacker=_attacker(), defender=_defender(), round_outcomes=[True])
    df = build_heatmap_data([m], "Combined attacker+defender latency (ms)")
    assert len(df) == 1
    assert df.iloc[0]["Value"] is None


def test_heatmap_data_tooltip_payload_is_complete() -> None:
    m = _matchup(attacker=_attacker(), defender=_defender(), round_outcomes=[True, False])
    df = build_heatmap_data([m], "Solve Rate")
    row = df.iloc[0]
    for col in (
        "Attacker",
        "Defender",
        "AttackerModel",
        "AttackerThinking",
        "DefenderModel",
        "DefenderThinking",
        "Trials",
        "ComparableRounds",
        "ExcludedRounds",
        "ExcludedTrials",
        "CILower",
        "CIUpper",
    ):
        assert col in row.index


def test_heatmap_data_rejects_unknown_metric() -> None:
    m = _matchup(attacker=_attacker(), defender=_defender(), round_outcomes=[True])
    with pytest.raises(ValueError):
        build_heatmap_data([m], "Not A Real Metric")


# --- efficiency ------------------------------------------------------------


def test_efficiency_data_preserves_none_for_missing_cost() -> None:
    m = _matchup(
        attacker=_attacker(),
        defender=_defender(),
        round_outcomes=[True],
        attacker_usage=RoleUsage(estimated_cost=None),
    )
    df = build_efficiency_data([m])
    row = df.iloc[0]
    assert row["Cost"] is None
    assert row["Attacker Cost"] is None


def test_efficiency_data_preserves_none_for_missing_latency() -> None:
    # rule_based defender: no defender_usage at all -> no defender latency.
    m = _matchup(
        attacker=_attacker(),
        defender=RoleConfig(provider="rule_based"),
        round_outcomes=[True],
        attacker_usage=RoleUsage(latency_ms=50.0),
    )
    df = build_efficiency_data([m])
    row = df.iloc[0]
    assert row["Combined Latency ms"] is None


# --- thinking comparison ----------------------------------------------------


def test_thinking_comparison_excludes_single_level_models() -> None:
    m = _matchup(attacker=_attacker(), defender=_defender(), round_outcomes=[True])
    att_df, dfd_df = build_thinking_comparison_data([m])
    assert att_df.empty
    assert dfd_df.empty


def test_thinking_comparison_is_weighted_across_matchups() -> None:
    high = RoleConfig(provider="openai", model="m1", thinking_level=ThinkingLevel.HIGH)
    low = RoleConfig(provider="openai", model="m1", thinking_level=ThinkingLevel.LOW)

    high_matchup_a = _matchup(
        attacker=high, defender=_defender("d1"), round_outcomes=[True] * 100
    )
    high_matchup_b = _matchup(
        attacker=high, defender=_defender("d2"), round_outcomes=[True] * 100
    )
    low_matchup = _matchup(attacker=low, defender=_defender("d3"), round_outcomes=[False] * 2)

    att_df, _ = build_thinking_comparison_data([high_matchup_a, high_matchup_b, low_matchup])
    assert set(att_df["Thinking"]) == {"high", "low"}
    high_row = att_df[att_df["Thinking"] == "high"].iloc[0]
    assert high_row["Solve Rate"] == pytest.approx(1.0)
    assert high_row["Comparable Rounds"] == 200


# --- MatchupLike protocol ----------------------------------------------------


def test_view_models_accept_stored_matchup_not_just_matchup_result() -> None:
    """The dashboard renders both freshly-run MatchupResult objects and
    StoredMatchup objects loaded from history through the same functions --
    they must be structurally interchangeable."""
    m = _matchup(attacker=_attacker(), defender=_defender(), round_outcomes=[True, False])
    stored = StoredMatchup(
        matchup_id=m.matchup_id,
        config=m.config,
        summary=m.summary,
        is_comparable=m.is_comparable,
        non_comparable_reason=m.non_comparable_reason,
        experiment_ids=(),
    )

    overview_from_result = build_overview([m])
    overview_from_stored = build_overview([stored])
    assert overview_from_result == overview_from_stored

    att_df = build_attacker_leaderboard([stored])
    assert len(att_df) == 1
