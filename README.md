# Password Arena

A safe, local adversarial-learning sandbox where a defender creates increasingly difficult **synthetic** passwords and an attacker adapts its bounded guessing strategy across rounds.

> Password Arena is an educational simulation. Never enter real credentials or connect it to a login system.

## Why this project exists

The project explores a practical question:

> Can an attacker agent improve its strategy while a defender agent learns that predictable human-style passwords are weaker than cryptographically secure randomness?

The project includes transparent, rule-based agents to establish a reproducible and trustworthy baseline (when using `deterministic-test` generator mode), alongside support for local and hosted LLM agents.

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

## Benchmark results

> **Methodology Warning:** Results generated under different protocol versions should not be interpreted as directly interchangeable. Protocol and strategy changes are versioned and documented. 
> 
> | Protocol generation | Benchmarks | Key difference |
> |---|---|---|
> | 1.0 | 001-002 | initial bounded benchmark |
> | 1.1 | 003+ | calibration-aware attacker coverage |
> | later extensions | 004+ | information policy / privilege controls |

### Benchmark 001 — Deterministic baseline

* rule vs rule
* 15 comparable rounds
* establishes deterministic baseline

[Read Benchmark 001](results/benchmark-001/README.md)

### Benchmark 002 — Qwen3 4B / Ollama

* first local LLM benchmark
* 3 role configurations
* 45 comparable rounds
* no exclusions
* 0 actual attack solves
* exposed an important calibration finding where weak targets can survive if the bounded attacker lacks the right strategy.

[Read Benchmark 002 Report](results/benchmark-002/README.md) | [Dataset CSV](results/benchmark-002/benchmark-002.csv) | [Dataset JSONL](results/benchmark-002/benchmark-002.jsonl)

### Benchmark 003 — Protocol Versioning & Calibration

* added benchmark protocol version 1.1
* integrated CalibrationPolicy to explicitly flag weak targets
* bounded attacker configuration added exhaustive strategy for lengths 1-3
* 45 comparable rounds
* 0 actual attack solves
* surfaced weak target survival as explicitly flagged calibration warnings rather than presenting misleading LLM success rates.

[Read Benchmark 003 Report](results/benchmark-003/README.md) | [Dataset CSV](results/benchmark-003/benchmark-003.csv) | [Dataset JSONL](results/benchmark-003/benchmark-003.jsonl)

### Benchmark 004, 005, and 006 — Co-Adaptation and Information Policy Matrix

* benchmarked 7 information-sharing policies using `qwen3:4b` locally
* matrix of primary (004), zero-knowledge replication (005), and cross-run accumulated knowledge (006)
* 420 comparable rounds across multiple seeds
* explicitly measured the impact of model context and transparency on adversarial success

#### Research Findings

1. **Does information sharing improve adversarial adaptation?**
   For this local 4B parameter model, information sharing did not lead to any attacker success (0 solves). For the defender, providing more information (mutual sharing) paradoxically reduced overall password entropy gain (from ~106 bits in `frozen` to ~34-36 bits in `mutual` sharing), suggesting the model was overwhelmed or distracted by the additional structured context.

2. **Does self-learning help when neither agent sees the other's detailed behavior?**
   No, the `self_only` policy performed significantly worse for the defender (24.77 bits entropy gain) compared to the `frozen` baseline (106.49 bits), showing that self-observation alone actually degraded generator performance for this specific 4B model.

3. **Does one-way learning favor attacker or defender?**
   One-way learning favored the defender *only* when the attacker received the information (`attacker_observes_defender`), which surprisingly resulted in a higher defender entropy gain (65.0 bits) than when the defender received the attacker's information (`defender_observes_attacker` at 34.29 bits).

4. **Does mutual information sharing create useful co-adaptation?**
   No evidence of useful co-adaptation was found. Mutual sharing policies consumed drastically more tokens (~10k-14k vs ~2k) but produced lower quality passwords and identical (zero) solve rates.

5. **Is full transparency actually better than bounded structured information?**
   Full transparency (`mutual_full`) performed similarly to bounded sharing (`mutual_bounded`) in entropy gain (36.35 vs 34.29) but heavily increased token cost (14.5k vs 10k tokens), showing no meaningful performance benefit over bounded structured information.

6. **If we repeat the exact same experiment from zero knowledge, how reproducible are the results?**
   Results are highly reproducible at a macro level (0.00 solve rates across all policies). However, token usage, latency, and exact generated entropy fluctuate across replications due to token generation variance.

7. **If agents are allowed to carry SAFE knowledge from a completed campaign into a new campaign, how much do they improve?**
   Continuous multi-campaign learning (`benchmark-006`) yielded an average entropy gain of 55.18, which is an improvement over the single-campaign `mutual_bounded` run (34.29). Accumulating safe knowledge over longer time horizons helped the defender model adjust gradually better than in single runs.

8. **How much additional efficiency/entropy is gained by carrying over safe learning?**
   The extended multi-run campaigns consumed roughly 70k tokens to gain ~55 bits of entropy. This is drastically less efficient per-token than the single-run `frozen` baseline (106 bits for ~2.3k tokens), proving that while learning is possible, this small model struggles to leverage historical observations efficiently.

[Read Benchmark 004 Report](results/benchmark-004/benchmark-summary.md) | [Dataset CSV](results/benchmark-004/public-dataset.csv) | [Dataset JSONL](results/benchmark-004/public-dataset.jsonl)
[Read Benchmark 005 Report](results/benchmark-005/benchmark-summary.md) | [Dataset CSV](results/benchmark-005/public-dataset.csv) | [Dataset JSONL](results/benchmark-005/public-dataset.jsonl)
[Read Benchmark 006 Report](results/benchmark-006/benchmark-summary.md) | [Dataset CSV](results/benchmark-006/public-dataset.csv) | [Dataset JSONL](results/benchmark-006/public-dataset.jsonl)

### Benchmark 007 — Privileged Information & Oracle Controls

* normal current-generation control produced measurable solves (13.3%)
* attacker privilege changed solve rate modestly (16.7%)
* defender privilege altered attacker success (6.7%)
* mutual privilege did not improve the attacker (0.0%)
* oracle achieved 100% one-guess solves (oracle != leaderboard result)

[Read Benchmark 007 Report](results/benchmark-007/README.md) | [Dataset CSV](results/benchmark-007/public-dataset.csv) | [Dataset JSONL](results/benchmark-007/public-dataset.jsonl)

## What we have learned so far

In these Qwen3 4B local experiments, the following patterns have emerged:

### 1. Survival alone is misleading
Benchmark 002 showed very weak targets can survive if attacker strategy coverage is incomplete.

### 2. Calibration matters
Benchmark 003 added protocol/calibration controls so weak-target survival is explicitly surfaced.

### 3. More context can hurt
Benchmarks 004–006 showed that `qwen3:4b` often produced lower defender entropy and much higher token usage under self-learning/mutual-context modes than under `frozen`.

### 4. Historical knowledge can help, but inefficiently
Cross-run memory improved some defender behavior but at a large token cost.

### 5. LLM runs drift
Fresh replication preserved some macro outcomes while latency/tokens/entropy varied.

### 6. Information asymmetry matters
Benchmark 007 shows privileged information changes outcomes.

### 7. Oracle controls separate benchmark failure from model failure
The oracle path proves the solve pipeline itself can succeed deterministically when the target is known.


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
