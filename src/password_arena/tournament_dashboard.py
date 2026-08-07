import time

import pandas as pd
import streamlit as st

from password_arena.models import RoleConfig, TournamentConfig
from password_arena.providers import ThinkingLevel
from password_arena.tournament import build_tournament_matrix, run_matchup


def _build_role(provider: str, model: str | None = None) -> RoleConfig:
    return RoleConfig(provider=provider, model=model, thinking_level=ThinkingLevel.AUTO)


def render_tournament_tab() -> None:
    st.header("Tournament Configuration")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Select Attackers")
        attackers = []
        if st.checkbox("Rule-based Attacker", value=True, key="att_rule"):
            attackers.append(_build_role("rule_based"))
        if st.checkbox("Gemini 2.5 Pro", key="att_gemini"):
            attackers.append(_build_role("gemini", "gemini-2.5-pro"))
        if st.checkbox("OpenAI GPT-4o", key="att_openai"):
            attackers.append(_build_role("openai", "gpt-4o"))
        if st.checkbox("Anthropic Claude 3.5 Sonnet", key="att_anthropic"):
            attackers.append(_build_role("anthropic", "claude-3-5-sonnet-20241022"))

    with col2:
        st.subheader("Select Defenders")
        defenders = []
        if st.checkbox("Rule-based Defender", value=True, key="def_rule"):
            defenders.append(_build_role("rule_based"))
        if st.checkbox("Gemini 2.5 Pro", key="def_gemini"):
            defenders.append(_build_role("gemini", "gemini-2.5-pro"))
        if st.checkbox("OpenAI GPT-4o", key="def_openai"):
            defenders.append(_build_role("openai", "gpt-4o"))
        if st.checkbox("Anthropic Claude 3.5 Sonnet", key="def_anthropic"):
            defenders.append(_build_role("anthropic", "claude-3-5-sonnet-20241022"))

    st.divider()

    c1, c2, c3 = st.columns(3)
    with c1:
        rounds_per_match = st.number_input("Rounds per Matchup", min_value=1, value=5)
    with c2:
        trials_count = st.number_input("Repeated Trials (Seeds)", min_value=1, value=3)
    with c3:
        max_guesses = st.number_input("Max Guesses", min_value=1, max_value=5000, value=100)

    exclude_self = st.checkbox("Exclude self-play matchups (e.g. GPT vs GPT)", value=True)

    run_disabled = len(attackers) == 0 or len(defenders) == 0
    if run_disabled:
        st.warning("Select at least one attacker and one defender.")

    if st.button("Run Tournament", type="primary", disabled=run_disabled):
        seeds = tuple(42 + i for i in range(int(trials_count)))
        config = TournamentConfig(
            attackers=tuple(attackers),
            defenders=tuple(defenders),
            seeds=seeds,
            rounds_per_match=int(rounds_per_match),
            max_guesses=int(max_guesses),
        )

        matrix = build_tournament_matrix(config, exclude_self=exclude_self)

        if not matrix:
            st.error("No valid matchups generated (perhaps only self-play was selected).")
            return

        st.info(
            f"Running {len(matrix)} matchups ({len(matrix) * trials_count} total experiments)..."
        )

        progress_bar = st.progress(0)
        status_text = st.empty()

        results = []
        for i, matchup in enumerate(matrix):
            status_text.text(
                f"Running Matchup {i + 1}/{len(matrix)}: "
                f"{matchup.attacker.provider} vs {matchup.defender.provider}..."
            )
            res = run_matchup(matchup)
            results.append(res)
            progress_bar.progress((i + 1) / len(matrix))
            time.sleep(0.1)

        status_text.text("Tournament complete.")

        # Build Results DataFrame
        data = []
        for r in results:
            att = f"{r.config.attacker.provider}" + (
                f" ({r.config.attacker.model})" if r.config.attacker.model else ""
            )
            dfd = f"{r.config.defender.provider}" + (
                f" ({r.config.defender.model})" if r.config.defender.model else ""
            )
            row = {
                "Attacker": att,
                "Defender": dfd,
                "Solve Rate": f"{r.summary.solve_rate * 100:.1f}%",
                "Mean Guesses": f"{r.summary.mean_guesses:.1f}"
                if r.summary.mean_guesses is not None
                else "-",
                "Completed Trials": f"{r.summary.completed_trials}/{r.summary.trials}",
                "Status": "OK" if r.is_comparable else f"WARN: {r.non_comparable_reason}",
            }
            data.append(row)

        df = pd.DataFrame(data)
        st.subheader("Tournament Results")
        st.dataframe(df, use_container_width=True)
