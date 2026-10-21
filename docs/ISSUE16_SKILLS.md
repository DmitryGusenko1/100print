# Specialist library for 100print

Runtime registry: `config/organization/skills.json` (45 existing + 17 narrow skills).
Readable specs: `skills/100print/*/SKILL.md`. Shared project preset:
`config/organization/100print.json`. Executable examples: `config/organization/examples.json`.

First pack: pricing, product, production, prepress, retention, growth, analytics,
procurement. Secondary pack: SEO, research/JTBD, logistics, legal, content, UX,
partnerships, competitive intelligence, PMO. Every spec defines purpose, triggers,
required evidence, checklist, output contract, KPIs, failure modes and escalation.

## Routing map

Finance owns pricing and procurement; Strategy owns product, research, analytics,
UX and competitive intelligence; Operations owns production, prepress, logistics,
partnerships and PMO; Sales owns retention; Marketing owns growth and content;
SEO owns search optimization; Critic owns legal triage. Existing specialists and
heads remain the execution roles; skills extend their authorized capabilities.

- L1: one selected skill and specialist, including simple metatag requests.
- L2: selected specialist(s) within one function, head synthesis, independent Critic.
- L3: two to four functions, selected skills, departmental heads, handoffs and Critic.
- L4: explicit Council or explicitly requested L4; retains existing council protocol.

Equipment decisions compose procurement, pricing and production. Network expansion
composes partnerships, pricing and product; opening a point does not automatically
invoke Council. Other matches compose by trigger; requests spanning more than four
functions require explicit L4 or narrowing, never silently drop functions.
Explicit `payload.skill_id` or `payload.skill_ids` takes precedence over text
matching, with department permission validation. L1 rejects multiple skills.
Existing generic routes remain fallbacks. Text routing is conservative keyword
matching, not semantic classification: use explicit IDs for ambiguous requests.

Specs and presets are supplied to the production provider with structured schemas.
Unknown inputs remain evidence gaps; calculations require units and assumptions.
Legal triage flags when qualified counsel is required and cannot grant clearance.
No universal prepress DPI/bleed threshold is assumed without a process specification.

Full structured artifacts persist through PostgresStore organization_steps and
conversation project memory; no hidden chain-of-thought is requested or stored.
The existing Telegram executive renderer presents concise public business fields.
Skills provide recommendations, not automatic authorization for purchases, campaigns,
contracts, customer outreach or printing.

## Verification

`.venv/bin/python -m unittest tests.test_specialist_skills -v` executes all ten
issue scenarios, checks actual specialist invocation, explicit composition,
permissions, first/secondary coverage and isolated L1 invocation of all 17 skills.
Full regression: `.venv/bin/python -m unittest discover -s tests -t . -q`.
Production acceptance: `scripts/verify_skills16.py` verifies all 17 DB registrations
and a real Codex L2 prepress task with persistent skill/head/Critic artifacts.
Production acceptance does not send Telegram messages or approve business decisions.
