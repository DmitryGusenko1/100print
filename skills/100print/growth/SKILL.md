---
name: growth
description: Growth / Performance Marketing decisions for 100print.
---

## Purpose

- Support evidence-based 100print decisions: Growth / Performance Marketing

## Trigger conditions

- канал
- cac
- performance
- масштабиров.*реклам
- реклам

## Required inputs

- Spend and attribution windows
- paid orders
- segment CAC
- creative and landing data
- capacity

## Analysis checklist

- Compare acquisition channels and funnel economics
- test creatives and landing conversion
- CAC by segment
- scale only with contribution/payback and capacity gates
- measure incrementality

## Output contract

- summary: recommendation and decision gate
- recommendations: actionable next steps, owner and review point; calculations with units and assumptions; KPIs and thresholds
- risks: failure modes and escalation
- assumptions: explicit unverified claims
- evidence_gaps: missing inputs, sources and validation required

## KPIs

- Incremental contribution after acquisition
- CAC
- payback
- paid conversion

## Risks / failure modes

- Attributed ROAS mistaken for incrementality
- scale exceeds production capacity

## Escalation rules

- Unprofitable scale requires Finance + Critic; cross-functional capacity decision L3

Runtime source: `config/organization/skills.json`, ID `marketing.growth`. Apply the shared `config/organization/100print.json` principles. Return structured evidence and a brief recommendation, never hidden chain-of-thought.
