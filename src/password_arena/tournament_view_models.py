"""Pure aggregation and transformation logic for the Tournament dashboard.

No Streamlit or Altair dependency lives here -- every function takes tournament
result data and returns a plain dataclass or `pandas.DataFrame`, fully unit
testable without exercising the UI. `tournament_views.py` is the thin rendering
layer that consumes these outputs; it must not recreate or weaken any of the
aggregation rules defined here or in `tournament.py`.

Weighting and "unknown is not zero" rules (why, not just what):

- Rates (solve rate, survival rate, solves/1k tokens) are recombined as a
  ratio of summed counts across matchups, never as a mean of each matchup's
  own percentage. A matchup with 2 comparable rounds and a matchup with 100
  comparable rounds do not carry equal statistical weight; averaging their
  percentages lets the small matchup dominate (see
  `tests/test_tournament_view_models.py` for a fixture proving this).
- Latency and guesses-to-solve are recombined as weighted means, using each
  contributing matchup's own count (`rounds_completed` / `rounds_solved`) as
  the weight. This is an exact reconstruction of the pooled mean from
  per-matchup means and counts. Medians are NOT recombined this way -- a
  "median of medians" is not a valid reconstruction of the true pooled
  median without the raw per-round data, so no weighted-median column is
  offered here.
- Cost is summed only when every contributing matchup's cost for that
  role/scope is known (`MatchupSummary.attacker_estimated_cost` /
  `defender_estimated_cost` / `total_estimated_cost`, each already `None`
  rather than `0.0` when unknown, per `tournament.py::aggregate_matchup`).
  If any contributor is unknown, the rollup is `None` -- never silently
  summed as if the unknown contributors were zero.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from password_arena.models import MatchupConfig, MatchupSummary
from password_arena.providers import ThinkingLevel


class MatchupLike(Protocol):
    """Structural type satisfied by both `MatchupResult` and `StoredMatchup` --
    the two concrete types the Tournament dashboard renders results from. Only
    the attributes the view layer actually touches are required. Declared as
    read-only properties (not plain attributes) so frozen dataclasses -- whose
    fields mypy treats as read-only -- satisfy this protocol structurally."""

    @property
    def config(self) -> MatchupConfig: ...

    @property
    def summary(self) -> MatchupSummary: ...

    @property
    def is_comparable(self) -> bool: ...


def _role_label(provider: str, model: str | None, thinking_level: ThinkingLevel) -> str:
    return f"{provider} ({model or '-'}) [{thinking_level.value}]"


def _weighted_mean(pairs: Sequence[tuple[float | None, float]]) -> float | None:
    """Reconstruct a pooled mean from (per-group mean, per-group weight) pairs.
    Groups whose mean is None (no observations) are skipped entirely -- their
    absence is not the same as a weight-zero contribution of value 0."""
    total_weight = 0.0
    weighted_sum = 0.0
    for value, weight in pairs:
        if value is None or weight <= 0:
            continue
        weighted_sum += value * weight
        total_weight += weight
    return weighted_sum / total_weight if total_weight > 0 else None


def _sum_known_or_none(values: Sequence[float | None]) -> float | None:
    """Sum values that are all known; None if any single one is unknown --
    unknown cost/etc. is never treated as zero when combined with known
    values. An empty sequence is treated as no data (None), not a known zero."""
    if not values:
        return None
    total = 0.0
    for v in values:
        if v is None:
            return None
        total += v
    return total


def aggregate_tournament_cost(results: Sequence[MatchupLike]) -> float | None:
    """Sum of `total_estimated_cost` across the given matchups. None if ANY
    matchup's cost is unknown -- unknown cost is never treated as zero cost
    (fixes BUG-017, where the Overview previously used `any()`/`or 0.0` and
    silently understated the total)."""
    return _sum_known_or_none([r.summary.total_estimated_cost for r in results])


@dataclass(frozen=True, slots=True)
class OverviewData:
    comparable_rounds: int
    total_solved: int
    total_resisted: int
    solve_rate: float | None
    survival_rate: float | None
    total_tokens: int
    total_cost: float | None
    interrupted_trials: int


def build_overview(results: Sequence[MatchupLike]) -> OverviewData:
    """Headline tournament totals. Restricted to comparable matchups, matching
    the same "comparable-only by default" convention as core's per-matchup
    statistics -- except `interrupted_trials`, which intentionally counts
    across ALL matchups (including fully non-comparable ones), since that is
    precisely the count of what got excluded and why."""
    comparable = [r for r in results if r.is_comparable]

    comparable_rounds = sum(r.summary.rounds_completed for r in comparable)
    total_solved = sum(r.summary.rounds_solved for r in comparable)
    total_resisted = sum(r.summary.rounds_resisted for r in comparable)
    total_tokens = sum(
        r.summary.attacker_input_tokens
        + r.summary.attacker_output_tokens
        + r.summary.defender_input_tokens
        + r.summary.defender_output_tokens
        for r in comparable
    )
    interrupted_trials = sum(r.summary.excluded_trials for r in results)

    return OverviewData(
        comparable_rounds=comparable_rounds,
        total_solved=total_solved,
        total_resisted=total_resisted,
        solve_rate=total_solved / comparable_rounds if comparable_rounds > 0 else None,
        survival_rate=total_resisted / comparable_rounds if comparable_rounds > 0 else None,
        total_tokens=total_tokens,
        total_cost=aggregate_tournament_cost(comparable),
        interrupted_trials=interrupted_trials,
    )


def build_attacker_leaderboard(results: Sequence[MatchupLike]) -> pd.DataFrame:
    """One row per unique attacker identity (provider/model/thinking level),
    aggregated across every matchup that attacker played, comparable matchups
    only. See module docstring for the weighting rules."""
    groups: dict[str, list[MatchupLike]] = defaultdict(list)
    for r in results:
        if not r.is_comparable:
            continue
        att = r.config.attacker
        groups[_role_label(att.provider, att.model, att.thinking_level)].append(r)

    rows = []
    for name, matchups in groups.items():
        rounds_completed = sum(m.summary.rounds_completed for m in matchups)
        rounds_solved = sum(m.summary.rounds_solved for m in matchups)
        tokens = sum(
            m.summary.attacker_input_tokens + m.summary.attacker_output_tokens
            for m in matchups
        )
        solve_rate = rounds_solved / rounds_completed if rounds_completed > 0 else None
        solves_per_1k_tokens = rounds_solved / (tokens / 1000) if tokens > 0 else None
        latency_ms = _weighted_mean(
            [(m.summary.attacker_mean_latency_ms, m.summary.rounds_completed) for m in matchups]
        )
        guesses_to_solve = _weighted_mean(
            [(m.summary.mean_guesses_to_solve, m.summary.rounds_solved) for m in matchups]
        )
        cost = _sum_known_or_none([m.summary.attacker_estimated_cost for m in matchups])

        rows.append(
            {
                "Attacker": name,
                "Solve Rate": solve_rate,
                "Comparable Rounds": rounds_completed,
                "Tokens": tokens,
                "Cost": cost,
                "Solves/1K Tokens": solves_per_1k_tokens,
                "Latency ms": latency_ms,
                "Guesses to Solve (weighted mean)": guesses_to_solve,
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Solve Rate", ascending=False, na_position="last")
    return df


def build_defender_leaderboard(results: Sequence[MatchupLike]) -> pd.DataFrame:
    """Mirror of `build_attacker_leaderboard` for defenders. Includes a Cost
    column (the original heatmap/leaderboard had none for defenders at all,
    silently attributing all matchup spend to the attacker -- BUG-018)."""
    groups: dict[str, list[MatchupLike]] = defaultdict(list)
    for r in results:
        if not r.is_comparable:
            continue
        dfd = r.config.defender
        groups[_role_label(dfd.provider, dfd.model, dfd.thinking_level)].append(r)

    rows = []
    for name, matchups in groups.items():
        rounds_completed = sum(m.summary.rounds_completed for m in matchups)
        rounds_resisted = sum(m.summary.rounds_resisted for m in matchups)
        tokens = sum(
            m.summary.defender_input_tokens + m.summary.defender_output_tokens
            for m in matchups
        )
        survival_rate = rounds_resisted / rounds_completed if rounds_completed > 0 else None
        survivals_per_1k_tokens = rounds_resisted / (tokens / 1000) if tokens > 0 else None
        latency_ms = _weighted_mean(
            [(m.summary.defender_mean_latency_ms, m.summary.rounds_completed) for m in matchups]
        )
        cost = _sum_known_or_none([m.summary.defender_estimated_cost for m in matchups])

        rows.append(
            {
                "Defender": name,
                "Survival Rate": survival_rate,
                "Comparable Rounds": rounds_completed,
                "Tokens": tokens,
                "Cost": cost,
                "Survivals/1K Tokens": survivals_per_1k_tokens,
                "Latency ms": latency_ms,
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Survival Rate", ascending=False, na_position="last")
    return df


HEATMAP_METRICS = (
    "Solve Rate",
    "Survival Rate",
    "Median Guesses to Solve",
    "Combined attacker+defender latency (ms)",
    "Combined attacker+defender tokens",
    "Cost",
)


def build_heatmap_data(results: Sequence[MatchupLike], metric: str) -> pd.DataFrame:
    """One row per comparable matchup. `metric` must be one of
    `HEATMAP_METRICS`. Combined attacker+defender metrics are explicitly
    labeled as combined (BUG-020) -- never presented under an ambiguous
    "Latency ms"/"Tokens" label. Every row carries the full tooltip payload
    (roles, models, thinking levels, comparable/excluded rounds, trials,
    interruptions, confidence interval) so the heatmap does not rely on color
    alone."""
    if metric not in HEATMAP_METRICS:
        raise ValueError(f"Unknown heatmap metric: {metric!r}")

    rows = []
    for r in results:
        if not r.is_comparable:
            continue
        att = r.config.attacker
        dfd = r.config.defender
        s = r.summary

        val: float | None = None
        if metric == "Solve Rate":
            val = s.solve_rate
        elif metric == "Survival Rate":
            val = s.survival_rate
        elif metric == "Median Guesses to Solve":
            val = s.median_guesses_to_solve
        elif metric == "Combined attacker+defender latency (ms)":
            if s.attacker_mean_latency_ms is not None and s.defender_mean_latency_ms is not None:
                val = s.attacker_mean_latency_ms + s.defender_mean_latency_ms
        elif metric == "Combined attacker+defender tokens":
            val = (
                s.attacker_input_tokens
                + s.attacker_output_tokens
                + s.defender_input_tokens
                + s.defender_output_tokens
            )
        elif metric == "Cost":
            val = s.total_estimated_cost

        rows.append(
            {
                "Attacker": _role_label(att.provider, att.model, att.thinking_level),
                "Defender": _role_label(dfd.provider, dfd.model, dfd.thinking_level),
                "Value": val,
                "AttackerProvider": att.provider,
                "AttackerModel": att.model or "-",
                "AttackerThinking": att.thinking_level.value,
                "DefenderProvider": dfd.provider,
                "DefenderModel": dfd.model or "-",
                "DefenderThinking": dfd.thinking_level.value,
                "Trials": s.comparable_trials,
                "ComparableRounds": s.rounds_completed,
                "ExcludedRounds": s.excluded_rounds,
                "ExcludedTrials": s.excluded_trials,
                "CILower": s.confidence_interval_lower,
                "CIUpper": s.confidence_interval_upper,
            }
        )

    return pd.DataFrame(rows)


def build_efficiency_data(results: Sequence[MatchupLike]) -> pd.DataFrame:
    """One row per comparable matchup. Missing latency/cost stay `None` --
    never fabricated as 0 just to satisfy a chart library."""
    rows = []
    for r in results:
        if not r.is_comparable:
            continue
        att = r.config.attacker
        dfd = r.config.defender
        s = r.summary

        latency: float | None = None
        if s.attacker_mean_latency_ms is not None and s.defender_mean_latency_ms is not None:
            latency = s.attacker_mean_latency_ms + s.defender_mean_latency_ms

        rows.append(
            {
                "Matchup": f"{att.provider}:{att.model} vs {dfd.provider}:{dfd.model}",
                "Solve Rate": s.solve_rate,
                "Survival Rate": s.survival_rate,
                "Attacker Tokens": s.attacker_input_tokens + s.attacker_output_tokens,
                "Defender Tokens": s.defender_input_tokens + s.defender_output_tokens,
                "Cost": s.total_estimated_cost,
                "Attacker Cost": s.attacker_estimated_cost,
                "Defender Cost": s.defender_estimated_cost,
                "Combined Latency ms": latency,
            }
        )

    return pd.DataFrame(rows)


def build_thinking_comparison_data(
    results: Sequence[MatchupLike],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Weighted per-thinking-level rollups, split by model, for every model
    tested at more than one thinking level. Returns (attacker_df, defender_df),
    each with one row per (Model, Thinking) pair, weighted the same way as the
    leaderboards -- not an unweighted mean of per-matchup percentages."""
    attacker_groups: dict[tuple[str, str], list[MatchupLike]] = defaultdict(list)
    defender_groups: dict[tuple[str, str], list[MatchupLike]] = defaultdict(list)
    attacker_models: dict[str, set[str]] = defaultdict(set)
    defender_models: dict[str, set[str]] = defaultdict(set)

    for r in results:
        if not r.is_comparable:
            continue
        att = r.config.attacker
        att_model = f"{att.provider}:{att.model}"
        attacker_groups[(att_model, att.thinking_level.value)].append(r)
        attacker_models[att_model].add(att.thinking_level.value)

        dfd = r.config.defender
        dfd_model = f"{dfd.provider}:{dfd.model}"
        defender_groups[(dfd_model, dfd.thinking_level.value)].append(r)
        defender_models[dfd_model].add(dfd.thinking_level.value)

    def _rows(
        groups: dict[tuple[str, str], list[MatchupLike]],
        multi_level_models: set[str],
        *,
        is_attacker: bool,
    ) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for (model, thinking), matchups in groups.items():
            if model not in multi_level_models:
                continue
            rounds_completed = sum(m.summary.rounds_completed for m in matchups)
            if is_attacker:
                solved_or_resisted = sum(m.summary.rounds_solved for m in matchups)
                tokens = sum(
                    m.summary.attacker_input_tokens + m.summary.attacker_output_tokens
                    for m in matchups
                )
                latency = _weighted_mean(
                    [
                        (m.summary.attacker_mean_latency_ms, m.summary.rounds_completed)
                        for m in matchups
                    ]
                )
                rate_key = "Solve Rate"
            else:
                solved_or_resisted = sum(m.summary.rounds_resisted for m in matchups)
                tokens = sum(
                    m.summary.defender_input_tokens + m.summary.defender_output_tokens
                    for m in matchups
                )
                latency = _weighted_mean(
                    [
                        (m.summary.defender_mean_latency_ms, m.summary.rounds_completed)
                        for m in matchups
                    ]
                )
                rate_key = "Survival Rate"

            rate = solved_or_resisted / rounds_completed if rounds_completed > 0 else None
            out.append(
                {
                    "Model": model,
                    "Thinking": thinking,
                    rate_key: rate,
                    "Latency ms": latency,
                    "Tokens": tokens,
                    "Comparable Rounds": rounds_completed,
                }
            )
        return out

    multi_att = {m for m, levels in attacker_models.items() if len(levels) > 1}
    multi_dfd = {m for m, levels in defender_models.items() if len(levels) > 1}

    att_df = pd.DataFrame(_rows(attacker_groups, multi_att, is_attacker=True))
    dfd_df = pd.DataFrame(_rows(defender_groups, multi_dfd, is_attacker=False))
    return att_df, dfd_df
