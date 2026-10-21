# TASKS

## NOW

- [x] Создать Python package structure
- [x] Config через pydantic-settings
- [x] Structured JSON bot event logging
- [x] FastAPI /health
- [x] PostgreSQL connection code
- [x] Alembic
- [x] Initial DB models
- [x] Telegram text ingestion
- [x] Telegram text -> message -> thought -> ACK vertical slice
- [x] pytest smoke tests prepared
- [x] Apply migrations 0001 and 0002 on private VPS PostgreSQL
- [x] Verify pgvector on private VPS PostgreSQL
- [x] Run pytest on VPS: 7 passed, including real PostgreSQL integration tests
- [x] Fix recursive pytest discovery of scripts/test_postgres.py and rerun tests
- [ ] Start systemd API service
- [ ] Start systemd bot service
- [ ] Verify Telegram -> PostgreSQL -> ACK on VPS
- [ ] Verify services survive reboot

## VPS acceptance status (2026-10-21)

- [x] Isolated Python 3.12 venv, private ai_brain DB, .env (600), logs
- [x] /health and /health/db return HTTP 200 on localhost:18090
- [x] Alembic schema matches all 13 ORM tables
- [x] systemd unit syntax verified; installation is blocked by execution scope/privileges
- [ ] Dedicated Telegram bot token supplied and live E2E verified
- [ ] systemd installation/enabling by authorized administrator
- [ ] Reboot verification
- [x] Push verified changes to main (ba1e53a; origin confirmed)

Issue #1 remains open; do not report stage 1 as complete.

## NEXT

- [ ] IntentRouter
- [ ] DepartmentRouter
- [ ] BrainProvider abstraction
- [ ] ContextBuilder
- [ ] Hybrid retrieval
- [ ] Department heads
- [ ] Council rounds
- [ ] Voice transcription
- [ ] Markdown / Obsidian export
