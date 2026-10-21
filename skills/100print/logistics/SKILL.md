---
name: logistics
description: Logistics / Delivery decisions for 100print.
---

## Purpose

- Support evidence-based 100print decisions: Logistics / Delivery

## Trigger conditions

- достав
- логист
- shipping
- упаков

## Required inputs

- Destinations
- shipment weights
- carrier tariffs
- packaging and failure data

## Analysis checklist

- Compare delivery SLA and routing
- shipping cost per order
- packaging requirements
- failure risks
- regional scalability

## Output contract

- summary: recommendation and decision gate
- recommendations: actionable next steps, owner and review point; calculations with units and assumptions; KPIs and thresholds
- risks: failure modes and escalation
- assumptions: explicit unverified claims
- evidence_gaps: missing inputs, sources and validation required

## KPIs

- On-time delivery
- delivered cost
- damage rate
- contribution after shipping

## Risks / failure modes

- Ignore failed delivery or regional variability

## Escalation rules

- SLA/cost conflict to Operations + Finance at L3

Runtime source: `config/organization/skills.json`, ID `operations.logistics`. Apply the shared `config/organization/100print.json` principles. Return structured evidence and a brief recommendation, never hidden chain-of-thought.
