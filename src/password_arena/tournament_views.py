"""Streamlit/Altair rendering only. All aggregation, weighting, and "unknown is
not zero" logic lives in `tournament_view_models.py` -- this module must not
recreate or weaken any of it; it only renders already-correct data."""

import altair as alt
import streamlit as st

from password_arena.tournament_view_models import (
    HEATMAP_METRICS,
    build_attacker_leaderboard,
    build_defender_leaderboard,
    build_efficiency_data,
    build_heatmap_data,
    build_overview,
    build_thinking_comparison_data,
)


def _rate_display(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.1f}%"


def _cost_display(value: float | None) -> str:
    return "unavailable" if value is None else f"${value:.4f}"


def render_overview(results: list) -> None:
    st.subheader("Tournament Overview")

    overview = build_overview(results)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Comparable Rounds", f"{overview.comparable_rounds}")
        st.metric("Total Tokens", f"{overview.total_tokens:,}")
    with c2:
        st.metric("Solve Rate", _rate_display(overview.solve_rate))
        st.metric("Estimated Cost", _cost_display(overview.total_cost))
    with c3:
        st.metric("Survival Rate", _rate_display(overview.survival_rate))
    with c4:
        st.metric("Interruptions", f"{overview.interrupted_trials}")

    if overview.total_cost is None:
        st.caption(
            "Estimated cost is unavailable because at least one comparable matchup "
            "used a provider without cost metadata -- unknown cost is never shown as $0."
        )


def render_leaderboards(results: list) -> None:
    st.subheader("Leaderboards")
    st.caption(
        "Rates are aggregated as sum(events) / sum(comparable rounds) across each "
        "model's matchups, not an unweighted average of each matchup's own "
        "percentage -- a matchup with few comparable rounds does not carry the "
        "same statistical weight as one with many."
    )

    att_df = build_attacker_leaderboard(results)
    if not att_df.empty:
        st.markdown("**Top Attackers**")
        st.dataframe(att_df, use_container_width=True, hide_index=True)

    def_df = build_defender_leaderboard(results)
    if not def_df.empty:
        st.markdown("**Top Defenders**")
        st.dataframe(def_df, use_container_width=True, hide_index=True)


def render_heatmap(results: list) -> None:
    st.subheader("Matchup Matrix")

    metric = st.selectbox("Metric", list(HEATMAP_METRICS))

    df = build_heatmap_data(results, metric)
    if df.empty:
        st.warning("No comparable data to display heatmap.")
        return

    tooltip = [
        "Attacker",
        "Defender",
        "Value",
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
    ]

    base = alt.Chart(df).encode(
        x=alt.X("Defender:O", title="Defender"),
        y=alt.Y("Attacker:O", title="Attacker"),
    )
    cells = base.mark_rect().encode(
        color=alt.Color("Value:Q", title=metric, scale=alt.Scale(scheme="viridis")),
        tooltip=tooltip,
    )
    # Visible value text on every cell -- the heatmap must not rely on color
    # alone to convey the metric.
    labels = base.mark_text(baseline="middle").encode(
        text=alt.Text("Value:Q", format=".2f"),
        color=alt.value("white"),
    )

    st.altair_chart((cells + labels).properties(height=400), use_container_width=True)


def render_efficiency(results: list) -> None:
    st.subheader("Efficiency")

    df = build_efficiency_data(results)
    if df.empty:
        return

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Solve Rate vs Cost**")
        if df["Cost"].notna().any():
            chart = (
                alt.Chart(df.dropna(subset=["Cost"]))
                .mark_circle(size=60)
                .encode(x="Cost:Q", y="Solve Rate:Q", tooltip=["Matchup", "Solve Rate", "Cost"])
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No cost data available.")

    with c2:
        st.markdown("**Solve Rate vs Tokens**")
        chart = (
            alt.Chart(df)
            .mark_circle(size=60)
            .encode(
                x="Attacker Tokens:Q",
                y="Solve Rate:Q",
                tooltip=["Matchup", "Solve Rate", "Attacker Tokens"],
            )
        )
        st.altair_chart(chart, use_container_width=True)


def render_thinking_comparison(results: list) -> None:
    st.subheader("Thinking-Level Comparison")

    att_df, dfd_df = build_thinking_comparison_data(results)
    if att_df.empty and dfd_df.empty:
        st.info("No models with multiple thinking levels were tested.")
        return

    for model in sorted(set(att_df["Model"]) | set(dfd_df["Model"])):
        st.markdown(f"**Model: {model}**")
        c1, c2 = st.columns(2)
        with c1:
            model_att = att_df[att_df["Model"] == model] if not att_df.empty else att_df
            if not model_att.empty:
                st.markdown("*As Attacker*")
                st.dataframe(model_att, hide_index=True, use_container_width=True)
                chart = (
                    alt.Chart(model_att)
                    .mark_bar()
                    .encode(x="Thinking:O", y="Solve Rate:Q", color="Thinking:N")
                )
                st.altair_chart(chart, use_container_width=True)

        with c2:
            model_dfd = dfd_df[dfd_df["Model"] == model] if not dfd_df.empty else dfd_df
            if not model_dfd.empty:
                st.markdown("*As Defender*")
                st.dataframe(model_dfd, hide_index=True, use_container_width=True)
                chart = (
                    alt.Chart(model_dfd)
                    .mark_bar()
                    .encode(x="Thinking:O", y="Survival Rate:Q", color="Thinking:N")
                )
                st.altair_chart(chart, use_container_width=True)
