---
name: postgres-memory
description: Designs and operates PostgreSQL-backed shared memory for 100print, including messages, decisions, tasks, project state, search, migrations, and backups.
---

# PostgreSQL Memory

Use for the project's persistent AI memory and related database work.

## Core model
Support owners, projects, dialogues, messages, decisions, tasks, and versioned project state.

## Invariants
- Every protected row must be attributable to its owner/project.
- External message IDs must be unique within the correct source scope to prevent duplicate delivery.
- Save incoming messages before AI processing.
- AI failure must not erase the user message or create a fake successful assistant response.
- Decisions and project-state summaries should retain source-message references.
- Explicit user-confirmed decisions must be distinguishable from automatic AI inferences.

## Search
Start with PostgreSQL full-text search and structured filters. Add vectors only when measured need justifies them.

## Migrations
- Use versioned migrations.
- Migrations must be repeatable in deployment flow and testable on a clean database.
- Avoid destructive production changes without a safe migration path.

## Backup/restore
Define automated backups, retention, and a tested restore procedure. A backup stored only on the same VPS is not disaster recovery.
