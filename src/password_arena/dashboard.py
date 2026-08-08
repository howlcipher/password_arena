from __future__ import annotations

import json
import re
from dataclasses import asdict

import altair as alt
import pandas as pd
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

from password_arena.engine import PreflightFailure, build_arena_engine
from password_arena.models import ArenaConfig
from password_arena.reporting import experiment_report_markdown
from password_arena.tournament_dashboard import render_tournament_tab
from password_arena.ui_helpers import render_role_config


def render_arena_tab() -> None:
    st.set_page_config(page_title="Password Arena", page_icon="🛡️", layout="wide")
    st.title("Password Arena")
    st.caption(
        "A safe, local attacker-versus-defender learning sandbox using synthetic passwords only."
    )

    default_values = {
        "rounds": 8,
        "start_difficulty": 1,
        "difficulty_step": 1,
        "max_guesses": 5000,
        "seed": 42,
        "reveal_passwords": False,
        "defender_provider": "rule_based",
        "defender_model": "",
        "defender_thinking": "auto",
        "attacker_provider": "rule_based",
        "attacker_model": "",
        "attacker_thinking": "auto",
    }
    for k, v in default_values.items():
        if k not in st.session_state:
            st.session_state[k] = v

    with st.sidebar:
        st.header("Experiment")
        rounds = st.slider("Rounds", 1, 30, key="rounds")
        start_difficulty = st.slider("Starting difficulty", 1, 10, key="start_difficulty")
        difficulty_step = st.slider("Difficulty increase per round", 0, 3, key="difficulty_step")
        max_guesses = st.number_input(
            "Maximum guesses per round", 10, 100_000, key="max_guesses", step=100
        )
        seed = st.number_input("Seed", 0, 1_000_000, key="seed")
        reveal_passwords = st.toggle("Reveal synthetic passwords", key="reveal_passwords")

        st.divider()
        st.header("Roles")

        defender_config = render_role_config(
            prefix="defender",
            label="Defender",
            default_provider=st.session_state.get("defender_provider", "rule_based"),
            default_model=st.session_state.get("defender_model", ""),
            default_thinking=st.session_state.get("defender_thinking", "auto"),
        )
        
        attacker_config = render_role_config(
            prefix="attacker",
            label="Attacker",
            default_provider=st.session_state.get("attacker_provider", "rule_based"),
            default_model=st.session_state.get("attacker_model", ""),
            default_thinking=st.session_state.get("attacker_thinking", "auto"),
        )

        st.divider()
        st.header("Profiles")

        uploaded_file = st.file_uploader("Load profile", type=["json"])
        if uploaded_file is not None:
            try:
                profile_data = json.load(uploaded_file)
                for k in default_values:
                    if k in profile_data:
                        st.session_state[k] = profile_data[k]
                
                # Delete internal UI helper keys so they re-initialize from default_values
                for k in list(st.session_state.keys()):
                    is_ui_key = (
                        k.endswith("_model_select")
                        or k.endswith("_model_input")
                        or k.endswith("_thinking")
                    )
                    if is_ui_key and k not in ["defender_thinking", "attacker_thinking"]:
                        del st.session_state[k]
                            
                st.success("Profile loaded! Settings applied.")
            except Exception as e:
                st.error(f"Failed to load profile: {e}")

        profile_name = st.text_input("Save profile as", "my_profile")

        config = ArenaConfig(
            rounds=int(rounds),
            start_difficulty=int(start_difficulty),
            difficulty_step=int(difficulty_step),
            max_guesses=int(max_guesses),
            seed=int(seed),
            reveal_passwords=reveal_passwords,
            defender_config=defender_config,
            attacker_config=attacker_config,
        )

        safe_name = re.sub(r"[^A-Za-z0-9_-]", "", profile_name) or "profile"
        st.download_button(
            "Save profile",
            data=json.dumps(asdict(config), indent=2),
            file_name=f"{safe_name}.json",
            mime="application/json",
        )

        st.divider()

        # Preflight check
        result = build_arena_engine(config)
        run_disabled = False
        if isinstance(result, PreflightFailure):
            st.error(f"Preflight failed for {result.role}: {result.message} ({result.state})")
            run_disabled = True

        run = st.button(
            "Run arena", type="primary", use_container_width=True, disabled=run_disabled
        )

    if run and not isinstance(result, PreflightFailure):
        st.session_state.experiment = result.run()

    if "experiment" not in st.session_state or st.session_state.experiment is None:
        if not run_disabled:
            st.info("Choose the experiment controls and run the arena.")
        st.stop()

    if isinstance(result, PreflightFailure) and run:
        st.stop()  # sanity check

    experiment = st.session_state.experiment
    if experiment.interruption_reason:
        st.error(
            f"Experiment paused early due to provider error ({experiment.interruption_state}): "
            f"{experiment.interruption_reason}"
        )
        if not experiment.rounds:
            st.warning("No rounds were completed.")
            st.stop()

    rows = []
    for item in experiment.rounds:
        rows.append(
            {
                "Round": item.round_number,
                "Difficulty": item.difficulty,
                "Password": item.password_display,
                "Length": item.password_length,
                "Entropy bits": item.strength.entropy_bits,
                "Strength score": item.strength.score,
                "Solved": item.attack.solved,
                "Outcome": item.attack.outcome.value,
                "Guesses": item.attack.guesses_used,
                "Winning strategy": item.attack.winning_strategy,
                "Defender strategy": item.defender_strategy,
                "Elapsed ms": round(item.attack.elapsed_ms, 3),
            }
        )
    frame = pd.DataFrame(rows)

    allocation_rows = []
    for item in experiment.rounds:
        for plan in item.attack.plan:
            allocation_rows.append(
                {
                    "Round": item.round_number,
                    "Strategy": plan.strategy,
                    "Budget allocation (%)": plan.weight * 100,
                    "Guesses budgeted": plan.guess_budget,
                    "Efficiency": (
                        (item.strength.entropy_bits / max(1, item.attack.guesses_used)) * 1000
                        if item.attack.solved and item.attack.winning_strategy == plan.strategy
                        else 0.0
                    ),
                }
            )
    allocation_frame = pd.DataFrame(allocation_rows) if allocation_rows else pd.DataFrame()

    st.subheader("Results Filter")
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
    with filter_col1:
        if not frame.empty:
            min_round, max_round = int(frame["Round"].min()), int(frame["Round"].max())
            if min_round < max_round:
                selected_rounds = st.slider(
                    "Round range", min_round, max_round, (min_round, max_round)
                )
            else:
                selected_rounds = (min_round, max_round)
                st.write(f"Round: {min_round}")
        else:
            selected_rounds = (0, 0)

    with filter_col2:
        if not frame.empty:
            families = ["All"] + sorted(list(frame["Defender strategy"].unique()))
        else:
            families = ["All"]
        selected_family = st.selectbox("Defender family", families)

    with filter_col3:
        outcomes = ["All"] + sorted(list(frame["Outcome"].unique())) if not frame.empty else ["All"]
        selected_outcome = st.selectbox("Outcome", outcomes)

    with filter_col4:
        if not frame.empty:
            strategies_list = [s for s in frame["Winning strategy"].unique() if s is not None]
            strategies = ["All"] + sorted(list(strategies_list))
        else:
            strategies = ["All"]
        selected_strategy = st.selectbox("Winning strategy", strategies)

    # Apply filters
    if not frame.empty:
        filtered_frame = frame[
            (frame["Round"] >= selected_rounds[0]) & (frame["Round"] <= selected_rounds[1])
        ]
        if selected_family != "All":
            filtered_frame = filtered_frame[filtered_frame["Defender strategy"] == selected_family]
        if selected_outcome != "All":
            filtered_frame = filtered_frame[filtered_frame["Outcome"] == selected_outcome]
        if selected_strategy != "All":
            filtered_frame = filtered_frame[filtered_frame["Winning strategy"] == selected_strategy]
    else:
        filtered_frame = frame

    st.subheader("Summary")
    col1, col2, col3, col4 = st.columns(4)
    solve_rate = filtered_frame["Solved"].mean() if not filtered_frame.empty else 0.0
    solved_count = filtered_frame["Solved"].sum() if not filtered_frame.empty else 0
    col1.metric("Solve rate", f"{solve_rate:.0%}")
    total_count = len(filtered_frame) if not filtered_frame.empty else 0
    col2.metric("Rounds solved", f"{solved_count}/{total_count}")
    final_entropy = filtered_frame.iloc[-1]["Entropy bits"] if not filtered_frame.empty else 0.0
    col3.metric("Final entropy", f"{final_entropy:.1f} bits")
    total_guesses = int(filtered_frame["Guesses"].sum()) if not filtered_frame.empty else 0
    col4.metric("Total guesses", f"{total_guesses:,}")

    st.subheader("Learning curves")
    if not filtered_frame.empty:
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.caption("Entropy progression")
            entropy_chart = (
                alt.Chart(filtered_frame)
                .mark_line(point=True)
                .encode(
                    x="Round:O",
                    y="Entropy bits:Q",
                    tooltip=["Round", "Entropy bits", "Defender strategy"],
                )
                .interactive()
            )
            st.altair_chart(entropy_chart, use_container_width=True)
        with chart_col2:
            st.caption("Guesses consumed")
            # Use symlog to handle zero and small values while scaling nicely for large budgets
            guess_chart = (
                alt.Chart(filtered_frame)
                .mark_line(point=True, color="red")
                .encode(
                    x="Round:O",
                    y=alt.Y("Guesses:Q", scale=alt.Scale(type="symlog")),
                    tooltip=["Round", "Guesses", "Winning strategy"],
                )
                .interactive()
            )
            st.altair_chart(guess_chart, use_container_width=True)

    if not allocation_frame.empty:
        st.subheader("Strategy Allocation & Efficiency")
        alloc_col1, alloc_col2 = st.columns(2)
        filtered_alloc = allocation_frame[
            (allocation_frame["Round"] >= selected_rounds[0])
            & (allocation_frame["Round"] <= selected_rounds[1])
        ]
        with alloc_col1:
            st.caption("Strategy Allocation (%)")
            alloc_chart = (
                alt.Chart(filtered_alloc)
                .mark_area()
                .encode(
                    x="Round:O",
                    y="Budget allocation (%):Q",
                    color="Strategy:N",
                    tooltip=["Round", "Strategy", "Budget allocation (%)"],
                )
                .interactive()
            )
            st.altair_chart(alloc_chart, use_container_width=True)
        with alloc_col2:
            st.caption("Efficiency (Bits solved per 1,000 actual guesses)")
            eff_chart = (
                alt.Chart(filtered_alloc)
                .mark_line(point=True)
                .encode(
                    x="Round:O",
                    y="Efficiency:Q",
                    color="Strategy:N",
                    tooltip=["Round", "Strategy", "Efficiency"],
                )
                .interactive()
            )
            st.altair_chart(eff_chart, use_container_width=True)

    st.subheader("Round results")
    st.dataframe(filtered_frame, use_container_width=True, hide_index=True)

    st.subheader("Arena journal")
    st.caption(
        "Each entry is assembled from recorded actions, budget allocations, "
        "observations, and state updates—not hidden chain-of-thought."
    )
    for item in experiment.rounds:
        status = "Solved" if item.attack.solved else "Resisted"
        with st.expander(f"Round {item.round_number} · {status} · Level {item.difficulty}"):
            defender_col, attacker_col = st.columns(2)
            with defender_col:
                st.markdown("### 🛡️ Defender")
                st.markdown(f"**Decision:** {item.report.defender.decision}")
                for action in item.report.defender.actions:
                    st.markdown(f"- {action}")
                st.markdown(f"**Observed:** {item.report.defender.observation}")
                st.markdown(f"**Learning update:** {item.report.defender.learning_update}")

            with attacker_col:
                st.markdown("### ⚔️ Attacker")
                st.markdown(f"**Decision:** {item.report.attacker.decision}")
                plan_frame = pd.DataFrame(
                    [
                        {
                            "Strategy": plan.strategy,
                            "Weight": f"{plan.weight:.1%}",
                            "Guess budget": plan.guess_budget,
                        }
                        for plan in item.attack.plan
                    ]
                )
                st.dataframe(plan_frame, use_container_width=True, hide_index=True)
                st.markdown(f"**Observed:** {item.report.attacker.observation}")
                st.markdown(f"**Learning update:** {item.report.attacker.learning_update}")

            st.markdown("### Evaluator")
            st.write(item.report.evaluator_summary)
            st.info(item.report.security_lesson)

    json_data = json.dumps(experiment.to_dict(), indent=2)
    markdown_data = experiment_report_markdown(experiment)
    download_json, download_report = st.columns(2)
    with download_json:
        st.download_button(
            "Download experiment JSON",
            data=json_data,
            file_name="password-arena-results.json",
            mime="application/json",
            use_container_width=True,
        )
    with download_report:
        st.download_button(
            "Download arena report",
            data=markdown_data,
            file_name="password-arena-report.md",
            mime="text/markdown",
            use_container_width=True,
        )

    st.warning(
        "Password Arena is an educational simulation. Never enter real credentials or connect "
        "the guessing engine to an authentication system."
    )


def render_dashboard() -> None:
    st.set_page_config(
        page_title="Password Arena", page_icon="🔐", layout="wide", initial_sidebar_state="expanded"
    )
    st.title("Password Arena")

    tab1, tab2 = st.tabs(["Arena", "Tournament"])
    with tab1:
        render_arena_tab()
    with tab2:
        render_tournament_tab()


if __name__ == "__main__" or get_script_run_ctx() is not None:
    render_dashboard()
