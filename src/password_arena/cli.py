from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from password_arena.engine import ArenaEngine
from password_arena.history import HistoryManager
from password_arena.models import ArenaConfig
from password_arena.reporting import experiment_report_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="password-arena",
        description="Run a safe local attacker-versus-defender password simulation.",
    )
    parser.add_argument("--config", type=Path, help="Path to JSON configuration file.")
    parser.add_argument("--rounds", type=int, default=argparse.SUPPRESS)
    parser.add_argument("--start-difficulty", type=int, default=argparse.SUPPRESS)
    parser.add_argument("--difficulty-step", type=int, default=argparse.SUPPRESS)
    parser.add_argument("--max-guesses", type=int, default=argparse.SUPPRESS)
    parser.add_argument("--seed", type=int, default=argparse.SUPPRESS)
    parser.add_argument("--reveal-passwords", action="store_true", default=argparse.SUPPRESS)
    parser.add_argument(
        "--generator-mode",
        choices=["secure", "deterministic-test"],
        default=argparse.SUPPRESS,
        help="Generator mode for cryptographic passwords.",
    )
    parser.add_argument(
        "--generator-version",
        choices=["1.0", "benchmark"],
        default=argparse.SUPPRESS,
        help="Generator version for vocabularies and templates.",
    )
    parser.add_argument("--output", type=Path, help="Write the complete experiment JSON.")
    parser.add_argument("--report", type=Path, help="Write a two-sided Markdown arena report.")
    parser.add_argument(
        "--export-csv", type=Path, help="Write a CSV of normalized round and strategy data."
    )
    parser.add_argument(
        "--export-html", type=Path, help="Write a standalone HTML report for portfolio sharing."
    )
    parser.add_argument("--history-list", action="store_true", help="List saved experiments.")
    parser.add_argument(
        "--history-load", type=str, metavar="ID",
        help="Load and display a saved experiment."
    )
    parser.add_argument(
        "--history-delete", type=str, metavar="ID",
        help="Delete a saved experiment."
    )
    parser.add_argument(
        "--history-export", nargs=2, metavar=("ID", "PATH"),
        help="Export a saved experiment to a file."
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    hm = HistoryManager()
    if args.history_list:
        runs = hm.list_runs()
        print(f"{'Experiment ID':<36}  {'Timestamp':<25}  {'Rounds':<6}  {'Solve Rate':<10}")
        print("=" * 86)
        for r in runs:
            print(f"{r['experiment_id']:<36}  {r['timestamp']:<25}  " \
                  f"{r['total_rounds']:<6}  {r['solve_rate']:.1%}")
        return 0

    if args.history_delete:
        try:
            hm.delete(args.history_delete)
            print(f"Deleted experiment {args.history_delete}.")
        except FileNotFoundError:
            print(f"Experiment {args.history_delete} not found.")
            return 1
        return 0

    if args.history_export:
        exp_id, out_path = args.history_export
        try:
            hm.export(exp_id, Path(out_path))
            print(f"Exported {exp_id} to {out_path}.")
        except FileNotFoundError:
            print(f"Experiment {exp_id} not found.")
            return 1
        return 0

    experiment = None
    if args.history_load:
        try:
            experiment = hm.load(args.history_load)
            print(f"Loaded experiment {args.history_load}.")
        except FileNotFoundError:
            print(f"Experiment {args.history_load} not found.")
            return 1
    else:
    
        config_dict = {}
        if hasattr(args, "config") and args.config is not None:
            try:
                config_content = args.config.read_text(encoding="utf-8")
                config_dict = json.loads(config_content)
            except Exception as e:
                parser.error(f"Failed to load config file: {e}")

        cli_args = vars(args)
        cli_keys = [
            "rounds",
            "start_difficulty",
            "difficulty_step",
            "max_guesses",
            "seed",
            "reveal_passwords",
            "generator_mode",
            "generator_version",
        ]
        for key in cli_keys:
            if key in cli_args:
                config_dict[key] = cli_args[key]

        if "defender_config" in config_dict and isinstance(config_dict["defender_config"], dict):
            from password_arena.models import RoleConfig
            config_dict["defender_config"] = RoleConfig(**config_dict["defender_config"])
        if "attacker_config" in config_dict and isinstance(config_dict["attacker_config"], dict):
            from password_arena.models import RoleConfig
            config_dict["attacker_config"] = RoleConfig(**config_dict["attacker_config"])
        if "evaluator_config" in config_dict and isinstance(config_dict["evaluator_config"], dict):
            from password_arena.models import RoleConfig
            config_dict["evaluator_config"] = RoleConfig(**config_dict["evaluator_config"])

        try:
            config = ArenaConfig(**config_dict)
        except TypeError as e:
            parser.error(f"Invalid configuration: {e}")

        try:
            config.validate()
        except ValueError as e:
            parser.error(str(e))

        experiment = ArenaEngine(config).run()
        hm.save(experiment)

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

    if args.export_csv:
        from password_arena.reporting import experiment_export_csv
        args.export_csv.parent.mkdir(parents=True, exist_ok=True)
        args.export_csv.write_text(experiment_export_csv(experiment), encoding="utf-8")
        print(f"Arena CSV written to {args.export_csv}")

    if args.export_html:
        from password_arena.reporting import experiment_export_html
        args.export_html.parent.mkdir(parents=True, exist_ok=True)
        args.export_html.write_text(experiment_export_html(experiment), encoding="utf-8")
        print(f"Arena HTML written to {args.export_html}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
