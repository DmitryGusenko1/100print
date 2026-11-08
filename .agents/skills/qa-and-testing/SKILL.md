---
name: qa-and-testing
description: Verifies 100print changes with risk-based automated and manual testing before they are called complete.
---

# QA and Testing

Use after implementation and during reviews.

## Principle
Test the behavior the user depends on, not just internal functions.

## Priority order
1. Critical user path.
2. Authorization and isolation.
3. Data integrity and idempotency.
4. Failure recovery.
5. Regression risk.
6. Edge cases.

## For shared memory
Verify at minimum:
- same Telegram account can continue across devices;
- restart preserves history and selected project;
- duplicate delivery creates no duplicate message;
- unauthorized Telegram ID is rejected;
- invalid API key is rejected;
- one owner cannot access another owner's project by ID;
- AI failure preserves inbound data and creates no fake answer;
- migrations work on a clean test database;
- backup restore is actually tested.

## Reporting
Separate: passed, failed, not run. Never convert “not run” into “passed”.
