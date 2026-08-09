"""Fail-closed public benchmark dataset export.

The exporter is intentionally separate from ordinary reports. It builds rows from
an explicit scalar allowlist and never serializes source experiment dictionaries,
events, prompts, notes, learning text, candidates, or password displays.
"""

from __future__ import annotations

import csv
import enum
import hashlib
import hmac
import json
import math
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, fields
from io import StringIO
from typing import TypeAlias

from password_arena.models import (
    ARENA_EVENT_SCHEMA_VERSION,
    ExperimentResult,
    MatchupLike,
    RoleConfig,
    RoleMetadata,
    RoleUsage,
    RoundResult,
)
from password_arena.tournament_history import TOURNAMENT_SCHEMA_VERSION

PASSWORD_ARENA_DATASET_SCHEMA_VERSION = "1.0.0"

PublicScalar: TypeAlias = str | int | float | bool | None


class DatasetExportFormat(enum.StrEnum):
    JSONL = "jsonl"
    CSV = "csv"


class PublicDatasetSafetyError(RuntimeError):
    """Raised instead of returning a partial or unsafe public dataset."""


@dataclass(frozen=True, slots=True)
class PublicBenchmarkSource:
    """One matchup paired with every full experiment record still available."""

    matchup: MatchupLike
    experiments: tuple[ExperimentResult, ...]


@dataclass(frozen=True, slots=True)
class PublicBenchmarkSummary:
    total_rows: int
    comparable_rows: int
    excluded_rows: int


@dataclass(frozen=True, slots=True)
class PublicBenchmarkRow:
    dataset_schema_version: str
    application_version: str | None
    tournament_storage_schema_version: str
    event_schema_version: str
    replay_schema_version: str | None
    attacker_prompt_version: str | None
    defender_prompt_version: str | None
    capability_registry_version: str | None

    tournament_id: str
    matchup_id: str
    experiment_id: str
    tournament_timestamp: str
    experiment_timestamp: str
    seed: int
    round_number: int
    difficulty: int
    generator_mode: str
    generator_version: str

    attacker_provider: str
    attacker_model: str | None
    attacker_requested_thinking_level: str | None
    attacker_effective_thinking_level: str | None
    attacker_input_tokens: int | None
    attacker_output_tokens: int | None
    attacker_reasoning_tokens: int | None
    attacker_latency_ms: float | None
    attacker_estimated_cost: float | None
    attacker_guesses_used: int
    attacker_winning_strategy: str | None
    attacker_solved: bool
    attacker_outcome: str

    defender_provider: str
    defender_model: str | None
    defender_requested_thinking_level: str | None
    defender_effective_thinking_level: str | None
    defender_input_tokens: int | None
    defender_output_tokens: int | None
    defender_reasoning_tokens: int | None
    defender_latency_ms: float | None
    defender_estimated_cost: float | None
    defender_password_family: str
    defender_password_length: int
    defender_entropy_bits: float
    defender_strength_score: int

    comparable: bool
    exclusion_reason: str | None

    def to_dict(self) -> dict[str, PublicScalar]:
        """Return fields in the one canonical public-column order."""
        return {
            column: getattr(self, column)
            for column in PUBLIC_BENCHMARK_COLUMNS
        }


PUBLIC_BENCHMARK_COLUMNS = tuple(field.name for field in fields(PublicBenchmarkRow))


@dataclass(frozen=True, slots=True)
class PublicBenchmarkDataset:
    rows: tuple[PublicBenchmarkRow, ...]
    summary: PublicBenchmarkSummary
    _source_secret_fingerprints: frozenset[tuple[int, str]] = frozenset()


def _enum_text(value: object | None) -> str | None:
    if value is None:
        return None
    enum_value = getattr(value, "value", value)
    return enum_value if isinstance(enum_value, str) else str(enum_value)


def _role_metadata(
    recorded: RoleMetadata | None, configured: RoleConfig
) -> RoleMetadata:
    return recorded or RoleMetadata.from_role_config(configured)


def _usage_values(
    usage: RoleUsage | None,
) -> tuple[int | None, int | None, int | None, float | None, float | None, str | None]:
    if usage is None:
        return (None, None, None, None, None, None)
    return (
        usage.input_tokens,
        usage.output_tokens,
        usage.reasoning_tokens,
        usage.latency_ms,
        usage.estimated_cost,
        _enum_text(usage.effective_thinking_level),
    )


def _recorded_exclusion_reason(
    source: PublicBenchmarkSource,
    experiment: ExperimentResult,
    round_result: RoundResult,
) -> str | None:
    """Use only a matching stored exclusion record; never infer a reason."""
    for record in source.matchup.excluded_round_records:
        experiment_matches = record.experiment_id == experiment.experiment_id or (
            record.experiment_id is None and record.seed == experiment.config.seed
        )
        if experiment_matches and record.round_number == round_result.round_number:
            return _enum_text(record.reason)
    return None


def _secret_fingerprint(value: str) -> tuple[int, str]:
    return (len(value), hashlib.sha256(value.encode("utf-8")).hexdigest())


def _source_secret_fingerprints(
    experiments: Sequence[ExperimentResult],
) -> frozenset[tuple[int, str]]:
    revealed: set[tuple[int, str]] = set()
    for experiment in experiments:
        if not experiment.config.reveal_passwords:
            continue
        for round_result in experiment.rounds:
            if round_result.password_display:
                revealed.add(_secret_fingerprint(round_result.password_display))
            if round_result.attack.candidate:
                revealed.add(_secret_fingerprint(round_result.attack.candidate))
    return frozenset(revealed)


def _build_row(
    tournament_id: str,
    tournament_timestamp: str,
    tournament_storage_schema_version: str,
    source: PublicBenchmarkSource,
    experiment: ExperimentResult,
    round_result: RoundResult,
) -> PublicBenchmarkRow:
    replay = source.matchup.replay
    attacker_metadata = _role_metadata(
        round_result.attacker_metadata, experiment.config.attacker_config
    )
    defender_metadata = _role_metadata(
        round_result.defender_metadata, experiment.config.defender_config
    )
    (
        attacker_input_tokens,
        attacker_output_tokens,
        attacker_reasoning_tokens,
        attacker_latency_ms,
        attacker_estimated_cost,
        attacker_effective_thinking_level,
    ) = _usage_values(round_result.attacker_usage)
    (
        defender_input_tokens,
        defender_output_tokens,
        defender_reasoning_tokens,
        defender_latency_ms,
        defender_estimated_cost,
        defender_effective_thinking_level,
    ) = _usage_values(round_result.defender_usage)

    return PublicBenchmarkRow(
        dataset_schema_version=PASSWORD_ARENA_DATASET_SCHEMA_VERSION,
        application_version=replay.application_version if replay else None,
        tournament_storage_schema_version=tournament_storage_schema_version,
        event_schema_version=ARENA_EVENT_SCHEMA_VERSION,
        replay_schema_version=replay.schema_version if replay else None,
        attacker_prompt_version=replay.attacker_prompt_version if replay else None,
        defender_prompt_version=replay.defender_prompt_version if replay else None,
        capability_registry_version=(
            replay.capability_registry_version if replay else None
        ),
        tournament_id=tournament_id,
        matchup_id=source.matchup.matchup_id,
        experiment_id=experiment.experiment_id,
        tournament_timestamp=tournament_timestamp,
        experiment_timestamp=experiment.timestamp,
        seed=experiment.config.seed,
        round_number=round_result.round_number,
        difficulty=round_result.difficulty,
        generator_mode=experiment.config.generator_mode,
        generator_version=experiment.config.generator_version,
        attacker_provider=attacker_metadata.provider,
        attacker_model=attacker_metadata.model,
        attacker_requested_thinking_level=_enum_text(attacker_metadata.thinking_level),
        attacker_effective_thinking_level=attacker_effective_thinking_level,
        attacker_input_tokens=attacker_input_tokens,
        attacker_output_tokens=attacker_output_tokens,
        attacker_reasoning_tokens=attacker_reasoning_tokens,
        attacker_latency_ms=attacker_latency_ms,
        attacker_estimated_cost=attacker_estimated_cost,
        attacker_guesses_used=round_result.attack.guesses_used,
        attacker_winning_strategy=round_result.attack.winning_strategy,
        attacker_solved=round_result.attack.solved,
        attacker_outcome=_enum_text(round_result.attack.outcome) or "",
        defender_provider=defender_metadata.provider,
        defender_model=defender_metadata.model,
        defender_requested_thinking_level=_enum_text(defender_metadata.thinking_level),
        defender_effective_thinking_level=defender_effective_thinking_level,
        defender_input_tokens=defender_input_tokens,
        defender_output_tokens=defender_output_tokens,
        defender_reasoning_tokens=defender_reasoning_tokens,
        defender_latency_ms=defender_latency_ms,
        defender_estimated_cost=defender_estimated_cost,
        defender_password_family=round_result.defender_strategy,
        defender_password_length=round_result.password_length,
        defender_entropy_bits=round_result.strength.entropy_bits,
        defender_strength_score=round_result.strength.score,
        comparable=round_result.comparable,
        exclusion_reason=_recorded_exclusion_reason(source, experiment, round_result),
    )


def build_public_benchmark_dataset(
    tournament_id: str,
    tournament_timestamp: str,
    sources: Sequence[PublicBenchmarkSource],
    *,
    tournament_storage_schema_version: str = TOURNAMENT_SCHEMA_VERSION,
) -> PublicBenchmarkDataset:
    """Build immutable rows for recorded rounds only.

    Preflight failures and unstarted interrupted rounds have no ``RoundResult`` and
    therefore cannot produce a row. Non-comparable recorded rounds remain present.
    """
    rows: list[PublicBenchmarkRow] = []
    all_experiments: list[ExperimentResult] = []
    for source in sources:
        all_experiments.extend(source.experiments)
        for experiment in source.experiments:
            for round_result in experiment.rounds:
                rows.append(
                    _build_row(
                        tournament_id,
                        tournament_timestamp,
                        tournament_storage_schema_version,
                        source,
                        experiment,
                        round_result,
                    )
                )

    comparable_rows = sum(row.comparable for row in rows)
    summary = PublicBenchmarkSummary(
        total_rows=len(rows),
        comparable_rows=comparable_rows,
        excluded_rows=len(rows) - comparable_rows,
    )
    return PublicBenchmarkDataset(
        rows=tuple(rows),
        summary=summary,
        _source_secret_fingerprints=_source_secret_fingerprints(all_experiments),
    )


_FORBIDDEN_FIELD_TERMS = (
    "authorization",
    "api_key",
    "candidate",
    "chain_of_thought",
    "credential",
    "event",
    "hf_token",
    "learning",
    "note",
    "password",
    "password_display",
    "prompt",
    "reasoning",
    "raw_reasoning",
    "secret",
)
_SECRET_PATTERNS = (
    re.compile(r"\bhf_[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b(?:gh[pousr]_|github_pat_)[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    re.compile(r"(?i)\bauthorization\s*:\s*(?:bearer|basic)\s+\S+"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|hf_token)\s*[:=]\s*\S+"
    ),
)


def _rows_from_serialized(
    payload: str, export_format: DatasetExportFormat | None
) -> list[Mapping[str, object]]:
    format_to_use = export_format
    if format_to_use is None:
        format_to_use = (
            DatasetExportFormat.JSONL
            if not payload.lstrip() or payload.lstrip().startswith("{")
            else DatasetExportFormat.CSV
        )
    try:
        if format_to_use == DatasetExportFormat.JSONL:
            parsed: list[Mapping[str, object]] = []
            for line in payload.splitlines():
                if not line.strip():
                    continue
                item = json.loads(line)
                if not isinstance(item, dict):
                    raise PublicDatasetSafetyError(
                        "Public dataset JSONL rows must be objects."
                    )
                parsed.append(item)
            return parsed

        reader = csv.DictReader(StringIO(payload))
        if reader.fieldnames is None:
            return []
        if tuple(reader.fieldnames) != PUBLIC_BENCHMARK_COLUMNS:
            raise PublicDatasetSafetyError("Public dataset contains an unknown column.")
        return list(reader)
    except PublicDatasetSafetyError:
        raise
    except (csv.Error, json.JSONDecodeError, TypeError, ValueError):
        raise PublicDatasetSafetyError("Public dataset serialization is invalid.") from None


def _validate_rows(rows: Sequence[Mapping[str, object]]) -> None:
    expected = set(PUBLIC_BENCHMARK_COLUMNS)
    for row in rows:
        actual = set(row)
        unknown = actual - expected
        if unknown:
            unknown_name = next(iter(unknown))
            normalized = str(unknown_name).lower()
            if any(term in normalized for term in _FORBIDDEN_FIELD_TERMS):
                raise PublicDatasetSafetyError(
                    "Public dataset contains an unknown column with a forbidden field name."
                )
            raise PublicDatasetSafetyError("Public dataset contains an unknown column.")
        if actual != expected:
            raise PublicDatasetSafetyError("Public dataset is missing a required column.")

        for value in row.values():
            if isinstance(value, (dict, list, tuple, set, frozenset)):
                raise PublicDatasetSafetyError(
                    "Public dataset values must be scalar."
                )
            if value is not None and not isinstance(value, (str, int, float, bool)):
                raise PublicDatasetSafetyError(
                    "Public dataset values must be scalar."
                )
            if isinstance(value, float) and not math.isfinite(value):
                raise PublicDatasetSafetyError(
                    "Public dataset values must be finite."
                )


def validate_public_dataset_payload(
    payload: str | Sequence[Mapping[str, object]],
    *,
    export_format: DatasetExportFormat | None = None,
    serialized_payload: str | None = None,
    source_secret_values: Collection[str] = (),
    source_secret_fingerprints: Collection[tuple[int, str]] = (),
) -> None:
    """Reject any schema drift, containers, token patterns, or source secrets."""
    if isinstance(payload, str):
        rows = _rows_from_serialized(payload, export_format)
        serialization = payload
    else:
        rows = list(payload)
        try:
            serialization = (
                serialized_payload
                if serialized_payload is not None
                else json.dumps(rows, ensure_ascii=False, allow_nan=False)
            )
        except (TypeError, ValueError):
            raise PublicDatasetSafetyError(
                "Public dataset serialization is invalid."
            ) from None

    _validate_rows(rows)

    for pattern in _SECRET_PATTERNS:
        if pattern.search(serialization):
            raise PublicDatasetSafetyError(
                "Public dataset contains a secret-like token pattern."
            )

    fingerprints = set(source_secret_fingerprints)
    fingerprints.update(
        _secret_fingerprint(value) for value in source_secret_values if value
    )
    if fingerprints:
        scalar_text = [
            str(value) for row in rows for value in row.values() if value is not None
        ]
        scan_values = [serialization, *scalar_text]
        for length, expected_digest in fingerprints:
            for value in scan_values:
                if length <= 0 or len(value) < length:
                    continue
                for start in range(len(value) - length + 1):
                    candidate = value[start : start + length]
                    candidate_digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
                    if hmac.compare_digest(candidate_digest, expected_digest):
                        raise PublicDatasetSafetyError(
                            "Public dataset serialization contains a source secret value."
                        )


def export_public_dataset_jsonl(dataset: PublicBenchmarkDataset) -> str:
    payload_rows = [row.to_dict() for row in dataset.rows]
    try:
        serialized = "\n".join(
            json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            for row in payload_rows
        )
    except (TypeError, ValueError):
        raise PublicDatasetSafetyError("Public dataset serialization is invalid.") from None
    validate_public_dataset_payload(
        payload_rows,
        export_format=DatasetExportFormat.JSONL,
        serialized_payload=serialized,
        source_secret_fingerprints=dataset._source_secret_fingerprints,
    )
    return serialized


def export_public_dataset_csv(dataset: PublicBenchmarkDataset) -> str:
    payload_rows = [row.to_dict() for row in dataset.rows]
    output = StringIO(newline="")
    try:
        writer = csv.DictWriter(
            output,
            fieldnames=PUBLIC_BENCHMARK_COLUMNS,
            extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(payload_rows)
        serialized = output.getvalue()
    except (csv.Error, TypeError, ValueError):
        raise PublicDatasetSafetyError("Public dataset serialization is invalid.") from None
    validate_public_dataset_payload(
        payload_rows,
        export_format=DatasetExportFormat.CSV,
        serialized_payload=serialized,
        source_secret_fingerprints=dataset._source_secret_fingerprints,
    )
    return serialized


def generate_dataset_card(dataset: PublicBenchmarkDataset) -> str:
    """Generate a static Hugging Face-compatible Dataset Card."""
    summary = dataset.summary
    return f"""---
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
`{PASSWORD_ARENA_DATASET_SCHEMA_VERSION}`.

## Synthetic source

All targets are generated synthetically inside Password Arena.
No real credentials are tested, collected, imported, or included. The export contains
{summary.total_rows}
recorded rounds: {summary.comparable_rows} comparable and {summary.excluded_rows}
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
"""
