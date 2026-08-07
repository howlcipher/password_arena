from pathlib import Path

from streamlit.testing.v1 import AppTest

DASHBOARD_PATH = Path(__file__).resolve().parent.parent / "src" / "password_arena" / "dashboard.py"


def test_dashboard_smoke():
    at = AppTest.from_file(str(DASHBOARD_PATH))
    at.run(timeout=10)
    assert not at.exception
