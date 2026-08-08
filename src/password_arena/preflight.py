"""Provider availability checking, separated from when it's safe to call.

`compute_role_fingerprint` is pure and cheap (no I/O) -- safe to call on
every Streamlit rerun to detect whether a cached preflight result is stale.
`check_role_availability`/`check_roles_availability` perform real network
I/O (`AgentBackend.check_availability()`) and must only be invoked from an
explicit user action (a "Test connections" button), never automatically on
a widget change or tab redraw -- see `dashboard.py`/`tournament_dashboard.py`
for the session-state caching that enforces this.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from password_arena.models import RoleConfig
from password_arena.providers import AvailabilityState, ProviderRegistry


def compute_role_fingerprint(roles: Sequence[RoleConfig]) -> str:
    """Deterministic fingerprint of a set of roles' provider/model/thinking
    level. No network I/O. A cached preflight result is stale whenever this
    fingerprint no longer matches the one it was computed against."""
    parts = sorted(f"{r.provider}:{r.model or ''}:{r.thinking_level.value}" for r in roles)
    return "|".join(parts)


def is_rule_based_only(roles: Sequence[RoleConfig]) -> bool:
    """rule_based roles are always immediately available -- no network check
    is ever needed or performed for them."""
    return all(r.provider == "rule_based" for r in roles)


@dataclass(frozen=True, slots=True)
class RolePreflightStatus:
    provider: str
    model: str
    thinking: str
    status: str
    message: str

    @property
    def is_available(self) -> bool:
        return self.status == "AVAILABLE"


def check_role_availability(role: RoleConfig) -> RolePreflightStatus:
    """Check one role's provider availability. This performs real network
    I/O for non-rule_based providers -- call only from an explicit user
    action, never automatically."""
    provider = role.provider
    model = role.model or "default"
    thinking = role.thinking_level.value

    if provider == "rule_based":
        return RolePreflightStatus(provider, model, thinking, "AVAILABLE", "")

    try:
        backend = ProviderRegistry.create(role)
        if backend is None:
            return RolePreflightStatus(provider, model, thinking, "AVAILABLE", "")
        avail = backend.check_availability()
        status = avail.state.value.upper()
        message = "" if avail.state == AvailabilityState.AVAILABLE else avail.message
        return RolePreflightStatus(provider, model, thinking, status, message)
    except Exception as e:
        return RolePreflightStatus(provider, model, thinking, "ERROR", str(e))


def check_roles_availability(roles: Sequence[RoleConfig]) -> list[RolePreflightStatus]:
    """One status per unique (provider, model, thinking level) role, in
    first-seen order. Duplicate role configs (e.g. the same model used as
    both attacker and defender) are checked only once."""
    seen: dict[str, RoleConfig] = {}
    for r in roles:
        key = f"{r.provider}:{r.model}:{r.thinking_level.value}"
        seen.setdefault(key, r)
    return [check_role_availability(r) for r in seen.values()]


def all_available(statuses: Sequence[RolePreflightStatus]) -> bool:
    return all(s.is_available for s in statuses)
