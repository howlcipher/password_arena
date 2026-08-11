from password_arena.calibration import CalibrationPolicy
from password_arena.models import StrengthReport


def test_calibration_policy_very_short_target() -> None:
    policy = CalibrationPolicy()
    strength = StrengthReport(
        entropy_bits=20.0, score=0, character_pool=10, pattern_penalty=1.0, findings=()
    )

    # Not solved, length <= 3 -> VERY_SHORT_TARGET_SURVIVED
    assert policy.evaluate("abc", strength, False) == "VERY_SHORT_TARGET_SURVIVED"

    # Solved -> None
    assert policy.evaluate("abc", strength, True) is None


def test_calibration_policy_low_entropy_target() -> None:
    policy = CalibrationPolicy()
    strength = StrengthReport(
        entropy_bits=10.0, score=0, character_pool=10, pattern_penalty=1.0, findings=()
    )

    # Not solved, length > 3, entropy < 15.0 -> LOW_ENTROPY_TARGET_SURVIVED
    assert policy.evaluate("abcd", strength, False) == "LOW_ENTROPY_TARGET_SURVIVED"

    # Solved -> None
    assert policy.evaluate("abcd", strength, True) is None


def test_calibration_policy_strong_target() -> None:
    policy = CalibrationPolicy()
    strength = StrengthReport(
        entropy_bits=50.0, score=3, character_pool=50, pattern_penalty=1.0, findings=()
    )

    # Not solved, length > 3, entropy >= 15.0 -> None
    assert policy.evaluate("strong_password123", strength, False) is None
