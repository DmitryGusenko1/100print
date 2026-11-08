---
name: github-issue-executor
description: Executes GitHub issues end to end for 100print: inspect, implement, test, commit, push, and report verified results.
---

# GitHub Issue Executor

Use when work originates from a GitHub issue or should be tracked as one.

## Workflow
1. Read the issue completely, including comments and acceptance criteria.
2. Load project context.
3. Inspect the relevant code before editing.
4. Create or use a dedicated branch unless the user explicitly requests direct work on the target branch.
5. Implement the smallest complete vertical slice.
6. Run the most relevant automated and manual checks.
7. Commit only coherent changes with a descriptive message.
8. Push the branch and update the issue with:
   - what changed;
   - what was verified;
   - what remains;
   - links to commit/PR when available.
9. Never claim completion when a required check has not actually run.

## Quality gate
A task is not done merely because code was written. It is done when the requested behavior is implemented and verified, or when the unverified part is explicitly identified.

## Safety
- Never commit credentials or production data.
- Do not rewrite shared history unless explicitly requested.
- Do not close an issue if acceptance criteria are still unmet.
