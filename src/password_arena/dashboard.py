from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from password_arena.engine import ArenaEngine
from password_arena.models import ArenaConfig
from password_arena.reporting import experiment_report_markdown

st.set_page_config(page_title="Password Arena", page_icon="🛡️", layout="wide")
st.title("Password Arena")
st.caption(
    "A safe, local attacker-versus-defender learning sandbox using synthetic passwords only."
)

with st.sidebar:
    st.header("Experiment")
    rounds = st.slider("Rounds", 1, 30, 8)
    start_difficulty = st.slider("Starting difficulty", 1, 10, 1)
    difficulty_step = st.slider("Difficulty increase per round", 0, 3, 1)
    max_guesses = st.number_input("Maximum guesses per round", 10, 100_000, 5_000, 100)
    seed = st.number_input("Seed", 0, 1_000_000, 42)
    reveal_passwords = st.toggle("Reveal synthetic passwords", value=False)
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
)
experiment = ArenaEngine(config).run()

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
st.line_chart(frame.set_index("Round")[["Entropy bits", "Guesses"]])

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
