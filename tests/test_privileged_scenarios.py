from unittest.mock import MagicMock

from password_arena.engine import build_arena_engine
from password_arena.models import ArenaConfig
from password_arena.providers import ProviderResponse, UsageMetrics


class MockBackend:
    def __init__(self, provider_name="mock"):
        self.provider_name = provider_name
        self.model_id = "mock"
        self.last_metrics = UsageMetrics(0,0)
        self.last_prompt = ""
    def check_availability(self):
        from password_arena.providers import AvailabilityResult, AvailabilityState
        return AvailabilityResult(AvailabilityState.AVAILABLE)
    def generate(self, req):
        self.last_prompt = req.prompt
        return ProviderResponse(req.prompt, UsageMetrics(0,0), True, {})

def test_attacker_privileged():
    config = ArenaConfig(rounds=1, privilege_mode="attacker_privileged")
    engine = build_arena_engine(config)
    assert not isinstance(engine, tuple)
    engine.attacker.backend = MockBackend("mock-attacker")
    engine.attacker.backend.generate = MagicMock(
        return_value=ProviderResponse(
            "", UsageMetrics(0, 0), True, {"weights": {"common": 1.0}, "reasoning": "test"}
        )
    )
    engine.run()
    
    prompt = engine.attacker.backend.generate.call_args[0][0].prompt
    assert "Privileged information for this round:" in prompt
    assert "defender_family" in prompt

def test_defender_privileged():
    config = ArenaConfig(rounds=1, privilege_mode="defender_privileged")
    engine = build_arena_engine(config)
    assert not isinstance(engine, tuple)
    
    engine.defender.backend = MockBackend("mock-defender")
    engine.defender.backend.generate = MagicMock(
        return_value=ProviderResponse(
            "", UsageMetrics(0, 0), True, {"family": "common", "note": "test"}
        )
    )
    engine.run()
    
    prompt = engine.defender.backend.generate.call_args[0][0].prompt
    assert "Privileged information for this round:" in prompt
    assert "attacker_plan" in prompt

def test_attacker_oracle():
    config = ArenaConfig(rounds=1, privilege_mode="attacker_oracle")
    engine = build_arena_engine(config)
    assert not isinstance(engine, tuple)
    res = engine.run()
    
    r = res.rounds[0]
    assert r.attack.solved
    assert r.attack.guesses_used == 1
    assert r.attack.winning_strategy == "oracle"

def test_boundary_challenge():
    config = ArenaConfig(rounds=1, privilege_mode="information_boundary_challenge")
    engine = build_arena_engine(config)
    assert not isinstance(engine, tuple)
    
    engine.attacker.backend = MockBackend("mock-attacker")
    engine.attacker.backend.generate = MagicMock(
        return_value=ProviderResponse(
            "",
            UsageMetrics(0, 0),
            True,
            {
                "weights": {"common": 1.0},
                "reasoning": "test",
                "information_requests": ["exact target"],
            },
        )
    )
    
    engine.defender.backend = MockBackend("mock-defender")
    engine.defender.backend.generate = MagicMock(
        return_value=ProviderResponse(
            "",
            UsageMetrics(0, 0),
            True,
            {
                "family": "eval-word",
                "note": "test",
                "information_requests": ["attacker plan"],
            },
        )
    )
    
    res = engine.run()
    
    r = res.rounds[0]
    assert r.forbidden_requests_attempted == 2
    assert r.forbidden_requests_denied == 2
    assert "information unavailable" in r.attacker_boundary_responses[0]
    assert "information unavailable" in r.defender_boundary_responses[0]

def test_normal_control():
    config = ArenaConfig(rounds=1, privilege_mode="normal_control")
    engine = build_arena_engine(config)
    assert not isinstance(engine, tuple)
    
    engine.attacker.backend = MockBackend("mock-attacker")
    engine.attacker.backend.generate = MagicMock(
        return_value=ProviderResponse(
            "", UsageMetrics(0, 0), True, {"weights": {"common": 1.0}, "reasoning": "test"}
        )
    )
    engine.run()
    
    prompt = engine.attacker.backend.generate.call_args[0][0].prompt
    assert "Privileged information for this round:" not in prompt
    assert "exact target" not in prompt
