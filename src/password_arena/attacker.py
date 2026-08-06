from __future__ import annotations

import itertools
import random
import string
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol

from password_arena.grammars import COMMON_PASSWORDS as COMMON
from password_arena.grammars import SHARED_WORDS, SYMBOLS
from password_arena.models import AttackResult, StrategyBudget
from password_arena.providers import AgentBackend, ProviderRequest


def _dedupe(candidates: Iterator[str]) -> Iterator[str]:
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            yield candidate


@dataclass(slots=True)
class AttackContext:
    password_length: int
    known_words: tuple[str, ...]
    rng: random.Random


class AttackStrategy(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def supported_inputs(self) -> str: ...
    def candidates(self, context: AttackContext) -> Iterator[str]: ...


class CommonStrategy:
    @property
    def name(self) -> str:
        return "common"

    @property
    def supported_inputs(self) -> str:
        return "common passwords list"

    def candidates(self, context: AttackContext) -> Iterator[str]:
        yield from COMMON


class MutationStrategy:
    @property
    def name(self) -> str:
        return "mutation"

    @property
    def supported_inputs(self) -> str:
        return "known words"

    def candidates(self, context: AttackContext) -> Iterator[str]:
        substitutions = {"a": "@", "e": "3", "i": "1", "o": "0", "s": "$"}
        for word in context.known_words:
            mutated = "".join(substitutions.get(char, char) for char in word)
            forms = tuple(
                dict.fromkeys((word, word.title(), word.upper(), mutated, mutated.title()))
            )
            yield from forms
            for number in range(0, 100):
                for form in forms:
                    yield f"{form}{number:02d}"
            for symbol in SYMBOLS:
                for form in forms:
                    yield f"{form}{symbol}"


class PassphraseStrategy:
    @property
    def name(self) -> str:
        return "passphrase"

    @property
    def supported_inputs(self) -> str:
        return "known words"

    def candidates(self, context: AttackContext) -> Iterator[str]:
        limited = context.known_words[: min(len(context.known_words), 12)]
        for count in range(2, 5):
            for parts in itertools.permutations(limited, count):
                variants = (
                    "-".join(parts),
                    "-".join(part.title() for part in parts),
                    f"{parts[0].title()}-" + "-".join(parts[1:]),
                )
                for base in dict.fromkeys(variants):
                    yield base
                    for suffix in range(0, 1000):
                        if suffix < 100:
                            yield f"{base}{suffix:02d}"
                        else:
                            yield f"{base}{suffix}"
                    for string_suffix in ("123", "2026"):
                        yield base + string_suffix


class RandomStrategy:
    @property
    def name(self) -> str:
        return "random"

    @property
    def supported_inputs(self) -> str:
        return "password length"

    def candidates(self, context: AttackContext) -> Iterator[str]:
        alphabet = string.ascii_letters + string.digits + SYMBOLS
        while True:
            yield "".join(context.rng.choice(alphabet) for _ in range(context.password_length))


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, AttackStrategy] = {}

    def register(self, strategy: AttackStrategy) -> None:
        self._strategies[strategy.name] = strategy

    def get(self, name: str) -> AttackStrategy | None:
        return self._strategies.get(name)

    def get_all(self) -> list[AttackStrategy]:
        return list(self._strategies.values())

    def __contains__(self, name: str) -> bool:
        return name in self._strategies


default_registry = StrategyRegistry()
default_registry.register(CommonStrategy())
default_registry.register(MutationStrategy())
default_registry.register(PassphraseStrategy())
default_registry.register(RandomStrategy())


@dataclass(slots=True)
class AdaptiveAttacker:
    """A strategy-selecting baseline attacker that adapts from prior synthetic rounds."""

    rng: random.Random
    learned_words: list[str] = field(default_factory=list)
    strategy_scores: dict[str, float] = field(
        default_factory=lambda: {"common": 1.0, "mutation": 1.0, "passphrase": 1.0, "random": 0.1}
    )
    backend: AgentBackend | None = None
    strategy_registry: StrategyRegistry = field(default_factory=lambda: default_registry)
    enabled_strategies: set[str] = field(
        default_factory=lambda: {"common", "mutation", "passphrase", "random"}
    )

    def _strategy_weights(self, difficulty: int, max_guesses: int) -> dict[str, float]:
        if self.backend:
            return self._strategy_weights_backend(difficulty, max_guesses)

        if difficulty <= 1:
            base = {"common": 0.70, "mutation": 0.20, "passphrase": 0.08, "random": 0.02}
        elif difficulty <= 3:
            base = {"common": 0.10, "mutation": 0.75, "passphrase": 0.10, "random": 0.05}
        elif difficulty <= 6:
            base = {"common": 0.05, "mutation": 0.15, "passphrase": 0.75, "random": 0.05}
        else:
            base = {"common": 0.01, "mutation": 0.04, "passphrase": 0.10, "random": 0.85}

        # Filter out disabled strategies
        base = {
            k: v
            for k, v in base.items()
            if k in self.enabled_strategies and k in self.strategy_registry
        }
        if not base:
            # Fallback if nothing enabled
            return {}

        weighted = {
            name: weight * min(1.75, max(0.75, 0.75 + 0.25 * self.strategy_scores.get(name, 1.0)))
            for name, weight in base.items()
        }
        total = sum(weighted.values())
        if total == 0:
            return {}
        return {name: weight / total for name, weight in weighted.items()}

    def _candidates(self, strategy: str, password_length: int) -> Iterator[str]:
        if strategy not in self.enabled_strategies:
            return iter([])
        strat_obj = self.strategy_registry.get(strategy)
        if strat_obj is None:
            return iter([])
        known = tuple(dict.fromkeys((*self.learned_words, *SHARED_WORDS, *COMMON)))
        ctx = AttackContext(password_length=password_length, known_words=known, rng=self.rng)
        return strat_obj.candidates(ctx)

    def attack(self, password: str, difficulty: int, max_guesses: int) -> AttackResult:
        started = time.perf_counter()
        weights = self._strategy_weights(difficulty, max_guesses)
        if not weights:
            # Nothing enabled
            elapsed = (time.perf_counter() - started) * 1000
            return AttackResult(False, 0, None, elapsed, None, (), ())

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
                weight=weights[name],
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
                    self.strategy_scores[strategy] = self.strategy_scores.get(strategy, 1.0) + 2.0
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
            # Reuse random strategy for overflow, if available
            overflow_strat = self.strategy_registry.get("random")
            if overflow_strat and "random" in self.enabled_strategies:
                known = tuple(dict.fromkeys((*self.learned_words, *SHARED_WORDS, *COMMON)))
                ctx = AttackContext(password_length=len(password), known_words=known, rng=self.rng)
                source = overflow_strat.candidates(ctx)
                for candidate in itertools.islice(source, max_guesses - guesses):
                    guesses += 1
                    if candidate == password:
                        elapsed = (time.perf_counter() - started) * 1000
                        new_score = self.strategy_scores.get("random", 1.0) + 2.0
                        self.strategy_scores["random"] = new_score
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
            self.strategy_scores[strategy] = self.strategy_scores.get(strategy, 1.0) * 0.98
        return AttackResult(
            False,
            guesses,
            None,
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
                "Successful strategy received a higher future selection weight." + learned_summary
            )
        return (
            "Failure recorded; attacker retained synthetic token structure for later rounds."
            + learned_summary
        )

    def _strategy_weights_backend(self, difficulty: int, max_guesses: int) -> dict[str, float]:
        schema = {
            "type": "object",
            "properties": {
                "weights": {"type": "object", "additionalProperties": {"type": "number"}},
                "reasoning": {"type": "string"},
            },
            "required": ["weights", "reasoning"],
        }

        # Build list of available strategies
        avail = [s for s in self.strategy_registry._strategies if s in self.enabled_strategies]

        prompt = (
            f"Allocate strategy weights (sum to 1.0) for a password attack at "
            f"difficulty {difficulty} (1-10).\n"
            f"Current strategy scores: {self.strategy_scores}.\n"
            f"Total guesses allowed: {max_guesses}.\n"
            f"Strategies typically available: {', '.join(avail)}.\n"
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
                "Provider response missing valid structured data"
            )

        weights = data.get("weights")
        if not isinstance(weights, dict):
            from password_arena.providers import AvailabilityState, ProviderError
            raise ProviderError(
                AvailabilityState.INVALID_RESPONSE,
                "Provider response failed schema validation: weights must be a dictionary"
            )

        parsed_weights: dict[str, float] = {}
        for k, v in weights.items():
            if not isinstance(k, str) or not isinstance(v, (int, float)):
                from password_arena.providers import AvailabilityState, ProviderError
                raise ProviderError(
                    AvailabilityState.INVALID_RESPONSE,
                    "Provider response failed schema validation: weights values must be numbers"
                )
            if k in avail:
                parsed_weights[k] = float(v)

        total = sum(parsed_weights.values())
        if total == 0:
            if "random" in avail:
                return {"random": 1.0}
            elif avail:
                return {avail[0]: 1.0}
            return {}
        return {k: v / total for k, v in parsed_weights.items()}
