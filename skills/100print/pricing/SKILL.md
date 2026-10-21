---
name: pricing
description: Pricing / Unit Economics decisions for 100print.
---

## Purpose

- Support evidence-based 100print decisions: Pricing / Unit Economics

## Trigger conditions

- марж
- margin
- pricing
- демпинг
- рентабель
- ценообраз
- прибыл

## Required inputs

- Revenue net of discounts/tax
- variable production, partner, delivery, rework costs
- CAC
- repeat cohorts
- fixed cost
- equipment quote

## Analysis checklist

- Contribution per order = net revenue minus all variable costs
- CAC payback by cohort
- repeat economics
- partner vs own incremental cost
- break-even volume
- price floor and target margin
- equipment ROI threshold

## Output contract

- summary: recommendation and decision gate
- recommendations: actionable next steps, owner and review point; calculations with units and assumptions; KPIs and thresholds
- risks: failure modes and escalation
- assumptions: explicit unverified claims
- evidence_gaps: missing inputs, sources and validation required

## KPIs

- Contribution margin
- contribution/order
- CAC payback
- cohort contribution LTV

## Risks / failure modes

- Double-counted overhead
- average margin hides unprofitable orders
- speculative LTV

## Escalation rules

- Escalate negative contribution or cash exposure to Finance head + Critic; irreversible CAPEX needs owner decision

Runtime source: `config/organization/skills.json`, ID `finance.pricing`. Apply the shared `config/organization/100print.json` principles. Return structured evidence and a brief recommendation, never hidden chain-of-thought.
