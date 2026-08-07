from password_arena.models import RoleConfig, TournamentConfig
from password_arena.tournament import (
    build_tournament_matrix,
    calculate_confidence_interval,
    run_matchup,
)


def test_build_tournament_matrix() -> None:
    r1 = RoleConfig(provider="rule_based")
    r2 = RoleConfig(provider="openai", model="gpt-4o")

    config = TournamentConfig(
        attackers=(r1, r2),
        defenders=(r1, r2),
        seeds=(42, 43),
        rounds_per_match=3,
    )

    matchups = build_tournament_matrix(config, exclude_self=False)
    assert len(matchups) == 4
    assert matchups[0].attacker == r1 and matchups[0].defender == r1

    matchups_no_self = build_tournament_matrix(config, exclude_self=True)
    assert len(matchups_no_self) == 2
    assert matchups_no_self[0].attacker == r1 and matchups_no_self[0].defender == r2


def test_run_matchup() -> None:
    r1 = RoleConfig(provider="rule_based")
    config = TournamentConfig(
        attackers=(r1,),
        defenders=(r1,),
        seeds=(42, 43),
        rounds_per_match=2,
        max_guesses=100,
    )
    matchups = build_tournament_matrix(config)
    matchup = matchups[0]

    result = run_matchup(matchup)

    assert result.config.seeds == (42, 43)
    assert result.summary.trials == 2
    assert result.summary.completed_trials == 2
    assert result.is_comparable is True
    assert result.summary.interrupted_trials == 0


def test_confidence_interval() -> None:
    ci = calculate_confidence_interval(50, 100)
    assert 0.39 < ci[0] < 0.41
    assert 0.59 < ci[1] < 0.61
