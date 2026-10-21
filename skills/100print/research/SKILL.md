---
name: research
description: Customer Research / JTBD decisions for 100print.
---

## Purpose

- Support evidence-based 100print decisions: Customer Research / JTBD

## Trigger conditions

- jtbd
- интервью
- customer research
- исследован.*клиент
- готовност.*плат

## Required inputs

- Interview transcripts
- recruitment criteria
- observed purchases
- alternatives

## Analysis checklist

- Identify jobs, triggers, barriers and alternatives
- distinguish stated willingness to pay from actual payment
- synthesize interviews with source IDs
- validate hypotheses without excluding audiences prematurely

## Output contract

- summary: recommendation and decision gate
- recommendations: actionable next steps, owner and review point; calculations with units and assumptions; KPIs and thresholds
- risks: failure modes and escalation
- assumptions: explicit unverified claims
- evidence_gaps: missing inputs, sources and validation required

## KPIs

- Validated hypotheses
- paid validation
- interview coverage

## Risks / failure modes

- Leading questions
- convenience sample
- invented quotes

## Escalation rules

- Conflicting evidence requires Product review; do not declare market validation from small sample

Runtime source: `config/organization/skills.json`, ID `strategy.research`. Apply the shared `config/organization/100print.json` principles. Return structured evidence and a brief recommendation, never hidden chain-of-thought.
