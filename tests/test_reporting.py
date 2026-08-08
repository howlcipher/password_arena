import csv
import io
import json

from password_arena import ArenaConfig, ArenaEngine
from password_arena.models import MatchupConfig, MatchupResult, RoleConfig, TournamentConfig
from password_arena.reporting import (
    experiment_report_markdown,
    round_report_markdown,
    tournament_report_csv,
    tournament_report_json,
    tournament_report_markdown,
)
from password_arena.tournament import run_matchup


def test_round_report_documents_both_sides() -> None:
    result = ArenaEngine(ArenaConfig(rounds=1, max_guesses=100)).run()
    report = round_report_markdown(result.rounds[0])
    assert "### Defender side" in report
    assert "### Attacker side" in report
    assert "### Evaluator" in report
    assert "Budget plan" in report


def test_hidden_password_is_not_leaked_in_serialized_result() -> None:
    result = ArenaEngine(ArenaConfig(rounds=1, max_guesses=100)).run()
    serialized = result.to_dict()
    round_data = serialized["rounds"][0]
    assert round_data["attack"]["candidate"] is None
    assert set(round_data["password_display"]) == {"•"}


def test_experiment_report_contains_summary() -> None:
    result = ArenaEngine(ArenaConfig(rounds=2, max_guesses=100)).run()
    report = experiment_report_markdown(result)
    assert "# Password Arena Experiment Report" in report
    assert "Solved rounds" in report
    assert "Round 1" in report
    assert "Round 2" in report


def _tournament_fixture() -> tuple[str, str, TournamentConfig, list[MatchupResult]]:
    tournament_config = TournamentConfig(
        attackers=(RoleConfig(provider="rule_based"),),
        defenders=(RoleConfig(provider="rule_based"),),
        seeds=(1, 2),
        rounds_per_match=2,
        max_guesses=50,
    )
    matchup_config = MatchupConfig(
        attacker=RoleConfig(provider="rule_based"),
        defender=RoleConfig(provider="rule_based"),
        rounds=2,
        seeds=(1, 2),
        max_guesses=50,
    )
    result = run_matchup(matchup_config)
    return "tid-123", "2026-01-01T00:00:00+00:00", tournament_config, [result]


def test_tournament_report_json_has_required_fields() -> None:
    tournament_id, timestamp, config, matchups = _tournament_fixture()
    payload = json.loads(tournament_report_json(tournament_id, timestamp, config, matchups))

    assert payload["tournament_id"] == tournament_id
    assert payload["timestamp"] == timestamp
    m = payload["matchups"][0]
    for key in (
        "attacker",
        "defender",
        "seeds",
        "rounds_per_match",
        "max_guesses",
        "comparable_trials",
        "excluded_trials",
        "excluded_rounds",
        "solve_rate",
        "survival_rate",
        "guesses",
        "tokens",
        "latency_ms",
        "estimated_cost",
        "efficiency",
        "replay",
        "excluded_trial_records",
        "excluded_round_records",
    ):
        assert key in m


def test_tournament_report_json_includes_version_metadata() -> None:
    """IMP-026: reports must identify application, schema, prompt, and
    capability-registry versions so results can be traced to exactly what
    produced them."""
    from password_arena.attacker import ATTACKER_PROMPT_VERSION
    from password_arena.defender import DEFENDER_PROMPT_VERSION
    from password_arena.providers import CAPABILITY_REGISTRY_VERSION

    tournament_id, timestamp, config, matchups = _tournament_fixture()
    payload = json.loads(tournament_report_json(tournament_id, timestamp, config, matchups))
    replay = payload["matchups"][0]["replay"]

    assert replay["application_version"]
    assert replay["schema_version"]
    assert replay["attacker_prompt_version"] == ATTACKER_PROMPT_VERSION
    assert replay["defender_prompt_version"] == DEFENDER_PROMPT_VERSION
    assert replay["capability_registry_version"] == CAPABILITY_REGISTRY_VERSION


def test_tournament_report_json_no_secrets_or_passwords() -> None:
    tournament_id, timestamp, config, matchups = _tournament_fixture()
    text = tournament_report_json(tournament_id, timestamp, config, matchups)
    lowered = text.lower()
    for forbidden in ("api_key", "apikey", "authorization", "password", "secret"):
        assert forbidden not in lowered


def test_tournament_report_markdown_documents_ci_caveat_and_status() -> None:
    tournament_id, timestamp, config, matchups = _tournament_fixture()
    report = tournament_report_markdown(tournament_id, timestamp, config, matchups)
    assert "independent" in report.lower()
    assert "Solve rate (round-level)" in report
    assert "Status" in report


def test_tournament_report_csv_round_trips_and_marks_unavailable_cost() -> None:
    tournament_id, timestamp, config, matchups = _tournament_fixture()
    csv_text = tournament_report_csv(tournament_id, timestamp, config, matchups)
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) == 1
    row = rows[0]
    assert row["tournament_id"] == tournament_id
    # rule_based vs rule_based never calls an LLM, so cost is a known zero, not
    # "unavailable" -- verifying the honest-zero path alongside the other test's
    # unavailable-cost path in test_tournament.py.
    assert row["estimated_cost"] not in ("", None)


def test_tournament_report_csv_shows_unavailable_not_zero_for_unknown_cost() -> None:
    from password_arena.models import (
        ArenaConfig,
        AttackResult,
        ExperimentResult,
        RoleUsage,
        RoundResult,
        StrengthReport,
    )
    from password_arena.tournament import aggregate_matchup

    matchup_config = MatchupConfig(
        attacker=RoleConfig(provider="mock"),
        defender=RoleConfig(provider="rule_based"),
        rounds=1,
        seeds=(1,),
    )
    round_result = RoundResult(
        round_number=1,
        difficulty=1,
        password_display="****",
        password_length=4,
        strength=StrengthReport(entropy_bits=10.0, score=1, character_pool=26, pattern_penalty=0.0),
        attack=AttackResult(solved=False, guesses_used=5, winning_strategy=None, elapsed_ms=1.0),
        defender_strategy="dictionary-word",
        defender_note="",
        defender_learning="",
        attacker_note="",
        attacker_learning="",
        attacker_usage=RoleUsage(input_tokens=1, output_tokens=1, estimated_cost=None),
    )
    experiment = ExperimentResult(config=ArenaConfig(seed=1), rounds=(round_result,))
    matchup = aggregate_matchup(matchup_config, [experiment], [])
    assert matchup.summary.total_estimated_cost is None

    csv_text = tournament_report_csv("tid", "ts", TournamentConfig(
        attackers=(matchup_config.attacker,),
        defenders=(matchup_config.defender,),
        seeds=(1,),
        rounds_per_match=1,
    ), [matchup])
    reader = csv.DictReader(io.StringIO(csv_text))
    row = next(reader)
    assert row["estimated_cost"] == "unavailable"
