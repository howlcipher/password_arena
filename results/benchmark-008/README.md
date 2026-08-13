# Benchmark 008 — Cross-Model Generalization: Qwen3 4B vs Gemma 3 4B

Are Password Arena's context-overload, information-sharing, and privilege effects
properties of Qwen3 4B specifically, or do they appear in another small local model
family? Benchmarks 001-007 used only `qwen3:4b`. This benchmark introduces a second,
architecturally unrelated 4B local model (`gemma3:4b`, Google's Gemma 3 family) and
re-runs the same compact six-scenario matrix for both models under identical
current-generation code, protocol, seeds, and budgets, so the comparison is clean —
not a reuse of older Qwen numbers gathered under earlier protocol versions.

## Environment

- **Runtime:** Ollama 0.32.9, local, dedicated `ollama-arena` container.
- **Resource ceiling:** 10 GiB memory / 11 GiB memory+swap / 4 CPUs (container cgroup
  limits, confirmed via `podman inspect` before and during the run). Context: 4096
  tokens. One model loaded at a time; one request in flight at a time. No distributed
  execution, no external network calls from either agent role.
- **Compute backend — correction to prior "CPU-only" framing:** inspecting the
  container during this benchmark's setup showed it is running `--privileged`, which
  exposes the host's `/dev/dri` render nodes. Ollama's own log confirms both
  `gemma3:4b` and `qwen3:4b` are loaded via the **Vulkan GPU backend** against the
  host's AMD Radeon RX 580 (RADV POLARIS10), offloading all model layers to the GPU.
  This was discovered mid-benchmark, not configured for this run. It means the
  "CPU-only" / "CPU limits applied" framing in Benchmarks 002-007 was very likely
  also describing GPU-accelerated (Vulkan) runs, since the same container has run
  Vulkan-backed inference since its first `qwen3:4b` pull. Those historical reports
  are not being rewritten (see repo history policy in `AGENTS.md`); this is a
  forward-looking correction. The memory/swap/CPU cgroup ceilings above remained
  accurate and enforced throughout — model weights live in GPU VRAM, not container
  RAM, so the container's own RAM usage stayed under 1% of its 10 GiB ceiling for
  the entire benchmark.

## Models

| | Qwen3 4B | Gemma 3 4B |
|---|---|---|
| Ollama tag | `qwen3:4b` | `gemma3:4b` |
| Digest | `359d7dd4bcda...` | `a2af6cc3eb7f...` |
| Parameters | 4.0B | 4.3B |
| Quantization | Q4_K_M | Q4_K_M |
| Size on disk | ~2.5 GB | ~3.3 GB |
| Native context length | 262144 | 131072 |
| Ollama capability tags | completion, tools, thinking | completion, vision |

Both models were run with identical `RoleConfig(provider="ollama", model=<tag>)` —
no model-specific code path exists anywhere in the benchmark or provider layer.
Neither tag advertises Ollama's "tools" capability the same way; Gemma additionally
lacks a "thinking" tag. This did not block qualification: Password Arena's
structured-output path uses Ollama's grammar-constrained `format` JSON-schema
parameter, which is independent of the tool-calling capability tag.

## Qualification gate

Before benchmarking, `gemma3:4b` was run through 20 real structured-output calls
(2 mini-experiments x 5 rounds x 2 roles) using the actual attacker
strategy-allocation and defender family-selection code paths — not a reimplemented
schema. Result: **20/20 schema-valid (100%)**, mean latency 7.9s, mean input tokens
143, mean output tokens 90. No fallback model was needed.

## Experimental controls

- Same code, same protocol generation, same prompts, same information-policy and
  privilege-mode implementations as Benchmarks 004-007.
- Seeds: `42, 43, 44`. Rounds per match: `5`. Guess budget: `500`. Generator:
  `deterministic-test` / `benchmark`.
- Each (model, scenario, seed) combination starts from fresh application state — no
  memory carried across models, scenarios, or seeds.
- 2 models x 6 scenarios x 3 seeds x 5 rounds = **180 requested rounds**
  (90 per model), plus an optional 30-round cross-model pilot.

## Scenarios

- **frozen** — no accumulated context between rounds (`information_policy=frozen`).
- **mutual_bounded** — bounded cross-agent information sharing.
- **mutual_full** — unbounded cross-agent information sharing, including the exact
  synthetic target and defender policy metadata.
- **normal_control** — current-generation privilege baseline (`legacy_current`
  information policy, `normal_control` privilege).
- **attacker_privileged** — attacker receives permitted defender metadata.
- **defender_privileged** — defender receives the precommitted attacker strategy.

## Results summary

_Updated 2026-08-13 from a full re-run of this matrix under identical code,
protocol, seeds, and budgets — see "Reproducibility check" below for what changed
and what held._

| Scenario | Qwen rounds | Qwen solve % | Qwen mean entropy | Gemma rounds | Gemma solve % | Gemma mean entropy |
|---|---|---|---|---|---|---|
| frozen | 15/15 | 0.0 | 81.2 | 15/15 | 0.0 | 42.1 |
| mutual_bounded | 15/15 | 0.0 | 36.3 | 15/15 | 0.0 | 56.6 |
| mutual_full | 15/15 | 0.0 | 36.3 | 15/15 | **6.7** | 39.9 |
| normal_control | 15/15 | 0.0 | 77.2 | 15/15 | 0.0 | 37.7 |
| attacker_privileged | 14/15 | **7.1** | 77.4 | 15/15 | 0.0 | 42.7 |
| defender_privileged | 15/15 | 0.0 | 92.3 | 15/15 | 0.0 | 37.7 |

"Rounds" is comparable rounds completed out of 15 requested (3 seeds x 5 rounds); a
shortfall means one or more trials were excluded for a schema-validation
interruption (see Stability below), not a silent drop — every exclusion is recorded
with its reason in the raw matchup data and the dataset export.

Token / latency detail (mean per structured call, input+output tokens summed across
the matchup):

| Scenario | Qwen attacker tok (in/out) | Qwen defender tok (in/out) | Gemma attacker tok (in/out) | Gemma defender tok (in/out) |
|---|---|---|---|---|
| frozen | 2454/3657 | 1515/781 | 2517/1962 | 1800/446 |
| mutual_bounded | 9838/5901 | 9166/1223 | 10142/2188 | 9686/782 |
| mutual_full | 9971/3637 | 12988/1074 | 10603/2278 | 14226/761 |
| normal_control | 2402/8270 | 1515/775 | 2517/2046 | 1800/466 |
| attacker_privileged | 2796/2691 | 1418/758 | 3030/2449 | 1800/524 |
| defender_privileged | 2376/4987 | 4082/1091 | 2517/1998 | 3917/592 |

## Interpretation

- **Context overload generalizes, but asymmetrically.** Qwen's defender entropy
  collapses from ~77-92 bits (frozen / normal_control / either privilege scenario) to
  ~36 bits under both mutual policies — a large, consistent drop, replicating the
  context-overload pattern from earlier Qwen-only benchmarks under this fresh
  matched protocol. Gemma's defender entropy is flat and already low across every
  scenario (38-57 bits) — it does not show a comparable collapse, because it never
  had the high baseline to collapse from. **Within this controlled run**, added
  cross-agent context measurably hurt Qwen's defender and left Gemma's defender
  essentially unchanged.
- **Token growth without benefit, for both models.** Both models' input-token usage
  grows roughly 4x from `frozen`/`normal_control` to `mutual_full`, and neither
  model's solve rate improves from it — mutual_full produced Gemma's only non-zero
  main-matrix solve rate (6.7%), not a larger one; Qwen stayed at 0% under both
  mutual scenarios. More context did not translate into more attacker value for
  either model in this run.
- **Privilege effects did not clearly replicate at this smaller scale.** Comparing
  `normal_control` to `attacker_privileged`/`defender_privileged`, Gemma's solve rate
  stayed at 0.0 in every case; Qwen's only non-zero solve rate in the entire main
  matrix (7.1%) came under `attacker_privileged`. Entropy shifts under privilege are
  modest and mixed (Qwen's attacker_privileged entropy is ~0 bits different from its
  normal_control this run; Gemma's is flat). Benchmark 007 found measurable privilege
  effects (13.3%-16.7% attacker solve rates) under a larger Qwen-only protocol; this
  compact 3-seed, 5-round matrix is not powered to confirm or refute that at the same
  resolution for either model. Treat this as inconclusive, not a null result.
- **Stability differed measurably, though less than in the first run.** Across the 18
  main-matrix trials per model, Qwen had 1 trial interrupted by a schema-validation
  failure (`attacker_privileged` seed 44) — 5.6% trial exclusion, down from 16.7% (3
  interruptions) in the original run. Gemma again had 0/18 trial exclusions across
  both runs. Qwen's interruptions remain transient and scenario-inconsistent (a
  different scenario/seed each run), consistent with occasional malformed output
  rather than a systemic incapability tied to any one scenario.
- **Defender family-selection style differs.** Under `normal_control`, Qwen's
  defender chose `two-word-passphrase` (7/15), `eval-two-word` (4/15), and
  `cryptographic-random` (4/15) — still passphrase-leaning, though the exact split
  shifted from the original run's 7/6/2. Gemma's defender chose `cryptographic-random`
  (14/15) and `eval-word` (1/15) — again almost exclusively cryptographic-random, at
  markedly lower measured entropy than Qwen's own cryptographic-random choices. The
  family label alone does not predict entropy; the two models differ in what they
  actually produce under the same label.
- **The one solvable configuration moved between runs — both were self-play.** In the
  original run, Gemma's attacker solved 2/15 rounds against Gemma's own defender
  under `mutual_bounded`. In this re-run, that specific cell reproduced at 0%, but
  Gemma solved 1/15 under `mutual_full` instead, and Qwen (previously 0% everywhere)
  solved 1/15 under `attacker_privileged`. Every non-zero solve across both runs has
  been self-play, and each run's single-digit solve count is well within Wilson noise
  at n=15 — the safest reading is "near-zero solve rate for both models, with an
  occasional single-round fluke landing in an unpredictable cell," not a stable
  per-scenario attacker advantage for either model.

## Cross-model pilot (exploratory, not headline)

`normal_control` only, both directions, seeds 42/43/44, 5 rounds, 500 guesses = 30
requested rounds.

| Direction | Rounds | Solve % | Survival % | Mean entropy |
|---|---|---|---|---|
| Qwen attacks Gemma | 15/15 | 0.0 | 100.0 | 36.3 |
| Gemma attacks Qwen | 15/15 | 0.0 | 100.0 | 87.0 |

Both directions produced 0% attacker solves, in both this run and the original
(which additionally saw one Qwen-side schema interruption at 12/15 rounds; this
re-run had none, 15/15 both directions). The defender's own identity dominates the
resulting entropy in both directions (Gemma-defended rounds average ~36 bits
regardless of attacker; Qwen-defended rounds average ~87 bits regardless of
attacker) — consistent with the self-vs-self matrix's finding that defender family
choice and entropy are primarily a property of the defending model, not the
attacking one. The clean, comparable result here suggests a full cross-family
attacker/defender tournament would be a reasonable next step, but 15 rounds per
direction is too small to support a stronger claim than "worth investigating
further."

## Reproducibility check (2026-08-13 re-run)

This benchmark was re-run once in full — same code, protocol, seeds (42/43/44),
rounds (5), and guess budget (500) — to check how much the headline findings depend
on a single run's luck versus holding up under repetition. The numbers above are
from the re-run; the original run's numbers are preserved in this section for
comparison.

**What held:** the core qualitative hierarchy did not change. Qwen's defender
entropy stayed well above Gemma's in every scenario in both runs (Qwen 36-95 bits
original / 36-92 bits re-run vs. Gemma 38-43 bits original / 38-57 bits re-run).
Both models' attacker solve rate stayed at or near 0% in both runs — no scenario
produced a stable, repeatable attacker advantage for either model. Structured-output
reliability ranking held (Gemma more reliable than Qwen in both runs, 0 vs.
1-3 interruptions). Token-growth-without-benefit under `mutual_full` held for both
models.

**What drifted:** individual entropy values moved by single-digit-to-~18-bit
amounts run to run (largest: Gemma's `mutual_bounded` entropy rose from 38.9 to 56.6
bits; Qwen's `normal_control` entropy fell from 95.6 to 77.2 bits) — normal
seed-to-seed/sampling variance at n=3 seeds, not a contradiction of the headline
claims. The one non-zero solve rate in each run's main matrix landed in a different
(model, scenario) cell both times (original: Gemma/`mutual_bounded`; re-run:
Gemma/`mutual_full` and Qwen/`attacker_privileged`) — this is itself informative: it
argues those single-round solves are closer to noise than a stable per-scenario
effect. Qwen's interrupted-trial count dropped from 3 to 1 between runs.

**Conclusion:** the headline model-comparison findings in this report are
reproducible at the level of "which model wins on which axis," not at the level of
"exact numbers." Anyone treating a single number from this benchmark (e.g. "Gemma
solved 13.3% under mutual_bounded") as a fixed property of the model rather than one
observation from a 3-seed sample should not.

## What this benchmark proves

- `gemma3:4b` is a qualified, reliable Password Arena participant: 100% schema-valid
  under qualification, and it completed more comparable rounds (90/90 main matrix)
  than Qwen (89/90 in this re-run; 83/90 in the original run) across both runs.
- Context-overload-style defender degradation is not unique to Qwen's specific
  failure mode, but the two models express it differently: Qwen degrades sharply
  from a high baseline, Gemma stays flat from an already-low baseline.
- The compute backend for this container is GPU-accelerated (Vulkan/AMD), not
  CPU-only, and has been since at least the container's first model pull — this is
  now measured and documented rather than assumed.

## What this benchmark does NOT prove

- That Gemma is "better" or "worse" than Qwen in any single-number sense — no
  composite score is reported, by design (see Findings above: different models lead
  different categories).
- That privilege effects (attacker/defender information advantage) generalize or
  fail to generalize across model families — this compact matrix is not powered to
  distinguish a real null effect from insufficient statistical power at 3 seeds x 5
  rounds.
- That the cross-model pilot's 0%/0% solve rates predict what a full cross-family
  tournament (all six scenarios, both directions) would show.
- Broad claims about either model family's general-purpose capability outside this
  narrow, synthetic, bounded password-arena task.

## Limitations

- Two small local 4B models, three seeds, five rounds per matchup — a small,
  bounded synthetic benchmark, not a general-purpose LLM leaderboard.
- CPU-only was the intended execution mode; this run was GPU-accelerated (Vulkan),
  discovered and documented rather than corrected, per an explicit decision made
  during this benchmark's setup (see Environment above). Timing/latency figures in
  this report should not be treated as representative of genuine CPU-only inference.
- Repeated hosted/local-model trials are stochastic; the Wilson confidence intervals
  reported in the underlying tournament data assume independent Bernoulli round
  outcomes, which is a descriptive convention, not a rigorous guarantee.
