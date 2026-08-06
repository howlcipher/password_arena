from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import streamlit as st

from password_arena.engine import PreflightFailure, build_arena_engine
from password_arena.models import ArenaConfig, RoleConfig
from password_arena.providers import ThinkingLevel
from password_arena.reporting import experiment_report_markdown

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
    
    providers = ["rule_based", "gemini", "ollama"]
    thinkings = ["auto", "minimal", "low", "medium", "high", "maximum"]

    st.subheader("Defender")
    def_prov = st.selectbox(
        "Provider",
        providers,
        index=providers.index(st.session_state["defender_provider"]),
        key="def_prov",
    )
    st.session_state["defender_provider"] = def_prov
    if def_prov != "rule_based":
        st.session_state["defender_model"] = st.text_input(
            "Model ID", st.session_state["defender_model"], key="def_mod"
        )
        st.session_state["defender_thinking"] = st.selectbox(
            "Thinking level",
            thinkings,
            index=thinkings.index(st.session_state["defender_thinking"]),
            key="def_think",
        )

    st.subheader("Attacker")
    att_prov = st.selectbox(
        "Provider",
        providers,
        index=providers.index(st.session_state["attacker_provider"]),
        key="att_prov",
    )
    st.session_state["attacker_provider"] = att_prov
    if att_prov != "rule_based":
        st.session_state["attacker_model"] = st.text_input(
            "Model ID", st.session_state["attacker_model"], key="att_mod"
        )
        st.session_state["attacker_thinking"] = st.selectbox(
            "Thinking level",
            thinkings,
            index=thinkings.index(st.session_state["attacker_thinking"]),
            key="att_think",
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
            st.success("Profile loaded! Settings applied.")
        except Exception as e:
            st.error(f"Failed to load profile: {e}")

    profile_name = st.text_input("Save profile as", "my_profile")
    if st.button("Save profile"):
        config_obj = ArenaConfig(
            rounds=int(st.session_state["rounds"]),
            start_difficulty=int(st.session_state["start_difficulty"]),
            difficulty_step=int(st.session_state["difficulty_step"]),
            max_guesses=int(st.session_state["max_guesses"]),
            seed=int(st.session_state["seed"]),
            reveal_passwords=bool(st.session_state["reveal_passwords"]),
            defender_config=RoleConfig(
                provider=st.session_state["defender_provider"],
                model=(
                    st.session_state["defender_model"]
                    if st.session_state["defender_provider"] != "rule_based"
                    else None
                ),
                thinking_level=(
                    ThinkingLevel(st.session_state["defender_thinking"])
                    if st.session_state["defender_provider"] != "rule_based"
                    else ThinkingLevel.AUTO
                ),
            ),
            attacker_config=RoleConfig(
                provider=st.session_state["attacker_provider"],
                model=(
                    st.session_state["attacker_model"]
                    if st.session_state["attacker_provider"] != "rule_based"
                    else None
                ),
                thinking_level=(
                    ThinkingLevel(st.session_state["attacker_thinking"])
                    if st.session_state["attacker_provider"] != "rule_based"
                    else ThinkingLevel.AUTO
                ),
            ),
        )
        profile_path = Path(f"{profile_name}.json")
        profile_path.write_text(json.dumps(asdict(config_obj), indent=2), encoding="utf-8")
        st.success(f"Saved to {profile_path.name}")

    st.divider()
    run = st.button("Run arena", type="primary", use_container_width=True)

if not run:
    st.info("Choose the experiment controls and run the arena.")
    st.stop()

config = ArenaConfig(
    rounds=int(rounds),
    start_difficulty=int(start_difficulty),
    difficulty_step=int(difficulty_step),
    max_guesses=int(max_guesses),
    seed=int(seed),
    reveal_passwords=reveal_passwords,
    defender_config=RoleConfig(
        provider=st.session_state["defender_provider"],
        model=(
            st.session_state["defender_model"]
            if st.session_state["defender_provider"] != "rule_based"
            else None
        ),
        thinking_level=(
            ThinkingLevel(st.session_state["defender_thinking"])
            if st.session_state["defender_provider"] != "rule_based"
            else ThinkingLevel.AUTO
        ),
    ),
    attacker_config=RoleConfig(
        provider=st.session_state["attacker_provider"],
        model=(
            st.session_state["attacker_model"]
            if st.session_state["attacker_provider"] != "rule_based"
            else None
        ),
        thinking_level=(
            ThinkingLevel(st.session_state["attacker_thinking"])
            if st.session_state["attacker_provider"] != "rule_based"
            else ThinkingLevel.AUTO
        ),
    ),
)
result = build_arena_engine(config)
if isinstance(result, PreflightFailure):
    st.error(f"Preflight failed for {result.role}: {result.message} ({result.state})")
    st.stop()
experiment = result.run()
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
            "Guesses": item.attack.guesses_used,
            "Attack strategy": item.attack.winning_strategy,
            "Defender strategy": item.defender_strategy,
            "Elapsed ms": round(item.attack.elapsed_ms, 3),
        }
    )
frame = pd.DataFrame(rows)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Solve rate", f"{experiment.solve_rate:.0%}")
col2.metric("Rounds solved", f"{experiment.solved_rounds}/{len(experiment.rounds)}")
col3.metric("Final entropy", f"{frame.iloc[-1]['Entropy bits']:.1f} bits")
col4.metric("Total guesses", f"{int(frame['Guesses'].sum()):,}")

st.subheader("Learning curves")
chart_col1, chart_col2 = st.columns(2)
with chart_col1:
    st.caption("Entropy bits")
    st.line_chart(frame.set_index("Round")[["Entropy bits"]])
with chart_col2:
    st.caption("Guesses")
    st.line_chart(frame.set_index("Round")[["Guesses"]])

st.subheader("Round results")
st.dataframe(frame, use_container_width=True, hide_index=True)

st.subheader("Arena journal")
st.caption(
    "Each entry is assembled from recorded actions, budget allocations, observations, and state "
    "updates—not hidden chain-of-thought."
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
