from __future__ import annotations

import csv
import html
import io
import json
from dataclasses import asdict
from typing import Any

from password_arena.models import (
    ExclusionRecord,
    ExperimentResult,
    MatchupResult,
    RoleConfig,
    RoundResult,
    TournamentConfig,
)


def round_report_markdown(item: RoundResult) -> str:
    """Render one auditable, password-safe round report."""

    status = "SOLVED" if item.attack.solved else "RESISTED"
    plan = ", ".join(
        f"{entry.strategy}: {entry.guess_budget:,} ({entry.weight:.1%})"
        for entry in item.attack.plan
    )
    outcome = "solved" if item.attack.solved else "resisted the bounded guess budget"
    findings = "; ".join(item.strength.findings)

    defender_actions = [
        f"- Generated a synthetic {item.defender_strategy} password.",
        f"- Set length to {item.password_length} characters.",
    ]
    defender_actions_str = "\n".join(defender_actions)

    attack_actions = [
        f"- Allocated {entry.guess_budget:,} guesses to {entry.strategy} "
        f"({entry.weight:.1%} of the plan)."
        for entry in item.attack.plan
    ]
    attacker_actions_str = "\n".join(attack_actions)

    winning_str = f" using `{item.attack.winning_strategy}`" if item.attack.winning_strategy else ""

    defender_observation = f"The password {outcome}. Evaluator findings: {findings}."

    attacker_observation = (
        f"{'Found a match' if item.attack.solved else 'Found no match'} after "
        f"{item.attack.guesses_used:,} guesses; attempted "
        f"{', '.join(item.attack.attempted_strategies)}."
    )

    evaluator_summary = (
        f"Round {item.round_number} {outcome}. Strength score was {item.strength.score}/4 with "
        f"an estimated {item.strength.entropy_bits:.2f} bits after structural penalties."
    )

    def get_security_lesson(family: str, solved: bool) -> str:
        if solved:
            return (
                f"The {family} structure remained predictable inside the current attack model; "
                "cosmetic complexity should not be treated as randomness."
            )
        if family == "cryptographic-random":
            return (
                "Cryptographically secure randomness removed the human patterns targeted by the "
                "bounded attacker; password-manager generation is the safer real-world endpoint."
            )
        return (
            "This structure survived this bounded experiment, but that is not proof of real-world "
            "security against larger or different attack models."
        )

    security_lesson = get_security_lesson(item.defender_strategy, item.attack.solved)

    attacker_note = (
        (
            f"Ranked {item.attack.plan[0].strategy} as the highest-priority strategy "
            f"for difficulty {item.difficulty}."
        )
        if not item.attacker_note
        else item.attacker_note
    )

    return f"""## Round {item.round_number} — {status}

**Difficulty:** {item.difficulty}  
**Password:** `{item.password_display}` ({item.password_length} characters)  
**Estimated entropy:** {item.strength.entropy_bits:.2f} bits  
**Guess result:** {item.attack.guesses_used:,} guesses{winning_str}  
**Runtime:** {item.attack.elapsed_ms:.3f} ms

### Defender side

**Decision:** {item.defender_note}

{defender_actions_str}

**Observed:** {defender_observation}  
**Learning update:** {item.defender_learning}

### Attacker side

**Decision:** {attacker_note}  
**Budget plan:** {plan}

{attacker_actions_str}

**Observed:** {attacker_observation}  
**Learning update:** {item.attacker_learning}

### Evaluator

{evaluator_summary}

**Security lesson:** {security_lesson}
"""


def experiment_report_markdown(experiment: ExperimentResult) -> str:
    """Render a complete two-sided experiment journal."""

    header = f"""# Password Arena Experiment Report

- **Rounds:** {len(experiment.rounds)}
- **Solved rounds:** {experiment.solved_rounds}
- **Solve rate:** {experiment.solve_rate:.1%}
- **Guess budget per round:** {experiment.config.max_guesses:,}
- **Passwords revealed:** {experiment.config.reveal_passwords}

> Reports are generated from recorded actions and metrics.
> They are not unverified agent chain-of-thought.

"""
    return header + "\n---\n\n".join(round_report_markdown(item) for item in experiment.rounds)


def experiment_export_csv(experiment: ExperimentResult) -> str:
    """Render a CSV of normalized round and strategy data."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "round_number",
            "difficulty",
            "password_length",
            "entropy_bits",
            "solved",
            "guesses_used",
            "winning_strategy",
            "elapsed_ms",
        ]
    )
    for item in experiment.rounds:
        writer.writerow(
            [
                item.round_number,
                item.difficulty,
                item.password_length,
                f"{item.strength.entropy_bits:.2f}",
                item.attack.solved,
                item.attack.guesses_used,
                item.attack.winning_strategy or "",
                f"{item.attack.elapsed_ms:.3f}",
            ]
        )
    return output.getvalue()


def experiment_export_html(experiment: ExperimentResult) -> str:
    """Render a standalone HTML report for portfolio sharing."""
    md_content = experiment_report_markdown(experiment)
    safe_content = html.escape(md_content).replace("\n", "<br>")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Password Arena Experiment Report</title>
<style>
  body {{
    font-family: system-ui, sans-serif;
    max-width: 800px;
    margin: 2rem auto;
    padding: 0 1rem;
    line-height: 1.5;
  }}
  h1, h2, h3 {{ color: #333; }}
</style>
</head>
<body>
<pre>{safe_content}</pre>
</body>
</html>"""


# --- Tournament-level (cross-model) reports -------------------------------------
#
# These functions operate only on TournamentConfig/MatchupResult (configuration and
# aggregate statistics) -- never on ExperimentResult.rounds password data -- so they
# cannot leak secrets, API keys, or unredacted passwords by construction. RoleConfig
# has no secret-bearing fields (provider/model/thinking_level/temperature/max_tokens/
# local_endpoint only).


def _cost_display(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.6f}"


def _rate_display(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.4f}"


def _role_payload(role: RoleConfig) -> dict[str, Any]:
    return {
        "provider": role.provider,
        "model": role.model,
        "thinking_level": str(role.thinking_level),
    }


def _exclusion_payload(records: tuple[ExclusionRecord, ...]) -> list[dict[str, Any]]:
    return [
        {
            "seed": r.seed,
            "experiment_id": r.experiment_id,
            "round_number": r.round_number,
            "reason": r.reason.value,
        }
        for r in records
    ]


def _matchup_payload(m: MatchupResult) -> dict[str, Any]:
    s = m.summary
    return {
        "matchup_id": m.matchup_id,
        "attacker": _role_payload(m.config.attacker),
        "defender": _role_payload(m.config.defender),
        "seeds": list(m.config.seeds),
        "rounds_per_match": m.config.rounds,
        "max_guesses": m.config.max_guesses,
        "generator_mode": m.config.generator_mode,
        "generator_version": m.config.generator_version,
        "is_comparable": m.is_comparable,
        "non_comparable_reason": m.non_comparable_reason,
        "trials": s.trials,
        "comparable_trials": s.comparable_trials,
        "excluded_trials": s.excluded_trials,
        "excluded_rounds": s.excluded_rounds,
        "rounds_completed": s.rounds_completed,
        "rounds_solved": s.rounds_solved,
        "rounds_resisted": s.rounds_resisted,
        "solve_rate": s.solve_rate,
        "survival_rate": s.survival_rate,
        "confidence_interval": (
            [s.confidence_interval_lower, s.confidence_interval_upper]
            if s.confidence_interval_lower is not None
            else None
        ),
        "guesses": {
            "mean_per_round": s.mean_guesses_per_round,
            "median_per_round": s.median_guesses_per_round,
            "std_per_round": s.std_guesses_per_round,
            "mean_to_solve": s.mean_guesses_to_solve,
            "median_to_solve": s.median_guesses_to_solve,
            "mean_total_per_trial": s.mean_total_guesses_per_trial,
        },
        "tokens": {
            "attacker_input": s.attacker_input_tokens,
            "attacker_output": s.attacker_output_tokens,
            "attacker_reasoning": s.attacker_reasoning_tokens,
            "defender_input": s.defender_input_tokens,
            "defender_output": s.defender_output_tokens,
            "defender_reasoning": s.defender_reasoning_tokens,
        },
        "latency_ms": {
            "attacker_mean": s.attacker_mean_latency_ms,
            "defender_mean": s.defender_mean_latency_ms,
        },
        "estimated_cost": s.total_estimated_cost,
        "efficiency": asdict(s.efficiency),
        "replay": asdict(m.replay) if m.replay else None,
        "excluded_trial_records": _exclusion_payload(m.excluded_trial_records),
        "excluded_round_records": _exclusion_payload(m.excluded_round_records),
    }


def tournament_report_json(
    tournament_id: str,
    timestamp: str,
    config: TournamentConfig,
    matchups: list[MatchupResult],
) -> str:
    """Provider-neutral JSON export for a completed tournament (IMP-026)."""
    payload = {
        "tournament_id": tournament_id,
        "timestamp": timestamp,
        "seeds": list(config.seeds),
        "rounds_per_match": config.rounds_per_match,
        "max_guesses": config.max_guesses,
        "generator_mode": config.generator_mode,
        "generator_version": config.generator_version,
        "matchups": [_matchup_payload(m) for m in matchups],
    }
    return json.dumps(payload, indent=2)


def tournament_report_markdown(
    tournament_id: str,
    timestamp: str,
    config: TournamentConfig,
    matchups: list[MatchupResult],
) -> str:
    """Human-readable cross-model tournament report (IMP-026)."""
    lines = [
        "# Password Arena Tournament Report",
        "",
        f"- **Tournament ID:** {tournament_id}",
        f"- **Timestamp:** {timestamp}",
        f"- **Seeds:** {list(config.seeds)}",
        f"- **Rounds per match:** {config.rounds_per_match}",
        f"- **Guess budget:** {config.max_guesses:,}",
        f"- **Generator:** {config.generator_mode} / {config.generator_version}",
        "",
        "> Confidence intervals assume independent Bernoulli round outcomes. "
        "Repeated hosted-model trials may not be strictly independent.",
        "",
    ]
    for m in matchups:
        s = m.summary
        att = m.config.attacker.provider + (
            f" ({m.config.attacker.model})" if m.config.attacker.model else ""
        )
        dfd = m.config.defender.provider + (
            f" ({m.config.defender.model})" if m.config.defender.model else ""
        )
        lines.append(f"## {att} vs {dfd}")
        lines.append("")
        status = "OK" if m.is_comparable else f"WARN: {m.non_comparable_reason}"
        lines.append(f"- **Status:** {status}")
        lines.append(
            f"- **Comparable trials:** {s.comparable_trials}/{s.trials} "
            f"(excluded: {s.excluded_trials}, excluded rounds: {s.excluded_rounds})"
        )
        lines.append(f"- **Solve rate (round-level):** {_rate_display(s.solve_rate)}")
        lines.append(f"- **Survival rate (round-level):** {_rate_display(s.survival_rate)}")
        if s.confidence_interval_lower is not None and s.confidence_interval_upper is not None:
            lines.append(
                "- **95% CI (round-level solve rate):** "
                f"[{s.confidence_interval_lower:.4f}, {s.confidence_interval_upper:.4f}]"
            )
        lines.append(
            f"- **Guesses:** mean/round={s.mean_guesses_per_round}, "
            f"median/round={s.median_guesses_per_round}, "
            f"std/round={s.std_guesses_per_round}, "
            f"mean-to-solve={s.mean_guesses_to_solve}, "
            f"median-to-solve={s.median_guesses_to_solve}, "
            f"mean-total/trial={s.mean_total_guesses_per_trial}"
        )
        lines.append(
            f"- **Attacker tokens:** in={s.attacker_input_tokens}, "
            f"out={s.attacker_output_tokens}, reasoning={s.attacker_reasoning_tokens}"
        )
        lines.append(
            f"- **Defender tokens:** in={s.defender_input_tokens}, "
            f"out={s.defender_output_tokens}, reasoning={s.defender_reasoning_tokens}"
        )
        lines.append(
            f"- **Latency (ms):** attacker={s.attacker_mean_latency_ms}, "
            f"defender={s.defender_mean_latency_ms}"
        )
        lines.append(f"- **Estimated cost:** {_cost_display(s.total_estimated_cost)}")
        eff = s.efficiency
        lines.append(
            "- **Efficiency:** "
            f"attacker solved/1k tokens={eff.attacker_solved_per_1k_tokens}, "
            f"attacker solved/sec={eff.attacker_solved_per_second}, "
            f"attacker solved/$={eff.attacker_solved_per_dollar}, "
            f"defender survived/1k tokens={eff.defender_survived_per_1k_tokens}, "
            f"defender survived/$={eff.defender_survived_per_dollar}"
        )
        if m.replay:
            lines.append(
                f"- **Replay:** deterministic={m.replay.deterministic} "
                f"(schema {m.replay.schema_version}, app {m.replay.application_version})"
            )
        if m.excluded_trial_records or m.excluded_round_records:
            lines.append("- **Exclusion reasons:**")
            for r in m.excluded_trial_records:
                lines.append(f"  - trial seed={r.seed}: {r.reason.value}")
            for r in m.excluded_round_records:
                lines.append(f"  - round seed={r.seed} round={r.round_number}: {r.reason.value}")
        lines.append("")
    return "\n".join(lines)


def tournament_report_csv(
    tournament_id: str,
    timestamp: str,
    config: TournamentConfig,
    matchups: list[MatchupResult],
) -> str:
    """One row per matchup (IMP-026). Unavailable values render as "unavailable",
    never as "0" or blank, so they cannot be misread as a measured zero."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "tournament_id",
            "timestamp",
            "attacker_provider",
            "attacker_model",
            "defender_provider",
            "defender_model",
            "is_comparable",
            "non_comparable_reason",
            "trials",
            "comparable_trials",
            "excluded_trials",
            "excluded_rounds",
            "rounds_completed",
            "rounds_solved",
            "rounds_resisted",
            "solve_rate",
            "survival_rate",
            "ci_lower",
            "ci_upper",
            "mean_guesses_per_round",
            "median_guesses_per_round",
            "std_guesses_per_round",
            "mean_guesses_to_solve",
            "median_guesses_to_solve",
            "mean_total_guesses_per_trial",
            "attacker_input_tokens",
            "attacker_output_tokens",
            "attacker_reasoning_tokens",
            "defender_input_tokens",
            "defender_output_tokens",
            "defender_reasoning_tokens",
            "attacker_mean_latency_ms",
            "defender_mean_latency_ms",
            "estimated_cost",
            "deterministic_replay",
        ]
    )

    def cell(value: Any) -> Any:
        return "unavailable" if value is None else value

    for m in matchups:
        s = m.summary
        writer.writerow(
            [
                tournament_id,
                timestamp,
                m.config.attacker.provider,
                m.config.attacker.model or "",
                m.config.defender.provider,
                m.config.defender.model or "",
                m.is_comparable,
                m.non_comparable_reason or "",
                s.trials,
                s.comparable_trials,
                s.excluded_trials,
                s.excluded_rounds,
                s.rounds_completed,
                s.rounds_solved,
                s.rounds_resisted,
                cell(s.solve_rate),
                cell(s.survival_rate),
                cell(s.confidence_interval_lower),
                cell(s.confidence_interval_upper),
                cell(s.mean_guesses_per_round),
                cell(s.median_guesses_per_round),
                cell(s.std_guesses_per_round),
                cell(s.mean_guesses_to_solve),
                cell(s.median_guesses_to_solve),
                cell(s.mean_total_guesses_per_trial),
                s.attacker_input_tokens,
                s.attacker_output_tokens,
                cell(s.attacker_reasoning_tokens),
                s.defender_input_tokens,
                s.defender_output_tokens,
                cell(s.defender_reasoning_tokens),
                cell(s.attacker_mean_latency_ms),
                cell(s.defender_mean_latency_ms),
                cell(s.total_estimated_cost),
                m.replay.deterministic if m.replay else "",
            ]
        )
    return output.getvalue()
