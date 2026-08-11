from __future__ import annotations

import datetime
import random
import time
from dataclasses import replace
from typing import Any, NamedTuple

import password_arena
from password_arena.attacker import AdaptiveAttacker
from password_arena.calibration import CalibrationPolicy
from password_arena.defender import AdaptiveDefender
from password_arena.models import (
    ARENA_EVENT_SCHEMA_VERSION,
    ArenaConfig,
    ArenaEvent,
    ExperimentResult,
    RoleMetadata,
    RoleUsage,
    RoundOutcome,
    RoundResult,
)
from password_arena.providers import (
    AgentBackend,
    AvailabilityResult,
    AvailabilityState,
    ModelCapabilities,
    ProviderError,
    ProviderRegistry,
    ProviderRequest,
    ProviderResponse,
    UsageMetrics,
)
from password_arena.strength import evaluate_strength


class PreflightFailure(NamedTuple):
    role: str
    state: str
    message: str


def _to_role_usage(metrics: UsageMetrics | None) -> RoleUsage | None:
    if metrics is None:
        return None
    return RoleUsage(
        input_tokens=metrics.input_tokens,
        output_tokens=metrics.output_tokens,
        reasoning_tokens=metrics.reasoning_tokens,
        latency_ms=metrics.latency_ms,
        estimated_cost=metrics.estimated_cost,
        fallback_used=metrics.fallback_used,
        requested_thinking_level=metrics.requested_thinking_level,
        effective_thinking_level=metrics.effective_thinking_level,
    )


def build_arena_engine(
    config: ArenaConfig, secrets_config: dict[str, str] | None = None
) -> ArenaEngine | PreflightFailure:
    config.validate()

    try:
        defender_backend = ProviderRegistry.create(config.defender_config, secrets_config)
    except Exception as e:
        return PreflightFailure("defender", AvailabilityState.UNKNOWN_ERROR.value, str(e))

    try:
        attacker_backend = ProviderRegistry.create(config.attacker_config, secrets_config)
    except Exception as e:
        return PreflightFailure("attacker", AvailabilityState.UNKNOWN_ERROR.value, str(e))

    if defender_backend:
        avail = defender_backend.check_availability()
        if avail.state != AvailabilityState.AVAILABLE:
            return PreflightFailure("defender", avail.state.value, avail.message)

    if attacker_backend:
        avail = attacker_backend.check_availability()
        if avail.state != AvailabilityState.AVAILABLE:
            return PreflightFailure("attacker", avail.state.value, avail.message)

    tracker = BudgetTracker(config)
    if defender_backend:
        defender_backend = BoundBackend(defender_backend, tracker)
    if attacker_backend:
        attacker_backend = BoundBackend(attacker_backend, tracker)

    return ArenaEngine(config, defender_backend, attacker_backend, tracker)


class BudgetExhaustedError(Exception):
    def __init__(self, reason: str, outcome_type: RoundOutcome = RoundOutcome.BUDGET_EXHAUSTED):
        super().__init__(reason)
        self.reason = reason
        self.outcome_type = outcome_type


class BudgetTracker:
    def __init__(self, config: ArenaConfig) -> None:
        self.config = config
        self.start_time = time.monotonic()
        self.total_tokens = 0
        self.total_cost = 0.0
        self.retries = 0

    def check_limits(self) -> None:
        if (
            self.config.max_wall_time_s is not None
            and (time.monotonic() - self.start_time) > self.config.max_wall_time_s
        ):
            raise BudgetExhaustedError("Time limit exceeded.", RoundOutcome.TIMED_OUT)
        if self.config.max_tokens is not None and self.total_tokens > self.config.max_tokens:
            raise BudgetExhaustedError("Token limit exceeded.", RoundOutcome.BUDGET_EXHAUSTED)
        if self.config.max_api_cost is not None and self.total_cost > self.config.max_api_cost:
            raise BudgetExhaustedError("API cost limit exceeded.", RoundOutcome.BUDGET_EXHAUSTED)
        if self.config.max_retries is not None and self.retries > self.config.max_retries:
            raise BudgetExhaustedError("Retries limit exceeded.", RoundOutcome.ERROR)

    def add_metrics(self, metrics: UsageMetrics) -> None:
        self.total_tokens += metrics.input_tokens + metrics.output_tokens
        if metrics.estimated_cost is not None:
            self.total_cost += metrics.estimated_cost
        self.retries += metrics.retries
        self.check_limits()

    def add_error_retry(self) -> None:
        self.retries += 1
        self.check_limits()


class BoundBackend(AgentBackend):
    def __init__(self, delegate: AgentBackend, tracker: BudgetTracker) -> None:
        self.delegate = delegate
        self.tracker = tracker
        self.last_metrics: UsageMetrics | None = None

    @property
    def provider_name(self) -> str:
        return self.delegate.provider_name

    @property
    def model_id(self) -> str:
        return self.delegate.model_id

    def get_capabilities(self) -> ModelCapabilities:
        return self.delegate.get_capabilities()

    def check_availability(self) -> AvailabilityResult:
        return self.delegate.check_availability()

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        self.tracker.check_limits()
        request_retries = 0
        ceiling = 3 if self.tracker.config.max_retries is None else self.tracker.config.max_retries
        while True:
            try:
                response = self.delegate.generate(request)
                self.tracker.add_metrics(response.metrics)
                self.tracker.check_limits()
                self.last_metrics = response.metrics
                return response
            except ProviderError as e:
                self.tracker.add_error_retry()
                if e.retryable and request_retries < ceiling:
                    request_retries += 1
                    time.sleep(min(e.retry_after or 1.0, 5.0))
                else:
                    raise e


class ArenaEngine:
    """Coordinates defender, attacker, evaluation, adaptation, and audit reporting."""

    def __init__(
        self,
        config: ArenaConfig,
        defender_backend: AgentBackend | None = None,
        attacker_backend: AgentBackend | None = None,
        tracker: BudgetTracker | None = None,
    ) -> None:
        config.validate()
        self.config = config
        self.tracker = tracker or BudgetTracker(config)
        self.defender_rng = random.Random(config.seed)
        self.attacker_rng = random.Random(config.seed + 1)
        self.defender = AdaptiveDefender(
            self.defender_rng,
            backend=defender_backend,
            generator_mode=config.generator_mode,
            generator_version=config.generator_version,
        )
        self.attacker = AdaptiveAttacker(self.attacker_rng, backend=attacker_backend)
        self.completed_rounds: list[RoundResult] = []
        self._experiment_id = __import__("uuid").uuid4().hex
        self.events: list[ArenaEvent] = []

    def _record_event(self, event_type: str, round_id: int | None, payload: dict[str, Any]) -> None:
        event = ArenaEvent(
            event_id=__import__("uuid").uuid4().hex,
            experiment_id=self._experiment_id,
            timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
            application_version=password_arena.__version__,
            schema_version=ARENA_EVENT_SCHEMA_VERSION,
            event_type=event_type,
            round_id=round_id,
            payload=payload,
        )
        self.events.append(event)

    def run(self) -> ExperimentResult:
        from password_arena.providers import ProviderError

        start_index = len(self.completed_rounds)
        if start_index == 0:
            self._record_event(
                "experiment_started",
                None,
                {
                    "config": self.config.to_dict()
                    if hasattr(self.config, "to_dict")
                    else __import__("dataclasses").asdict(self.config)
                },
            )

        for index in range(start_index, self.config.rounds):
            try:
                difficulty = min(
                    10, self.config.start_difficulty + index * self.config.difficulty_step
                )
                password, family, defender_note = self.defender.create_password(difficulty)
                defender_metrics = getattr(self.defender.backend, "last_metrics", None)
                strength = evaluate_strength(password)
                raw_attack = self.attacker.attack(password, difficulty, self.config.max_guesses)
                attacker_metrics = getattr(self.attacker.backend, "last_metrics", None)

                defender_usage = _to_role_usage(defender_metrics)
                attacker_usage = _to_role_usage(attacker_metrics)
                comparable = not (defender_usage and defender_usage.fallback_used) and not (
                    attacker_usage and attacker_usage.fallback_used
                )

                defender_learning = self.defender.observe(family, raw_attack.solved)
                attacker_learning = self.attacker.observe(password, raw_attack.solved)
                display = password if self.config.reveal_passwords else "•" * len(password)
                candidate_display = raw_attack.candidate if self.config.reveal_passwords else None
                attack = replace(raw_attack, candidate=candidate_display)

                if self.tracker:
                    self.tracker.check_limits()

                outcome_val = RoundOutcome.COMPLETED if attack.solved else RoundOutcome.RESISTED
                attack = replace(attack, outcome=outcome_val)

                defender_metadata = RoleMetadata(
                    provider=self.config.defender_config.provider,
                    model=self.config.defender_config.model,
                    thinking_level=self.config.defender_config.thinking_level,
                )
                attacker_metadata = RoleMetadata(
                    provider=self.config.attacker_config.provider,
                    model=self.config.attacker_config.model,
                    thinking_level=self.config.attacker_config.thinking_level,
                )
                evaluator_metadata = RoleMetadata(
                    provider=self.config.evaluator_config.provider,
                    model=self.config.evaluator_config.model,
                    thinking_level=self.config.evaluator_config.thinking_level,
                )

                attacker_note = (
                    (
                        f"Ranked {attack.plan[0].strategy} as the highest-priority strategy "
                        f"for difficulty {difficulty}."
                    )
                    if attack.plan
                    else ""
                )

                policy = CalibrationPolicy()
                calibration_warning = policy.evaluate(password, strength, attack.solved)

                round_res = RoundResult(
                    round_number=index + 1,
                    difficulty=difficulty,
                    password_display=display,
                    password_length=len(password),
                    strength=strength,
                    attack=attack,
                    defender_strategy=family,
                    attacker_note=attacker_note,
                    defender_note=defender_note,
                    defender_learning=defender_learning,
                    attacker_learning=attacker_learning,
                    defender_metadata=defender_metadata,
                    attacker_metadata=attacker_metadata,
                    evaluator_metadata=evaluator_metadata,
                    attacker_usage=attacker_usage,
                    defender_usage=defender_usage,
                    calibration_warning=calibration_warning,
                    comparable=comparable,
                )
                self.completed_rounds.append(round_res)
                self._record_event("round_completed", index + 1, round_res.to_dict())

            except BudgetExhaustedError as e:
                self._record_event(
                    "experiment_interrupted",
                    index + 1,
                    {"reason": e.reason, "state": e.outcome_type.value},
                )
                return ExperimentResult(
                    config=self.config,
                    rounds=tuple(self.completed_rounds),
                    events=tuple(self.events),
                    experiment_id=self._experiment_id,
                    interruption_reason=e.reason,
                    interruption_state=e.outcome_type.value,
                )
            except ProviderError as e:
                self._record_event(
                    "experiment_interrupted", index + 1, {"reason": str(e), "state": e.state.value}
                )
                return ExperimentResult(
                    config=self.config,
                    rounds=tuple(self.completed_rounds),
                    events=tuple(self.events),
                    experiment_id=self._experiment_id,
                    interruption_reason=str(e),
                    interruption_state=e.state.value,
                )

        self._record_event("experiment_completed", None, {})
        return ExperimentResult(
            config=self.config,
            rounds=tuple(self.completed_rounds),
            events=tuple(self.events),
            experiment_id=self._experiment_id,
        )
