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
    defender_actions = "\n".join(f"- {action}" for action in item.report.defender.actions)
    attacker_actions = "\n".join(f"- {action}" for action in item.report.attacker.actions)
    winning_str = f" using `{item.attack.winning_strategy}`" if item.attack.winning_strategy else ""

    return f"""## Round {item.round_number} — {status}

**Difficulty:** {item.difficulty}  
**Password:** `{item.password_display}` ({item.password_length} characters)  
**Estimated entropy:** {item.strength.entropy_bits:.2f} bits  
**Guess result:** {item.attack.guesses_used:,} guesses{winning_str}  
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


def experiment_export_csv(experiment: ExperimentResult) -> str:
    """Render a CSV of normalized round and strategy data."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "round_number", "difficulty", "password_length", "entropy_bits",
        "solved", "guesses_used", "winning_strategy", "elapsed_ms"
    ])
    for item in experiment.rounds:
        writer.writerow([
            item.round_number,
            item.difficulty,
            item.password_length,
            f"{item.strength.entropy_bits:.2f}",
            item.attack.solved,
            item.attack.guesses_used,
            item.attack.winning_strategy or "",
            f"{item.attack.elapsed_ms:.3f}"
        ])
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
