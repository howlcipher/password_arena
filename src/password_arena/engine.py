from __future__ import annotations

import random
from dataclasses import replace

from password_arena.attacker import AdaptiveAttacker
from password_arena.defender import AdaptiveDefender
from password_arena.models import (
    AgentReport,
    ArenaConfig,
    ExperimentResult,
    RoleMetadata,
    RoundReport,
    RoundResult,
)
from password_arena.strength import evaluate_strength


class ArenaEngine:
    """Coordinates defender, attacker, evaluation, adaptation, and audit reporting."""

    def __init__(self, config: ArenaConfig) -> None:
        config.validate()
        self.config = config
        defender_rng = random.Random(config.seed)
        attacker_rng = random.Random(config.seed + 1)
        self.defender = AdaptiveDefender(defender_rng)
        self.attacker = AdaptiveAttacker(attacker_rng)

    def run(self) -> ExperimentResult:
        results: list[RoundResult] = []

        for index in range(self.config.rounds):
            difficulty = min(10, self.config.start_difficulty + index * self.config.difficulty_step)
            password, family, defender_note = self.defender.create_password(difficulty)
            strength = evaluate_strength(password)
            raw_attack = self.attacker.attack(password, difficulty, self.config.max_guesses)

            defender_learning = self.defender.observe(family, raw_attack.solved)
            attacker_learning = self.attacker.observe(password, raw_attack.solved)
            display = password if self.config.reveal_passwords else "•" * len(password)
            candidate_display = raw_attack.candidate if self.config.reveal_passwords else None
            attack = replace(raw_attack, candidate=candidate_display)

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

            results.append(
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

        return ExperimentResult(config=self.config, rounds=tuple(results))

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
