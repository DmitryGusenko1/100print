---
name: product
description: Product Management decisions for 100print.
---

## Purpose

- Support evidence-based 100print decisions: Product Management

## Trigger conditions

- продукт
- mvp
- мвп
- roadmap
- добавить.*портал
- метрик.*портал

## Required inputs

- Customer jobs
- portal funnel
- hypotheses
- delivery capacity
- feature cost

## Analysis checklist

- Define MVP and explicit exclusions
- prioritize value vs complexity
- map customer journey
- test product hypotheses
- sequence portal roadmap
- saved designs and repeat-order mechanics

## Output contract

- summary: recommendation and decision gate
- recommendations: actionable next steps, owner and review point; calculations with units and assumptions; KPIs and thresholds
- risks: failure modes and escalation
- assumptions: explicit unverified claims
- evidence_gaps: missing inputs, sources and validation required

## KPIs

- Activation
- paid order conversion
- repeat order rate
- contribution per feature cohort

## Risks / failure modes

- Feature volume mistaken for value
- untested segment exclusion

## Escalation rules

- Cross-functional roadmap conflicts require L3; portfolio commitment requires owner

Runtime source: `config/organization/skills.json`, ID `strategy.product`. Apply the shared `config/organization/100print.json` principles. Return structured evidence and a brief recommendation, never hidden chain-of-thought.
