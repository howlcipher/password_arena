from streamlit.testing.v1 import AppTest


def test_dashboard_smoke():
    at = AppTest.from_file("src/password_arena/dashboard.py")
    at.run(timeout=10)
    assert not at.exception
