from password_arena import ArenaConfig, ArenaEngine
from password_arena.reporting import experiment_report_markdown, round_report_markdown


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
