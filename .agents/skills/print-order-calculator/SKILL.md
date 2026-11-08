---
name: print-order-calculator
description: Calculates and validates printing order economics for 100print: materials, production, finishing, waste, margin, and customer price.
---

# Print Order Calculator

Use for quotes, unit economics, price tables, and estimator logic.

## Required input model
Product, finished size, material, print sides/colors, quantity, print method, finishing, deadline, and delivery where relevant.

## Cost structure
Calculate separately:
- material consumption;
- setup/makeready;
- machine run;
- ink/toner/click or equivalent;
- finishing;
- labor where separately modeled;
- waste/spoilage;
- outsourced operations;
- packaging/logistics;
- taxes/fees if applicable.

Then calculate full cost, target margin/markup according to company rules, total customer price, and unit price.

## Guardrails
- Never hide an assumed parameter.
- Do not confuse markup with gross margin.
- Round only at the defined commercial stage, not throughout intermediate calculations.
- Preserve a traceable breakdown so a manager can audit the quote.
- Flag orders where capacity, deadline, or margin falls outside policy.
