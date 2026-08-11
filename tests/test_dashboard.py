import json
from pathlib import Path
from typing import Any, cast

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import DownloadButton

from password_arena.huggingface_catalog import OpenModelInfo

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


def test_completed_tournament_has_public_dataset_downloads(tmp_path: Any, monkeypatch: Any) -> None:
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(DASHBOARD_PATH))
    at.run(timeout=30)
    at = _run_a_tiny_rule_based_tournament(at, rounds_per_match=2)
    assert not at.exception

    assert any(s.value == "Public Benchmark Dataset" for s in at.subheader)
    metrics = {metric.label: metric.value for metric in at.metric}
    assert metrics["Total public rows"] == "6"
    assert metrics["Comparable public rows"] == "6"
    assert metrics["Excluded public rows"] == "0"

    download_buttons = [cast(DownloadButton, item) for item in at.get("download_button")]
    public_downloads = {
        item.label: item for item in download_buttons if "public" in item.label.lower()
    }
    assert set(public_downloads) == {
        "Download public JSONL",
        "Download public CSV",
    }
    assert not public_downloads["Download public JSONL"].proto.disabled
    assert not public_downloads["Download public CSV"].proto.disabled
    card = next(item for item in download_buttons if item.label == "Download Dataset Card")
    assert not card.proto.disabled
    assert any("not uploaded" in info.value for info in at.info)


def _run_a_tiny_rule_based_tournament(
    at: AppTest, *, rounds_per_match: int | None = None
) -> AppTest:
    self_play_checkbox = next(
        c for c in at.checkbox if c.label == "Exclude self-play matchups (e.g. GPT vs GPT)"
    )
    if self_play_checkbox.value:
        self_play_checkbox.set_value(False)
        at.run(timeout=30)

    if rounds_per_match is not None:
        rpm = next(n for n in at.number_input if n.label == "Rounds per Matchup")
        rpm.set_value(rounds_per_match)
        at.run(timeout=30)

    run_button = next(b for b in at.button if b.label == "Run Tournament")
    run_button.click()
    at.run(timeout=60)
    return at


def test_load_saved_tournament_from_history_renders_without_error(
    tmp_path: Any, monkeypatch: Any
) -> None:
    """Regression: loading a previously-saved tournament used to crash while
    generating its downloadable reports, because StoredMatchup silently
    dropped `replay`/`excluded_trial_records`/`excluded_round_records` on
    save, and reporting.py's report builders unconditionally access those
    attributes."""
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(DASHBOARD_PATH))
    at.run(timeout=30)
    at = _run_a_tiny_rule_based_tournament(at)
    assert not at.exception

    saved = next(m for m in at.multiselect if m.label == "Saved tournaments")
    saved.set_value(saved.options[:1])
    at.run(timeout=30)

    load_button = next(b for b in at.button if b.label == "Load tournament details")
    load_button.click()
    at.run(timeout=60)
    assert not at.exception

    subheader_texts = {s.value for s in at.subheader}
    assert "Tournament Overview" in subheader_texts
    assert "Matchup Matrix" in subheader_texts


def test_saved_tournament_missing_linked_experiment_disables_public_export(
    tmp_path: Any, monkeypatch: Any
) -> None:
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(DASHBOARD_PATH))
    at.run(timeout=30)
    at = _run_a_tiny_rule_based_tournament(at, rounds_per_match=1)
    assert not at.exception

    experiment_files = sorted((tmp_path / ".password_arena_history").glob("*.json"))
    assert experiment_files
    experiment_files[0].unlink()

    at.run(timeout=30)
    saved = next(m for m in at.multiselect if m.label == "Saved tournaments")
    saved.set_value(saved.options[:1])
    at.run(timeout=30)
    next(b for b in at.button if b.label == "Load tournament details").click()
    at.run(timeout=60)
    assert not at.exception

    assert any(
        "Public export is disabled because 1 linked experiment" in warning.value
        for warning in at.warning
    )
    public_labels = {
        "Download public JSONL",
        "Download public CSV",
        "Download Dataset Card",
    }
    public_downloads = [
        cast(DownloadButton, item)
        for item in at.get("download_button")
        if cast(DownloadButton, item).label in public_labels
    ]
    assert {item.label for item in public_downloads} == public_labels
    assert all(item.proto.disabled for item in public_downloads)


def test_compare_two_tournaments_renders_without_error(tmp_path: Any, monkeypatch: Any) -> None:
    """Regression: comparing two saved tournaments used to crash with
    StreamlitDuplicateElementId because render_heatmap()'s metric selectbox
    had no explicit key, so rendering two tournaments side by side in the
    same script run produced two selectboxes with an identical auto-ID.
    Also exercises compare_tournament_configs() end to end (not just its
    unit tests) against real saved-and-reloaded TournamentConfigs."""
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(DASHBOARD_PATH))
    at.run(timeout=30)
    at = _run_a_tiny_rule_based_tournament(at)
    assert not at.exception

    at = _run_a_tiny_rule_based_tournament(at, rounds_per_match=2)
    assert not at.exception

    saved = next(m for m in at.multiselect if m.label == "Saved tournaments")
    assert len(saved.options) == 2
    saved.set_value(saved.options[:2])
    at.run(timeout=30)

    compare_button = next(b for b in at.button if b.label == "Compare Tournaments")
    compare_button.click()
    at.run(timeout=60)
    assert not at.exception

    assert any(
        "Tournaments differ and may not be directly comparable" in w.value for w in at.warning
    )
    assert any("rounds_per_match" in w.value for w in at.warning)


def test_compare_saved_tournaments_explains_replay_version_difference(
    tmp_path: Any, monkeypatch: Any
) -> None:
    """IMP-029: the history UI must distinguish matching benchmark settings
    from a persisted replay-version difference, not issue a generic verdict."""
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(DASHBOARD_PATH))
    at.run(timeout=30)
    at = _run_a_tiny_rule_based_tournament(at)
    at = _run_a_tiny_rule_based_tournament(at)

    stored_files = sorted((tmp_path / ".password_arena_tournaments").glob("*.json"))
    assert len(stored_files) == 2
    stored_data = json.loads(stored_files[0].read_text(encoding="utf-8"))
    stored_data["matchups"][0]["replay"]["attacker_prompt_version"] = "test-prompt-2"
    stored_files[0].write_text(json.dumps(stored_data), encoding="utf-8")

    at.run(timeout=30)
    saved = next(m for m in at.multiselect if m.label == "Saved tournaments")
    saved.set_value(saved.options[:2])
    at.run(timeout=30)
    compare_button = next(b for b in at.button if b.label == "Compare Tournaments")
    compare_button.click()
    at.run(timeout=60)

    assert any(
        "Benchmark configuration matches, but execution metadata differs" in warning.value
        and "Attacker prompt version" in warning.value
        for warning in at.warning
    )


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


def test_preflight_not_checked_automatically_for_non_rule_based_provider() -> None:
    """Selecting a hosted provider must not trigger a network availability
    check on the ordinary rerun that follows -- only an explicit "Test
    connections" click may do that. Run arena must stay disabled until the
    user explicitly checks and it comes back available."""
    at = AppTest.from_file(str(DASHBOARD_PATH))
    at.run(timeout=10)

    provider_select = next(s for s in at.selectbox if s.key == "defender_provider")
    provider_select.select("openai")
    at.run(timeout=10)
    assert not at.exception

    assert any(i.value == "Configuration changed. Status: Not checked." for i in at.info)
    assert any(b.label == "Test connections" for b in at.button)
    run_button = next(b for b in at.button if b.label == "Run arena")
    assert run_button.disabled


def test_test_connections_caches_result_until_config_changes() -> None:
    """Clicking "Test connections" performs and caches the check; the status
    table then persists across unrelated reruns without another click.
    Changing the model afterward invalidates the cache and the button
    reappears -- config changes must invalidate old preflight results."""
    at = AppTest.from_file(str(DASHBOARD_PATH))
    at.run(timeout=10)

    provider_select = next(s for s in at.selectbox if s.key == "defender_provider")
    provider_select.select("openai")
    at.run(timeout=10)

    test_connections = next(b for b in at.button if b.label == "Test connections")
    test_connections.click()
    at.run(timeout=10)
    assert not at.exception

    # No OPENAI_API_KEY in the test environment -> a deterministic, offline
    # AUTHENTICATION_FAILED status (OpenAIProvider.check_availability() never
    # makes a network call; it just reports the state set at construction).
    status_df = next(df for df in at.dataframe)
    assert "AUTHENTICATION_FAILED" in status_df.value["Status"].to_list()
    assert not any(b.label == "Test connections" for b in at.button)

    model_select = next(s for s in at.selectbox if s.key == "defender_model_select")
    model_select.select("gpt-4o-mini")
    at.run(timeout=10)
    assert any(i.value == "Configuration changed. Status: Not checked." for i in at.info)
    assert any(b.label == "Test connections" for b in at.button)


def test_tournament_preflight_gate_disables_run_for_unchecked_hosted_provider() -> None:
    """The Tournament tab shares the same cached, explicit preflight gate as
    Arena -- selecting a hosted provider for a tournament role must disable
    "Run Tournament" until explicitly checked, without an automatic network
    call on the ordinary rerun that follows the selection."""
    at = AppTest.from_file(str(DASHBOARD_PATH))
    at.run(timeout=10)

    attacker_provider = next(s for s in at.selectbox if s.key == "t_attacker_0_provider")
    attacker_provider.select("openai")
    at.run(timeout=10)
    assert not at.exception

    assert any(i.value == "Configuration changed. Status: Not checked." for i in at.info)
    run_button = next(b for b in at.button if b.label == "Run Tournament")
    assert run_button.disabled


def test_huggingface_search_is_explicit_and_selection_keeps_provider_semantics(
    monkeypatch: Any,
) -> None:
    from password_arena.huggingface_catalog import HuggingFaceCatalog

    calls: list[dict[str, Any]] = []

    def fake_search(
        self: HuggingFaceCatalog,
        query: str,
        *,
        pipeline_tag: str | None,
        limit: int,
        sort: str,
    ) -> tuple[OpenModelInfo, ...]:
        del self
        calls.append(
            {
                "query": query,
                "pipeline_tag": pipeline_tag,
                "limit": limit,
                "sort": sort,
            }
        )
        return (
            OpenModelInfo(
                model_id="acme/synthetic-generator",
                author="acme",
                pipeline_tag="text-generation",
                library_name="transformers",
                downloads=123,
                likes=7,
                tags=("synthetic", "safetensors"),
                gated=False,
                private=False,
                inference_warm=True,
            ),
        )

    monkeypatch.setattr(HuggingFaceCatalog, "search_models", fake_search)

    at = AppTest.from_file(str(DASHBOARD_PATH))
    at.run(timeout=10)
    assert not at.exception
    assert calls == []
    assert not any(button.label == "Search Hugging Face" for button in at.button)

    provider_select = next(s for s in at.selectbox if s.key == "defender_provider")
    provider_select.select("openai")
    at.run(timeout=10)
    assert not at.exception
    assert calls == []

    query_input = next(t for t in at.text_input if t.key == "defender_hf_query")
    query_input.set_value("synthetic")
    at.run(timeout=10)
    assert not at.exception
    assert calls == []

    task_select = next(s for s in at.selectbox if s.key == "defender_hf_task")
    task_select.select("text-generation")
    at.run(timeout=10)
    assert not at.exception
    assert calls == []

    search_button = next(b for b in at.button if b.key == "defender_hf_search")
    search_button.click()
    at.run(timeout=10)
    assert not at.exception
    assert calls == [
        {
            "query": "synthetic",
            "pipeline_tag": "text-generation",
            "limit": 10,
            "sort": "downloads",
        }
    ]

    result_frame = next(
        frame
        for frame in at.dataframe
        if "Model ID" in frame.value.columns
        and "acme/synthetic-generator" in frame.value["Model ID"].to_list()
    )
    assert result_frame.value.iloc[0]["Inference warm"] == "YES"
    assert result_frame.value.iloc[0]["Execution support"] == "UNKNOWN"

    result_select = next(s for s in at.selectbox if s.key == "defender_hf_result")
    result_select.select("acme/synthetic-generator")
    at.run(timeout=10)
    assert not at.exception
    assert len(calls) == 1

    provider_select = next(s for s in at.selectbox if s.key == "defender_provider")
    model_select = next(s for s in at.selectbox if s.key == "defender_model_select")
    model_input = next(t for t in at.text_input if t.key == "defender_model_input")
    assert provider_select.value == "openai"
    assert model_select.value == "Other (manual input)"
    assert model_input.value == "acme/synthetic-generator"


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
