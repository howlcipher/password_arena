from pathlib import Path
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

DASHBOARD_PATH = Path(__file__).resolve().parent.parent / "src" / "password_arena" / "dashboard.py"


def test_dashboard_smoke() -> None:
    at = AppTest.from_file(str(DASHBOARD_PATH))
    at.run(timeout=10)
    assert not at.exception


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

    assert list(tmp_path.iterdir()) == []
    assert not (tmp_path.parent / "outside.json").exists()
    assert not (tmp_path.parent.parent / "outside.json").exists()
