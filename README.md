# AI Business Brain

Telegram-first AI business brain with PostgreSQL/pgvector as the source of truth.

## Vertical slice

Current MVP path:

`Telegram text -> messages -> memory_items(type=thought) -> ACK with internal IDs`.

## Local setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env
.venv/bin/alembic upgrade head
.venv/bin/pytest -q
.venv/bin/python scripts/check_db.py
```

Run API:

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8090
```

Checks:

```bash
curl -fsS http://127.0.0.1:8090/health
curl -fsS http://127.0.0.1:8090/health/db
```

Run Telegram bot:

```bash
.venv/bin/python -m app.bot.main
```

A text message is persisted in `messages`, projected to a `memory_items` record with
`type=thought`, and acknowledged with both internal IDs.

## VPS target

- application: `/opt/ai-business-brain`
- database: `ai_brain`
- API service: `ai-business-brain-api.service`
- bot service: `ai-business-brain-bot.service`
- Docker is not used.

Before starting the bot, verify there is no other polling process using the same Telegram token.
