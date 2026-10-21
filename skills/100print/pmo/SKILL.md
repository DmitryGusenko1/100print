---
name: pmo
description: Project Management / PMO decisions for 100print.
---

## Purpose

- Support evidence-based 100print decisions: Project Management / PMO

## Trigger conditions

- дедлайн
- milestone
- pmo
- блокер
- инициатив
- проектн.*управ

## Required inputs

- Initiatives
- owners
- deadlines
- dependencies
- status and decision rights

## Analysis checklist

- Map initiatives, owners, dependencies, deadlines, milestones, blockers, status, next review
- escalate blocked critical path

## Output contract

- summary: recommendation and decision gate
- recommendations: actionable next steps, owner and review point; calculations with units and assumptions; KPIs and thresholds
- risks: failure modes and escalation
- assumptions: explicit unverified claims
- evidence_gaps: missing inputs, sources and validation required

## KPIs

- Milestone reliability
- blocked age
- review freshness

## Risks / failure modes

- Status theater
- missing owner
- invented deadline commitments

## Escalation rules

- Unowned blockers to head; cross-functional priority conflict L3

Runtime source: `config/organization/skills.json`, ID `operations.pmo`. Apply the shared `config/organization/100print.json` principles. Return structured evidence and a brief recommendation, never hidden chain-of-thought.
