# CEO Orchestrator

Isolated durable worker for GitHub issue #3. Root: `/opt/ceo-orchestrator`.
Runs as Linux user `ceoorch` using its own `.venv`, `.env`, database, logs and data.
No HTTP server, Redis, nginx changes, external API or paid provider required.

## Running installation

`ceo-orchestrator.service` is enabled at boot and uses `Restart=always`, `RestartSec=5`.
Its existing unit is preserved; a reference copy is in `config/systemd/`.
The worker starts its own PostgreSQL cluster on startup if necessary. All cluster
binaries, data, socket, and logs live inside this project. PostgreSQL accepts only
the Unix socket `data/pgsocket/.s.PGSQL.55433`; **no TCP ports are opened**.
The socket's PostgreSQL port identifier is 55433. Database and application role:
`ceo_orchestrator`. Application role has no superuser/createdb/createrole privileges.
Administrative bootstrap roles cannot log in. `vector` extension is installed;
vector retrieval is deferred to the future brain provider.

```bash
cd /opt/ceo-orchestrator
systemctl status ceo-orchestrator.service --no-pager
systemctl is-enabled ceo-orchestrator.service
.venv/bin/python scripts/tasks.py status
tail -50 logs/orchestrator.log
.venv/bin/python scripts/tasks.py add --payload '{"message":"hello"}'
# Copy the returned UUID:
.venv/bin/python scripts/tasks.py show --id UUID
```

A test task becomes `new -> processing -> done`, with its JSON result in `tasks`
and a durable `agent_runs` audit row. `echo` supports an optional `delay_seconds`
(0–60) to exercise recovery. An unsupported type retries then fails explicitly.

## Operation and recovery

The default poll interval is 2 seconds (`CEO_POLL_SECONDS` in the private `.env`).
A heartbeat is committed each loop independently of the handler thread. One enabled
local agent is selected and recorded with a routing decision. A session advisory
lock enforces one worker. Claims use `FOR UPDATE SKIP LOCKED` and commit before
handler execution. Results and run completion commit together.

On startup interrupted processing tasks are recovered immediately. Maintenance every
60 seconds retries stale tasks (default 300 seconds), reviews pending handoffs and
creates deduplicated follow-ups. The active local task is excluded from stale recovery.
Failed handlers retry with exponential delay, capped at 300 seconds, and at most
`max_attempts` (default 3). Exhausted tasks become `failed`. Delivery is **at least once**;
future handlers with external effects must use task UUIDs as idempotency keys.

Hourly, tasks with no progress for an hour receive one deduplicated follow-up.
Daily, `reports` records status counts, work completed in the last day, stuck/decision
items and available automatic actions. Scheduler timestamps persist across restarts.
The built-in follow-up handler records a decision requirement; no external messages
are sent automatically. All queue data is in this private database.

The main loop exits on database/lock loss, allowing systemd to restart it and start
PostgreSQL again. PostgreSQL runs under the same unit once started by the worker;
there is no dependency on another project's database unit. Do not reboot this shared
VPS just to test this service. Boot enablement and a stopped private database startup
are verified without interrupting other projects.

`logs/orchestrator.log` rotates at 5 MB with three backups. PostgreSQL logs use
`logs/postgres.log`; database and logs need normal disk monitoring and backups.

## Brain and Codex adapters

`app/providers.py` defines `BrainProvider` and a local deterministic implementation.
A real provider can replace it without coupling the queue to an API or CLI.
`app/codex_runner.py` is a separate, currently unconnected process adapter. It
requires an executable installed inside this project, an explicit timeout (max 300s),
captures stdout/stderr (returned output capped at 1 MiB each), returns a JSON wrapper,
and logs start/completion. It invokes the installed executable with prompt on stdin;
a CLI-specific executable wrapper can supply provider flags later.

By default only `jobs/workspaces/**` is accepted. Paths are resolved before checking,
including symlinks. Additional workdirs require explicit administrator whitelist
configuration in the adapter constructor. `bubblewrap` provides an offline mount
namespace exposing only the selected workdir, executable, and read-only system runtime;
project secrets, other projects and host home directories are absent. This VPS currently rejects creation of user namespaces (`Permission denied`).
Failure to create the sandbox fails the run; there is no unsandboxed fallback. Provider authentication
and online connectivity must be designed explicitly before enabling a real provider.

## Reproduce a fresh installation

The target must be this exact directory, owned by the dedicated `ceoorch` account.
User creation and installation of the reference systemd unit on a new host require
an administrator. On this VPS both user and unit already existed and were reused
only for this project. Do not run these commands in another project's directory.

```bash
python3 -m venv /opt/ceo-orchestrator/.venv
.venv/bin/pip install -r requirements.txt
mkdir -p agents departments jobs/workspaces memory logs data config scripts
# Ubuntu 24.04 / PostgreSQL 16; downloads/extracts packages locally, no apt install:
.venv/bin/python scripts/prepare_postgres.py
.venv/bin/python scripts/bootstrap_db.py
# Administrator, fresh host only:
# install -m 644 config/systemd/ceo-orchestrator.service /etc/systemd/system/
# systemctl daemon-reload
# systemctl enable --now ceo-orchestrator.service
```

Bootstrap refuses an existing cluster or `.env`. It creates a fresh random secret
with mode 0600, a dedicated nonprivileged application role/database and pgvector.
Never commit `.env`, `.codex`, `.config`, database files, logs or other credentials.
On this installation PostgreSQL binaries were copied from an existing distribution
inside this same project; no credentials, virtualenv or database were reused.

## Verification

```bash
.venv/bin/python -m unittest tests.test_runtime -v
```

These live checks create isolated test tasks in our database and deliberately kill
**only** the own service's MainPID to verify automatic restart and durable recovery.
They also check retry exhaustion, result/audit persistence, heartbeat freshness,
scheduler/handoff deduplication, reports, nonprivileged DB role, and adapter path policy.
Expected `failed` test tasks remain as evidence. No other service is stopped or restarted.
