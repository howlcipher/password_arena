# Password Arena

A safe, local adversarial-learning sandbox where a defender creates increasingly difficult **synthetic** passwords and an attacker adapts its bounded guessing strategy across rounds.

> Password Arena is an educational simulation. Never enter real credentials or connect it to a login system.

## Why this project exists

The project explores a practical question:

> Can an attacker agent improve its strategy while a defender agent learns that predictable human-style passwords are weaker than cryptographically secure randomness?

The MVP deliberately uses transparent, rule-based agents. That makes the experiment reproducible (when using `deterministic-test` generator mode) and establishes a trustworthy baseline before optional LLM or reinforcement-learning agents are added.

## What it measures

- Estimated entropy and structural penalties
- Attacker success rate
- Guesses used per round
- Runtime per attack
- Attacker strategy selection
- Defender password-family progression
- Defender entropy change per recorded model token for complete comparable tournament trials
- Agent observations across rounds
- Two-sided audit reports showing defender decisions, attacker budget allocation, outcomes, and learning updates

## Current architecture

- **Adaptive defender:** escalates from dictionary words to passphrases and finally CSPRNG-generated passwords.
- **Adaptive attacker:** ranks common-password, mutation, passphrase, and bounded-random strategies using prior synthetic results.
- **Multi-Model Support:** Configure AI-vs-AI matchups using Gemini, OpenAI, Anthropic, Ollama, and Rule-Based agents. Thinking-level choices are restricted to what the selected model's own capability registry accepts, not shown unconditionally.
- **Optional Hugging Face discovery:** Search public model metadata only after an
  explicit button click. A discovered model ID is copied into manual input; it is
  not registered as an execution provider and is never downloaded or run.
- **Tournament Engine:** Build robust multi-model evaluation matrices, run repeated trials, and enforce budget constraints (cost, time, tokens). Provider availability is checked only on an explicit "Test connections" click, cached until the configuration changes -- never on every widget interaction.
- **Evaluator:** calculates strength indicators and captures experiment metrics.
- **Dashboard:** visualizes learning curves, generates weighted leaderboards, plots per-role efficiency (including defender entropy gain per 1K tokens when measured), filters results by role/provider/model/thinking-level/comparability, compares saved execution versions, exports experiment and tournament JSON/Markdown/CSV, and creates fail-closed public benchmark JSONL/CSV files plus a Dataset Card.

The MVP performs persistent-state adaptation; it does not claim to retrain model weights.

## Quick start

Requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[all]"
```

The core package has no required third-party dependencies. Install only the
features you need:

```bash
pip install -e "."                  # Offline rule-based CLI
pip install -e ".[dashboard]"       # Dashboard without Hub discovery
pip install -e ".[dashboard,hf]"    # Dashboard with Hub catalog search
```

`HF_TOKEN` is optional. It is read only when **Search Hugging Face** is clicked.
When absent, discovery explicitly disables use of any machine-persisted Hub login.
Discovery calls only the model-listing API. Password Arena never downloads model
weights, performs Hub inference, uploads a dataset, or adds a Hugging Face execution
provider.

Run the CLI:

```bash
password-arena --rounds 8 --max-guesses 5000 \
  --output results/run.json \
  --report results/run.md
```

Launch the dashboard (Arena and Tournament modes):

```bash
streamlit run src/password_arena/dashboard.py
```

Or run the dashboard with Docker:

```bash
docker build -t password-arena .
docker run --rm -p 8501:8501 password-arena
```

Run quality checks:

```bash
ruff check .
mypy src/password_arena
pytest
```

## Example experiment flow

1. The defender generates a synthetic password for the current difficulty.
2. The evaluator records strength characteristics.
3. The attacker spends a fixed guess budget across ranked strategies.
4. Both agents observe the synthetic result and update local state.
5. The evaluator creates a factual two-sided arena report from the recorded actions.
6. Difficulty increases and the next round begins.

Tournament results also offer an explicit public benchmark boundary. JSONL and CSV
contain one scalar, allowlisted row per recorded round, including recorded excluded
rounds. Dataset generation never exports passwords, candidates, prompts, notes,
events, model prose, or reasoning content. Saved tournaments require every linked
experiment to be present before public downloads are enabled.

## Two-sided arena journal

Every round documents the experiment from three views:

- **Defender:** selected password family, concrete actions, observed outcome, and state update.
- **Attacker:** ranked strategy, exact bounded guess allocation, attempted strategies, and adaptation.
- **Evaluator:** measured result and a security lesson grounded in the round metrics.

The journal is an audit log, not a request for private model chain-of-thought. Passwords and matched candidates remain redacted unless `reveal_passwords` is explicitly enabled. Export it from the dashboard or with `--report results/run.md`.

## Configuration

| Setting | Purpose | Default |
|---|---|---:|
| `rounds` | Number of attacker-versus-defender rounds | 8 |
| `start_difficulty` | Initial defender level from 1–10 | 1 |
| `difficulty_step` | Increase after each round | 1 |
| `max_guesses` | Hard attack budget per round | 5,000 |
| `seed` | Reproducible baseline behavior | 42 |
| `reveal_passwords` | Display synthetic passwords | false |
| `generator_mode` | `secure` (CSPRNG) or `deterministic-test` (PRNG) | `secure` |

## Project planning

- [blueprint.md](blueprint.md) defines the product vision, architecture, safety model, and delivery phases.
- [improvements.md](improvements.md) is the prioritized feature and engineering backlog.
- [bugs.md](bugs.md) tracks confirmed defects, reproduction steps, and acceptance criteria.
- [AGENTS.md](AGENTS.md) defines the workflow coding agents must follow when changing the repository.
- [docs/MODEL_PROVIDERS.md](docs/MODEL_PROVIDERS.md) specifies planned OpenAI, Anthropic, Gemini, Ollama/local, thinking-level, and availability behavior.
- [docs/DATASET_EXPORT.md](docs/DATASET_EXPORT.md) defines the public benchmark
  schema, null semantics, fail-closed validation, Dataset Card, and no-upload policy.

## Safety boundaries

- Synthetic passwords only
- Local comparisons only
- No login endpoints or credential datasets
- Bounded guess budgets
- Passwords hidden by default
- Cryptographically secure generation at high defender levels

See [SECURITY.md](SECURITY.md) for the full policy, [docs/REPORTING.md](docs/REPORTING.md) for journal semantics, [docs/MODEL_PROVIDERS.md](docs/MODEL_PROVIDERS.md) for multi-model design, [docs/DATASET_EXPORT.md](docs/DATASET_EXPORT.md) for public-export guarantees, and [docs/ROADMAP.md](docs/ROADMAP.md) for planned delivery phases.
