from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from password_arena.engine import ArenaEngine
from password_arena.models import ArenaConfig
from password_arena.reporting import experiment_report_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="password-arena",
        description="Run a safe local attacker-versus-defender password simulation.",
    )
    parser.add_argument("--rounds", type=int, default=8)
    parser.add_argument("--start-difficulty", type=int, default=1)
    parser.add_argument("--difficulty-step", type=int, default=1)
    parser.add_argument("--max-guesses", type=int, default=5_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reveal-passwords", action="store_true")
    parser.add_argument(
        "--generator-mode",
        choices=["secure", "deterministic-test"],
        default="secure",
        help="Generator mode for cryptographic passwords.",
    )
    parser.add_argument("--output", type=Path, help="Write the complete experiment JSON.")
    parser.add_argument("--report", type=Path, help="Write a two-sided Markdown arena report.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = ArenaConfig(
        rounds=args.rounds,
        start_difficulty=args.start_difficulty,
        difficulty_step=args.difficulty_step,
        max_guesses=args.max_guesses,
        seed=args.seed,
        reveal_passwords=args.reveal_passwords,
        generator_mode=args.generator_mode,
    )
    try:
        config.validate()
    except ValueError as e:
        parser.error(str(e))
    
    experiment = ArenaEngine(config).run()

    print("\nPassword Arena")
    print("=" * 86)
    header = (
        f"{'Rnd':>3}  {'Lvl':>3}  {'Length':>6}  {'Entropy':>8}  "
        f"{'Solved':>6}  {'Guesses':>8}  Strategy"
    )
    print(header)
    for item in experiment.rounds:
        print(
            f"{item.round_number:>3}  {item.difficulty:>3}  {item.password_length:>6}  "
            f"{item.strength.entropy_bits:>8.2f}  {str(item.attack.solved):>6}  "
            f"{item.attack.guesses_used:>8}  {item.attack.winning_strategy or '<none>'}"
        )
    print("=" * 86)
    total_rounds = len(experiment.rounds)
    print(f"Solve rate: {experiment.solve_rate:.0%} ({experiment.solved_rounds}/{total_rounds})")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(experiment.to_dict(), indent=2), encoding="utf-8")
        print(f"Results written to {args.output}")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(experiment_report_markdown(experiment), encoding="utf-8")
        print(f"Arena report written to {args.report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
