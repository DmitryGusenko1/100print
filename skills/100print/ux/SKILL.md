---
name: ux
description: UX / Conversion Optimization decisions for 100print.
---

## Purpose

- Support evidence-based 100print decisions: UX / Conversion Optimization

## Trigger conditions

- ux
- конверси
- checkout
- редактор
- оформлен.*заказ
- usability

## Required inputs

- Funnel events
- session observations
- editor errors
- saved design/reorder usage

## Analysis checklist

- Locate friction in editor, quote, checkout and order flow
- test saved designs/reorder usability
- prioritize conversion hypotheses with contribution guardrails

## Output contract

- summary: recommendation and decision gate
- recommendations: actionable next steps, owner and review point; calculations with units and assumptions; KPIs and thresholds
- risks: failure modes and escalation
- assumptions: explicit unverified claims
- evidence_gaps: missing inputs, sources and validation required

## KPIs

- Paid conversion
- task completion
- reorder completion
- error rate

## Risks / failure modes

- Conversion uplift destroys margin
- unrepresentative usability sample

## Escalation rules

- Production-impacting promises to Operations; uncertain effects to Analytics

Runtime source: `config/organization/skills.json`, ID `strategy.ux`. Apply the shared `config/organization/100print.json` principles. Return structured evidence and a brief recommendation, never hidden chain-of-thought.
