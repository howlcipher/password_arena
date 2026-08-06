# Roadmap

## 0.1 — Safe simulation MVP

- Rule-based attacker and defender agents
- Configurable rounds, difficulty, and guess budget
- CLI, Streamlit dashboard, JSON export
- Strength, runtime, strategy, and success metrics
- Side-by-side defender and attacker audit journal
- JSON and Markdown report exports with password redaction

## 0.2 — Multi-model provider arena

- Common `AgentBackend` protocol
- Independent model selection for attacker, defender, and evaluator
- Optional OpenAI, Anthropic, Gemini, Ollama, and OpenAI-compatible local adapters
- Capability-aware normalized thinking levels
- Token, latency, retry, availability, and API-cost accounting
- Pause and resume when a model is unavailable
- No silent fallback between models
- Structured model output validation
- No model receives network or authentication tools

## 0.3 — Better adversarial evaluation

- Markov and probabilistic context-free grammar strategies
- Holdout password-pattern generator
- Strategy ablation experiments
- Repeated seeded runs with confidence intervals

## 0.4 — Genuine learning mode

- Small reinforcement-learning policy for strategy selection
- Separate training and evaluation sets
- Checkpoint comparison and regression tests
- Clear distinction between contextual adaptation and weight updates
