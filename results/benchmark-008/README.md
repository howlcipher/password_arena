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

| Scenario | Qwen rounds | Qwen solve % | Qwen mean entropy | Gemma rounds | Gemma solve % | Gemma mean entropy |
|---|---|---|---|---|---|---|
| frozen | 12/15 | 0.0 | 80.2 | 15/15 | 0.0 | 43.1 |
| mutual_bounded | 15/15 | 0.0 | 36.3 | 15/15 | **13.3** | 38.9 |
| mutual_full | 15/15 | 0.0 | 36.3 | 15/15 | 0.0 | 38.1 |
| normal_control | 15/15 | 0.0 | 95.6 | 15/15 | 0.0 | 39.2 |
| attacker_privileged | 11/15 | 0.0 | 86.0 | 15/15 | 0.0 | 42.0 |
| defender_privileged | 15/15 | 0.0 | 95.1 | 15/15 | 0.0 | 37.9 |

"Rounds" is comparable rounds completed out of 15 requested (3 seeds x 5 rounds); a
shortfall means one or more trials were excluded for a schema-validation
interruption (see Stability below), not a silent drop — every exclusion is recorded
with its reason in the raw matchup data and the dataset export.

Token / latency detail (mean per structured call, input+output tokens summed across
the matchup):

| Scenario | Qwen attacker tok (in/out) | Qwen defender tok (in/out) | Gemma attacker tok (in/out) | Gemma defender tok (in/out) |
|---|---|---|---|---|
| frozen | 1791/2975 | 1212/732 | 2517/2066 | 1800/445 |
| mutual_bounded | 9768/3580 | 9168/1069 | 10027/2173 | 9602/604 |
| mutual_full | 10001/3814 | 13204/1066 | 10679/2245 | 14171/729 |
| normal_control | 2450/7690 | 1515/726 | 2517/2050 | 1800/514 |
| attacker_privileged | 2059/2097 | 1111/656 | 3143/2395 | 1800/391 |
| defender_privileged | 2428/7272 | 4241/1037 | 2517/1992 | 3982/706 |

## Interpretation

- **Context overload generalizes, but asymmetrically.** Qwen's defender entropy
  collapses from ~80-96 bits (frozen / normal_control / either privilege scenario) to
  ~36 bits under both mutual policies — a large, consistent drop, replicating the
  context-overload pattern from earlier Qwen-only benchmarks under this fresh
  matched protocol. Gemma's defender entropy is flat and already low across every
  scenario (37-43 bits) — it does not show a comparable collapse, because it never
  had the high baseline to collapse from. **Within this controlled run**, added
  cross-agent context measurably hurt Qwen's defender and left Gemma's defender
  essentially unchanged.
- **Token growth without benefit, for both models.** Both models' input-token usage
  grows roughly 4-11x from `frozen`/`normal_control` to `mutual_full`, and neither
  model's solve rate improves from it — mutual_full produced 0% solves for both.
  Gemma's only non-zero solve rate (13.3%) came under `mutual_bounded`, the smaller
  information payload, not `mutual_full`, the larger one — more context did not mean
  more attacker value for either model in this run.
- **Privilege effects did not clearly replicate at this smaller scale.** Comparing
  `normal_control` to `attacker_privileged`/`defender_privileged`, solve rate stayed
  at 0.0 for both models in every case (Gemma's one non-zero result was under a
  different scenario). Entropy shifts under privilege are modest and mixed
  (Qwen's attacker_privileged entropy is ~10 bits lower than its normal_control;
  Gemma's is flat). Benchmark 007 found measurable privilege effects (13.3%-16.7%
  attacker solve rates) under a larger Qwen-only protocol; this compact 3-seed,
  5-round matrix is not powered to confirm or refute that at the same resolution for
  either model. Treat this as inconclusive, not a null result.
- **Stability differed measurably.** Across the 18 main-matrix trials per model,
  Qwen had 3 trials interrupted by a structured-output schema-validation failure
  (`frozen` seed 43, `attacker_privileged` seeds 42 and 43) — 16.7% trial exclusion.
  Gemma had 0/18 trial exclusions. The cross-model pilot adds one more Qwen-side
  interruption (Qwen attacking Gemma, seed 43). In this specific run, Gemma was the
  more reliable structured-output participant; Qwen's failures were transient
  (retried trials at other seeds in the same scenario succeeded cleanly), consistent
  with occasional malformed output rather than a systemic incapability.
- **Defender family-selection style differs.** Under `normal_control`, Qwen's
  defender chose `eval-two-word` (7/15), `two-word-passphrase` (6/15), and
  `cryptographic-random` (2/15) — passphrase-leaning. Gemma's defender chose
  `cryptographic-random` (13/15) and `eval-word` (2/15) — almost exclusively
  cryptographic-random, yet at markedly lower measured entropy than Qwen's own
  cryptographic-random choices. The family label alone does not predict entropy;
  the two models differ in what they actually produce under the same label.
- **The one solvable configuration was self-play, not cross-play.** Gemma's attacker
  solved 2/15 rounds against Gemma's own defender under `mutual_bounded` — the only
  non-zero solve rate in the entire main matrix. The cross-model pilot (below) did
  not reproduce a solve in either direction, suggesting this result is tied to
  Gemma's specific (lower-entropy) defender baseline combined with bounded shared
  context, not a generically stronger Gemma attacker.

## Cross-model pilot (exploratory, not headline)

`normal_control` only, both directions, seeds 42/43/44, 5 rounds, 500 guesses = 30
requested rounds.

| Direction | Rounds | Solve % | Survival % | Mean entropy |
|---|---|---|---|---|
| Qwen attacks Gemma | 12/15 | 0.0 | 100.0 | 34.3 |
| Gemma attacks Qwen | 15/15 | 0.0 | 100.0 | 94.6 |

Both directions produced 0% attacker solves. The defender's own identity dominates
the resulting entropy in both directions (Gemma-defended rounds average ~34 bits
regardless of attacker; Qwen-defended rounds average ~95 bits regardless of
attacker) — consistent with the self-vs-self matrix's finding that defender family
choice and entropy are primarily a property of the defending model, not the
attacking one. The clean, comparable result here (no schema-validity concerns beyond
the one already-recorded interruption) suggests a full cross-family attacker/
defender tournament would be a reasonable next step, but 15 rounds per direction is
too small to support a stronger claim than "worth investigating further."

## What this benchmark proves

- `gemma3:4b` is a qualified, reliable Password Arena participant: 100% schema-valid
  under qualification, and it completed more comparable rounds (90/90 main matrix)
  than Qwen (83/90) in this specific run.
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
