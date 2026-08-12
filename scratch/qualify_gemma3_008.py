"""One-off qualification gate for gemma3:4b ahead of Benchmark 008.

Runs a handful of tiny real arena experiments (not a bespoke reimplementation
of the schema) so the attacker strategy-allocation and defender family-selection
structured-output calls are exercised through the exact same code path
Password Arena uses during a real benchmark round. Reports schema-valid rate,
latency, and token usage. Not part of the committed benchmark runner -- scratch,
one-off, per repo convention (see scratch/run_experiment_a_and_b.py etc).
"""

import json
import time

from password_arena.engine import build_arena_engine
from password_arena.models import ArenaConfig, RoleConfig

MODEL = "gemma3:4b"
SEEDS = [42, 43]
ROUNDS_PER_EXPERIMENT = 5


def main():
    role = RoleConfig(provider="ollama", model=MODEL)
    experiments = []

    for seed in SEEDS:
        config = ArenaConfig(
            rounds=ROUNDS_PER_EXPERIMENT,
            max_guesses=50,
            seed=seed,
            defender_config=role,
            attacker_config=role,
            generator_mode="deterministic-test",
            generator_version="benchmark",
        )
        result_or_failure = build_arena_engine(config)
        if not hasattr(result_or_failure, "run"):
            experiments.append(
                {
                    "seed": seed,
                    "preflight_failure": {
                        "role": result_or_failure.role,
                        "state": result_or_failure.state,
                        "message": result_or_failure.message,
                    },
                }
            )
            continue

        t0 = time.time()
        exp = result_or_failure.run()
        wall_s = time.time() - t0

        rounds_data = []
        for r in exp.rounds:
            rounds_data.append(
                {
                    "round_number": r.round_number,
                    "attacker_usage": (
                        {
                            "input_tokens": r.attacker_usage.input_tokens,
                            "output_tokens": r.attacker_usage.output_tokens,
                            "latency_ms": r.attacker_usage.latency_ms,
                        }
                        if r.attacker_usage
                        else None
                    ),
                    "defender_usage": (
                        {
                            "input_tokens": r.defender_usage.input_tokens,
                            "output_tokens": r.defender_usage.output_tokens,
                            "latency_ms": r.defender_usage.latency_ms,
                        }
                        if r.defender_usage
                        else None
                    ),
                    "calibration_warning": r.calibration_warning,
                }
            )

        experiments.append(
            {
                "seed": seed,
                "wall_s": wall_s,
                "rounds_completed": len(exp.rounds),
                "rounds_requested": ROUNDS_PER_EXPERIMENT,
                "interruption_reason": exp.interruption_reason,
                "interruption_state": exp.interruption_state,
                "rounds": rounds_data,
            }
        )
        print(
            f"seed={seed}: {len(exp.rounds)}/{ROUNDS_PER_EXPERIMENT} rounds, "
            f"interruption={exp.interruption_state}, wall={wall_s:.1f}s"
        )

    # Aggregate schema-valid rate: each completed round implies one successful
    # attacker structured call and one successful defender structured call.
    # An interruption with state "invalid_response" implies exactly one
    # additional failed structured call (whichever role failed).
    successful_calls = 0
    failed_calls = 0
    latencies_ms = []
    input_tokens = []
    output_tokens = []

    for e in experiments:
        if "preflight_failure" in e:
            continue
        successful_calls += 2 * e["rounds_completed"]
        if e["interruption_state"] == "invalid_response":
            failed_calls += 1
        for r in e["rounds"]:
            for usage_key in ("attacker_usage", "defender_usage"):
                u = r[usage_key]
                if u:
                    latencies_ms.append(u["latency_ms"])
                    input_tokens.append(u["input_tokens"])
                    output_tokens.append(u["output_tokens"])

    total_calls = successful_calls + failed_calls
    schema_valid_rate = successful_calls / total_calls if total_calls else None

    summary = {
        "model": MODEL,
        "seeds": SEEDS,
        "rounds_per_experiment": ROUNDS_PER_EXPERIMENT,
        "total_structured_calls_observed": total_calls,
        "successful_structured_calls": successful_calls,
        "failed_structured_calls": failed_calls,
        "schema_valid_rate": schema_valid_rate,
        "mean_latency_ms": sum(latencies_ms) / len(latencies_ms) if latencies_ms else None,
        "mean_input_tokens": sum(input_tokens) / len(input_tokens) if input_tokens else None,
        "mean_output_tokens": sum(output_tokens) / len(output_tokens) if output_tokens else None,
        "experiments": experiments,
    }

    with open("scratch/gemma3_qualification_result.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps({k: v for k, v in summary.items() if k != "experiments"}, indent=2))


if __name__ == "__main__":
    main()
