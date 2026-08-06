from password_arena.strength import evaluate_strength


def test_secure_random_style_password_scores_above_common_word() -> None:
    weak = evaluate_strength("tiger")
    strong = evaluate_strength("qA7!mZ2@vL9#xP4$")
    assert strong.entropy_bits > weak.entropy_bits
    assert strong.score > weak.score


def test_common_token_is_reported() -> None:
    report = evaluate_strength("Password2026")
    assert any("common" in finding.lower() for finding in report.findings)
