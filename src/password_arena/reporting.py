from __future__ import annotations

from password_arena.models import ExperimentResult, RoundResult


def round_report_markdown(item: RoundResult) -> str:
    """Render one auditable, password-safe round report."""

    status = "SOLVED" if item.attack.solved else "RESISTED"
    plan = ", ".join(
        f"{entry.strategy}: {entry.guess_budget:,} ({entry.weight:.1%})"
        for entry in item.attack.plan
    )
    defender_actions = "\n".join(f"- {action}" for action in item.report.defender.actions)
    attacker_actions = "\n".join(f"- {action}" for action in item.report.attacker.actions)

    return f"""## Round {item.round_number} — {status}

**Difficulty:** {item.difficulty}  
**Password:** `{item.password_display}` ({item.password_length} characters)  
**Estimated entropy:** {item.strength.entropy_bits:.2f} bits  
**Guess result:** {item.attack.guesses_used:,} guesses using `{item.attack.strategy}`  
**Runtime:** {item.attack.elapsed_ms:.3f} ms

### Defender side

**Decision:** {item.report.defender.decision}

{defender_actions}

**Observed:** {item.report.defender.observation}  
**Learning update:** {item.report.defender.learning_update}

### Attacker side

**Decision:** {item.report.attacker.decision}  
**Budget plan:** {plan}

{attacker_actions}

**Observed:** {item.report.attacker.observation}  
**Learning update:** {item.report.attacker.learning_update}

### Evaluator

{item.report.evaluator_summary}

**Security lesson:** {item.report.security_lesson}
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
