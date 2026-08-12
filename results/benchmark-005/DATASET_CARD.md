---
pretty_name: Password Arena Public Benchmark
license: mit
language:
  - en
tags:
  - synthetic
  - cybersecurity
  - benchmark
---

# Password Arena Public Benchmark

## Purpose

This dataset documents bounded Password Arena attacker-versus-defender experiments
for reproducible analysis and educational comparison. Dataset schema version:
`1.1.0`.

## Synthetic source

All targets are generated synthetically inside Password Arena.
No real credentials are tested, collected, imported, or included. The export contains
101
recorded rounds: 101 comparable and 0
excluded from headline comparison.

## Methodology

Each row represents one round that actually completed far enough to create a recorded
round result. Preflight failures and unstarted interrupted rounds do not create rows.
Repeated trials use recorded seeds and generator settings. The deterministic test mode
supports exact generator replay; hosted models are stochastic even with repeated seeds.

## Attacker and defender roles

The defender chooses a synthetic password family. The attacker selects and executes a
bounded strategy plan against an in-memory equality check. Provider-generated prose is
not an execution record and is not exported.

## Comparability

`comparable` preserves the recorded round flag. `exclusion_reason` comes only from a
matching recorded round-exclusion record. A null reason means unavailable or unknown;
the exporter does not infer a reason for legacy data.

## Solve rate

Solve rate is the share of comparable recorded rounds solved within the configured
guess budget. Bounded benchmark performance is not evidence of real-world cracking,
account compromise, or performance against authentication systems.

## Entropy and strength

Entropy bits and strength score are Password Arena's structural estimates for synthetic
targets. They are comparative heuristics, not guarantees of real-world password safety
or exact crack time.

## Model and thinking metadata

Provider and model IDs identify the recorded role configuration. Requested thinking is
the recorded request setting. Effective thinking is null when no provider call occurred
or when the provider did not record it. Provider and model behavior can change over time.

## Tokens, latency, and cost

Input, output, and reasoning token fields are numeric usage counts, never reasoning
content. Latency and estimated cost are included only when recorded. JSON null and blank
CSV cells mean unavailable; unavailable values are not zero.

## Intended uses

Use this dataset for synthetic benchmark analysis, reproducibility checks, educational
visualization, and comparison of bounded strategy behavior.

## Prohibited uses

Do not use this dataset or Password Arena for real credential collection, breach-dump
ingestion, login targeting, credential stuffing, distributed guessing, or claims about
compromising real accounts.

## Limitations

The password generators and attack strategies are intentionally bounded and synthetic.
Hosted models are stochastic, repeated rounds may not be independent, capability data
can become stale, and provider and model behavior can change over time.

## Security guarantees

The public schema is a fixed scalar allowlist. It excludes passwords, candidates,
prompts, events, notes, learning text, model prose, private reasoning, credentials,
authorization headers, environment values, and API tokens. Every JSONL and CSV payload
is validated immediately before return. Export is local and performs no upload.
