# Agent Instructions

These instructions apply to coding agents working in Password Arena.

## Read before changing code

1. Read `blueprint.md` for product boundaries and architecture.
2. Read `SECURITY.md` for prohibited uses.
3. Read `improvements.md` and `bugs.md`.
4. Select one clearly scoped backlog item or create a new item before implementing untracked work.

## Required workflow

1. Change the selected backlog item to **In Progress**.
2. Inspect the relevant implementation and tests before editing.
3. Preserve synthetic-only, local-only, bounded execution.
4. Add or update tests for behavior changes and edge cases.
5. Run:

   ```bash
   ruff check .
   mypy src/password_arena
   pytest
   ```

6. Update user-facing documentation when behavior or configuration changes.
7. Change the backlog item to **Done** or **Resolved**, including a concise implementation note and validation performed.
8. Do not delete completed backlog entries; they are project history.

## Safety invariants

Agents must not add:

- real credential collection or import;
- breach-dump ingestion;
- authentication endpoint targeting;
- browser automation for login attempts;
- credential stuffing or distributed guessing;
- unrestricted shell or network tools for attacker or defender agents;
- password disclosure in default reports;
- claims of model training when only prompts, context, or memory changed;
- silent provider/model fallback that contaminates benchmark results;
- unsupported thinking settings sent without capability validation;
- claims about consumer chat-session limits based only on API errors.

When a proposed change conflicts with these invariants, stop implementation and document the conflict in the relevant backlog item.

## Reporting standard

The arena may document decisions, actions, observations, outputs, and state updates that were actually recorded. It must not request or present private model chain-of-thought as an audit artifact.

## Commit scope

- Keep commits focused on the selected backlog item.
- Do not mix unrelated refactors with a bug fix.
- Reference backlog IDs in commit or pull request descriptions when possible.
