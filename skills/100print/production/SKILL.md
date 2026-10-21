---
name: production
description: Production Planning decisions for 100print.
---

## Purpose

- Support evidence-based 100print decisions: Production Planning

## Trigger conditions

- производств
- мощност
- узкое место
- bottleneck
- очеред
- заказ.*партн

## Required inputs

- Order mix
- machine calendars
- setup/run times
- partner capacity
- due dates

## Analysis checklist

- Calculate effective capacity and utilization
- locate bottleneck
- schedule queues by due date and setup
- route orders between own/partner
- account for SLA and load balancing

## Output contract

- summary: recommendation and decision gate
- recommendations: actionable next steps, owner and review point; calculations with units and assumptions; KPIs and thresholds
- risks: failure modes and escalation
- assumptions: explicit unverified claims
- evidence_gaps: missing inputs, sources and validation required

## KPIs

- On-time SLA
- queue age
- bottleneck utilization
- throughput
- contribution/hour

## Risks / failure modes

- 100% utilization inflates queues
- ignore setup or partner reliability

## Escalation rules

- Escalate SLA breach to Operations; cost tradeoff adds pricing at L3

Runtime source: `config/organization/skills.json`, ID `operations.production`. Apply the shared `config/organization/100print.json` principles. Return structured evidence and a brief recommendation, never hidden chain-of-thought.
