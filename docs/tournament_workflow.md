# Multi-Model Tournament Workflow

Password Arena now includes a fully functional Tournament and Benchmark mode. 

## Features
- **Fair Comparisons:** Runs identical difficulty progression, seeds, and token budgets across multiple models.
- **Repeated Trials:** Each matchup executes across a designated number of seeds to build statistical confidence in solve rates.
- **Matrix Orchestration:** Compare `N` attackers versus `M` defenders efficiently.
- **Automatic History Persisting:** Matchup summaries are saved to `.password_arena_tournaments` while full round logs are saved alongside single-experiment history.

## How to use the Tournament Dashboard
1. Run `password-arena --ui` to start the Streamlit application.
2. Navigate to the **Tournament** tab.
3. Select any combination of attacker roles and defender roles (e.g. GPT-4o vs Claude 3.5 Sonnet).
4. Configure standard constraints: rounds per match, trials (seeds), and max guesses.
5. Click **Run Tournament**.

The UI will automatically filter out self-play matches (like GPT-4o defending against GPT-4o) if selected, and execute the complete matchup matrix in sequence.

## Aggregated Results
Once finished, a summary table is generated with:
- `Solve Rate`: The percentage of trials won by the attacker.
- `Mean Guesses`: The average guesses required on solved rounds.
- `Completed Trials`: The number of successful seeds (accounting for any provider interruptions).
- `Status`: If rate limits or timeouts caused a preflight failure, the run is flagged as non-comparable.

All data is automatically serialized to disk for later benchmark reporting.
