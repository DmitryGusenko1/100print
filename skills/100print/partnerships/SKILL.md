---
name: partnerships
description: Partnerships / Franchise / Network Expansion decisions for 100print.
---

## Purpose

- Support evidence-based 100print decisions: Partnerships / Franchise / Network Expansion

## Trigger conditions

- нов.*точк
- нов.*типограф
- франшиз
- партнерств
- партнёрств
- расширен.*сет

## Required inputs

- Partner candidates
- territories
- economics
- quality audits
- SLA
- local demand

## Analysis checklist

- Score partner typographies on quality, SLA, economics, territory
- define expansion gates
- test franchise suitability vs partner network
- hybrid capacity

## Output contract

- summary: recommendation and decision gate
- recommendations: actionable next steps, owner and review point; calculations with units and assumptions; KPIs and thresholds
- risks: failure modes and escalation
- assumptions: explicit unverified claims
- evidence_gaps: missing inputs, sources and validation required

## KPIs

- Partner contribution
- SLA
- defects
- territory payback

## Risks / failure modes

- Expansion before process repeatability
- assumed exclusivity

## Escalation rules

- Expansion cash/territory conflicts require L3 Finance/Strategy/Operations; enterprise strategy may request Council

Runtime source: `config/organization/skills.json`, ID `operations.partnerships`. Apply the shared `config/organization/100print.json` principles. Return structured evidence and a brief recommendation, never hidden chain-of-thought.
