from __future__ import annotations

import random
import secrets
import string
from dataclasses import dataclass, field
from typing import Any

from password_arena.grammars import HELD_OUT_WORDS, SHARED_WORDS, SYMBOLS
from password_arena.providers import AgentBackend, ProviderRequest

# Bump whenever the defender's LLM-facing prompt text materially changes
# (wording, schema, requested fields) -- lets reports and tournament
# comparisons distinguish results produced under different prompts.
DEFENDER_PROMPT_VERSION = "1.0"


@dataclass(slots=True)
class AdaptiveDefender:
    """Rule-based baseline defender with memory of breached structures."""

    rng: random.Random
    breached_families: set[str] = field(default_factory=set)
    backend: AgentBackend | None = None
    generator_mode: str = "secure"
    generator_version: str = "1.0"
    observations: list[Any] = field(default_factory=list)

    def create_password(self, difficulty: int) -> tuple[str, str, str]:
        effective = min(max(difficulty, 1), 10)
        if self.backend:
            return self._create_password_backend(effective)

        family = self._get_default_family(effective)
        return self._generate_from_family(family, effective)

    def _get_default_family(self, effective: int) -> str:
        if effective > 6:
            return "cryptographic-random"
        if self.generator_version == "benchmark":
            if effective == 1:
                return "eval-word"
            if effective == 2:
                return "eval-number-prefix"
            if effective == 3:
                return "eval-substitution"
            if effective == 4:
                return "eval-two-word"
            return "eval-multi-word"
        else:
            if effective == 1:
                return "dictionary-word"
            if effective == 2:
                return "capitalized-word-number"
            if effective == 3:
                return "substitution-pattern"
            if effective == 4:
                return "two-word-passphrase"
            return "multi-word-passphrase"

    def _generate_from_family(
        self, family: str, effective: int, custom_note: str | None = None
    ) -> tuple[str, str, str]:
        if family == "cryptographic-random":
            length = 14 + (effective - 7) * 2
            alphabet = string.ascii_letters + string.digits + SYMBOLS
            if self.generator_mode == "deterministic-test":
                password = "".join(self.rng.choice(alphabet) for _ in range(length))
            else:
                password = "".join(secrets.choice(alphabet) for _ in range(length))
        elif family == "eval-word":
            password = self.rng.choice(HELD_OUT_WORDS)
        elif family == "eval-number-prefix":
            password = f"{self.rng.randint(10, 99)}{self.rng.choice(HELD_OUT_WORDS).title()}"
        elif family == "eval-substitution":
            word = self.rng.choice(HELD_OUT_WORDS)
            password = self.rng.choice(SYMBOLS) + word.title().replace("o", "0").replace(
                "i", "1"
            ).replace("e", "3")
        elif family == "eval-two-word":
            first = self.rng.choice(HELD_OUT_WORDS)
            second = self.rng.choice(HELD_OUT_WORDS).title()
            password = f"{first}.{second}.{self.rng.randint(10, 99)}"
        elif family == "eval-multi-word":
            count = 3 if effective == 5 else 4
            password = ".".join(self.rng.sample(HELD_OUT_WORDS, count))
            password += self.rng.choice(SYMBOLS)
        elif family == "dictionary-word":
            password = self.rng.choice(SHARED_WORDS[:4])
        elif family == "capitalized-word-number":
            password = f"{self.rng.choice(SHARED_WORDS).title()}{self.rng.randint(10, 99)}"
        elif family == "substitution-pattern":
            word = self.rng.choice(SHARED_WORDS)
            password = word.title().replace("a", "@").replace("e", "3") + self.rng.choice(SYMBOLS)
        elif family == "two-word-passphrase":
            first = self.rng.choice(SHARED_WORDS).title()
            second = self.rng.choice(SHARED_WORDS)
            password = f"{first}-{second}-{self.rng.randint(10, 99)}"
        elif family == "multi-word-passphrase":
            count = 3 if effective == 5 else 4
            password = "-".join(self.rng.sample(SHARED_WORDS, count))
            password += str(self.rng.randint(100, 999))
        else:
            password = f"fallback-{self.rng.randint(1000, 9999)}"

        if family in self.breached_families and effective < 7:
            password += self.rng.choice(SYMBOLS) + str(self.rng.randint(100, 999))
            base_note = (
                f"Prior breach detected for {family}; added length and another character class."
            )
        else:
            base_note = f"Selected {family} for difficulty {effective}."

        note = custom_note if custom_note else base_note
        return password, family, note

    def observe(self, family: str, solved: bool, observation: Any = None) -> str:
        msg = ""
        if solved:
            self.breached_families.add(family)
            msg = f"Recorded {family} as breached and will harden it if reused."
        else:
            msg = f"Recorded {family} as surviving the current bounded attack."

        if observation is not None:
            self.observations.append(observation)
            obs_type = type(observation).__name__
            msg += f" Appended {obs_type} memory."

        return msg

    def _create_password_backend(self, difficulty: int) -> tuple[str, str, str]:
        available_families = [
            "cryptographic-random",
            "eval-word",
            "eval-number-prefix",
            "eval-substitution",
            "eval-two-word",
            "eval-multi-word",
            "dictionary-word",
            "capitalized-word-number",
            "substitution-pattern",
            "two-word-passphrase",
            "multi-word-passphrase",
        ]
        schema = {
            "type": "object",
            "properties": {
                "family": {"type": "string", "enum": available_families},
                "note": {"type": "string"},
            },
            "required": ["family", "note"],
        }
        breached = ", ".join(self.breached_families) or "None"

        from dataclasses import asdict

        recent_obs = self.observations[-5:]
        obs_dicts = [asdict(o) for o in recent_obs]
        import json

        obs_str = json.dumps(obs_dicts) if obs_dicts else "[]"

        prompt = (
            f"Select a password strategy family for difficulty {difficulty} (1-10).\n"
            f"Breached families you should avoid reusing in predictable ways: {breached}.\n"
            f"Recent structured observations (max 5): {obs_str}\n"
            f"Available families: {', '.join(available_families)}.\n"
            "Respond strictly in the provided JSON schema."
        )
        assert self.backend is not None
        request = ProviderRequest(prompt=prompt, structured_schema=schema)
        response = self.backend.generate(request)

        if not response.metrics.structured_validation_success:
            from password_arena.providers import AvailabilityState, ProviderError

            raise ProviderError(
                AvailabilityState.INVALID_RESPONSE, "Provider response failed schema validation"
            )

        data = response.parsed_structured_data
        if not data or not isinstance(data, dict):
            from password_arena.providers import AvailabilityState, ProviderError

            raise ProviderError(
                AvailabilityState.INVALID_RESPONSE,
                "Provider response missing valid structured data",
            )

        family = data.get("family")
        note = data.get("note")

        valid = isinstance(family, str) and isinstance(note, str)
        if not valid or family not in available_families:
            from password_arena.providers import AvailabilityState, ProviderError

            raise ProviderError(
                AvailabilityState.INVALID_RESPONSE, "Provider response failed schema validation"
            )
        return self._generate_from_family(family, difficulty, custom_note=note)
