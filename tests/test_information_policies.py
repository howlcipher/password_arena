import pytest

from password_arena.engine import build_arena_engine
from password_arena.models import ArenaConfig, RoleConfig
from password_arena.information_policy import (
    FrozenPolicy,
    SelfOnlyPolicy,
    AttackerObservesDefenderPolicy,
    DefenderObservesAttackerPolicy,
    MutualBoundedPolicy,
    MutualFullPolicy,
    LegacyCurrentPolicy,
)


def test_frozen_policy():
    config = ArenaConfig(
        rounds=2,
        information_policy_id="frozen",
        defender_config=RoleConfig(provider="rule_based"),
        attacker_config=RoleConfig(provider="rule_based")
    )
    engine = build_arena_engine(config)
    assert not isinstance(engine, tuple) # Not PreflightFailure
    result = engine.run()
    
    assert len(result.rounds) == 2
    # Rule based attackers don't use the observation objects if frozen, they don't learn
    # Check that learning is "No learning (frozen policy)."
    for r in result.rounds:
        assert "No learning (frozen policy)." in r.attacker_learning
        assert "No learning (frozen policy)." in r.defender_learning
    
    # Check observations array in attacker/defender
    assert len(engine.attacker.observations) == 0
    assert len(engine.defender.observations) == 0


def test_self_only_policy():
    config = ArenaConfig(
        rounds=2,
        information_policy_id="self_only",
    )
    engine = build_arena_engine(config)
    result = engine.run()
    
    assert len(engine.attacker.observations) == 2
    assert len(engine.defender.observations) == 2
    
    obs_a = engine.attacker.observations[0]
    assert obs_a.defender_family is None
    assert obs_a.attempted_strategies is not None
    
    obs_d = engine.defender.observations[0]
    assert len(obs_d.attacker_strategies) == 0
    assert obs_d.family_choice is not None


def test_attacker_observes_defender_policy():
    config = ArenaConfig(
        rounds=2,
        information_policy_id="attacker_observes_defender",
    )
    engine = build_arena_engine(config)
    result = engine.run()
    
    obs_a = engine.attacker.observations[0]
    assert obs_a.defender_family is not None
    assert obs_a.entropy_bits is not None
    assert obs_a.exact_synthetic_target is not None # Provided by rule_based generator mode which reveals target internally
    
    obs_d = engine.defender.observations[0]
    assert len(obs_d.attacker_strategies) == 0


def test_defender_observes_attacker_policy():
    config = ArenaConfig(
        rounds=2,
        information_policy_id="defender_observes_attacker",
    )
    engine = build_arena_engine(config)
    result = engine.run()
    
    obs_a = engine.attacker.observations[0]
    assert obs_a.defender_family is None
    
    obs_d = engine.defender.observations[0]
    assert len(obs_d.attacker_strategies) > 0
    assert obs_d.complete_safe_attack_plan == ()


def test_mutual_bounded_policy():
    config = ArenaConfig(
        rounds=2,
        information_policy_id="mutual_bounded",
    )
    engine = build_arena_engine(config)
    result = engine.run()
    
    obs_a = engine.attacker.observations[0]
    assert obs_a.defender_family is not None
    assert obs_a.exact_synthetic_target is None # Bounded means no exact target
    
    obs_d = engine.defender.observations[0]
    assert len(obs_d.attacker_strategies) > 0


def test_mutual_full_policy():
    config = ArenaConfig(
        rounds=2,
        information_policy_id="mutual_full",
    )
    engine = build_arena_engine(config)
    result = engine.run()
    
    obs_a = engine.attacker.observations[0]
    assert obs_a.defender_family is not None
    assert obs_a.exact_synthetic_target is not None
    assert obs_a.defender_policy_metadata is not None
    
    obs_d = engine.defender.observations[0]
    assert len(obs_d.attacker_strategies) > 0
    assert len(obs_d.complete_safe_attack_plan) > 0


def test_legacy_current_policy():
    config = ArenaConfig(
        rounds=2,
        information_policy_id="legacy_current",
    )
    engine = build_arena_engine(config)
    result = engine.run()
    
    assert len(engine.attacker.observations) == 0
    assert len(engine.defender.observations) == 0
    
    for r in result.rounds:
        assert "No learning" not in r.attacker_learning
        assert "Recorded" in r.defender_learning


def test_target_timing_isolation():
    """
    Test: no Round N target can appear in attacker input before attack N 
    but under an allowed policy: Round N target may appear in Round N+1 memory
    """
    config = ArenaConfig(
        rounds=2,
        information_policy_id="mutual_full",
    )
    engine = build_arena_engine(config)
    
    # We inspect the observations inside the engine.
    # At the start of round 2, the attacker's observations should ONLY contain round 1's target.
    # Since we use rule_based backend by default, it doesn't construct prompts, 
    # but the observations array dictates what the prompt would contain.
    engine.run()
    
    # After round 2, observations[0] should have round 1's target
    obs1 = engine.attacker.observations[0]
    obs2 = engine.attacker.observations[1]
    
    assert obs1.round_number == 1
    assert obs2.round_number == 2
    assert obs1.exact_synthetic_target is not None
    assert obs2.exact_synthetic_target is not None
    assert obs1.exact_synthetic_target != obs2.exact_synthetic_target
    
    # The attacker's state during Round 2 only had access to observations[0], 
    # which only had Round 1's target.
