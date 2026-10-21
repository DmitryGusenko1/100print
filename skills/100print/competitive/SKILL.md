---
name: competitive
description: Competitive Intelligence decisions for 100print.
---

## Purpose

- Support evidence-based 100print decisions: Competitive Intelligence

## Trigger conditions

- конкурент
- competitor
- заменител

## Required inputs

- Dated public offers
- comparable basket
- terms
- substitutes
- source links

## Analysis checklist

- Map competitors/substitutes
- normalize price/service comparison
- positioning and offer gaps
- derive independent hypotheses, never copy blindly

## Output contract

- summary: recommendation and decision gate
- recommendations: actionable next steps, owner and review point; calculations with units and assumptions; KPIs and thresholds
- risks: failure modes and escalation
- assumptions: explicit unverified claims
- evidence_gaps: missing inputs, sources and validation required

## KPIs

- Validated differentiation
- win/loss
- contribution at comparable offer

## Risks / failure modes

- Stale prices
- unlike-for-like basket
- copying business model

## Escalation rules

- Unverified prices remain assumptions; strategic repositioning to Strategy head

Runtime source: `config/organization/skills.json`, ID `strategy.competitive`. Apply the shared `config/organization/100print.json` principles. Return structured evidence and a brief recommendation, never hidden chain-of-thought.
