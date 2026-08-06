# Password Arena Experiment Report

- **Rounds:** 8
- **Solved rounds:** 2
- **Solve rate:** 25.0%
- **Guess budget per round:** 5,000
- **Passwords revealed:** False

> Reports are generated from recorded actions and metrics. They are not unverified agent chain-of-thought.

## Round 1 — SOLVED

**Difficulty:** 1  
**Password:** `•••••` (5 characters)  
**Estimated entropy:** 10.58 bits  
**Guess result:** 8 guesses using `common`  
**Runtime:** 0.026 ms

### Defender side

**Decision:** Selected dictionary-word for difficulty 1.

- Generated a synthetic dictionary-word password.
- Set length to 5 characters.

**Observed:** The password solved. Evaluator findings: Contains a common password token.  
**Learning update:** Recorded dictionary-word as breached and will harden it if reused.

### Attacker side

**Decision:** Ranked common as the highest-priority strategy for difficulty 1.  
**Budget plan:** common: 3,518 (70.3%), mutation: 1,004 (20.1%), passphrase: 401 (8.0%), random: 77 (1.6%)

- Allocated 3,518 guesses to common (70.3% of the plan).
- Allocated 1,004 guesses to mutation (20.1% of the plan).
- Allocated 401 guesses to passphrase (8.0% of the plan).
- Allocated 77 guesses to random (1.6% of the plan).

**Observed:** Found a match after 8 guesses; attempted common.  
**Learning update:** Successful strategy received a higher future selection weight. Learned 1 new synthetic token(s).

### Evaluator

Round 1 solved. Strength score was 0/4 with an estimated 10.58 bits after structural penalties.

**Security lesson:** The dictionary-word structure remained predictable inside the current attack model; cosmetic complexity should not be treated as randomness.

---

## Round 2 — SOLVED

**Difficulty:** 2  
**Password:** `•••••••` (7 characters)  
**Estimated entropy:** 18.76 bits  
**Guess result:** 232 guesses using `mutation`  
**Runtime:** 0.086 ms

### Defender side

**Decision:** Selected capitalized-word-number for difficulty 2.

- Generated a synthetic capitalized-word-number password.
- Set length to 7 characters.

**Observed:** The password solved. Evaluator findings: Contains a common password token.  
**Learning update:** Recorded capitalized-word-number as breached and will harden it if reused.

### Attacker side

**Decision:** Ranked mutation as the highest-priority strategy for difficulty 2.  
**Budget plan:** mutation: 3,611 (72.2%), common: 722 (14.4%), passphrase: 481 (9.6%), random: 186 (3.7%)

- Allocated 3,611 guesses to mutation (72.2% of the plan).
- Allocated 722 guesses to common (14.4% of the plan).
- Allocated 481 guesses to passphrase (9.6% of the plan).
- Allocated 186 guesses to random (3.7% of the plan).

**Observed:** Found a match after 232 guesses; attempted mutation.  
**Learning update:** Successful strategy received a higher future selection weight.

### Evaluator

Round 2 solved. Strength score was 0/4 with an estimated 18.76 bits after structural penalties.

**Security lesson:** The capitalized-word-number structure remained predictable inside the current attack model; cosmetic complexity should not be treated as randomness.

---

## Round 3 — RESISTED

**Difficulty:** 3  
**Password:** `•••••••` (7 characters)  
**Estimated entropy:** 44.87 bits  
**Guess result:** 5,000 guesses using `mutation`  
**Runtime:** 2.377 ms

### Defender side

**Decision:** Selected substitution-pattern for difficulty 3.

- Generated a synthetic substitution-pattern password.
- Set length to 7 characters.

**Observed:** The password resisted the bounded guess budget. Evaluator findings: No obvious structural weakness detected.  
**Learning update:** Recorded substitution-pattern as surviving the current bounded attack.

### Attacker side

**Decision:** Ranked mutation as the highest-priority strategy for difficulty 3.  
**Budget plan:** mutation: 3,980 (79.6%), common: 530 (10.6%), passphrase: 353 (7.1%), random: 137 (2.7%)

- Allocated 3,980 guesses to mutation (79.6% of the plan).
- Allocated 530 guesses to common (10.6% of the plan).
- Allocated 353 guesses to passphrase (7.1% of the plan).
- Allocated 137 guesses to random (2.7% of the plan).

**Observed:** Found no match after 5,000 guesses; attempted mutation, common, passphrase, random, random-overflow.  
**Learning update:** Failure recorded; attacker retained synthetic token structure for later rounds.

### Evaluator

Round 3 resisted the bounded guess budget. Strength score was 2/4 with an estimated 44.87 bits after structural penalties.

**Security lesson:** This structure survived this bounded experiment, but that is not proof of real-world security against larger or different attack models.

---

## Round 4 — RESISTED

**Difficulty:** 4  
**Password:** `••••••••••••••••` (16 characters)  
**Estimated entropy:** 105.12 bits  
**Guess result:** 5,000 guesses using `passphrase`  
**Runtime:** 2.978 ms

### Defender side

**Decision:** Selected two-word-passphrase for difficulty 4.

- Generated a synthetic two-word-passphrase password.
- Set length to 16 characters.

**Observed:** The password resisted the bounded guess budget. Evaluator findings: No obvious structural weakness detected.  
**Learning update:** Recorded two-word-passphrase as surviving the current bounded attack.

### Attacker side

**Decision:** Ranked passphrase as the highest-priority strategy for difficulty 4.  
**Budget plan:** passphrase: 3,450 (69.0%), mutation: 1,029 (20.6%), common: 343 (6.9%), random: 178 (3.6%)

- Allocated 3,450 guesses to passphrase (69.0% of the plan).
- Allocated 1,029 guesses to mutation (20.6% of the plan).
- Allocated 343 guesses to common (6.9% of the plan).
- Allocated 178 guesses to random (3.6% of the plan).

**Observed:** Found no match after 5,000 guesses; attempted passphrase, mutation, common, random, random-overflow.  
**Learning update:** Failure recorded; attacker retained synthetic token structure for later rounds. Learned 2 new synthetic token(s).

### Evaluator

Round 4 resisted the bounded guess budget. Strength score was 4/4 with an estimated 105.12 bits after structural penalties.

**Security lesson:** This structure survived this bounded experiment, but that is not proof of real-world security against larger or different attack models.

---

## Round 5 — RESISTED

**Difficulty:** 5  
**Password:** `••••••••••••••••••••••` (22 characters)  
**Estimated entropy:** 134.39 bits  
**Guess result:** 5,000 guesses using `passphrase`  
**Runtime:** 3.611 ms

### Defender side

**Decision:** Selected multi-word-passphrase for difficulty 5.

- Generated a synthetic multi-word-passphrase password.
- Set length to 22 characters.

**Observed:** The password resisted the bounded guess budget. Evaluator findings: No obvious structural weakness detected.  
**Learning update:** Recorded multi-word-passphrase as surviving the current bounded attack.

### Attacker side

**Decision:** Ranked passphrase as the highest-priority strategy for difficulty 5.  
**Budget plan:** passphrase: 3,455 (69.1%), mutation: 1,025 (20.5%), common: 341 (6.8%), random: 179 (3.6%)

- Allocated 3,455 guesses to passphrase (69.1% of the plan).
- Allocated 1,025 guesses to mutation (20.5% of the plan).
- Allocated 341 guesses to common (6.8% of the plan).
- Allocated 179 guesses to random (3.6% of the plan).

**Observed:** Found no match after 5,000 guesses; attempted passphrase, mutation, common, random, random-overflow.  
**Learning update:** Failure recorded; attacker retained synthetic token structure for later rounds. Learned 2 new synthetic token(s).

### Evaluator

Round 5 resisted the bounded guess budget. Strength score was 4/4 with an estimated 134.39 bits after structural penalties.

**Security lesson:** This structure survived this bounded experiment, but that is not proof of real-world security against larger or different attack models.

---

## Round 6 — RESISTED

**Difficulty:** 6  
**Password:** `••••••••••••••••••••••••••••` (28 characters)  
**Estimated entropy:** 76.97 bits  
**Guess result:** 5,000 guesses using `passphrase`  
**Runtime:** 4.227 ms

### Defender side

**Decision:** Selected multi-word-passphrase for difficulty 6.

- Generated a synthetic multi-word-passphrase password.
- Set length to 28 characters.

**Observed:** The password resisted the bounded guess budget. Evaluator findings: Contains a common password token.  
**Learning update:** Recorded multi-word-passphrase as surviving the current bounded attack.

### Attacker side

**Decision:** Ranked passphrase as the highest-priority strategy for difficulty 6.  
**Budget plan:** passphrase: 3,459 (69.1%), mutation: 1,021 (20.4%), common: 340 (6.8%), random: 180 (3.6%)

- Allocated 3,459 guesses to passphrase (69.1% of the plan).
- Allocated 1,021 guesses to mutation (20.4% of the plan).
- Allocated 340 guesses to common (6.8% of the plan).
- Allocated 180 guesses to random (3.6% of the plan).

**Observed:** Found no match after 5,000 guesses; attempted passphrase, mutation, common, random, random-overflow.  
**Learning update:** Failure recorded; attacker retained synthetic token structure for later rounds. Learned 1 new synthetic token(s).

### Evaluator

Round 6 resisted the bounded guess budget. Strength score was 3/4 with an estimated 76.97 bits after structural penalties.

**Security lesson:** This structure survived this bounded experiment, but that is not proof of real-world security against larger or different attack models.

---

## Round 7 — RESISTED

**Difficulty:** 7  
**Password:** `••••••••••••••` (14 characters)  
**Estimated entropy:** 79.81 bits  
**Guess result:** 5,000 guesses using `random`  
**Runtime:** 13.189 ms

### Defender side

**Decision:** Selected cryptographic-random for difficulty 7.

- Generated a synthetic cryptographic-random password.
- Set length to 14 characters.

**Observed:** The password resisted the bounded guess budget. Evaluator findings: No obvious structural weakness detected.  
**Learning update:** Recorded cryptographic-random as surviving the current bounded attack.

### Attacker side

**Decision:** Ranked random as the highest-priority strategy for difficulty 7.  
**Budget plan:** random: 3,973 (79.4%), passphrase: 592 (11.8%), mutation: 348 (7.0%), common: 87 (1.7%)

- Allocated 3,973 guesses to random (79.4% of the plan).
- Allocated 592 guesses to passphrase (11.8% of the plan).
- Allocated 348 guesses to mutation (7.0% of the plan).
- Allocated 87 guesses to common (1.7% of the plan).

**Observed:** Found no match after 5,000 guesses; attempted random, passphrase, mutation, common, random-overflow.  
**Learning update:** Failure recorded; attacker retained synthetic token structure for later rounds. Learned 1 new synthetic token(s).

### Evaluator

Round 7 resisted the bounded guess budget. Strength score was 3/4 with an estimated 79.81 bits after structural penalties.

**Security lesson:** Cryptographically secure randomness removed the human patterns targeted by the bounded attacker; password-manager generation is the safer real-world endpoint.

---

## Round 8 — RESISTED

**Difficulty:** 8  
**Password:** `••••••••••••••••` (16 characters)  
**Estimated entropy:** 105.12 bits  
**Guess result:** 5,000 guesses using `random`  
**Runtime:** 15.127 ms

### Defender side

**Decision:** Selected cryptographic-random for difficulty 8.

- Generated a synthetic cryptographic-random password.
- Set length to 16 characters.

**Observed:** The password resisted the bounded guess budget. Evaluator findings: No obvious structural weakness detected.  
**Learning update:** Recorded cryptographic-random as surviving the current bounded attack.

### Attacker side

**Decision:** Ranked random as the highest-priority strategy for difficulty 8.  
**Budget plan:** random: 3,979 (79.5%), passphrase: 590 (11.8%), mutation: 345 (6.9%), common: 86 (1.7%)

- Allocated 3,979 guesses to random (79.5% of the plan).
- Allocated 590 guesses to passphrase (11.8% of the plan).
- Allocated 345 guesses to mutation (6.9% of the plan).
- Allocated 86 guesses to common (1.7% of the plan).

**Observed:** Found no match after 5,000 guesses; attempted random, passphrase, mutation, common, random-overflow.  
**Learning update:** Failure recorded; attacker retained synthetic token structure for later rounds.

### Evaluator

Round 8 resisted the bounded guess budget. Strength score was 4/4 with an estimated 105.12 bits after structural penalties.

**Security lesson:** Cryptographically secure randomness removed the human patterns targeted by the bounded attacker; password-manager generation is the safer real-world endpoint.
