---
name: analytics
description: Data Analytics / Experiment Design decisions for 100print.
---

## Purpose

- Support evidence-based 100print decisions: Data Analytics / Experiment Design

## Trigger conditions

- метрик
- эксперимент
- experiment
- аналитик
- атрибуц
- статист

## Required inputs

- Hypothesis
- baseline
- unit of randomization
- event quality
- sample size
- decision cost

## Analysis checklist

- Specify hypothesis and baseline
- primary success criterion and guardrails
- attribution limits
- confidence/uncertainty
- flag insufficient sample size
- predeclare stop/continue rules
- inspect novelty and seasonality

## Output contract

- summary: recommendation and decision gate
- recommendations: actionable next steps, owner and review point; calculations with units and assumptions; KPIs and thresholds
- risks: failure modes and escalation
- assumptions: explicit unverified claims
- evidence_gaps: missing inputs, sources and validation required

## KPIs

- Decision quality
- event completeness
- experiment power
- incremental contribution

## Risks / failure modes

- Peeking
- multiple comparisons
- underpowered tests
- correlation claimed as causality

## Escalation rules

- Insufficient data yields provisional recommendation; financial exposure adds Finance

Runtime source: `config/organization/skills.json`, ID `strategy.analytics`. Apply the shared `config/organization/100print.json` principles. Return structured evidence and a brief recommendation, never hidden chain-of-thought.
