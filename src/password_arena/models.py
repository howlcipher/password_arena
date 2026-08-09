from __future__ import annotations

import enum
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from password_arena.providers import ThinkingLevel

ARENA_EVENT_SCHEMA_VERSION = "1.0"


class RoundOutcome(enum.StrEnum):
    COMPLETED = "completed"
    RESISTED = "resisted"
    TIMED_OUT = "timed_out"
    BUDGET_EXHAUSTED = "budget_exhausted"
    ERROR = "error"


class ExclusionReason(enum.StrEnum):
    """Why an observation was excluded from headline tournament statistics."""

    PREFLIGHT_FAILED = "preflight_failed"
    INTERRUPTED_PROVIDER = "interrupted_provider"
    FALLBACK_USED = "fallback_used"
    MISMATCHED_GENERATOR_VERSION = "mismatched_generator_version"
    MISMATCHED_GUESS_BUDGET = "mismatched_guess_budget"
    MISMATCHED_SEED_SET = "mismatched_seed_set"
    UNSUPPORTED_CONFIGURATION = "unsupported_configuration"


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

    @classmethod
    def from_role_config(cls, role_config: RoleConfig) -> RoleMetadata:
        return cls(
            provider=role_config.provider,
            model=role_config.model,
            thinking_level=role_config.thinking_level,
        )


@dataclass(frozen=True, slots=True)
class RoleUsage:
    """Per-role, per-round LLM usage. Absent (None on RoundResult) means no backend call."""

    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int | None = None
    latency_ms: float = 0.0
    estimated_cost: float | None = None
    fallback_used: bool = False
    requested_thinking_level: ThinkingLevel | None = None
    effective_thinking_level: ThinkingLevel | None = None


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
    attacker_usage: RoleUsage | None = None
    defender_usage: RoleUsage | None = None
    comparable: bool = True

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.defender_metadata:
            d["defender_metadata"] = asdict(self.defender_metadata)
        if self.attacker_metadata:
            d["attacker_metadata"] = asdict(self.attacker_metadata)
        if self.evaluator_metadata:
            d["evaluator_metadata"] = asdict(self.evaluator_metadata)
        if self.attacker_usage:
            d["attacker_usage"] = asdict(self.attacker_usage)
        if self.defender_usage:
            d["defender_usage"] = asdict(self.defender_usage)
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

    @property
    def rounds_attempted(self) -> int:
        """Recorded rounds plus the in-progress round that was interrupted, if any.

        A round is only appended to `rounds` once it fully completes (see
        ArenaEngine.run); an interruption always aborts before that append, so the
        round in progress at interruption time is exactly one more than len(rounds).
        """
        return len(self.rounds) + (1 if self.interruption_reason else 0)

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
                role_data = config_data[role].copy()
                # ThinkingLevel is a StrEnum, so JSON round-tripping leaves it
                # as a plain str; re-wrap it or later `.thinking_level.value`
                # access on a loaded experiment raises AttributeError.
                if "thinking_level" in role_data:
                    role_data["thinking_level"] = ThinkingLevel(role_data["thinking_level"])
                config_data[role] = RoleConfig(**role_data)
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
                    metadata = round_data[meta_key].copy()
                    if metadata.get("thinking_level") is not None:
                        metadata["thinking_level"] = ThinkingLevel(metadata["thinking_level"])
                    round_data[meta_key] = RoleMetadata(**metadata)

            for usage_key in ["attacker_usage", "defender_usage"]:
                if round_data.get(usage_key):
                    usage = round_data[usage_key].copy()
                    for thinking_key in [
                        "requested_thinking_level",
                        "effective_thinking_level",
                    ]:
                        if usage.get(thinking_key) is not None:
                            usage[thinking_key] = ThinkingLevel(usage[thinking_key])
                    round_data[usage_key] = RoleUsage(**usage)

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


@dataclass(frozen=True, slots=True)
class MatchupConfig:
    attacker: RoleConfig
    defender: RoleConfig
    rounds: int
    seeds: tuple[int, ...]
    generator_version: str = "benchmark"
    generator_mode: str = "deterministic-test"
    max_guesses: int = 5000
    max_wall_time_s: float | None = None
    max_tokens: int | None = None
    max_api_cost: float | None = None
    max_retries: int | None = None


@dataclass(frozen=True, slots=True)
class ExclusionRecord:
    seed: int
    experiment_id: str | None
    round_number: int | None
    reason: ExclusionReason


@dataclass(frozen=True, slots=True)
class EfficiencyMetrics:
    """Transparent per-role efficiency ratios. None when the denominator is unavailable or zero."""

    attacker_solved_per_1k_tokens: float | None = None
    attacker_solved_per_second: float | None = None
    attacker_solved_per_dollar: float | None = None
    defender_survived_per_1k_tokens: float | None = None
    defender_survived_per_dollar: float | None = None
    defender_entropy_gain_per_1k_tokens: float | None = None


@dataclass(frozen=True, slots=True)
class ReplayMetadata:
    """Enough metadata to reconstruct a matchup's configuration for a re-run.

    `deterministic=True` only when both roles are rule_based AND generator_mode is
    "deterministic-test" -- only then does re-running guarantee an identical result.
    Otherwise this only supports "configuration replay": re-running the same
    configuration, with no claim that a hosted model will reproduce prior output.
    """

    attacker: RoleMetadata
    defender: RoleMetadata
    seeds: tuple[int, ...]
    rounds_per_match: int
    max_guesses: int
    generator_mode: str
    generator_version: str
    application_version: str
    schema_version: str
    deterministic: bool
    attacker_prompt_version: str
    defender_prompt_version: str
    capability_registry_version: str


@dataclass(frozen=True, slots=True)
class MatchupSummary:
    """Tournament matchup statistics.

    Round-level fields (rounds_completed/solved/resisted, solve_rate, survival_rate,
    guess metrics, token/latency/cost totals) are computed only from *comparable*
    rounds (see RoundResult.comparable) across ALL trials, including trials that were
    later interrupted -- their already-recorded, non-fallback rounds are still valid
    Bernoulli observations. Trial-level fields (final_round_*, mean_total_guesses_per_trial,
    comparable_trials) require the whole trial to be comparable, since they are not
    decomposable to individual rounds.

    Cost is tracked both combined (`total_estimated_cost`) and per role
    (`attacker_estimated_cost`, `defender_estimated_cost`); each is `None`, never
    `0.0`, unless every contributing comparable round's cost for that scope is
    known. A role that made no LLM calls (e.g. rule_based) contributes a real,
    known `0.0` to its own field, not `None`.
    """

    trials: int
    comparable_trials: int
    excluded_trials: int
    excluded_rounds: int

    rounds_completed: int
    rounds_solved: int
    rounds_resisted: int

    solve_rate: float | None
    survival_rate: float | None
    confidence_interval_lower: float | None
    confidence_interval_upper: float | None

    final_round_solved_count: int
    final_round_resisted_count: int

    mean_guesses_per_round: float | None
    median_guesses_per_round: float | None
    std_guesses_per_round: float | None
    mean_guesses_to_solve: float | None
    median_guesses_to_solve: float | None
    mean_total_guesses_per_trial: float | None

    attacker_input_tokens: int = 0
    attacker_output_tokens: int = 0
    attacker_reasoning_tokens: int | None = None
    defender_input_tokens: int = 0
    defender_output_tokens: int = 0
    defender_reasoning_tokens: int | None = None
    attacker_mean_latency_ms: float | None = None
    defender_mean_latency_ms: float | None = None
    total_estimated_cost: float | None = None
    attacker_estimated_cost: float | None = None
    defender_estimated_cost: float | None = None
    # A trajectory is usable only when its trial completed with every scheduled
    # round comparable. It is intentionally separate from round-level headline
    # statistics, which can include valid rounds from an interrupted trial.
    entropy_gain_trials: int = 0
    mean_initial_entropy_bits: float | None = None
    mean_final_entropy_bits: float | None = None
    mean_entropy_gain_bits: float | None = None
    defender_entropy_gain_tokens: int | None = None
    efficiency: EfficiencyMetrics = field(default_factory=EfficiencyMetrics)


@dataclass(frozen=True, slots=True)
class MatchupResult:
    matchup_id: str
    config: MatchupConfig
    experiments: tuple[ExperimentResult, ...]
    summary: MatchupSummary
    is_comparable: bool = True
    non_comparable_reason: str | None = None
    excluded_trial_records: tuple[ExclusionRecord, ...] = ()
    excluded_round_records: tuple[ExclusionRecord, ...] = ()
    replay: ReplayMetadata | None = None


class MatchupLike(Protocol):
    """Structural type satisfied by both `MatchupResult` (a fresh, in-memory
    tournament result) and `tournament_history.StoredMatchup` (one
    reconstructed from disk) -- the two concrete types the Tournament
    dashboard and reporting.py's report builders consume interchangeably.
    Lives in models.py (not tournament_view_models.py) specifically so
    reporting.py can use it without pulling in tournament_view_models.py's
    pandas dependency, which is only in the optional `dashboard` extra.
    Declared as read-only properties (not plain attributes) so frozen
    dataclasses -- whose fields mypy treats as read-only -- satisfy this
    protocol structurally."""

    @property
    def matchup_id(self) -> str: ...

    @property
    def config(self) -> MatchupConfig: ...

    @property
    def summary(self) -> MatchupSummary: ...

    @property
    def is_comparable(self) -> bool: ...

    @property
    def non_comparable_reason(self) -> str | None: ...

    @property
    def replay(self) -> ReplayMetadata | None: ...

    @property
    def excluded_trial_records(self) -> tuple[ExclusionRecord, ...]: ...

    @property
    def excluded_round_records(self) -> tuple[ExclusionRecord, ...]: ...


@dataclass(frozen=True, slots=True)
class TournamentConfig:
    attackers: tuple[RoleConfig, ...]
    defenders: tuple[RoleConfig, ...]
    seeds: tuple[int, ...]
    rounds_per_match: int
    generator_version: str = "benchmark"
    generator_mode: str = "deterministic-test"
    max_guesses: int = 5000
    max_wall_time_s: float | None = None
    max_tokens: int | None = None
    max_api_cost: float | None = None
    max_retries: int | None = None
