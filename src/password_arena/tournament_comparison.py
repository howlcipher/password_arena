"""Pure structural comparison of two `TournamentConfig`s (IMP-013 audit item).

The Tournament history UI used to decide "directly comparable" by checking
only four scalar fields (rounds_per_match, seeds, max_guesses,
generator_version). That is not enough to justify the claim: differing
provider/model/thinking-level role configurations, differing budgets, or a
differing retry policy all invalidate a head-to-head comparison just as much
as a differing round count does. `compare_tournament_configs` checks every
field that plausibly affects comparability and returns a structured result
instead of a single boolean, so the caller can show exactly what differs
rather than a blanket "not comparable" verdict.

Known gap: prompt version (`ATTACKER_PROMPT_VERSION`/`DEFENDER_PROMPT_VERSION`)
and `CAPABILITY_REGISTRY_VERSION` are NOT compared here, because they are not
part of `TournamentConfig` and are not currently persisted anywhere at the
tournament level -- `ReplayMetadata` (which carries them) is built per-matchup
at run time and `StoredMatchup` does not persist it. Two tournaments run under
different prompt/capability-registry versions could therefore be reported as
"identical" by this function even though they are not truly comparable. This
is a real limitation, not an oversight; closing it requires persisting
`ReplayMetadata` (or at least its version fields) on `StoredMatchup`, which is
out of scope for this function. Tracked as a follow-up (see backlog).
"""

from __future__ import annotations

from dataclasses import dataclass

from password_arena.models import RoleConfig, TournamentConfig


@dataclass(frozen=True, slots=True)
class ConfigComparison:
    identical: bool
    differences: tuple[str, ...]


def _role_signature(role: RoleConfig) -> tuple[str, str | None, str, float | None, int | None]:
    return (role.provider, role.model, role.thinking_level.value, role.temperature, role.max_tokens)


def _compare_role_sets(
    label: str,
    a: tuple[RoleConfig, ...],
    b: tuple[RoleConfig, ...],
    differences: list[str],
) -> None:
    sig_a = {_role_signature(r) for r in a}
    sig_b = {_role_signature(r) for r in b}
    only_a = sig_a - sig_b
    only_b = sig_b - sig_a
    if only_a:
        differences.append(f"{label} only in A: {sorted(only_a)}")
    if only_b:
        differences.append(f"{label} only in B: {sorted(only_b)}")


def compare_tournament_configs(a: TournamentConfig, b: TournamentConfig) -> ConfigComparison:
    """Structured diff of every `TournamentConfig` field that affects whether
    two tournaments' results can be meaningfully compared. Seed sets are
    compared as sets (trial order does not affect aggregate comparability);
    everything else is compared exactly."""
    differences: list[str] = []

    def _cmp(label: str, va: object, vb: object) -> None:
        if va != vb:
            differences.append(f"{label}: {va!r} vs {vb!r}")

    _cmp("generator_version", a.generator_version, b.generator_version)
    _cmp("generator_mode", a.generator_mode, b.generator_mode)
    _cmp("seeds", tuple(sorted(a.seeds)), tuple(sorted(b.seeds)))
    _cmp("rounds_per_match", a.rounds_per_match, b.rounds_per_match)
    _cmp("max_guesses", a.max_guesses, b.max_guesses)
    _cmp("max_tokens", a.max_tokens, b.max_tokens)
    _cmp("max_api_cost", a.max_api_cost, b.max_api_cost)
    _cmp("max_wall_time_s", a.max_wall_time_s, b.max_wall_time_s)
    _cmp("max_retries", a.max_retries, b.max_retries)

    _compare_role_sets("attackers", a.attackers, b.attackers, differences)
    _compare_role_sets("defenders", a.defenders, b.defenders, differences)

    return ConfigComparison(identical=not differences, differences=tuple(differences))
