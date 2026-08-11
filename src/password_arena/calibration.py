from __future__ import annotations

from dataclasses import dataclass

from password_arena.models import StrengthReport


@dataclass(frozen=True)
class CalibrationPolicy:
    """Versioned policy for identifying weak synthetic targets that survive bounded attacks.

    The purpose is NOT to declare passwords universally secure or insecure, but to
    detect cases worthy of benchmark scrutiny (e.g., when a bounded strategy fails to
    guess a trivially small password because it lacked a short-space search strategy).
    """

    version: str = "1.0"
    short_target_threshold_length: int = 3
    low_entropy_threshold_bits: float = 15.0

    def evaluate(self, password: str, strength: StrengthReport, solved: bool) -> str | None:
        """Evaluate a round and return a calibration warning if a weak target survived."""
        if solved:
            return None

        if len(password) <= self.short_target_threshold_length:
            return "VERY_SHORT_TARGET_SURVIVED"

        if strength.entropy_bits < self.low_entropy_threshold_bits:
            return "LOW_ENTROPY_TARGET_SURVIVED"

        return None
