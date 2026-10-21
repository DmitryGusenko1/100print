---
name: seo
description: SEO decisions for 100print.
---

## Purpose

- Support evidence-based 100print decisions: SEO

## Trigger conditions

- seo
- сео
- семантик
- органическ
- поисков
- метатег

## Required inputs

- Search demand
- query intent
- index/crawl data
- location
- leads and revenue

## Analysis checklist

- Build semantic clusters
- commercial vs informational intent
- landing mapping
- technical crawl checks
- local SEO
- content SEO
- connect qualified organic visits to leads and revenue

## Output contract

- summary: recommendation and decision gate
- recommendations: actionable next steps, owner and review point; calculations with units and assumptions; KPIs and thresholds
- risks: failure modes and escalation
- assumptions: explicit unverified claims
- evidence_gaps: missing inputs, sources and validation required

## KPIs

- Qualified organic traffic
- leads
- revenue contribution

## Risks / failure modes

- Rankings without sales
- cannibalization
- unsupported crawl claims

## Escalation rules

- Technical blockers to Operations; weak attribution to Analytics

Runtime source: `config/organization/skills.json`, ID `seo.seo`. Apply the shared `config/organization/100print.json` principles. Return structured evidence and a brief recommendation, never hidden chain-of-thought.
