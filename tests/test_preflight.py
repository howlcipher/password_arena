import pytest

from password_arena.models import RoleConfig
from password_arena.preflight import (
    RolePreflightStatus,
    all_available,
    check_role_availability,
    check_roles_availability,
    compute_role_fingerprint,
    is_rule_based_only,
)
from password_arena.providers import AvailabilityResult, AvailabilityState, ThinkingLevel


def test_compute_role_fingerprint_stable_and_order_independent() -> None:
    a = RoleConfig(provider="openai", model="gpt-4o", thinking_level=ThinkingLevel.HIGH)
    b = RoleConfig(provider="anthropic", model="claude", thinking_level=ThinkingLevel.AUTO)
    assert compute_role_fingerprint([a, b]) == compute_role_fingerprint([b, a])


def test_compute_role_fingerprint_changes_on_any_field_change() -> None:
    base = RoleConfig(provider="openai", model="gpt-4o", thinking_level=ThinkingLevel.HIGH)
    diff_model = RoleConfig(
        provider="openai", model="gpt-4o-mini", thinking_level=ThinkingLevel.HIGH
    )
    diff_thinking = RoleConfig(provider="openai", model="gpt-4o", thinking_level=ThinkingLevel.LOW)

    fp = compute_role_fingerprint([base])
    assert fp != compute_role_fingerprint([diff_model])
    assert fp != compute_role_fingerprint([diff_thinking])


def test_is_rule_based_only() -> None:
    both_rule_based = [RoleConfig(provider="rule_based"), RoleConfig(provider="rule_based")]
    assert is_rule_based_only(both_rule_based)
    assert not is_rule_based_only(
        [RoleConfig(provider="rule_based"), RoleConfig(provider="openai", model="gpt-4o")]
    )


def test_check_role_availability_rule_based_is_always_available() -> None:
    status = check_role_availability(RoleConfig(provider="rule_based"))
    assert status.is_available
    assert status.status == "AVAILABLE"


def test_check_role_availability_mock_provider_default_available() -> None:
    status = check_role_availability(RoleConfig(provider="mock"))
    assert status.is_available


def test_check_role_availability_reports_offline_state(monkeypatch: pytest.MonkeyPatch) -> None:
    class _OfflineBackend:
        def check_availability(self) -> AvailabilityResult:
            return AvailabilityResult(
                state=AvailabilityState.LOCAL_SERVER_OFFLINE, message="server is down"
            )

    monkeypatch.setattr(
        "password_arena.preflight.ProviderRegistry.create", lambda *a, **k: _OfflineBackend()
    )
    status = check_role_availability(RoleConfig(provider="ollama", model="llama3"))
    assert not status.is_available
    assert status.status == "LOCAL_SERVER_OFFLINE"
    assert status.message == "server is down"


def test_check_role_availability_wraps_exceptions_as_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*a: object, **k: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("password_arena.preflight.ProviderRegistry.create", _raise)
    status = check_role_availability(RoleConfig(provider="openai", model="gpt-4o"))
    assert status.status == "ERROR"
    assert "boom" in status.message


def test_check_roles_availability_dedups_identical_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    class _Backend:
        def check_availability(self) -> AvailabilityResult:
            calls.append(1)
            return AvailabilityResult(state=AvailabilityState.AVAILABLE, message="ok")

    monkeypatch.setattr(
        "password_arena.preflight.ProviderRegistry.create", lambda *a, **k: _Backend()
    )
    same = RoleConfig(provider="openai", model="gpt-4o", thinking_level=ThinkingLevel.AUTO)
    statuses = check_roles_availability([same, same, same])
    assert len(statuses) == 1
    assert len(calls) == 1


def test_all_available() -> None:
    ok = RolePreflightStatus("openai", "gpt-4o", "auto", "AVAILABLE", "")
    bad = RolePreflightStatus("ollama", "llama3", "auto", "LOCAL_SERVER_OFFLINE", "offline")
    assert all_available([ok])
    assert not all_available([ok, bad])
    assert all_available([])
