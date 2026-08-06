from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from password_arena.providers import ThinkingLevel


@dataclass(frozen=True, slots=True)
class RoleConfig:
    provider: str = "rule_based"
    model: str | None = None
    thinking_level: ThinkingLevel = ThinkingLevel.AUTO
    temperature: float | None = None
    max_tokens: int | None = None
    local_endpoint: str | None = None


@dataclass(frozen=True, slots=True)
class ArenaConfig:
    """Runtime controls for one arena experiment."""

    rounds: int = 8
    start_difficulty: int = 1
    difficulty_step: int = 1
    max_guesses: int = 5_000
    seed: int = 42
    reveal_passwords: bool = False
    defender_config: RoleConfig = field(default_factory=RoleConfig)
    attacker_config: RoleConfig = field(default_factory=RoleConfig)
    evaluator_config: RoleConfig = field(default_factory=RoleConfig)
    generator_mode: str = "secure"
    generator_version: str = "1.0"

    def validate(self) -> None:
        if not 1 <= self.rounds <= 100:
            raise ValueError("rounds must be between 1 and 100")
        if not 1 <= self.start_difficulty <= 10:
            raise ValueError("start_difficulty must be between 1 and 10")
        if not 0 <= self.difficulty_step <= 5:
            raise ValueError("difficulty_step must be between 0 and 5")
        if not 1 <= self.max_guesses <= 1_000_000:
            raise ValueError("max_guesses must be between 1 and 1,000,000")
        if self.generator_mode not in ("secure", "deterministic-test"):
            raise ValueError("generator_mode must be 'secure' or 'deterministic-test'")
        if self.generator_version not in ("1.0", "benchmark"):
            raise ValueError("generator_version must be '1.0' or 'benchmark'")


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
    winning_strategy: str | None
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
class RoleMetadata:
    provider: str
    model: str | None
    thinking_level: ThinkingLevel


@dataclass(frozen=True, slots=True)
class RoundReport:
    defender: AgentReport
    attacker: AgentReport
    evaluator_summary: str
    security_lesson: str
    defender_metadata: RoleMetadata | None = None
    attacker_metadata: RoleMetadata | None = None
    evaluator_metadata: RoleMetadata | None = None


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
    experiment_id: str = field(default_factory=lambda: __import__("uuid").uuid4().hex)
    timestamp: str = field(default_factory=lambda: __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).isoformat())

    @property
    def solved_rounds(self) -> int:
        return sum(item.attack.solved for item in self.rounds)

    @property
    def solve_rate(self) -> float:
        return self.solved_rounds / len(self.rounds) if self.rounds else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "timestamp": self.timestamp,
            "schema_version": "1.0",
            "config": asdict(self.config),
            "summary": {
                "solved_rounds": self.solved_rounds,
                "total_rounds": len(self.rounds),
                "solve_rate": self.solve_rate,
            },
            "rounds": [item.to_dict() for item in self.rounds],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentResult:
        config_data = data["config"].copy()
        for role in ["defender_config", "attacker_config", "evaluator_config"]:
            if role in config_data and isinstance(config_data[role], dict):
                config_data[role] = RoleConfig(**config_data[role])
        config = ArenaConfig(**config_data)

        rounds = []
        for r_data in data.get("rounds", []):
            strength = StrengthReport(**r_data["strength"])
            plan = []
            for p_data in r_data["attack"].get("plan", []):
                plan.append(StrategyBudget(**p_data))
            attack_data = r_data["attack"].copy()
            attack_data["plan"] = tuple(plan)
            attack_data["attempted_strategies"] = tuple(attack_data.get("attempted_strategies", []))
            attack = AttackResult(**attack_data)

            report_data = r_data["report"].copy()
            report_data["defender"] = AgentReport(**report_data["defender"])
            report_data["attacker"] = AgentReport(**report_data["attacker"])
            for meta_key in ["defender_metadata", "attacker_metadata", "evaluator_metadata"]:
                if report_data.get(meta_key):
                    report_data[meta_key] = RoleMetadata(**report_data[meta_key])
            report = RoundReport(**report_data)

            round_data = r_data.copy()
            round_data["strength"] = strength
            round_data["attack"] = attack
            round_data["report"] = report
            rounds.append(RoundResult(**round_data))

        return cls(
            config=config,
            rounds=tuple(rounds),
            experiment_id=data.get("experiment_id", __import__("uuid").uuid4().hex),
            timestamp=data.get("timestamp", __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).isoformat())
        )
