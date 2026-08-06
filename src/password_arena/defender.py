from __future__ import annotations

import random
import secrets
import string
from dataclasses import dataclass, field

from password_arena.providers import AgentBackend, ProviderRequest

WORDS = (
    "tiger",
    "orbit",
    "cobalt",
    "harbor",
    "ember",
    "signal",
    "vector",
    "comet",
    "meadow",
    "lantern",
    "quartz",
    "falcon",
)
SYMBOLS = "!@#$%&*?"


@dataclass(slots=True)
class AdaptiveDefender:
    """Rule-based baseline defender with memory of breached structures."""

    rng: random.Random
    breached_families: set[str] = field(default_factory=set)
    backend: AgentBackend | None = None

    def create_password(self, difficulty: int) -> tuple[str, str, str]:
        if self.backend:
            return self._create_password_backend(difficulty)
        
        effective = min(max(difficulty, 1), 10)

        if effective == 1:
            family = "dictionary-word"
            password = self.rng.choice(WORDS[:4])
        elif effective == 2:
            family = "capitalized-word-number"
            password = f"{self.rng.choice(WORDS).title()}{self.rng.randint(10, 99)}"
        elif effective == 3:
            family = "substitution-pattern"
            word = self.rng.choice(WORDS)
            password = word.title().replace("a", "@").replace("e", "3") + self.rng.choice(SYMBOLS)
        elif effective == 4:
            family = "two-word-passphrase"
            first = self.rng.choice(WORDS).title()
            second = self.rng.choice(WORDS)
            password = f"{first}-{second}-{self.rng.randint(10, 99)}"
        elif effective <= 6:
            family = "multi-word-passphrase"
            count = 3 if effective == 5 else 4
            password = "-".join(self.rng.sample(WORDS, count))
            password += str(self.rng.randint(100, 999))
        else:
            family = "cryptographic-random"
            length = 14 + (effective - 7) * 2
            alphabet = string.ascii_letters + string.digits + SYMBOLS
            # secrets is intentionally used here: the secure endpoint of defender learning.
            password = "".join(secrets.choice(alphabet) for _ in range(length))

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
                "note": {"type": "string"}
            },
            "required": ["password", "family", "note"]
        }
        breached = ', '.join(self.breached_families) or 'None'
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
        
        valid = (
            isinstance(password, str) 
            and isinstance(family, str) 
            and isinstance(note, str)
        )
        if not valid:
            raise ValueError("Provider response failed schema validation")
        return str(password), str(family), str(note)
