import csv
import json
from dataclasses import replace
from io import StringIO
from typing import cast

import pytest

from password_arena.dataset_export import (
    PASSWORD_ARENA_DATASET_SCHEMA_VERSION,
    PUBLIC_BENCHMARK_COLUMNS,
    DatasetExportFormat,
    PublicBenchmarkDataset,
    PublicBenchmarkSource,
    PublicDatasetSafetyError,
    build_public_benchmark_dataset,
    export_public_dataset_csv,
    export_public_dataset_jsonl,
    generate_dataset_card,
    validate_public_dataset_payload,
)
from password_arena.models import (
    ArenaConfig,
    ArenaEvent,
    AttackResult,
    ExclusionReason,
    ExclusionRecord,
    ExperimentResult,
    MatchupConfig,
    MatchupResult,
    ReplayMetadata,
    RoleConfig,
    RoleMetadata,
    RoleUsage,
    RoundOutcome,
    RoundResult,
    StrengthReport,
)
from password_arena.providers import ThinkingLevel
from password_arena.tournament import aggregate_matchup

TOURNAMENT_ID = "tournament-public-test"
TOURNAMENT_TIMESTAMP = "2026-08-09T12:00:00+00:00"


def _build_source(*, reveal_passwords: bool = False) -> PublicBenchmarkSource:
    attacker_config = RoleConfig(
        provider="mock",
        model="attacker-model",
        thinking_level=ThinkingLevel.HIGH,
    )
    defender_config = RoleConfig(
        provider="mock",
        model="defender-model",
        thinking_level=ThinkingLevel.LOW,
    )
    arena_config = ArenaConfig(
        rounds=2,
        seed=101,
        reveal_passwords=reveal_passwords,
        attacker_config=attacker_config,
        defender_config=defender_config,
        generator_mode="deterministic-test",
        generator_version="benchmark",
    )

    target = "Target-Secret-483"
    candidate = "Solved-Candidate-483"
    first_round = RoundResult(
        round_number=1,
        difficulty=3,
        password_display=target if reveal_passwords else "•" * len(target),
        password_length=len(target),
        strength=StrengthReport(
            entropy_bits=52.5,
            score=3,
            character_pool=62,
            pattern_penalty=1.5,
        ),
        attack=AttackResult(
            solved=True,
            guesses_used=17,
            winning_strategy="mutation",
            elapsed_ms=1.25,
            candidate=candidate if reveal_passwords else None,
            outcome=RoundOutcome.COMPLETED,
        ),
        defender_strategy="eval-substitution",
        defender_note="SYSTEM PROMPT: never publish this prompt text",
        defender_learning="private defender adaptation text",
        attacker_note="sk-test-private-api-key-123456789",
        attacker_learning="raw private reasoning must stay private",
        defender_metadata=RoleMetadata(
            provider="mock",
            model="defender-model",
            thinking_level=ThinkingLevel.LOW,
        ),
        attacker_metadata=RoleMetadata(
            provider="mock",
            model="attacker-model",
            thinking_level=ThinkingLevel.HIGH,
        ),
        attacker_usage=RoleUsage(
            input_tokens=11,
            output_tokens=7,
            reasoning_tokens=3,
            latency_ms=120.5,
            estimated_cost=0.012,
            requested_thinking_level=ThinkingLevel.HIGH,
            effective_thinking_level=ThinkingLevel.MEDIUM,
        ),
        defender_usage=RoleUsage(
            input_tokens=13,
            output_tokens=5,
            reasoning_tokens=None,
            latency_ms=80.25,
            estimated_cost=None,
            requested_thinking_level=ThinkingLevel.LOW,
            effective_thinking_level=ThinkingLevel.LOW,
        ),
        comparable=True,
    )
    second_round = RoundResult(
        round_number=2,
        difficulty=4,
        password_display="•" * 20,
        password_length=20,
        strength=StrengthReport(
            entropy_bits=80.0,
            score=4,
            character_pool=62,
            pattern_penalty=0.0,
        ),
        attack=AttackResult(
            solved=False,
            guesses_used=100,
            winning_strategy=None,
            elapsed_ms=2.5,
            outcome=RoundOutcome.RESISTED,
        ),
        defender_strategy="secure-random",
        defender_note="Authorization: Bearer should-never-leak",
        defender_learning="hidden defender prose",
        attacker_note="hidden attacker prose",
        attacker_learning="hidden attacker memory",
        defender_metadata=RoleMetadata(
            provider="mock",
            model="defender-model",
            thinking_level=ThinkingLevel.LOW,
        ),
        attacker_metadata=RoleMetadata(
            provider="mock",
            model="attacker-model",
            thinking_level=ThinkingLevel.HIGH,
        ),
        attacker_usage=None,
        defender_usage=None,
        comparable=False,
    )
    experiment = ExperimentResult(
        config=arena_config,
        rounds=(first_round, second_round),
        experiment_id="experiment-101",
        timestamp="2026-08-09T12:01:00+00:00",
        events=(
            ArenaEvent(
                event_id="event-secret-test",
                experiment_id="experiment-101",
                timestamp="2026-08-09T12:01:01+00:00",
                application_version="test-app",
                schema_version="1.0",
                event_type="private_test_payload",
                round_id=1,
                payload={
                    "prompt": "event prompt must not be exported",
                    "authorization": "Bearer event-secret",
                    "candidate": candidate,
                    "target": target,
                },
            ),
        ),
    )
    matchup_config = MatchupConfig(
        attacker=attacker_config,
        defender=defender_config,
        rounds=2,
        seeds=(101,),
        generator_version="benchmark",
        generator_mode="deterministic-test",
        max_guesses=100,
    )
    matchup = aggregate_matchup(matchup_config, [experiment], [])
    matchup = replace(
        matchup,
        matchup_id="matchup-public-test",
        replay=ReplayMetadata(
            attacker=RoleMetadata.from_role_config(attacker_config),
            defender=RoleMetadata.from_role_config(defender_config),
            seeds=(101,),
            rounds_per_match=2,
            max_guesses=100,
            generator_mode="deterministic-test",
            generator_version="benchmark",
            application_version="0.1-test",
            schema_version="1.7-test",
            deterministic=False,
            attacker_prompt_version="attacker-prompt-test",
            defender_prompt_version="defender-prompt-test",
            capability_registry_version="capability-test",
        ),
    )
    return PublicBenchmarkSource(matchup=matchup, experiments=(experiment,))


def _build_dataset(source: PublicBenchmarkSource | None = None) -> PublicBenchmarkDataset:
    return build_public_benchmark_dataset(
        TOURNAMENT_ID,
        TOURNAMENT_TIMESTAMP,
        (source or _build_source(),),
        tournament_storage_schema_version="2.2-test",
    )


def test_dataset_format_values_are_stable() -> None:
    assert DatasetExportFormat.JSONL.value == "jsonl"
    assert DatasetExportFormat.CSV.value == "csv"
    assert PASSWORD_ARENA_DATASET_SCHEMA_VERSION == "1.0.0"


def test_builds_one_row_per_recorded_round_with_versions_and_metrics() -> None:
    dataset = _build_dataset()

    assert dataset.summary.total_rows == 2
    assert dataset.summary.comparable_rows == 1
    assert dataset.summary.excluded_rows == 1
    assert len(dataset.rows) == 2

    first = dataset.rows[0]
    assert tuple(first.to_dict()) == PUBLIC_BENCHMARK_COLUMNS
    assert first.dataset_schema_version == PASSWORD_ARENA_DATASET_SCHEMA_VERSION
    assert first.application_version == "0.1-test"
    assert first.tournament_storage_schema_version == "2.2-test"
    assert first.event_schema_version == "1.0"
    assert first.replay_schema_version == "1.7-test"
    assert first.attacker_prompt_version == "attacker-prompt-test"
    assert first.defender_prompt_version == "defender-prompt-test"
    assert first.capability_registry_version == "capability-test"

    assert first.tournament_id == TOURNAMENT_ID
    assert first.matchup_id == "matchup-public-test"
    assert first.experiment_id == "experiment-101"
    assert first.tournament_timestamp == TOURNAMENT_TIMESTAMP
    assert first.experiment_timestamp == "2026-08-09T12:01:00+00:00"
    assert first.seed == 101
    assert first.round_number == 1
    assert first.difficulty == 3
    assert first.generator_mode == "deterministic-test"
    assert first.generator_version == "benchmark"

    assert first.attacker_provider == "mock"
    assert first.attacker_model == "attacker-model"
    assert first.attacker_requested_thinking_level == "high"
    assert first.attacker_effective_thinking_level == "medium"
    assert first.attacker_input_tokens == 11
    assert first.attacker_output_tokens == 7
    assert first.attacker_reasoning_tokens == 3
    assert first.attacker_latency_ms == 120.5
    assert first.attacker_estimated_cost == 0.012
    assert first.attacker_guesses_used == 17
    assert first.attacker_winning_strategy == "mutation"
    assert first.attacker_solved is True
    assert first.attacker_outcome == "completed"

    assert first.defender_provider == "mock"
    assert first.defender_model == "defender-model"
    assert first.defender_requested_thinking_level == "low"
    assert first.defender_effective_thinking_level == "low"
    assert first.defender_input_tokens == 13
    assert first.defender_output_tokens == 5
    assert first.defender_reasoning_tokens is None
    assert first.defender_latency_ms == 80.25
    assert first.defender_estimated_cost is None
    assert first.defender_password_family == "eval-substitution"
    assert first.defender_password_length == len("Target-Secret-483")
    assert first.defender_entropy_bits == 52.5
    assert first.defender_strength_score == 3
    assert first.comparable is True
    assert first.exclusion_reason is None

    second = dataset.rows[1]
    assert second.comparable is False
    assert second.exclusion_reason == ExclusionReason.FALLBACK_USED.value
    assert second.attacker_requested_thinking_level == "high"
    assert second.attacker_effective_thinking_level is None
    assert second.attacker_input_tokens is None
    assert second.attacker_latency_ms is None
    assert second.attacker_estimated_cost is None


def test_non_comparable_legacy_round_without_recorded_reason_stays_unknown() -> None:
    source = _build_source()
    matchup = cast(MatchupResult, source.matchup)
    source = replace(
        source,
        matchup=replace(matchup, excluded_round_records=()),
    )

    dataset = _build_dataset(source)

    assert dataset.rows[1].comparable is False
    assert dataset.rows[1].exclusion_reason is None


def test_no_rows_are_invented_for_preflight_failures_or_unstarted_rounds() -> None:
    source = _build_source()
    recorded_round = source.experiments[0].rounds[0]
    interrupted = replace(
        source.experiments[0],
        rounds=(recorded_round,),
        interruption_reason="provider unavailable",
    )
    config = replace(source.matchup.config, rounds=3, seeds=(101, 102))
    matchup = aggregate_matchup(
        config,
        [interrupted],
        [
            ExclusionRecord(
                seed=102,
                experiment_id=None,
                round_number=None,
                reason=ExclusionReason.PREFLIGHT_FAILED,
            )
        ],
    )
    source = PublicBenchmarkSource(matchup=matchup, experiments=(interrupted,))

    dataset = _build_dataset(source)

    assert dataset.summary.total_rows == 1
    assert [row.round_number for row in dataset.rows] == [1]


def test_jsonl_and_csv_are_parseable_and_preserve_null_semantics() -> None:
    dataset = _build_dataset()

    jsonl_data = export_public_dataset_jsonl(dataset)
    json_rows = [json.loads(line) for line in jsonl_data.splitlines()]
    assert len(json_rows) == 2
    assert tuple(json_rows[0]) == PUBLIC_BENCHMARK_COLUMNS
    assert json_rows[0]["defender_reasoning_tokens"] is None
    assert json_rows[1]["attacker_input_tokens"] is None

    csv_data = export_public_dataset_csv(dataset)
    csv_rows = list(csv.DictReader(StringIO(csv_data)))
    assert len(csv_rows) == 2
    assert tuple(csv_rows[0]) == PUBLIC_BENCHMARK_COLUMNS
    assert csv_rows[0]["defender_reasoning_tokens"] == ""
    assert csv_rows[1]["attacker_input_tokens"] == ""
    assert csv_rows[1]["exclusion_reason"] == "fallback_used"


def test_empty_recorded_dataset_exports_no_synthetic_rows() -> None:
    dataset = build_public_benchmark_dataset(
        TOURNAMENT_ID,
        TOURNAMENT_TIMESTAMP,
        (),
        tournament_storage_schema_version="2.2-test",
    )

    assert dataset.summary.total_rows == 0
    assert export_public_dataset_jsonl(dataset) == ""
    csv_data = export_public_dataset_csv(dataset)
    assert tuple(next(csv.reader(StringIO(csv_data)))) == PUBLIC_BENCHMARK_COLUMNS
    assert list(csv.DictReader(StringIO(csv_data))) == []


def test_dataset_card_contains_required_methodology_and_safety_statements() -> None:
    card = generate_dataset_card(_build_dataset())
    lowered = card.lower()

    assert card.startswith("---\n")
    assert "# Password Arena Public Benchmark" in card
    assert "synthetic" in lowered
    assert "no real credentials are tested" in lowered
    assert "bounded benchmark performance is not evidence of real-world cracking" in lowered
    assert "hosted models are stochastic" in lowered
    assert "provider and model behavior can change over time" in lowered
    assert "unavailable values are not zero" in lowered
    assert "comparability" in lowered
    assert "solve rate" in lowered
    assert "entropy" in lowered
    assert "prohibited uses" in lowered
    assert "security guarantees" in lowered


def test_security_boundary_excludes_source_secrets_and_private_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hf_token = "hf_environment_token_must_not_escape_123456"
    environment_secret = "environment-secret-value-987654"
    monkeypatch.setenv("HF_TOKEN", hf_token)
    monkeypatch.setenv("PASSWORD_ARENA_TEST_SECRET", environment_secret)
    dataset = _build_dataset(_build_source(reveal_passwords=True))
    assert "Target-Secret-483" not in repr(dataset)
    assert "Solved-Candidate-483" not in repr(dataset)

    outputs = "\n".join(
        (
            export_public_dataset_jsonl(dataset),
            export_public_dataset_csv(dataset),
            generate_dataset_card(dataset),
        )
    )

    forbidden_values = (
        "Target-Secret-483",
        "Solved-Candidate-483",
        "sk-test-private-api-key-123456789",
        "Authorization: Bearer should-never-leak",
        "event prompt must not be exported",
        "Bearer event-secret",
        "raw private reasoning must stay private",
        "private defender adaptation text",
        hf_token,
        environment_secret,
    )
    for forbidden in forbidden_values:
        assert forbidden not in outputs


def test_validator_rejects_unknown_forbidden_and_nested_fields() -> None:
    row = _build_dataset().rows[0].to_dict()

    with pytest.raises(PublicDatasetSafetyError, match="unknown column"):
        validate_public_dataset_payload([{**row, "password": "do-not-export"}])

    nested: dict[str, object] = dict(row)
    nested["attacker_model"] = {"nested": "not allowed"}
    with pytest.raises(PublicDatasetSafetyError, match="scalar"):
        validate_public_dataset_payload([nested])


@pytest.mark.parametrize(
    "secret_value",
    [
        "hf_abcdefghijklmnopqrstuvwxyz123456",
        "sk-proj-abcdefghijklmnopqrstuvwxyz123456",
        "Authorization: Bearer abcdefghijklmnopqrstuvwxyz",
        "HF_TOKEN=abcdefghijklmnopqrstuvwxyz123456",
    ],
)
def test_validator_rejects_secret_like_values(secret_value: str) -> None:
    row = _build_dataset().rows[0].to_dict()
    row["attacker_model"] = secret_value

    with pytest.raises(PublicDatasetSafetyError, match="secret-like"):
        validate_public_dataset_payload([row])


def test_validator_rejects_any_source_password_or_candidate_in_serialization() -> None:
    row = _build_dataset().rows[0].to_dict()
    source_value = "synthetic-source-password-8831"
    row["attacker_model"] = source_value

    with pytest.raises(PublicDatasetSafetyError, match="source secret"):
        validate_public_dataset_payload([row], source_secret_values={source_value})


def test_exporters_fail_closed_for_tampered_rows() -> None:
    dataset = _build_dataset()
    tampered_row = replace(
        dataset.rows[0], attacker_model="hf_abcdefghijklmnopqrstuvwxyz123456"
    )
    tampered = replace(dataset, rows=(tampered_row, *dataset.rows[1:]))

    with pytest.raises(PublicDatasetSafetyError):
        export_public_dataset_jsonl(tampered)
    with pytest.raises(PublicDatasetSafetyError):
        export_public_dataset_csv(tampered)
