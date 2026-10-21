---
name: project-context
description: Loads the authoritative context, decisions, architecture, and active tasks for the 100print project before making material changes.
---

# Project Context

Use this skill before architecture changes, cross-cutting implementation, planning, or answering questions about project state.

## Read first
1. `docs/PROJECT_CONTEXT.md`
2. `docs/DECISIONS.md`
3. `docs/ARCHITECTURE.md`
4. `docs/TASKS.md`
5. `IMPLEMENTATION.md` when work concerns the shared-memory platform.

## Rules
- Treat documented confirmed decisions as authoritative until explicitly changed.
- Distinguish facts, assumptions, proposed changes, and user-confirmed decisions.
- Do not silently override prior decisions.
- Prefer the smallest change compatible with the current architecture.
- Keep Git free of secrets, tokens, private conversation data, database dumps, and runtime state.
- When implementation changes architecture or an important operating rule, update the relevant project documentation in the same change.

## Output
State the decision or implementation result, evidence/checks, and one next action when useful.
