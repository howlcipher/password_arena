import pandas as pd
import streamlit as st

from password_arena.history import HistoryManager
from password_arena.models import TournamentConfig
from password_arena.providers import AvailabilityState, ProviderRegistry
from password_arena.reporting import (
    tournament_report_csv,
    tournament_report_json,
    tournament_report_markdown,
)
from password_arena.tournament import build_tournament_matrix, run_matchup
from password_arena.tournament_history import TournamentHistoryManager
from password_arena.tournament_views import (
    render_efficiency,
    render_heatmap,
    render_leaderboards,
    render_overview,
    render_thinking_comparison,
)
from password_arena.ui_helpers import render_tournament_role_manager


def render_tournament_tab() -> None:
    st.header("Tournament Configuration")

    col1, col2 = st.columns(2)

    with col1:
        attackers = render_tournament_role_manager("Attacker")

    with col2:
        defenders = render_tournament_role_manager("Defender")

    st.divider()
    st.subheader("Tournament Parameters")

    c1, c2, c3 = st.columns(3)
    with c1:
        rounds_per_match = st.number_input("Rounds per Matchup", min_value=1, value=5)
    with c2:
        trials_count = st.number_input("Repeated Trials (Seeds)", min_value=1, value=3)
    with c3:
        max_guesses = st.number_input("Max Guesses", min_value=1, max_value=100000, value=100)
        
    st.subheader("Budgets & Limits (Optional)")
    l1, l2, l3, l4 = st.columns(4)
    with l1:
        max_tokens = st.number_input("Max Tokens", min_value=0, value=0, help="0 means unlimited")
    with l2:
        max_cost = st.number_input(
            "Max Cost ($)", min_value=0.0, value=0.0, help="0.0 means unlimited"
        )
    with l3:
        max_time = st.number_input(
            "Max Time (s)", min_value=0.0, value=0.0, help="0.0 means unlimited"
        )
    with l4:
        max_retries = st.number_input("Max Retries", min_value=0, value=3)

    exclude_self = st.checkbox("Exclude self-play matchups (e.g. GPT vs GPT)", value=True)

    run_disabled = len(attackers) == 0 or len(defenders) == 0
    if run_disabled:
        st.warning("Select at least one attacker and one defender.")

    # Preflight Matrix
    st.divider()
    st.subheader("Preflight Status")
    unique_roles = {}
    for r in attackers + defenders:
        key = f"{r.provider}:{r.model}:{r.thinking_level.value}"
        if key not in unique_roles:
            unique_roles[key] = r

    preflight_failed = False
    status_rows = []
    
    # We want to display the preflight status
    for r in unique_roles.values():
        prov_display = r.provider
        mod_display = r.model or "default"
        think_display = r.thinking_level.value
        
        status = "AVAILABLE"
        reason = ""
        
        if r.provider != "rule_based":
            try:
                backend = ProviderRegistry.create(r)
                if backend:
                    avail = backend.check_availability()
                    status = avail.state.value.upper()
                    if avail.state != AvailabilityState.AVAILABLE:
                        reason = avail.message
                        preflight_failed = True
            except Exception as e:
                status = "ERROR"
                reason = str(e)
                preflight_failed = True
                
        status_rows.append({
            "Provider": prov_display,
            "Model": mod_display,
            "Thinking": think_display,
            "Status": status,
            "Details": reason
        })
        
    st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)

    if preflight_failed:
        st.error("Some configurations are offline or invalid. Please fix them before running.")
        run_disabled = True

    # Estimated Scale
    config = TournamentConfig(
        attackers=tuple(attackers),
        defenders=tuple(defenders),
        seeds=tuple(42 + i for i in range(int(trials_count))),
        rounds_per_match=int(rounds_per_match),
        max_guesses=int(max_guesses),
        max_tokens=int(max_tokens) if max_tokens > 0 else None,
        max_api_cost=float(max_cost) if max_cost > 0.0 else None,
        max_wall_time_s=float(max_time) if max_time > 0.0 else None,
        max_retries=int(max_retries),
    )
    matrix = build_tournament_matrix(config, exclude_self=exclude_self)
    total_experiments = len(matrix) * trials_count
    max_rounds = total_experiments * rounds_per_match
    
    st.info(
        f"**Estimated Scale:** {len(matrix)} Matchups | {total_experiments} Experiments | "
        f"Max {max_rounds} Scored Rounds\n\n"
        "⚠️ *This tournament may make paid API requests. Actual cost depends on selected "
        "providers and models.*"
    )

    if st.button("Run Tournament", type="primary", disabled=run_disabled):
        if not matrix:
            st.error("No valid matchups generated (perhaps only self-play was selected).")
            return

        st.success(
            f"Running {len(matrix)} matchups ({total_experiments} total experiments)..."
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
        status_text.text("Tournament complete. Saving history...")

        history_mgr = HistoryManager()
        tourney_mgr = TournamentHistoryManager()
        for r in results:
            for exp in r.experiments:
                history_mgr.save(exp)
        t_id, timestamp = tourney_mgr.save(config, results)

        status_text.text(f"Tournament complete. Saved as {t_id}.")

        _render_results(t_id, timestamp, config, results)

    st.divider()
    render_tournament_history()


def _cost_display(value: float | None) -> str:
    return "unavailable" if value is None else f"${value:.4f}"


def _rate_display(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.1f}%"


def _render_results(
    tournament_id: str, timestamp: str, config: TournamentConfig, results: list
) -> None:
    # Use tabbed layout for views
    t1, t2, t3, t4 = st.tabs([
        "Overview & Leaderboard", "Matchup Heatmap", "Efficiency", "Thinking Levels"
    ])
    
    with t1:
        render_overview(results)
        st.divider()
        render_leaderboards(results)
        
    with t2:
        render_heatmap(results)
        
    with t3:
        render_efficiency(results)
        
    with t4:
        render_thinking_comparison(results)

    st.divider()
    json_report = tournament_report_json(tournament_id, timestamp, config, results)
    markdown_report = tournament_report_markdown(tournament_id, timestamp, config, results)
    csv_report = tournament_report_csv(tournament_id, timestamp, config, results)

    dl1, dl2, dl3 = st.columns(3)
    with dl1:
        st.download_button(
            "Download JSON report",
            data=json_report,
            file_name=f"tournament-{tournament_id}.json",
            mime="application/json",
            use_container_width=True,
        )
    with dl2:
        st.download_button(
            "Download Markdown report",
            data=markdown_report,
            file_name=f"tournament-{tournament_id}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with dl3:
        st.download_button(
            "Download CSV report",
            data=csv_report,
            file_name=f"tournament-{tournament_id}.csv",
            mime="text/csv",
            use_container_width=True,
        )


def render_tournament_history() -> None:
    st.subheader("Tournament History")
    tourney_mgr = TournamentHistoryManager()
    runs = tourney_mgr.list_runs()
    if not runs:
        st.caption("No saved tournaments yet.")
        return

    labels = {
        f"{run['timestamp']} · {run['tournament_id'][:8]} · {run['matchup_count']} matchups": run[
            "tournament_id"
        ]
        for run in runs
    }
    
    st.write("Select one or two tournaments to view or compare.")
    selected_labels = st.multiselect("Saved tournaments", list(labels.keys()), max_selections=2)
    
    if not selected_labels:
        return
        
    if len(selected_labels) == 1:
        selected_id = labels[selected_labels[0]]
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Load tournament details", type="primary"):
                st.session_state["loaded_tournament"] = selected_id
        with col2:
            if st.button("Delete tournament", type="secondary"):
                tourney_mgr.delete(selected_id)
                if st.session_state.get("loaded_tournament") == selected_id:
                    del st.session_state["loaded_tournament"]
                st.success(f"Deleted {selected_id}.")
                st.rerun()
                
        if st.session_state.get("loaded_tournament") == selected_id:
            stored = tourney_mgr.load(selected_id)
            if stored.missing_experiment_ids:
                st.warning(
                    f"{len(stored.missing_experiment_ids)} linked experiment(s) are no longer "
                    "in single-run history and could not be hydrated."
                )
            
            st.divider()
            st.subheader(f"Tournament: {selected_id[:8]}")
            _render_results(selected_id, stored.timestamp, stored.config, stored.matchups)
            
    elif len(selected_labels) == 2:
        id_a = labels[selected_labels[0]]
        id_b = labels[selected_labels[1]]
        
        if st.button("Compare Tournaments", type="primary"):
            stored_a = tourney_mgr.load(id_a)
            stored_b = tourney_mgr.load(id_b)
            
            st.divider()
            st.subheader("Comparison")
            
            # Simple config diff
            ca = stored_a.config
            cb = stored_b.config
            
            st.markdown("#### Configuration Differences")
            diffs = []
            if ca.rounds_per_match != cb.rounds_per_match:
                diffs.append(f"Rounds: {ca.rounds_per_match} vs {cb.rounds_per_match}")
            if ca.seeds != cb.seeds:
                diffs.append(f"Trials (seeds): {len(ca.seeds)} vs {len(cb.seeds)}")
            if ca.max_guesses != cb.max_guesses:
                diffs.append(f"Max Guesses: {ca.max_guesses} vs {cb.max_guesses}")
            if ca.generator_version != cb.generator_version:
                diffs.append(f"Generator: {ca.generator_version} vs {cb.generator_version}")
                
            if not diffs:
                st.success(
                    "Tournaments share identical core parameters and are directly comparable."
                )
            else:
                msg = (
                    "Tournaments have different parameters and may not be directly comparable:\n"
                    + "\n".join(f"- {d}" for d in diffs)
                )
                st.warning(msg)
                
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Tournament A ({id_a[:8]})**")
                _render_results(id_a, stored_a.timestamp, stored_a.config, stored_a.matchups)
            with c2:
                st.markdown(f"**Tournament B ({id_b[:8]})**")
                _render_results(id_b, stored_b.timestamp, stored_b.config, stored_b.matchups)
