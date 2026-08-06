# Arena reporting

Password Arena records a factual, two-sided journal for every synthetic round.

## Defender record

- Password family selected
- Difficulty and generated length
- Whether the family had been breached previously
- Evaluator findings
- State update applied after the outcome

## Attacker record

- Ranked strategy order
- Exact bounded guess allocation per strategy
- Strategies actually attempted
- Guesses consumed and runtime
- State update applied after the outcome

## Evaluator record

- Solved or resisted result
- Strength score and estimated entropy
- A scoped security lesson

The report is assembled from structured runtime events. It does not request or expose private model chain-of-thought. Synthetic passwords and matched candidates are hidden unless the operator explicitly enables `reveal_passwords`.

The training baseline reveals the synthetic password to both learning components only after the round is complete so they can update local state. This post-round reveal is part of the controlled simulation and is not intended to model access to real credentials.
