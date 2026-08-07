from __future__ import annotations

import enum
from dataclasses import asdict, dataclass, field
from typing import Any

from password_arena.providers import ThinkingLevel


class RoundOutcome(enum.StrEnum):
    COMPLETED = "completed"
    RESISTED = "resisted"
    TIMED_OUT = "timed_out"
    BUDGET_EXHAUSTED = "budget_exhausted"
    ERROR = "error"


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
    max_wall_time_s: float | None = None
    max_tokens: int | None = None
    max_api_cost: float | None = None
    max_retries: int | None = None
    seed: int = 42
    reveal_passwords: bool = False
    defender_config: RoleConfig = field(default_factory=RoleConfig)
    attacker_config: RoleConfig = field(default_factory=RoleConfig)
    evaluator_config: RoleConfig = field(default_factory=RoleConfig)
    generator_mode: str = "secure"
    generator_version: str = "1.0"

    def validate(self) -> None:
        for key in asdict(self):
            k_lower = key.lower()
            if (
                "key" in k_lower or "token" in k_lower or "secret" in k_lower
            ) and k_lower != "max_tokens":
                raise ValueError(f"Profile configuration must not contain secret-like field: {key}")
        for role_config in [self.defender_config, self.attacker_config, self.evaluator_config]:
            for key in asdict(role_config):
                k_lower = key.lower()
                if (
                    "key" in k_lower or "token" in k_lower or "secret" in k_lower
                ) and k_lower != "max_tokens":
                    raise ValueError(
                        f"Profile configuration must not contain secret-like field: {key}"
                    )
        if not 1 <= self.rounds <= 100:
            raise ValueError("rounds must be between 1 and 100")
        if not 1 <= self.start_difficulty <= 10:
            raise ValueError("start_difficulty must be between 1 and 10")
        if not 0 <= self.difficulty_step <= 5:
            raise ValueError("difficulty_step must be between 0 and 5")
        if not 1 <= self.max_guesses <= 1_000_000:
            raise ValueError("max_guesses must be between 1 and 1,000,000")
        if self.max_wall_time_s is not None and self.max_wall_time_s <= 0:
            raise ValueError("max_wall_time_s must be positive")
        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if self.max_api_cost is not None and self.max_api_cost < 0:
            raise ValueError("max_api_cost cannot be negative")
        if self.max_retries is not None and self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")
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
    outcome: RoundOutcome = RoundOutcome.COMPLETED


@dataclass(frozen=True, slots=True)
class RoleMetadata:
    provider: str
    model: str | None
    thinking_level: ThinkingLevel


@dataclass(frozen=True, slots=True)
class RoundResult:
    round_number: int
    difficulty: int
    password_display: str
    password_length: int
    strength: StrengthReport
    attack: AttackResult
    defender_strategy: str
    defender_note: str
    defender_learning: str
    attacker_note: str
    attacker_learning: str
    defender_metadata: RoleMetadata | None = None
    attacker_metadata: RoleMetadata | None = None
    evaluator_metadata: RoleMetadata | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.defender_metadata:
            d["defender_metadata"] = asdict(self.defender_metadata)
        if self.attacker_metadata:
            d["attacker_metadata"] = asdict(self.attacker_metadata)
        if self.evaluator_metadata:
            d["evaluator_metadata"] = asdict(self.evaluator_metadata)
        return d


@dataclass(frozen=True, slots=True)
class ArenaEvent:
    event_id: str
    experiment_id: str
    timestamp: str
    application_version: str
    schema_version: str
    event_type: str
    round_id: int | None
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    config: ArenaConfig
    rounds: tuple[RoundResult, ...] = field(default_factory=tuple)
    experiment_id: str = field(default_factory=lambda: __import__("uuid").uuid4().hex)
    timestamp: str = field(
        default_factory=lambda: (
            __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        )
    )
    interruption_reason: str | None = None
    interruption_state: str | None = None
    events: tuple[ArenaEvent, ...] = field(default_factory=tuple)

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
            "application_version": __import__("password_arena").__version__,
            "config": asdict(self.config),
            "summary": {
                "solved_rounds": self.solved_rounds,
                "total_rounds": len(self.rounds),
                "solve_rate": self.solve_rate,
            },
            "rounds": [item.to_dict() for item in self.rounds],
            "events": [event.to_dict() for event in self.events],
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

            round_data = r_data.copy()
            round_data["strength"] = strength
            round_data["attack"] = attack

            for meta_key in ["defender_metadata", "attacker_metadata", "evaluator_metadata"]:
                if round_data.get(meta_key):
                    round_data[meta_key] = RoleMetadata(**round_data[meta_key])

            # Handle backward compatibility: older runs may have report embedded
            if "report" in round_data:
                report = round_data.pop("report")
                if not round_data.get("defender_learning"):
                    round_data["defender_learning"] = report["defender"]["learning_update"]
                    round_data["attacker_learning"] = report["attacker"]["learning_update"]
                    round_data["defender_note"] = report["defender"]["decision"]
                    round_data["attacker_note"] = report["attacker"]["decision"]

            rounds.append(RoundResult(**round_data))

        events = []
        for e_data in data.get("events", []):
            events.append(ArenaEvent(**e_data))

        return cls(
            config=config,
            rounds=tuple(rounds),
            events=tuple(events),
            experiment_id=data.get("experiment_id", __import__("uuid").uuid4().hex),
            timestamp=data.get(
                "timestamp",
                __import__("datetime")
                .datetime.now(__import__("datetime").timezone.utc)
                .isoformat(),
            ),
        )
