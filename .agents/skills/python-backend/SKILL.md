---
name: python-backend
description: Builds and reviews Python backend services for 100print with clear boundaries, robust error handling, and production-ready configuration.
---

# Python Backend

Use for FastAPI, services, integrations, business logic, background jobs, and Python application structure.

## Standards
- Prefer Python 3.12+ compatible code unless the repository pins another version.
- Separate configuration, transport/API, domain logic, persistence, and external integrations.
- Use typed interfaces and explicit data models.
- Keep secrets in environment variables or secret stores, never source code.
- Fail clearly: distinguish validation errors, dependency failures, authorization failures, and unexpected errors.
- Do not swallow exceptions silently.
- Make retry behavior explicit and idempotent where external systems are involved.
- Add health/readiness checks for long-running services.
- Preserve backward compatibility unless the task explicitly changes the contract.

## Testing
Cover critical business logic, authorization boundaries, idempotency, and failure paths. Prefer integration tests for API + database behavior that matters to users.

## Review checklist
Correctness, data integrity, auth, timeouts, retries, logging, config, migrations, and test coverage.
