from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ArenaConfig:
    """Runtime controls for one arena experiment."""

    rounds: int = 8
    start_difficulty: int = 1
    difficulty_step: int = 1
    max_guesses: int = 5_000
    seed: int = 42
    reveal_passwords: bool = False

    def validate(self) -> None:
        if not 1 <= self.rounds <= 100:
            raise ValueError("rounds must be between 1 and 100")
        if not 1 <= self.start_difficulty <= 10:
            raise ValueError("start_difficulty must be between 1 and 10")
        if not 0 <= self.difficulty_step <= 5:
            raise ValueError("difficulty_step must be between 0 and 5")
        if not 1 <= self.max_guesses <= 1_000_000:
            raise ValueError("max_guesses must be between 1 and 1,000,000")


@dataclass(frozen=True, slots=True)
class StrengthReport:
    entropy_bits: float
    score: int
    character_pool: int
    pattern_penalty: float
    findings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StrategyBudget:
    """One attack strategy's measured share of the bounded guess budget."""

    strategy: str
    weight: float
    guess_budget: int


@dataclass(frozen=True, slots=True)
class AttackResult:
    solved: bool
    guesses_used: int
    strategy: str
    elapsed_ms: float
    candidate: str | None = None
    plan: tuple[StrategyBudget, ...] = ()
    attempted_strategies: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AgentReport:
    """Auditable account generated from recorded agent actions, not free-form invention."""

    decision: str
    actions: tuple[str, ...]
    observation: str
    learning_update: str


@dataclass(frozen=True, slots=True)
class RoundReport:
    defender: AgentReport
    attacker: AgentReport
    evaluator_summary: str
    security_lesson: str


@dataclass(frozen=True, slots=True)
class RoundResult:
    round_number: int
    difficulty: int
    password_display: str
    password_length: int
    strength: StrengthReport
    attack: AttackResult
    defender_strategy: str
    attacker_note: str
    defender_note: str
    report: RoundReport

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    config: ArenaConfig
    rounds: tuple[RoundResult, ...] = field(default_factory=tuple)

    @property
    def solved_rounds(self) -> int:
        return sum(item.attack.solved for item in self.rounds)

    @property
    def solve_rate(self) -> float:
        return self.solved_rounds / len(self.rounds) if self.rounds else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": asdict(self.config),
            "summary": {
                "solved_rounds": self.solved_rounds,
                "total_rounds": len(self.rounds),
                "solve_rate": self.solve_rate,
            },
            "rounds": [item.to_dict() for item in self.rounds],
        }
