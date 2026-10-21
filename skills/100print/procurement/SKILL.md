---
name: procurement
description: Procurement / Equipment ROI decisions for 100print.
---

## Purpose

- Support evidence-based 100print decisions: Procurement / Equipment ROI

## Trigger conditions

- оборудован
- equipment
- станок
- capex
- закуп
- купить.*машин

## Required inputs

- Supplier quotes
- CAPEX
- OPEX
- demand distribution
- capacity
- maintenance and residual value

## Analysis checklist

- Compare own-vs-outsourced incremental cash flow
- CAPEX/OPEX
- break-even utilization
- payback
- supplier scorecard
- maintenance burden
- replacement risk
- downside demand scenario

## Output contract

- summary: recommendation and decision gate
- recommendations: actionable next steps, owner and review point; calculations with units and assumptions; KPIs and thresholds
- risks: failure modes and escalation
- assumptions: explicit unverified claims
- evidence_gaps: missing inputs, sources and validation required

## KPIs

- Incremental cash ROI
- payback
- break-even utilization
- downtime
- TCO

## Risks / failure modes

- Sunk costs
- optimistic demand
- omitted maintenance/working capital

## Escalation rules

- CAPEX approval belongs to owner; Operations validates utilization at L3

Runtime source: `config/organization/skills.json`, ID `finance.procurement`. Apply the shared `config/organization/100print.json` principles. Return structured evidence and a brief recommendation, never hidden chain-of-thought.
