from __future__ import annotations

import itertools
import random
import string
import time
from collections.abc import Iterator
from dataclasses import dataclass, field

from password_arena.defender import SYMBOLS, WORDS
from password_arena.models import AttackResult, StrategyBudget

COMMON = (
    "password",
    "123456",
    "qwerty",
    "admin",
    "welcome",
    "letmein",
    "dragon",
    "tiger",
    "orbit",
    "cobalt",
    "harbor",
    "ember",
)


def _dedupe(candidates: Iterator[str]) -> Iterator[str]:
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            yield candidate


def common_candidates() -> Iterator[str]:
    yield from COMMON


def mutation_candidates(words: tuple[str, ...]) -> Iterator[str]:
    substitutions = {"a": "@", "e": "3", "i": "1", "o": "0", "s": "$"}
    for word in words:
        mutated = "".join(substitutions.get(char, char) for char in word)
        forms = tuple(dict.fromkeys((word, word.title(), word.upper(), mutated, mutated.title())))
        yield from forms
        for number in range(0, 100):
            for form in forms:
                yield f"{form}{number:02d}"
        for symbol in SYMBOLS:
            for form in forms:
                yield f"{form}{symbol}"


def passphrase_candidates(words: tuple[str, ...], max_words: int = 3) -> Iterator[str]:
    limited = words[: min(len(words), 12)]
    for count in range(2, max_words + 1):
        for parts in itertools.permutations(limited, count):
            variants = (
                "-".join(parts),
                "-".join(part.title() for part in parts),
                f"{parts[0].title()}-" + "-".join(parts[1:]),
            )
            for base in dict.fromkeys(variants):
                yield base
                for suffix in range(0, 100):
                    yield f"{base}{suffix:02d}"
                for string_suffix in ("123", "2026"):
                    yield base + string_suffix


def random_candidates(rng: random.Random, length: int = 16) -> Iterator[str]:
    alphabet = string.ascii_letters + string.digits + SYMBOLS
    while True:
        yield "".join(rng.choice(alphabet) for _ in range(length))


@dataclass(slots=True)
class AdaptiveAttacker:
    """A strategy-selecting baseline attacker that adapts from prior synthetic rounds."""

    rng: random.Random
    learned_words: list[str] = field(default_factory=list)
    strategy_scores: dict[str, float] = field(
        default_factory=lambda: {"common": 1.0, "mutation": 1.0, "passphrase": 1.0, "random": 0.1}
    )

    def _strategy_weights(self, difficulty: int) -> dict[str, float]:
        if difficulty <= 1:
            base = {"common": 0.70, "mutation": 0.20, "passphrase": 0.08, "random": 0.02}
        elif difficulty <= 3:
            base = {"common": 0.10, "mutation": 0.75, "passphrase": 0.10, "random": 0.05}
        elif difficulty <= 6:
            base = {"common": 0.05, "mutation": 0.15, "passphrase": 0.75, "random": 0.05}
        else:
            base = {"common": 0.01, "mutation": 0.04, "passphrase": 0.10, "random": 0.85}

        weighted = {
            name: weight * min(1.75, max(0.75, 0.75 + 0.25 * self.strategy_scores[name]))
            for name, weight in base.items()
        }
        total = sum(weighted.values())
        return {name: weight / total for name, weight in weighted.items()}

    def _candidates(self, strategy: str, password_length: int) -> Iterator[str]:
        known = tuple(dict.fromkeys((*self.learned_words, *WORDS, *COMMON)))
        if strategy == "common":
            return common_candidates()
        if strategy == "mutation":
            return mutation_candidates(known)
        if strategy == "passphrase":
            return passphrase_candidates(known)
        return random_candidates(self.rng, password_length)

    def attack(self, password: str, difficulty: int, max_guesses: int) -> AttackResult:
        started = time.perf_counter()
        weights = self._strategy_weights(difficulty)
        ordered = sorted(weights, key=lambda k: weights[k], reverse=True)
        raw_allocations = {name: max_guesses * weights[name] for name in ordered}
        allocations = {name: int(raw_allocations[name]) for name in ordered}
        remaining = max_guesses - sum(allocations.values())
        remainder_order = sorted(
            ordered,
            key=lambda name: raw_allocations[name] - allocations[name],
            reverse=True,
        )
        for name in remainder_order[:remaining]:
            allocations[name] += 1

        plan = tuple(
            StrategyBudget(
                strategy=name,
                weight=round(weights[name], 4),
                guess_budget=allocations[name],
            )
            for name in ordered
        )
        attempted: list[str] = []
        guesses = 0

        for strategy in ordered:
            budget = allocations[strategy]
            if budget <= 0:
                continue
            attempted.append(strategy)
            source = _dedupe(self._candidates(strategy, len(password)))
            for candidate in itertools.islice(source, budget):
                guesses += 1
                if candidate == password:
                    elapsed = (time.perf_counter() - started) * 1000
                    self.strategy_scores[strategy] += 2.0
                    return AttackResult(
                        True,
                        guesses,
                        strategy,
                        elapsed,
                        candidate,
                        plan,
                        tuple(attempted),
                    )

        if guesses < max_guesses:
            attempted.append("random-overflow")
            source = random_candidates(self.rng, len(password))
            for candidate in itertools.islice(source, max_guesses - guesses):
                guesses += 1
                if candidate == password:
                    elapsed = (time.perf_counter() - started) * 1000
                    self.strategy_scores["random"] += 2.0
                    return AttackResult(
                        True,
                        guesses,
                        "random",
                        elapsed,
                        candidate,
                        plan,
                        tuple(attempted),
                    )

        elapsed = (time.perf_counter() - started) * 1000
        for strategy in ordered:
            self.strategy_scores[strategy] *= 0.98
        return AttackResult(
            False,
            guesses,
            ordered[0],
            elapsed,
            None,
            plan,
            tuple(attempted),
        )

    def observe(self, password: str, solved: bool) -> str:
        # This is only permitted because all arena passwords are synthetic and local.
        parts = password.replace("_", "-").split("-")
        tokens = [token.lower() for token in parts if token.isalpha()]
        learned_now: list[str] = []
        for token in tokens:
            if 3 <= len(token) <= 20 and token not in self.learned_words:
                self.learned_words.append(token)
                learned_now.append(token)
        learned_summary = (
            f" Learned {len(learned_now)} new synthetic token(s)." if learned_now else ""
        )
        if solved:
            return (
                "Successful strategy received a higher future selection weight."
                + learned_summary
            )
        return (
            "Failure recorded; attacker retained synthetic token structure for later rounds."
            + learned_summary
        )
