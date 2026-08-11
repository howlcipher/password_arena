# Password Arena Tournament Report

- **Tournament ID:** 97af7819324c4a6d8b8820e43271ee4d
- **Timestamp:** 2026-08-11T21:32:05.880890+00:00
- **Seeds:** [42, 43, 44]
- **Rounds per match:** 5
- **Guess budget:** 500
- **Generator:** deterministic-test / benchmark

> Confidence intervals assume independent Bernoulli round outcomes. Repeated hosted-model trials may not be strictly independent.

## ollama (qwen3:4b) vs rule_based (v1)

- **Status:** OK
- **Comparable trials:** 3/3 (excluded: 0, excluded rounds: 0)
- **Solve rate (round-level):** 0.0000
- **Survival rate (round-level):** 1.0000
- **95% CI (round-level solve rate):** [0.0000, 0.2039]
- **Guesses:** mean/round=500, median/round=500, std/round=0.0, mean-to-solve=None, median-to-solve=None, mean-total/trial=2500
- **Attacker tokens:** in=2293, out=7971, reasoning=None
- **Defender tokens:** in=0, out=0, reasoning=None
- **Latency (ms):** attacker=13250.516313266417, defender=None
- **Estimated cost:** total=unavailable, attacker=unavailable, defender=0.000000
- **Efficiency:** attacker solved/1k tokens=0.0, attacker solved/sec=0.0, attacker solved/$=None, defender survived/1k tokens=None, defender survived/$=None, defender entropy gain/1k tokens=None
- **Defender entropy trajectory (complete comparable trials only):** trials=3, initial=31.333333333333332, final=135.3, gain=103.96666666666667, tokens=0
- **Replay:** deterministic=False (schema 1.0, app 0.1.0, attacker prompt 1.1, defender prompt 1.0, capability registry 1.0)

## rule_based (v1) vs ollama (qwen3:4b)

- **Status:** OK
- **Comparable trials:** 3/3 (excluded: 0, excluded rounds: 0)
- **Solve rate (round-level):** 0.0000
- **Survival rate (round-level):** 1.0000
- **95% CI (round-level solve rate):** [0.0000, 0.2039]
- **Guesses:** mean/round=500, median/round=500, std/round=0.0, mean-to-solve=None, median-to-solve=None, mean-total/trial=2500
- **Attacker tokens:** in=0, out=0, reasoning=None
- **Defender tokens:** in=1380, out=797, reasoning=None
- **Latency (ms):** attacker=None, defender=4101.91464679956
- **Estimated cost:** total=unavailable, attacker=0.000000, defender=unavailable
- **Efficiency:** attacker solved/1k tokens=None, attacker solved/sec=None, attacker solved/$=None, defender survived/1k tokens=6.890215893431328, defender survived/$=None, defender entropy gain/1k tokens=84.0238860817639
- **Defender entropy trajectory (complete comparable trials only):** trials=3, initial=44.14666666666667, final=105.12, gain=60.973333333333336, tokens=2177
- **Replay:** deterministic=False (schema 1.0, app 0.1.0, attacker prompt 1.1, defender prompt 1.0, capability registry 1.0)

## ollama (qwen3:4b) vs ollama (qwen3:4b)

- **Status:** OK
- **Comparable trials:** 3/3 (excluded: 0, excluded rounds: 0)
- **Solve rate (round-level):** 0.0000
- **Survival rate (round-level):** 1.0000
- **95% CI (round-level solve rate):** [0.0000, 0.2039]
- **Guesses:** mean/round=500, median/round=500, std/round=0.0, mean-to-solve=None, median-to-solve=None, mean-total/trial=2500
- **Attacker tokens:** in=2189, out=7340, reasoning=None
- **Defender tokens:** in=1380, out=819, reasoning=None
- **Latency (ms):** attacker=12502.712979334077, defender=4148.616764400019
- **Estimated cost:** total=unavailable, attacker=unavailable, defender=unavailable
- **Efficiency:** attacker solved/1k tokens=0.0, attacker solved/sec=0.0, attacker solved/$=None, defender survived/1k tokens=6.8212824010914055, defender survived/$=None, defender entropy gain/1k tokens=85.9981809913597
- **Defender entropy trajectory (complete comparable trials only):** trials=3, initial=42.083333333333336, final=105.12, gain=63.03666666666667, tokens=2199
- **Replay:** deterministic=False (schema 1.0, app 0.1.0, attacker prompt 1.1, defender prompt 1.0, capability registry 1.0)
