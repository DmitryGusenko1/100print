# CEO Orchestrator

Isolated durable worker and AI organization for GitHub issues #3 and #5. Root: `/opt/ceo-orchestrator`.
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

## AI organization (issue #5)

The organization has CEO / Chief of Staff, seven heads (Strategy, Marketing,
SEO, Sales, Finance, Operations, Chief Critic / Risk), and three specialists per
head. The 29 role definitions are in `config/organization/roles.json`; the 45
versioned skills and their schemas, instructions and test cases are in
`config/organization/skills.json`. Skills are capabilities, not agents. Startup
validates and synchronizes the catalog to `skills_registry`, `organization_roles`,
`agents` and `departments` in the private `ceo_orchestrator` database.
Run `python config/organization/build_catalog.py` to rebuild the checked-in catalog.

Skills v1: Strategy: problem framing, strategic options, prioritization, business
model analysis, scenario analysis, decision memo. Marketing: ICP / segmentation,
positioning, offer analysis, channel strategy, campaign planning, competitor
analysis. SEO: semantic core planning, keyword clustering, search intent, content
brief, on-page audit, technical SEO checklist, internal linking, competitor SERP
analysis. Sales: funnel analysis, sales process, objection analysis, offer-to-close
logic, KPI / conversion diagnostics, sales playbook. Finance: unit economics,
CAC/LTV, margin, break-even, ROI, scenario model, budget sanity check. Operations:
process decomposition, resource plan, bottleneck analysis, execution plan,
owner/deadline assignment, risk dependencies. Critic: assumption attack,
contradiction detection, pre-mortem, failure modes, evidence gap, alternative
hypothesis.

`IntentRouter`, `DepartmentRouter` and `ComplexityRouter` accept explicit commands
and infer departments from labels/title/problem. L1 invokes one specialist/skill;
L2 invokes a head and its specialists; L3 invokes multiple heads with persisted
request/receipt handoffs and conflict agreement; L4 invokes all seven heads.
Council saves rounds 0–6: context, independent positions, mutual criticism,
disagreement map, focused resolution and departmental acknowledgments, Critic
challenge, Chief of Staff synthesis. Final JSON contains decision, why,
alternatives_rejected, risks, assumptions, action_plan, KPI, next_decision_point.
Blocking challenges, unresolved conflicts or remaining departmental objections
set `requires_decision`; no business spending or execution is authorized.

Every completed step is committed to `organization_steps`; handoffs also appear
in `organization_handoffs`. Queue recovery reuses completed steps by task UUID,
step key and input fingerprint. Changed context, provider identity or catalog
fails closed instead of mixing incompatible runs. Failed/invalid provider output
is not checkpointed. Use a new task for revised inputs.

### GitHub business commands

The running worker polls open issues in `DmitryGusenko1/100print` every minute.
Only issues authored by `DmitryGusenko1` are accepted. Add `ai-task`, a department
label, or `council`, or start the body with exactly `CEO-AI-TASK` followed by a
newline and a JSON object:

```text
CEO-AI-TASK
{"type":"ai-task","level":"L3","departments":["marketing","finance"],"problem":"Evaluate acquisition experiment","goal":"Validate contribution","constraints":["Budget 1000"],"criteria":["Positive contribution"],"facts":[],"assumptions":[]}
```

For L1 use `level: L1`, one department and e.g. `skill_id: seo.02`. Omit level to
select L1 for a skill, L2 for one department or L3 for multiple departments.
`type: council` selects L4. Operations and critic labels are also supported.
Unknown fields/types are rejected. Ordinary development issues are not business
commands. Intake deduplicates by repository/issue; results are posted back with a
stable comment marker and retried after restart. Completed issues are not rerun;
create a new issue for a new analysis. `CEO_GITHUB_AI_ENABLED=0` disables polling.

The default `CEO_BRAIN_MODE=deterministic` is explicitly a workflow demonstration,
with unverified assumptions and blocking evidence gaps. It is not live AI advice.
`production` uses the separate `ProductionBrainProvider` strict JSON adapter,
configured with `CEO_BRAIN_EXECUTABLE`, `CEO_BRAIN_WORKDIR` and
`CEO_BRAIN_IDENTITY`. The executable is an installed project-local wrapper that
accepts a JSON request on stdin and returns a schema-valid JSON object on stdout.
The existing offline sandbox restrictions apply; unavailable sandbox/credentials
fail explicitly without mock fallback. Another provider can implement `respond`
without changing any role, skill, router or council code.

```bash
.venv/bin/python -m unittest tests.test_organization -v
# Explicit live tests; only this project's database/service:
.venv/bin/python -m unittest tests.test_organization_postgres tests.test_runtime -v
```

Tests cover all skills, L1–L4, Marketing/Finance conflict, Critic challenge,
round persistence, fresh-store restart recovery, invalid output, routing and
allowlist checks. Runtime checks exercise actual service crash recovery. Domain
isolation tests prohibit file writes, network connections and child processes;
all live checks use only this project's Unix socket and service MainPID.

## ChatGPT project memory (#6)

The authenticated MCP endpoint `/mcp/` and HTTP adapter `/tools/{method}` use
`ceo_orchestrator` for project `100print` only. Conversations, typed memory,
analysis queue links and organization checkpoints survive service restarts.
The existing worker supervises the localhost API on port 8096 when
`config/chatgpt.env` supplies `CEO_CHATGPT_TOKEN` (32+ characters).

See [project instructions](docs/CHATGPT_PROJECT_INSTRUCTIONS.md) and
[tool setup, transport and production limitations](docs/CHATGPT_TOOL_SETUP.md).
ChatGPT account connection, trusted HTTPS/OAuth gateway and Telegram credentials
are deployment prerequisites. The default deterministic provider is a labelled
workflow demonstration; it must not be presented as production business advice.

### GitHub worker progress (issue #7)

The GitHub executor in `app/github_worker.py` records structured JSON progress
and a heartbeat every 30 seconds in `logs/github_worker.log`, including while
Codex is running. Inspect progress without reading process listings:

```sh
/opt/ceo-orchestrator/scripts/progress.py
# issue #7 | 60% | integration | current: memory bridge tests
watch -n 2 /opt/ceo-orchestrator/scripts/progress.py
```

The executor reports actual stage changes and subtasks with:

```sh
python3 scripts/progress.py --issue 7 --stage integration \
  --current 'memory bridge tests' --action 'connected memory bridge'
```

Stages are `analysis` (10%), `planning` (25%), `implementation` (40%),
`integration` (60%), `tests` (75%), `commit/push` (90%), and `done` (100%).
The worker sets `done` after a successful executor exit. Failed or timed out
execution retains its actual stage and records the failure in `last_action`.
Percentages never increase merely because time passes. The executor prompt
requires reporting each stage and updating the current subtask as work changes.

`data/progress.json` stores `issue_number`, `stage`, `percent`, `started_at`,
`updated_at`, `last_action`, `current_subtask`, and nullable `eta_optional`.
Updates use a process lock, fsync and atomic replacement; state survives worker
restarts, and the same issue resumes at its saved stage. Backward stage changes
are rejected. `--eta` supplies an optional estimate. Heartbeats refresh
`updated_at` without changing the stage, start time or last substantive action.
A new issue starts at 10%; completed progress remains visible until then.
If the worker stops, the timestamp stops advancing; inspect the JSON or log to
check freshness. No GitHub comment is required for heartbeat visibility.

Run isolated verification with `python3 -m unittest tests.test_progress -v`.
Deploy worker changes by restarting only `ceo-github-worker.service` after its
current executor has finished (restarting during an issue interrupts that run).
