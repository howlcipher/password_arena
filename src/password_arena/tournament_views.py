import altair as alt
import pandas as pd
import streamlit as st


def _rate_display(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.1f}%"

def _cost_display(value: float | None) -> str:
    return "-" if value is None else f"${value:.4f}"

def render_overview(results: list) -> None:
    st.subheader("Tournament Overview")
    
    comparable_rounds = sum(r.summary.rounds_completed for r in results if r.is_comparable)
    total_solved = sum(r.summary.rounds_solved for r in results if r.is_comparable)
    total_resisted = sum(r.summary.rounds_resisted for r in results if r.is_comparable)
    
    total_tokens = sum(
        (r.summary.attacker_input_tokens + r.summary.attacker_output_tokens + 
         r.summary.defender_input_tokens + r.summary.defender_output_tokens)
        for r in results
    )
    
    cost_known = any(r.summary.total_estimated_cost is not None for r in results)
    total_cost = sum((r.summary.total_estimated_cost or 0.0) for r in results)
    
    interrupted = sum(r.summary.excluded_trials for r in results)
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Comparable Rounds", f"{comparable_rounds}")
        st.metric("Total Tokens", f"{total_tokens:,}")
    with c2:
        solve_rate = total_solved / max(1, comparable_rounds)
        st.metric("Solve Rate", f"{solve_rate:.1%}")
        if cost_known:
            st.metric("Estimated Cost", f"${total_cost:.2f}")
        else:
            st.metric("Estimated Cost", "unavailable")
    with c3:
        survival_rate = total_resisted / max(1, comparable_rounds)
        st.metric("Survival Rate", f"{survival_rate:.1%}")
        
    with c4:
        st.metric("Interruptions", f"{interrupted}")

def render_leaderboards(results: list) -> None:
    st.subheader("Leaderboards")
    
    attacker_data = []
    defender_data = []
    
    for r in results:
        att = r.config.attacker
        dfd = r.config.defender
        
        att_name = f"{att.provider} ({att.model or '-'}) [{att.thinking_level.value}]"
        dfd_name = f"{dfd.provider} ({dfd.model or '-'}) [{dfd.thinking_level.value}]"
        
        if r.is_comparable:
            attacker_data.append({
                "Attacker": att_name,
                "Solve Rate": r.summary.solve_rate,
                "Tokens": r.summary.attacker_input_tokens + r.summary.attacker_output_tokens,
                "Cost": r.summary.total_estimated_cost,  # Fallback: per role not separated
                "Solves/1K Tokens": r.summary.efficiency.attacker_solved_per_1k_tokens,
                "Latency ms": r.summary.attacker_mean_latency_ms,
                "Guesses to Solve": r.summary.median_guesses_to_solve
            })
            
            defender_data.append({
                "Defender": dfd_name,
                "Survival Rate": r.summary.survival_rate,
                "Tokens": r.summary.defender_input_tokens + r.summary.defender_output_tokens,
                "Survivals/1K Tokens": r.summary.efficiency.defender_survived_per_1k_tokens,
                "Latency ms": r.summary.defender_mean_latency_ms,
            })
            
    if attacker_data:
        att_df = pd.DataFrame(attacker_data)
        att_df = att_df.groupby("Attacker").mean(numeric_only=True).reset_index()
        att_df = att_df.sort_values("Solve Rate", ascending=False)
        st.markdown("**Top Attackers**")
        st.dataframe(att_df, use_container_width=True, hide_index=True)
        
    if defender_data:
        def_df = pd.DataFrame(defender_data)
        def_df = def_df.groupby("Defender").mean(numeric_only=True).reset_index()
        def_df = def_df.sort_values("Survival Rate", ascending=False)
        st.markdown("**Top Defenders**")
        st.dataframe(def_df, use_container_width=True, hide_index=True)

def render_heatmap(results: list) -> None:
    st.subheader("Matchup Matrix")
    
    metric = st.selectbox(
        "Metric", ["Solve Rate", "Survival Rate", "Median Guesses", "Latency ms", "Tokens"]
    )
    
    rows = []
    for r in results:
        if not r.is_comparable:
            continue
        att = r.config.attacker
        dfd = r.config.defender
        att_name = f"{att.provider} ({att.model or '-'}) [{att.thinking_level.value}]"
        dfd_name = f"{dfd.provider} ({dfd.model or '-'}) [{dfd.thinking_level.value}]"
        
        val = None
        if metric == "Solve Rate":
            val = r.summary.solve_rate
        elif metric == "Survival Rate":
            val = r.summary.survival_rate
        elif metric == "Median Guesses":
            val = r.summary.median_guesses_to_solve
        elif metric == "Latency ms":
            if r.summary.attacker_mean_latency_ms and r.summary.defender_mean_latency_ms:
                val = r.summary.attacker_mean_latency_ms + r.summary.defender_mean_latency_ms
        elif metric == "Tokens":
            val = (r.summary.attacker_input_tokens + r.summary.attacker_output_tokens + 
                   r.summary.defender_input_tokens + r.summary.defender_output_tokens)
                   
        rows.append({
            "Attacker": att_name,
            "Defender": dfd_name,
            "Value": val,
            "Trials": r.summary.comparable_trials
        })
        
    if not rows:
        st.warning("No comparable data to display heatmap.")
        return
        
    df = pd.DataFrame(rows)
    
    chart = alt.Chart(df).mark_rect().encode(
        x=alt.X("Defender:O", title="Defender"),
        y=alt.Y("Attacker:O", title="Attacker"),
        color=alt.Color("Value:Q", title=metric, scale=alt.Scale(scheme="viridis")),
        tooltip=["Attacker", "Defender", "Value", "Trials"]
    ).properties(height=400)
    
    st.altair_chart(chart, use_container_width=True)

def render_efficiency(results: list) -> None:
    st.subheader("Efficiency")
    
    rows = []
    for r in results:
        if not r.is_comparable:
            continue
        att = r.config.attacker
        dfd = r.config.defender
        
        att_name = f"{att.provider}:{att.model}"
        dfd_name = f"{dfd.provider}:{dfd.model}"
        
        cost = r.summary.total_estimated_cost
        
        rows.append({
            "Matchup": f"{att_name} vs {dfd_name}",
            "Solve Rate": r.summary.solve_rate,
            "Survival Rate": r.summary.survival_rate,
            "Attacker Tokens": r.summary.attacker_input_tokens + r.summary.attacker_output_tokens,
            "Defender Tokens": r.summary.defender_input_tokens + r.summary.defender_output_tokens,
            "Cost": cost,
            "Latency": (r.summary.attacker_mean_latency_ms or 0) + (
                r.summary.defender_mean_latency_ms or 0
            )
        })
        
    df = pd.DataFrame(rows)
    if df.empty:
        return
        
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Solve Rate vs Cost**")
        if df["Cost"].notna().any():
            chart = alt.Chart(df.dropna(subset=["Cost"])).mark_circle(size=60).encode(
                x="Cost:Q", y="Solve Rate:Q", tooltip=["Matchup", "Solve Rate", "Cost"]
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No cost data available.")
            
    with c2:
        st.markdown("**Solve Rate vs Tokens**")
        chart = alt.Chart(df).mark_circle(size=60).encode(
            x="Attacker Tokens:Q", 
            y="Solve Rate:Q", 
            tooltip=["Matchup", "Solve Rate", "Attacker Tokens"]
        )
        st.altair_chart(chart, use_container_width=True)

def render_thinking_comparison(results: list) -> None:
    st.subheader("Thinking-Level Comparison")
    
    rows = []
    for r in results:
        if not r.is_comparable:
            continue
            
        att = r.config.attacker
        rows.append({
            "Role": "Attacker",
            "Model": f"{att.provider}:{att.model}",
            "Thinking": att.thinking_level.value,
            "Solve Rate": r.summary.solve_rate,
            "Latency ms": r.summary.attacker_mean_latency_ms or 0,
            "Tokens": r.summary.attacker_input_tokens + r.summary.attacker_output_tokens
        })
        
        dfd = r.config.defender
        rows.append({
            "Role": "Defender",
            "Model": f"{dfd.provider}:{dfd.model}",
            "Thinking": dfd.thinking_level.value,
            "Survival Rate": r.summary.survival_rate,
            "Latency ms": r.summary.defender_mean_latency_ms or 0,
            "Tokens": r.summary.defender_input_tokens + r.summary.defender_output_tokens
        })
        
    if not rows:
        st.info("No data available.")
        return
        
    df = pd.DataFrame(rows)
    
    models_with_multiple_think = []
    for model, group in df.groupby("Model"):
        if group["Thinking"].nunique() > 1:
            models_with_multiple_think.append(model)
            
    if not models_with_multiple_think:
        st.info("No models with multiple thinking levels were tested.")
        return
        
    for model in models_with_multiple_think:
        st.markdown(f"**Model: {model}**")
        mdf = df[df["Model"] == model]
        
        att_df = mdf[mdf["Role"] == "Attacker"]
        if not att_df.empty:
            att_df = att_df.groupby("Thinking").mean(numeric_only=True).reset_index()
            
        def_df = mdf[mdf["Role"] == "Defender"]
        if not def_df.empty:
            def_df = def_df.groupby("Thinking").mean(numeric_only=True).reset_index()
        
        c1, c2 = st.columns(2)
        with c1:
            if not att_df.empty:
                st.markdown("*As Attacker*")
                st.dataframe(att_df, hide_index=True, use_container_width=True)
                
                chart = alt.Chart(att_df).mark_bar().encode(
                    x="Thinking:O",
                    y="Solve Rate:Q",
                    color="Thinking:N"
                )
                st.altair_chart(chart, use_container_width=True)
                
        with c2:
            if not def_df.empty:
                st.markdown("*As Defender*")
                st.dataframe(def_df, hide_index=True, use_container_width=True)
                
                chart = alt.Chart(def_df).mark_bar().encode(
                    x="Thinking:O",
                    y="Survival Rate:Q",
                    color="Thinking:N"
                )
                st.altair_chart(chart, use_container_width=True)
