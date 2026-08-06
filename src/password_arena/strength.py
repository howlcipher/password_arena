from __future__ import annotations

import math
import re
from collections.abc import Iterable

from password_arena.models import StrengthReport

COMMON_TOKENS = {
    "password",
    "admin",
    "welcome",
    "dragon",
    "tiger",
    "monkey",
    "football",
    "baseball",
    "qwerty",
    "letmein",
}
SEQUENCES = ("0123456789", "abcdefghijklmnopqrstuvwxyz", "qwertyuiop", "asdfghjkl")


def _character_pool(password: str) -> int:
    pool = 0
    if re.search(r"[a-z]", password):
        pool += 26
    if re.search(r"[A-Z]", password):
        pool += 26
    if re.search(r"\d", password):
        pool += 10
    if re.search(r"[^A-Za-z0-9]", password):
        pool += 33
    return max(pool, 1)


def _contains_sequence(password: str, sequences: Iterable[str] = SEQUENCES) -> bool:
    lowered = password.lower()
    for sequence in sequences:
        for size in range(3, min(6, len(sequence) + 1)):
            windows = (
                sequence[index : index + size]
                for index in range(len(sequence) - size + 1)
            )
            if any(window in lowered for window in windows):
                return True
    return False


def evaluate_strength(password: str) -> StrengthReport:
    """Estimate strength for comparison inside the simulation, not real crack-time prediction."""

    if not password:
        return StrengthReport(0.0, 0, 1, 1.0, ("Password is empty",))

    pool = _character_pool(password)
    raw_entropy = len(password) * math.log2(pool)
    penalty = 1.0
    findings: list[str] = []
    lowered = password.lower()

    if any(token in lowered for token in COMMON_TOKENS):
        penalty *= 0.45
        findings.append("Contains a common password token")
    if re.search(r"(.)\1{2,}", password):
        penalty *= 0.60
        findings.append("Contains repeated characters")
    if _contains_sequence(password):
        penalty *= 0.65
        findings.append("Contains a predictable sequence")
    if re.search(r"(19|20)\d{2}$", password):
        penalty *= 0.75
        findings.append("Ends with a likely year")
    if len(set(password)) <= max(2, len(password) // 3):
        penalty *= 0.70
        findings.append("Has low character diversity")

    entropy = round(raw_entropy * penalty, 2)
    thresholds = (28, 40, 60, 80)
    score = sum(entropy >= threshold for threshold in thresholds)
    if not findings:
        findings.append("No obvious structural weakness detected")

    return StrengthReport(
        entropy_bits=entropy,
        score=score,
        character_pool=pool,
        pattern_penalty=round(penalty, 3),
        findings=tuple(findings),
    )
