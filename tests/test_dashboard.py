from pathlib import Path
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

DASHBOARD_PATH = Path(__file__).resolve().parent.parent / "src" / "password_arena" / "dashboard.py"


def test_dashboard_smoke() -> None:
    at = AppTest.from_file(str(DASHBOARD_PATH))
    at.run(timeout=10)
    assert not at.exception


def test_tournament_tab_accessible_without_arena_run() -> None:
    """BUG-016 regression: the Tournament tab used to be unreachable because
    render_arena_tab() called st.stop(), which halts the *entire* script run
    (both tabs are queued in the same run), not just the Arena tab's container.

    On a completely fresh session (no Arena experiment has ever been run):
      * Arena controls must still exist (sidebar "Run arena" button).
      * Tournament controls must exist too (attacker/defender role manager,
        "Run Tournament" button) -- proving render_tournament_tab() actually
        executed in the same script run.
      * Tournament must be usable without first running anything on Arena.
    """
    at = AppTest.from_file(str(DASHBOARD_PATH))
    at.run(timeout=10)
    assert not at.exception

    button_labels = {b.label for b in at.button}
    assert "Run arena" in button_labels, "Arena controls should render on a fresh session"
    assert "Run Tournament" in button_labels, (
        "Tournament controls must render on a fresh session without requiring "
        "an Arena experiment first"
    )
    assert "Add Attacker" in button_labels
    assert "Add Defender" in button_labels

    header_texts = {h.value for h in at.header}
    assert "Tournament Configuration" in header_texts


def test_run_tournament_renders_all_result_tabs_without_error(
    tmp_path: Any, monkeypatch: Any
) -> None:
    """End-to-end exercise of the rewritten tournament_views.py rendering
    layer (Overview, Leaderboards, Heatmap, Efficiency, Thinking Levels)
    against real (rule_based vs rule_based, so fast and free) tournament
    data, not just the pure tournament_view_models functions in isolation."""
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(DASHBOARD_PATH))
    at.run(timeout=30)
    assert not at.exception

    # Default attacker/defender are both rule_based with no model, so
    # "Exclude self-play matchups" would otherwise exclude the only possible
    # matchup entirely -- uncheck it for this rule_based-vs-rule_based case.
    self_play_checkbox = next(
        c for c in at.checkbox if c.label == "Exclude self-play matchups (e.g. GPT vs GPT)"
    )
    self_play_checkbox.set_value(False)
    at.run(timeout=30)
    assert not at.exception

    run_button = next(b for b in at.button if b.label == "Run Tournament")
    run_button.click()
    at.run(timeout=60)
    assert not at.exception

    subheader_texts = {s.value for s in at.subheader}
    assert "Tournament Overview" in subheader_texts
    assert "Leaderboards" in subheader_texts
    assert "Matchup Matrix" in subheader_texts
    assert "Efficiency" in subheader_texts
    assert "Thinking-Level Comparison" in subheader_texts


def test_thinking_level_selector_is_capability_aware() -> None:
    """Regression for the audit finding that ui_helpers.py used to expose all
    six normalized thinking levels regardless of the selected model's actual
    capabilities. Selecting a narrow-capability model (o1-preview, which only
    accepts LOW/MEDIUM/HIGH) must restrict the selectbox to exactly that set,
    and a previously-valid selection that becomes invalid (AUTO, from
    gpt-4o's default) must be downgraded with a visible warning, not
    silently."""
    at = AppTest.from_file(str(DASHBOARD_PATH))
    at.run(timeout=10)
    assert not at.exception

    provider_select = next(s for s in at.selectbox if s.key == "defender_provider")
    provider_select.select("openai")
    at.run(timeout=10)
    assert not at.exception

    model_select = next(s for s in at.selectbox if s.key == "defender_model_select")
    assert model_select.value == "gpt-4o"  # first known model, thinking defaults to auto-only
    thinking_select = next(s for s in at.selectbox if s.key == "defender_thinking")
    assert thinking_select.options == ["auto"]

    model_select.select("o1-preview")
    at.run(timeout=10)
    assert not at.exception

    thinking_select = next(s for s in at.selectbox if s.key == "defender_thinking")
    assert thinking_select.options == ["low", "medium", "high"]
    assert thinking_select.value == "low"  # downgraded from the no-longer-valid "auto"
    assert any(
        "not supported by openai:o1-preview" in w.value and "reset to 'low'" in w.value
        for w in at.warning
    )


def _find_profile_name_input(at: AppTest) -> Any:
    for ti in at.text_input:
        if ti.label == "Save profile as":
            return ti
    raise AssertionError("'Save profile as' text_input not found")


@pytest.mark.parametrize(
    "malicious_name",
    ["../../outside", "../foo", "C:\\temp\\thing"],
)
def test_save_profile_never_writes_to_filesystem(
    tmp_path: Any, monkeypatch: Any, malicious_name: str
) -> None:
    """Regression test: 'Save profile' used to build Path(f"{profile_name}.json")
    directly from this input and write it -- a path traversal vulnerability. It is
    now a browser download button that never touches the filesystem."""
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(DASHBOARD_PATH))
    at.run(timeout=10)
    assert not at.exception

    profile_input = _find_profile_name_input(at)
    profile_input.set_value(malicious_name)
    at.run(timeout=10)
    assert not at.exception

    # Tournament renders alongside Arena now (BUG-016 fix), and its history
    # managers create their storage directories on init as a legitimate side
    # effect -- allow only those, and assert nothing else (in particular no
    # file/dir derived from the malicious profile name) was written.
    expected_dirs = {".password_arena_history", ".password_arena_tournaments"}
    created = {p.name for p in tmp_path.iterdir()}
    assert created <= expected_dirs, f"Unexpected filesystem writes: {created - expected_dirs}"
    assert not (tmp_path.parent / "outside.json").exists()
    assert not (tmp_path.parent.parent / "outside.json").exists()
