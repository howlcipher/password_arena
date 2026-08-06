import subprocess
import sys


def test_cli_invalid_config():
    # Test passing an invalid rounds value
    # We can run it via sys.executable -m password_arena.cli
    result = subprocess.run(
        [sys.executable, "-m", "password_arena.cli", "--rounds", "0"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "error" in result.stderr.lower()
    assert "traceback" not in result.stderr.lower()
