from __future__ import annotations

import csv
import html
import io

from password_arena.models import ExperimentResult, RoundResult


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
