# Bugs Backlog

This file tracks confirmed defects and behavioral mismatches. Product ideas belong in `improvements.md`.

## Severity guide

- **P0:** unsafe behavior, credential exposure, or unusable core system.
- **P1:** major incorrect behavior or broken primary workflow.
- **P2:** meaningful defect with a workaround.
- **P3:** minor display, reporting, or edge-case issue.

## Status values

- **Open**
- **In Progress**
- **Blocked**
- **Resolved**
- **Won't Fix**

---

## BUG-001 — Guess budgets below four can create negative allocations

**Priority:** P1  
**Status:** Resolved  
**Resolved in:** Initial repository setup

### Previous behavior

The allocator forced at least one guess into all four strategies and then subtracted the excess from the highest-ranked strategy. With budgets of one or two, the highest allocation became negative and `itertools.islice` raised `ValueError`. A budget of three could assign zero guesses to the highest-ranked strategy.

### Resolution

The allocator now uses largest-remainder distribution. Allocations are non-negative, sum exactly to the configured budget, and zero-budget strategies are skipped.

### Regression coverage

`test_tiny_guess_budgets_are_valid_and_bounded` validates budgets one through four.

---

## BUG-002 — Seeded high-difficulty runs are not fully reproducible

**Priority:** P1  
**Status:** Open

### Reproduction

1. Run two experiments with the same seed, `reveal_passwords=True`, and a difficulty of seven or higher.
2. Compare the generated cryptographic-random passwords.
3. The values differ because `secrets.choice` intentionally ignores the experiment seed.

### Impact

The README describes the baseline as reproducible, but secure-random defender rounds are intentionally nondeterministic. This also prevents exact replay of complete experiments.

### Expected resolution

- Add explicit generator modes such as `secure` and `deterministic-test`.
- Record the generator mode in results.
- Keep `secure` as the default for the password-manager endpoint.
- Update replay and reproducibility claims to distinguish the modes.

---

## BUG-003 — Attacker passphrase grammar does not match all defender passphrases

**Priority:** P1  
**Status:** Open

### Reproduction

Run difficulty five or six rounds. The defender emits three- or four-word passphrases with arbitrary three-digit suffixes. The attacker generates at most three words and mostly two-digit suffixes, plus only `123` and `2026` as longer suffixes.

### Impact

Some rounds are structurally unreachable by the intended passphrase strategy regardless of a reasonable budget. The experiment can therefore measure grammar mismatch rather than adaptive strategy quality.

### Expected resolution

- Move password grammars into versioned, testable components.
- Decide which patterns are shared training data and which are held out.
- Add four-word generation and configurable suffix distributions where appropriate.
- Add tests proving benchmark cases are reachable while held-out cases remain genuinely novel.

---

## BUG-004 — Failed attacks report a strategy as though it solved the password

**Priority:** P2  
**Status:** Open

### Reproduction

Run a resistant round and inspect `AttackResult.strategy` or the dashboard's “Attack strategy” column. The field contains the highest-priority strategy even though no strategy succeeded and several may have been attempted.

### Impact

Consumers can misread the field as the successful strategy. The full attempted list is accurate, but the summary field is ambiguous.

### Expected resolution

- Rename the field to `winning_strategy` and make it `None` on failure, or add a separate `primary_strategy` field.
- Update CLI, dashboard, JSON schema, reports, and tests.

---

## BUG-005 — Reusing one ArenaEngine instance carries state into a second run

**Priority:** P2  
**Status:** Open

### Reproduction

1. Construct one `ArenaEngine` instance.
2. Call `run()` twice.
3. The second call starts with defender breach memory, attacker learned words, strategy scores, and advanced random state from the first call.

### Impact

A caller may expect `run()` to represent a fresh experiment because the configuration is unchanged. The current lifecycle is not documented.

### Expected resolution

Choose and document one contract:

- make `run()` single-use and raise on a second call;
- reset agents at the start of each run; or
- rename the operation to make continued training explicit and introduce a separate fresh-run API.

---

## BUG-006 — Invalid CLI configuration produces a Python traceback

**Priority:** P2  
**Status:** Resolved
**Resolved in:** CLI validation update

### Reproduction

Run `password-arena --rounds 0` or another value rejected by `ArenaConfig.validate()`.

### Impact

The CLI exposes an implementation traceback instead of a concise usage error, which makes normal input validation look like an application crash.

### Expected resolution

Catch validation errors at the CLI boundary and pass them to `argparse.ArgumentParser.error()` or return a concise non-zero error message. Add subprocess-level CLI tests.

### Resolution

Added a call to `config.validate()` in `src/password_arena/cli.py` and caught the `ValueError`, passing the error message to `argparse.ArgumentParser.error()`. Added `test_cli_invalid_config` in `tests/test_cli.py` to assert the CLI outputs a concise error message without tracebacks.

---

## BUG-007 — Entropy and guess counts share one chart scale

**Priority:** P2  
**Status:** Open

### Reproduction

Run the Streamlit dashboard with a guess budget in the thousands. The “Learning curves” chart plots entropy bits and guesses on the same numeric scale.

### Impact

The entropy line appears almost flat and the chart can imply that strength is not changing.

### Expected resolution

Render separate charts or use a clearly labeled dual-axis visualization. Add strategy efficiency and solve outcome overlays only when they remain readable.

---

## BUG-008 — Rounded strategy weights may not display as exactly 100 percent

**Priority:** P3  
**Status:** Open

### Reproduction

Inspect serialized `StrategyBudget.weight` values. Weights are rounded to four decimal places before storage, so displayed percentages can sum slightly above or below 100 percent.

### Impact

The exact integer guess budgets remain authoritative, but the report can look internally inconsistent.

### Expected resolution

Store full-precision normalized weights and round only in presentation layers, or derive displayed percentages directly from integer allocations.
