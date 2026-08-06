from __future__ import annotations

import random
import secrets
import string
from dataclasses import dataclass, field

from password_arena.grammars import HELD_OUT_WORDS, SHARED_WORDS, SYMBOLS
from password_arena.providers import AgentBackend, ProviderRequest


@dataclass(slots=True)
class AdaptiveDefender:
    """Rule-based baseline defender with memory of breached structures."""

    rng: random.Random
    breached_families: set[str] = field(default_factory=set)
    backend: AgentBackend | None = None
    generator_mode: str = "secure"
    generator_version: str = "1.0"

    def create_password(self, difficulty: int) -> tuple[str, str, str]:
        if self.backend:
            return self._create_password_backend(difficulty)

        effective = min(max(difficulty, 1), 10)

        if effective > 6:
            family = "cryptographic-random"
            length = 14 + (effective - 7) * 2
            alphabet = string.ascii_letters + string.digits + SYMBOLS
            if self.generator_mode == "deterministic-test":
                password = "".join(self.rng.choice(alphabet) for _ in range(length))
            else:
                # secrets is intentionally used here: the secure endpoint of defender learning.
                password = "".join(secrets.choice(alphabet) for _ in range(length))
        elif self.generator_version == "benchmark":
            words: tuple[str, ...] = HELD_OUT_WORDS
            if effective == 1:
                family = "eval-word"
                password = self.rng.choice(words)
            elif effective == 2:
                family = "eval-number-prefix"
                password = f"{self.rng.randint(10, 99)}{self.rng.choice(words).title()}"
            elif effective == 3:
                family = "eval-substitution"
                word = self.rng.choice(words)
                password = self.rng.choice(SYMBOLS) + word.title().replace("o", "0").replace(
                    "i", "1"
                ).replace("e", "3")
            elif effective == 4:
                family = "eval-two-word"
                first = self.rng.choice(words)
                second = self.rng.choice(words).title()
                password = f"{first}.{second}.{self.rng.randint(10, 99)}"
            else:
                family = "eval-multi-word"
                count = 3 if effective == 5 else 4
                password = ".".join(self.rng.sample(words, count))
                password += self.rng.choice(SYMBOLS)
        else:
            words = SHARED_WORDS
            if effective == 1:
                family = "dictionary-word"
                password = self.rng.choice(words[:4])
            elif effective == 2:
                family = "capitalized-word-number"
                password = f"{self.rng.choice(words).title()}{self.rng.randint(10, 99)}"
            elif effective == 3:
                family = "substitution-pattern"
                word = self.rng.choice(words)
                password = word.title().replace("a", "@").replace("e", "3") + self.rng.choice(
                    SYMBOLS
                )
            elif effective == 4:
                family = "two-word-passphrase"
                first = self.rng.choice(words).title()
                second = self.rng.choice(words)
                password = f"{first}-{second}-{self.rng.randint(10, 99)}"
            else:
                family = "multi-word-passphrase"
                count = 3 if effective == 5 else 4
                password = "-".join(self.rng.sample(words, count))
                password += str(self.rng.randint(100, 999))

        if family in self.breached_families and effective < 7:
            password += self.rng.choice(SYMBOLS) + str(self.rng.randint(100, 999))
            note = f"Prior breach detected for {family}; added length and another character class."
        else:
            note = f"Selected {family} for difficulty {effective}."

        return password, family, note

    def observe(self, family: str, solved: bool) -> str:
        if solved:
            self.breached_families.add(family)
            return f"Recorded {family} as breached and will harden it if reused."
        return f"Recorded {family} as surviving the current bounded attack."

    def _create_password_backend(self, difficulty: int) -> tuple[str, str, str]:
        schema = {
            "type": "object",
            "properties": {
                "password": {"type": "string"},
                "family": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["password", "family", "note"],
        }
        breached = ", ".join(self.breached_families) or "None"
        prompt = (
            f"Generate a synthetic password for difficulty {difficulty} (1-10).\n"
            f"Breached families you should avoid reusing in predictable ways: {breached}.\n"
            "Respond strictly in the provided JSON schema."
        )
        assert self.backend is not None
        request = ProviderRequest(prompt=prompt, structured_schema=schema)
        response = self.backend.generate(request)

        data = response.parsed_structured_data
        if not data or not isinstance(data, dict):
            raise ValueError("Provider response missing valid structured data")

        password = data.get("password")
        family = data.get("family")
        note = data.get("note")

        valid = isinstance(password, str) and isinstance(family, str) and isinstance(note, str)
        if not valid:
            raise ValueError("Provider response failed schema validation")
        return str(password), str(family), str(note)
