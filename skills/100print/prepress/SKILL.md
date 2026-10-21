---
name: prepress
description: Quality Control / Prepress decisions for 100print.
---

## Purpose

- Support evidence-based 100print decisions: Quality Control / Prepress

## Trigger conditions

- макет
- prepress
- preflight
- dpi
- вылет
- до печати
- брак

## Required inputs

- Actual file metadata
- product/process spec
- printer profile
- proof approval

## Analysis checklist

- Check file readiness
- bleed and safe margins against process spec
- effective DPI at final size
- color space/profile and fonts
- preflight
- defect prevention
- trace rework
- define acceptance criteria before release

## Output contract

- summary: recommendation and decision gate
- recommendations: actionable next steps, owner and review point; calculations with units and assumptions; KPIs and thresholds
- risks: failure modes and escalation
- assumptions: explicit unverified claims
- evidence_gaps: missing inputs, sources and validation required

## KPIs

- First-pass yield
- rework cost
- defect rate
- preflight rejection rate

## Risks / failure modes

- Universal DPI or bleed guessed without process
- visual inspection cannot certify file metadata

## Escalation rules

- Missing file/spec blocks print-ready claim; unresolved color/IP issues escalate to Operations or Legal

Runtime source: `config/organization/skills.json`, ID `operations.prepress`. Apply the shared `config/organization/100print.json` principles. Return structured evidence and a brief recommendation, never hidden chain-of-thought.
