---
name: legal
description: Legal / Contracts / Claims decisions for 100print.
---

## Purpose

- Support evidence-based 100print decisions: Legal / Contracts / Claims

## Trigger conditions

- договор
- юрид
- претензи
- copyright
- персональн.*данн
- возврат

## Required inputs

- Jurisdiction
- customer/partner terms
- claim evidence
- consent/data flow
- design rights

## Analysis checklist

- Review customer and supplier terms
- claims procedure
- refund/reprint logic
- uploaded design copyright/IP
- privacy touchpoints
- identify counsel questions

## Output contract

- summary: recommendation and decision gate
- recommendations: actionable next steps, owner and review point; calculations with units and assumptions; KPIs and thresholds
- risks: failure modes and escalation
- assumptions: explicit unverified claims
- evidence_gaps: missing inputs, sources and validation required

## KPIs

- Claim resolution time
- reprint/refund cost
- unresolved compliance issues

## Risks / failure modes

- Assuming jurisdiction
- definitive legal advice without counsel

## Escalation rules

- Qualified legal counsel required for jurisdiction-specific interpretation, disputed IP, personal data obligations or material contract liability; no legal clearance from this skill

Runtime source: `config/organization/skills.json`, ID `critic.legal`. Apply the shared `config/organization/100print.json` principles. Return structured evidence and a brief recommendation, never hidden chain-of-thought.
