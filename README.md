# AI Business Brain

Telegram-first MVP: `Telegram text → messages → memory_items(type=thought) → ACK`.
Python 3.12+, aiogram 3, FastAPI, SQLAlchemy/Alembic, PostgreSQL + pgvector.
PostgreSQL is the source of truth; Markdown/Obsidian will be a projection.

## Current VPS deployment

Checkout: `/opt/ceo-orchestrator/ai-business-brain` (separate worktree on `main`).
All application files, credentials, logs and the private PostgreSQL cluster are inside
this directory. Existing CEO Orchestrator code/services and other databases are untouched.
The issue's `/opt/ai-business-brain` path is superseded by the user's directory restriction.

API: `127.0.0.1:18090` (8090 was occupied). Private PostgreSQL: `127.0.0.1:55432`,
database/role `ai_brain`; administrative role `brain_admin` is used only for provisioning.
No Docker or system package installation. `.env` and `.runtime` are ignored by Git;
credentials are generated and stored with restrictive permissions.

**Stage 1 is incomplete:** API and private PostgreSQL are running as processes;
systemd units are validated but not installed/enabled because this execution has no
sudo access and writes outside this directory are prohibited. Reboot persistence is
not established. The bot requires its own `TELEGRAM_BOT_TOKEN`; live Telegram E2E has
not been verified. Issue #1 must remain open until these checks pass.

## Setup from a clean checkout

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/pip install --no-deps -e .
mkdir -p logs .runtime/packages
cd .runtime/packages
apt download postgresql-16 postgresql-client-16 postgresql-16-pgvector libpq5
for package in ./*.deb; do dpkg-deb -x "$package" ../postgres; done
cd ../..
.venv/bin/python scripts/bootstrap_local_postgres.py
.venv/bin/python scripts/provision_local_db.py
.venv/bin/alembic upgrade head
```

The private PostgreSQL bootstrap targets Ubuntu 24.04 amd64 and refuses to overwrite
an existing `.env` or cluster. It binds only localhost and uses SCRAM authentication.
With an externally provisioned, dedicated PostgreSQL database instead, copy
`.env.example` to `.env`, set `DATABASE_URL`, and have its administrator install the
`vector` extension before applying migrations. Never point migrations at another project DB.

## Verification

Run from the checkout:

```bash
.venv/bin/python scripts/check_db.py
.venv/bin/alembic current
.venv/bin/alembic check
.venv/bin/pytest -q                    # unit smoke tests; DB tests skipped
.venv/bin/python scripts/test_postgres.py  # real DB + handler tests, cleans up test rows
.venv/bin/ruff check app scripts tests migrations
systemd-analyze verify deploy/*.service
curl -fsS http://127.0.0.1:18090/health
curl -fsS http://127.0.0.1:18090/health/db
```

`/health` is liveness (200); `/health/db` checks PostgreSQL (200 or 503).
Integration tests cover persistence, thought creation, concurrent first messages,
redelivery, transaction rollback, immutable original text and handler ACK with committed IDs.
The ACK test uses a mocked Telegram transport and a real PostgreSQL database.

## Processes and logs

Start the private cluster after a manual shutdown/reboot:

```bash
export LD_LIBRARY_PATH="$PWD/.runtime/postgres/usr/lib/x86_64-linux-gnu"
.runtime/postgres/usr/lib/postgresql/16/bin/pg_ctl -D "$PWD/.runtime/pgdata" -l "$PWD/logs/postgres.log" start -w
```

Run API and bot in separate sessions:

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 18090
.venv/bin/python -m app.bot.main
```

Set a dedicated bot token in this checkout's `.env` (mode 600), then send the bot a
text and verify `ACK message_id=<UUID> memory_id=<UUID>`. Do not reuse a token
already polled by another service. JSON bot logs contain internal IDs, never message text.
Current background API log: `logs/api.log`; database log: `logs/postgres.log`.

## systemd handoff (administrator; requires separately authorized system writes)

`deploy/` contains three units for this exact checkout and user `ceoorch`:
private PostgreSQL → API (runs migrations before startup) → Telegram bot.
After stopping only these manually started Brain processes, an administrator can
install the units and enable them. Do not run a second PostgreSQL process on the
same data directory or a second poller for the same token.

```bash
sudo install -m 644 deploy/ai-business-brain-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ai-business-brain-postgres.service ai-business-brain-api.service ai-business-brain-bot.service
systemctl is-active ai-business-brain-postgres ai-business-brain-api ai-business-brain-bot
systemctl is-enabled ai-business-brain-postgres ai-business-brain-api ai-business-brain-bot
```

After an authorized reboot, repeat service, health and Telegram checks. Until then,
reboot survival remains unverified. Back up `.runtime/pgdata` using PostgreSQL tools
and protect `.env` separately; neither is included in Git.

Next stage: IntentRouter, DepartmentRouter, BrainProvider, ContextBuilder, hybrid
retrieval, department heads, logged handoffs and Council rounds 0–6. See `docs/`.
