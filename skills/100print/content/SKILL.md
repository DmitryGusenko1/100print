---
name: content
description: Content Strategy decisions for 100print.
---

## Purpose

- Support evidence-based 100print decisions: Content Strategy

## Trigger conditions

- контент
- content
- telegram
- телеграм
- тем.*стат

## Required inputs

- Use cases
- funnel
- topic demand
- channel performance
- order attribution

## Analysis checklist

- Use-case education and demand generation
- topic clusters
- product-led content
- Telegram/short-form/SEO formats
- CTA mapping
- content-to-order funnel

## Output contract

- summary: recommendation and decision gate
- recommendations: actionable next steps, owner and review point; calculations with units and assumptions; KPIs and thresholds
- risks: failure modes and escalation
- assumptions: explicit unverified claims
- evidence_gaps: missing inputs, sources and validation required

## KPIs

- Qualified leads
- assisted/incremental order contribution
- CTA conversion

## Risks / failure modes

- Vanity views
- copied competitor content

## Escalation rules

- Weak attribution to Analytics; pricing claims to Finance

Runtime source: `config/organization/skills.json`, ID `marketing.content`. Apply the shared `config/organization/100print.json` principles. Return structured evidence and a brief recommendation, never hidden chain-of-thought.
