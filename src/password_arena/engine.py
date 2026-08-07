from __future__ import annotations

import random
import time
from dataclasses import replace
from typing import NamedTuple

from password_arena.attacker import AdaptiveAttacker
from password_arena.defender import AdaptiveDefender
from password_arena.models import (
    AgentReport,
    ArenaConfig,
    ExperimentResult,
    RoleMetadata,
    RoundOutcome,
    RoundReport,
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
        retries = 0
        while True:
            try:
                response = self.delegate.generate(request)
                self.tracker.add_metrics(response.metrics)
                self.tracker.check_limits()
                return response
            except ProviderError as e:
                self.tracker.add_error_retry()
                self.tracker.check_limits()
                if e.retryable:
                    retries += 1
                    time.sleep(min(e.retry_after or 1, 5))
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

    def run(self) -> ExperimentResult:
        from password_arena.providers import ProviderError
        
        start_index = len(self.completed_rounds)
        for index in range(start_index, self.config.rounds):
            try:
                difficulty = min(
                    10, self.config.start_difficulty + index * self.config.difficulty_step
                )
                password, family, defender_note = self.defender.create_password(difficulty)
                strength = evaluate_strength(password)
                raw_attack = self.attacker.attack(password, difficulty, self.config.max_guesses)

                defender_learning = self.defender.observe(family, raw_attack.solved)
                attacker_learning = self.attacker.observe(password, raw_attack.solved)
                display = password if self.config.reveal_passwords else "•" * len(password)
                candidate_display = raw_attack.candidate if self.config.reveal_passwords else None
                attack = replace(raw_attack, candidate=candidate_display)

                if self.tracker:
                    self.tracker.check_limits()
                
                outcome_val = RoundOutcome.COMPLETED if attack.solved else RoundOutcome.RESISTED
                attack = replace(attack, outcome=outcome_val)

                outcome = "solved" if attack.solved else "resisted the bounded guess budget"
                findings = "; ".join(strength.findings)
                attack_actions = tuple(
                f"Allocated {entry.guess_budget:,} guesses to {entry.strategy} "
                f"({entry.weight:.1%} of the plan)."
                for entry in attack.plan
                )
                report = RoundReport(
                defender=AgentReport(
                decision=defender_note,
                actions=(
                f"Generated a synthetic {family} password.",
                f"Set length to {len(password)} characters.",
                ),
                observation=f"The password {outcome}. Evaluator findings: {findings}.",
                learning_update=defender_learning,
                ),
                attacker=AgentReport(
                decision=(
                f"Ranked {attack.plan[0].strategy} as the highest-priority strategy "
                f"for difficulty {difficulty}."
                ),
                actions=attack_actions,
                observation=(
                f"{'Found a match' if attack.solved else 'Found no match'} after "
                f"{attack.guesses_used:,} guesses; attempted "
                f"{', '.join(attack.attempted_strategies)}."
                ),
                learning_update=attacker_learning,
                ),
                evaluator_summary=(
                f"Round {index + 1} {outcome}. Strength score was {strength.score}/4 with "
                f"an estimated {strength.entropy_bits:.2f} bits after structural penalties."
                ),
                security_lesson=self._security_lesson(family, attack.solved),
                defender_metadata=RoleMetadata(
                provider=self.config.defender_config.provider,
                model=self.config.defender_config.model,
                thinking_level=self.config.defender_config.thinking_level,
                ),
                attacker_metadata=RoleMetadata(
                provider=self.config.attacker_config.provider,
                model=self.config.attacker_config.model,
                thinking_level=self.config.attacker_config.thinking_level,
                ),
                evaluator_metadata=RoleMetadata(
                provider=self.config.evaluator_config.provider,
                model=self.config.evaluator_config.model,
                thinking_level=self.config.evaluator_config.thinking_level,
                ),
                )

                self.completed_rounds.append(
                    RoundResult(
                        round_number=index + 1,
                        difficulty=difficulty,
                        password_display=display,
                        password_length=len(password),
                        strength=strength,
                        attack=attack,
                        defender_strategy=family,
                        attacker_note=attacker_learning,
                        defender_note=defender_note,
                        report=report,
                    )
                )

            except BudgetExhaustedError as e:
                return ExperimentResult(
                    config=self.config,
                    rounds=tuple(self.completed_rounds),
                    experiment_id=self._experiment_id,
                    interruption_reason=e.reason,
                    interruption_state=e.outcome_type.value,
                )
            except ProviderError as e:
                return ExperimentResult(
                    config=self.config,
                    rounds=tuple(self.completed_rounds),
                    experiment_id=self._experiment_id,
                    interruption_reason=str(e),
                    interruption_state=e.state.value,
                )

        return ExperimentResult(
            config=self.config, 
            rounds=tuple(self.completed_rounds),
            experiment_id=self._experiment_id,
        )

    @staticmethod
    def _security_lesson(family: str, solved: bool) -> str:
        if solved:
            return (
                f"The {family} structure remained predictable inside the current attack model; "
                "cosmetic complexity should not be treated as randomness."
            )
        if family == "cryptographic-random":
            return (
                "Cryptographically secure randomness removed the human patterns targeted by the "
                "bounded attacker; password-manager generation is the safer real-world endpoint."
            )
        return (
            "This structure survived this bounded experiment, but that is not proof of real-world "
            "security against larger or different attack models."
        )
