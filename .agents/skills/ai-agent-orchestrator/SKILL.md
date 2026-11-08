---
name: ai-agent-orchestrator
description: Coordinates specialized AI agents for 100print and returns only evidence-backed, attributable results.
---

# AI Agent Orchestrator

Use when work should be delegated among specialized agents or requires multi-step coordination.

## Operating model
- One orchestrator owns the user goal and final result.
- Delegate by capability, not by vague role names.
- Give each agent a bounded task, required inputs, acceptance criteria, and expected output.
- Preserve shared project context and relevant decision history.
- Prefer parallel work only for independent tasks.
- Resolve conflicting agent outputs using evidence and project rules.

## Result contract
A delegated result should include:
- status: completed / blocked / failed;
- concrete output;
- evidence or checks;
- changed resources;
- unresolved risks.

Do not present invented sub-agent actions as completed. Only report actions backed by actual tool or system results.

## Memory
Persist important confirmed decisions, task outcomes, and project-state changes through the project's shared-memory layer when available.
