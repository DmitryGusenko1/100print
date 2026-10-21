---
name: retention
description: CRM / Retention / Repeat Orders decisions for 100print.
---

## Purpose

- Support evidence-based 100print decisions: CRM / Retention / Repeat Orders

## Trigger conditions

- повтор
- retention
- crm
- реактивац
- удержан
- ltv

## Required inputs

- Consent
- lifecycle events
- order cohorts
- saved designs
- order frequency and contribution

## Analysis checklist

- Segment by observed lifecycle
- identify repeat triggers
- saved-template reorder convenience
- reactivation control group
- retention cohorts
- frequency and contribution LTV

## Output contract

- summary: recommendation and decision gate
- recommendations: actionable next steps, owner and review point; calculations with units and assumptions; KPIs and thresholds
- risks: failure modes and escalation
- assumptions: explicit unverified claims
- evidence_gaps: missing inputs, sources and validation required

## KPIs

- Incremental repeat contribution
- cohort retention
- repeat frequency
- LTV

## Risks / failure modes

- Spam
- selection bias
- discounts erase margin

## Escalation rules

- Privacy requires Legal; negative cohort economics requires Finance

Runtime source: `config/organization/skills.json`, ID `sales.retention`. Apply the shared `config/organization/100print.json` principles. Return structured evidence and a brief recommendation, never hidden chain-of-thought.
