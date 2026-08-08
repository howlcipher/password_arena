# Architecture

Password Arena uses three cooperating roles:

1. **Defender** creates a synthetic password according to the current difficulty and remembers which password families were breached.
2. **Attacker** ranks bounded guessing strategies, receives the previous round outcome, and adjusts future strategy weights.
3. **Evaluator** measures estimated entropy, structural weaknesses, guesses, runtime, and outcome.
4. **Reporter** converts structured runtime events into a two-sided defender/attacker journal and evaluator summary.

`ArenaEngine` coordinates the loop and returns serializable experiment results. `reporting.py` exports the same structured record as a password-safe Markdown experiment journal. The first release is deterministic and rule-based so the project is inexpensive, testable, and reproducible. Future model providers should implement the same role boundaries rather than receiving unrestricted tool access.

## Learning terminology

The MVP performs **adaptation through persisted state**, not model-weight training. A later reinforcement-learning mode may update a trainable policy, but it should be labeled separately so project claims remain accurate.

## Tournament module layout

Tournament Mode follows the same role boundaries, split so core statistics never
depend on Streamlit:

- `models.py` -- tournament data models (`MatchupConfig`, `MatchupSummary`,
  `MatchupResult`, `TournamentConfig`, `RoleUsage`, `ExclusionRecord`,
  `EfficiencyMetrics`, `ReplayMetadata`).
- `tournament.py` -- orchestration (`run_matchup`, `build_tournament_matrix`) and
  aggregation (`aggregate_matchup`, `compute_efficiency`, `calculate_confidence_interval`,
  `replay_matchup`). Each trial is executed through the same `build_arena_engine`
  path used by single-experiment runs -- no duplicated engine logic.
- `tournament_history.py` -- persistence (`TournamentHistoryManager`: save/list/
  load/delete), schema versioning, and linking back to full experiments stored in
  `history.py`'s `HistoryManager`.
- `reporting.py` -- serialization, including the tournament-level JSON/Markdown/CSV
  exports, alongside the existing single-experiment exports.
- `tournament_dashboard.py` -- Streamlit presentation only. It sources every
  number it displays from `tournament.py`/`tournament_history.py`/`reporting.py`
  and computes no statistics itself.
