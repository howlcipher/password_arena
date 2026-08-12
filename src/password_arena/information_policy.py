from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from password_arena.models import RoundResult, StrategyBudget


@dataclass(frozen=True, slots=True)
class AttackerObservation:
    """Safe structured observation provided to the attacker after a round."""

    round_number: int
    difficulty: int
    outcome: str

    # Self info
    attempted_strategies: tuple[str, ...] = ()
    guesses_used: int | None = None
    winning_strategy: str | None = None
    strategy_plan: tuple[StrategyBudget, ...] = ()

    # Defender info (depending on policy)
    defender_family: str | None = None
    password_length: int | None = None
    entropy_bits: float | None = None
    strength_score: int | None = None

    # Only in mutual_full
    defender_policy_metadata: dict[str, str] | None = None
    exact_synthetic_target: str | None = None


@dataclass(frozen=True, slots=True)
class DefenderObservation:
    """Safe structured observation provided to the defender after a round."""

    round_number: int
    difficulty: int
    outcome: str

    # Self info
    family_choice: str | None = None
    strength_score: int | None = None

    # Attacker info (depending on policy)
    attacker_strategies: tuple[str, ...] = ()
    attempted_strategies: tuple[str, ...] = ()
    strategy_allocations: tuple[StrategyBudget, ...] = ()
    guesses_used: int | None = None
    winning_strategy: str | None = None

    # Only in mutual_full
    complete_safe_attack_plan: tuple[StrategyBudget, ...] = ()
    safe_usage_metrics: dict[str, float] | None = None


class InformationPolicy(Protocol):
    @property
    def policy_id(self) -> str: ...

    def create_attacker_observation(
        self, round_result: RoundResult
    ) -> AttackerObservation | None: ...
    def create_defender_observation(
        self, round_result: RoundResult
    ) -> DefenderObservation | None: ...


class FrozenPolicy:
    @property
    def policy_id(self) -> str:
        return "frozen"

    def create_attacker_observation(self, round_result: RoundResult) -> AttackerObservation | None:
        return None

    def create_defender_observation(self, round_result: RoundResult) -> DefenderObservation | None:
        return None


class SelfOnlyPolicy:
    @property
    def policy_id(self) -> str:
        return "self_only"

    def create_attacker_observation(self, round_result: RoundResult) -> AttackerObservation | None:
        return AttackerObservation(
            round_number=round_result.round_number,
            difficulty=round_result.difficulty,
            outcome=round_result.attack.outcome,
            attempted_strategies=round_result.attack.attempted_strategies,
            guesses_used=round_result.attack.guesses_used,
            winning_strategy=round_result.attack.winning_strategy,
            strategy_plan=round_result.attack.plan,
        )

    def create_defender_observation(self, round_result: RoundResult) -> DefenderObservation | None:
        return DefenderObservation(
            round_number=round_result.round_number,
            difficulty=round_result.difficulty,
            outcome=round_result.attack.outcome,
            family_choice=round_result.defender_strategy,
            strength_score=round_result.strength.score,
        )


class AttackerObservesDefenderPolicy:
    @property
    def policy_id(self) -> str:
        return "attacker_observes_defender"

    def create_attacker_observation(self, round_result: RoundResult) -> AttackerObservation | None:
        return AttackerObservation(
            round_number=round_result.round_number,
            difficulty=round_result.difficulty,
            outcome=round_result.attack.outcome,
            attempted_strategies=round_result.attack.attempted_strategies,
            guesses_used=round_result.attack.guesses_used,
            winning_strategy=round_result.attack.winning_strategy,
            strategy_plan=round_result.attack.plan,
            defender_family=round_result.defender_strategy,
            password_length=round_result.password_length,
            entropy_bits=round_result.strength.entropy_bits,
            strength_score=round_result.strength.score,
            exact_synthetic_target=(
                round_result.password_display
                if round_result.password_display != "•" * len(round_result.password_display)
                else None
            ),
        )

    def create_defender_observation(self, round_result: RoundResult) -> DefenderObservation | None:
        return SelfOnlyPolicy().create_defender_observation(round_result)


class DefenderObservesAttackerPolicy:
    @property
    def policy_id(self) -> str:
        return "defender_observes_attacker"

    def create_attacker_observation(self, round_result: RoundResult) -> AttackerObservation | None:
        return SelfOnlyPolicy().create_attacker_observation(round_result)

    def create_defender_observation(self, round_result: RoundResult) -> DefenderObservation | None:
        return DefenderObservation(
            round_number=round_result.round_number,
            difficulty=round_result.difficulty,
            outcome=round_result.attack.outcome,
            family_choice=round_result.defender_strategy,
            strength_score=round_result.strength.score,
            attacker_strategies=tuple(
                set(round_result.attack.attempted_strategies)
            ),  # just a set or tuple
            attempted_strategies=round_result.attack.attempted_strategies,
            strategy_allocations=round_result.attack.plan,
            guesses_used=round_result.attack.guesses_used,
            winning_strategy=round_result.attack.winning_strategy,
        )


class MutualBoundedPolicy:
    @property
    def policy_id(self) -> str:
        return "mutual_bounded"

    def create_attacker_observation(self, round_result: RoundResult) -> AttackerObservation | None:
        return AttackerObservation(
            round_number=round_result.round_number,
            difficulty=round_result.difficulty,
            outcome=round_result.attack.outcome,
            attempted_strategies=round_result.attack.attempted_strategies,
            guesses_used=round_result.attack.guesses_used,
            winning_strategy=round_result.attack.winning_strategy,
            strategy_plan=round_result.attack.plan,
            defender_family=round_result.defender_strategy,
            password_length=round_result.password_length,
            entropy_bits=round_result.strength.entropy_bits,
            strength_score=round_result.strength.score,
            exact_synthetic_target=None,  # Never
        )

    def create_defender_observation(self, round_result: RoundResult) -> DefenderObservation | None:
        return DefenderObservesAttackerPolicy().create_defender_observation(round_result)


class MutualFullPolicy:
    @property
    def policy_id(self) -> str:
        return "mutual_full"

    def create_attacker_observation(self, round_result: RoundResult) -> AttackerObservation | None:
        return AttackerObservation(
            round_number=round_result.round_number,
            difficulty=round_result.difficulty,
            outcome=round_result.attack.outcome,
            attempted_strategies=round_result.attack.attempted_strategies,
            guesses_used=round_result.attack.guesses_used,
            winning_strategy=round_result.attack.winning_strategy,
            strategy_plan=round_result.attack.plan,
            defender_family=round_result.defender_strategy,
            password_length=round_result.password_length,
            entropy_bits=round_result.strength.entropy_bits,
            strength_score=round_result.strength.score,
            defender_policy_metadata={
                "provider": round_result.defender_metadata.provider
                if round_result.defender_metadata
                else "unknown"
            },
            exact_synthetic_target=round_result.password_display
            if round_result.password_display != "•" * len(round_result.password_display)
            else None,  # Engine needs to supply unmasked.
        )

    def create_defender_observation(self, round_result: RoundResult) -> DefenderObservation | None:
        usage = {}
        if round_result.attacker_usage:
            usage["tokens"] = float(
                round_result.attacker_usage.input_tokens + round_result.attacker_usage.output_tokens
            )
        return DefenderObservation(
            round_number=round_result.round_number,
            difficulty=round_result.difficulty,
            outcome=round_result.attack.outcome,
            family_choice=round_result.defender_strategy,
            strength_score=round_result.strength.score,
            attacker_strategies=tuple(set(round_result.attack.attempted_strategies)),
            attempted_strategies=round_result.attack.attempted_strategies,
            strategy_allocations=round_result.attack.plan,
            guesses_used=round_result.attack.guesses_used,
            winning_strategy=round_result.attack.winning_strategy,
            complete_safe_attack_plan=round_result.attack.plan,
            safe_usage_metrics=usage,
        )


class LegacyCurrentPolicy:
    @property
    def policy_id(self) -> str:
        return "legacy_current"

    def create_attacker_observation(self, round_result: RoundResult) -> AttackerObservation | None:
        return None  # Special case: engine handles string learning natively

    def create_defender_observation(self, round_result: RoundResult) -> DefenderObservation | None:
        return None  # Special case: engine handles string learning natively


POLICY_REGISTRY: dict[str, InformationPolicy] = {
    "frozen": FrozenPolicy(),
    "self_only": SelfOnlyPolicy(),
    "attacker_observes_defender": AttackerObservesDefenderPolicy(),
    "defender_observes_attacker": DefenderObservesAttackerPolicy(),
    "mutual_bounded": MutualBoundedPolicy(),
    "mutual_full": MutualFullPolicy(),
    "legacy_current": LegacyCurrentPolicy(),
}


def get_policy(policy_id: str) -> InformationPolicy:
    if policy_id not in POLICY_REGISTRY:
        raise ValueError(f"Unknown information policy: {policy_id}")
    return POLICY_REGISTRY[policy_id]
