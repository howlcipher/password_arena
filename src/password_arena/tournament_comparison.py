"""Comparability checks for tournament configurations and saved tournament runs.

`compare_tournament_configs` deliberately owns only fields on
`TournamentConfig`. Saved history has a second comparability layer:
`ReplayMetadata` is persisted per `StoredMatchup` as of tournament-history
schema 2.1, so `compare_stored_tournaments` compares the set of recorded
execution versions across every matchup. It never chooses the first matchup's
metadata. Older history without replay metadata is reported as unavailable,
not assumed to match a newer or another old tournament.
"""

from __future__ import annotations

from dataclasses import dataclass

from password_arena.models import RoleConfig, TournamentConfig
from password_arena.tournament_history import StoredTournament


@dataclass(frozen=True, slots=True)
class ConfigComparison:
    """Comparison result for values that belong to `TournamentConfig` alone."""

    identical: bool
    differences: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StoredTournamentComparison:
    """Complete saved-tournament comparability result.

    `metadata_differences` includes unavailable and mixed replay metadata as
    comparability concerns even when the known version sets happen to overlap.
    Consequently `identical` means both configuration and execution metadata
    are fully known, homogeneous within each tournament, and equal between
    tournaments.
    """

    configuration: ConfigComparison
    metadata_differences: tuple[str, ...]

    @property
    def configuration_identical(self) -> bool:
        return self.configuration.identical

    @property
    def execution_metadata_identical(self) -> bool:
        return not self.metadata_differences

    @property
    def identical(self) -> bool:
        return self.configuration_identical and self.execution_metadata_identical

    @property
    def differences(self) -> tuple[str, ...]:
        return self.configuration.differences + self.metadata_differences


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
    """Compare every `TournamentConfig` field affecting benchmark conditions.

    Seed sets are compared as sets because trial order does not alter aggregate
    comparability; all other configuration values are compared exactly.
    Execution versions intentionally do not belong here. Use
    `compare_stored_tournaments` when saved matchup replay metadata is present.
    """
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


def _recorded_versions(tournament: StoredTournament, attribute: str) -> tuple[tuple[str, ...], int]:
    """Return non-empty replay values and the count unavailable for one field."""
    if not tournament.matchups:
        # No matchup means no recorded execution metadata. Treat it exactly as
        # unavailable rather than allowing two empty version sets to look equal.
        return (), 1

    versions: set[str] = set()
    unavailable = 0
    for matchup in tournament.matchups:
        replay = matchup.replay
        value = getattr(replay, attribute) if replay is not None else None
        if not value:
            unavailable += 1
        else:
            versions.add(value)
    return tuple(sorted(versions)), unavailable


def _version_display(versions: tuple[str, ...], unavailable: int) -> str:
    if not versions:
        return "version metadata unavailable"
    display = "{" + ", ".join(versions) + "}"
    if unavailable:
        return f"{display}; version metadata unavailable for {unavailable} matchup(s)"
    return display


def _compare_replay_versions(a: StoredTournament, b: StoredTournament) -> tuple[str, ...]:
    metadata_differences: list[str] = []
    fields = (
        ("Application version", "application_version"),
        ("Experiment/schema version", "schema_version"),
        ("Attacker prompt version", "attacker_prompt_version"),
        ("Defender prompt version", "defender_prompt_version"),
        ("Capability-registry version", "capability_registry_version"),
        ("Benchmark protocol version", "benchmark_protocol_version"),
    )
    for label, attribute in fields:
        versions_a, unavailable_a = _recorded_versions(a, attribute)
        versions_b, unavailable_b = _recorded_versions(b, attribute)
        display_a = _version_display(versions_a, unavailable_a)
        display_b = _version_display(versions_b, unavailable_b)
        if unavailable_a or unavailable_b:
            metadata_differences.append(
                f"{label}: A = {display_a}; B = {display_b} "
                "(version metadata unavailable; direct comparability cannot be established)"
            )
        elif len(versions_a) > 1 or len(versions_b) > 1:
            metadata_differences.append(
                f"{label}: A = {display_a}; B = {display_b} "
                "(mixed version metadata within a tournament)"
            )
        elif versions_a != versions_b:
            metadata_differences.append(f"{label}: A = {display_a}; B = {display_b}")

    if a.schema_version != b.schema_version:
        metadata_differences.append(
            f"Tournament history schema version: A = {a.schema_version!r}; B = {b.schema_version!r}"
        )
    return tuple(metadata_differences)


def compare_stored_tournaments(
    a: StoredTournament, b: StoredTournament
) -> StoredTournamentComparison:
    """Compare saved benchmarks' configuration and every persisted replay version.

    Each execution field is derived as a set over all matchups in each saved
    tournament. Missing replay metadata remains an explicit unavailable state,
    preserving compatibility with pre-2.1 history while preventing an
    unsupported claim that old runs used the same code or prompts.
    """
    configuration = compare_tournament_configs(a.config, b.config)
    return StoredTournamentComparison(
        configuration=configuration,
        metadata_differences=_compare_replay_versions(a, b),
    )
