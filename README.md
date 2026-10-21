# CEO Orchestrator

Isolated durable worker and AI organization for GitHub issues #3 and #5. Root: `/opt/ceo-orchestrator`.
Runs as Linux user `ceoorch` using its own `.venv`, `.env`, database, logs and data.
The queue runs locally; production business analysis requires the authenticated Codex service.

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

Business inference defaults to `ProductionCodexProvider` (`production-codex-v1`),
using the installed `/usr/bin/codex` and only ceoorch's existing authentication.
All API, GitHub bridge and Telegram analysis tasks use this same queue provider.
The old offline `CodexRunner` remains a separate legacy adapter and is not used
for production inference.

Codex runs only as `ceoorch`, with exact resolved workdir allowlisting for
`/opt/ceo-orchestrator` and its owned `ai-business-brain` directory. The optional
`/opt/ai-business-brain` alias is accepted only when resolving into this project.
Nested directories, foreign directories and symlink escapes are rejected.
Only PATH, HOME, CODEX_HOME and LANG enter the subprocess environment; application,
DB and Telegram secrets are not inherited. User config, rules, hooks, plugins,
apps, shell tools, images, browser, memory and agent tools are disabled. Project
instructions are disabled. Inference uses supplied context only, with no tools,
read-only sandbox policy, no approval prompts and no persistent CLI sessions.
Configuration flags follow the [official Codex reference](https://developers.openai.com/codex/config-reference).

`CEO_BRAIN_MODE=production` is the default. Optional project `.env` settings:
`CEO_BRAIN_MODEL=gpt-6.1-sol`, `CEO_BRAIN_WORKDIR=/opt/ceo-orchestrator`,
`CEO_BRAIN_TIMEOUT=180` (maximum 300 seconds per call). Four concurrent inference
calls maximum; independent specialist/department outputs retain stable ordering
and individual durable checkpoints. No CLI wrapper or new API key is required.
Timeout kills the process group. stdout/stderr are captured with a 1 MiB read
limit each and discarded; only validated structured final artifacts are stored.
Nonzero exit, timeout, absent/oversized output, invalid JSON or schema mismatch
fails closed. There is no mock fallback. CLI credentials and subscription/network
availability remain operational dependencies.

Task results and checkpoint metadata include provider, model, protocol and
`demonstration=false`; checkpoint fingerprints include model metadata to prevent
mixing models after recovery. Departmental positions and analytical briefs include
position, evidence, assumptions, alternatives, arguments for/against, risks,
confidence, objections, recommendation and change conditions. Critic adds challenges,
evidence gaps, blocking and alternative hypotheses. Council returns independent
positions, conflict map, critique and synthesis. Only structured analytical artifacts
are persisted; no hidden chain-of-thought is retained.

`CEO_BRAIN_MODE=deterministic` is rejected by the live runtime. Tests inject the
mock provider directly; never configure this mode on the live worker.

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

Production is configured as described above. `DeterministicBrainProvider` is
retained for explicit mock tests only; it returns zero confidence and labelled
demonstration results. Other providers can implement `respond` without changing
roles, skills, routing or council logic.

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
are deployment prerequisites. Analysis uses the shared production Codex provider. Telegram delivery still requires
its own token and explicit chat allowlist.

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

## Live GitHub → VPS bridge (#8)

Permanent bridge thread: **https://github.com/DmitryGusenko1/100print/issues/8**.
`ceo-github-watcher.service` polls its comments every 10 seconds, including when
this issue is closed. Only comments authored by `DmitryGusenko1` are accepted;
the GitHub plugin must publish using that account. The repository and issue are
hardcoded allowlists. Post a comment using this exact format (message may span lines):

```text
CHATGPT_IN
session=voice-100print-2026-10-21
message=Стоит ли снижать цену? Сравни альтернативы, риски и рекомендации.
```

Replies use:

```text
CHATGPT_OUT
session=voice-100print-2026-10-21
task_id=<UUID>
result=<JSON with recommendation, alternatives with for/against, risks, critic, confidence>
```

Keep the same session across turns to resume a conversation. Every new comment
is a new request; edits to processed comments are not re-executed. Inputs,
context retrieval, task links, outputs and specialist/Critic/Council artifacts
use the existing `ceo_orchestrator` project memory. Automatic L1–L4 routing and
the queue worker are reused. Responses explicitly identify the provider and
`demonstration`; the live production Codex provider returns structured business analysis.
Missing business metrics remain explicit evidence gaps, rather than invented facts.

`chatgpt_bridge_state` stores the last processed comment ID;
`chatgpt_bridge_comments` durably links each input to its task and reply.
Intake commits before advancing the cursor. Failed tasks receive an explicit
failed result. Pending replies are retried independently of new input. A DB
advisory lock prevents concurrent watchers. A stable HTML task marker recovers
from a crash after GitHub POST but before committing delivery. GitHub does not
provide an idempotency key for comments; ambiguous POST outcomes rely on the
reply becoming visible on a subsequent paginated read before retry.

The existing watcher unit is enabled at boot with `Restart=always`; a reference
copy is in `config/systemd/ceo-github-watcher.service`. To deploy code changes,
restart **only** that watcher (or signal its own MainPID to let systemd recover).
No new credentials, public listener or custom MCP connection is needed.

```sh
.venv/bin/python -m unittest tests.test_github_bridge -v
systemctl status ceo-github-watcher.service --no-pager
systemctl is-enabled ceo-github-watcher.service
```

In ChatGPT, ask the connected GitHub plugin to add the `CHATGPT_IN` comment,
then read new comments on issue #8 for the matching `CHATGPT_OUT` session.
This is a polling transport: Voice must invoke the plugin to read the reply;
it does not push audio or automatically wake ChatGPT.

Verified live transport on 2026-10-21: [input](https://github.com/DmitryGusenko1/100print/issues/8#issuecomment-6315318611) → PostgreSQL
→ L4 Council + Critic → [reply](https://github.com/DmitryGusenko1/100print/issues/8#issuecomment-6315337310).
Task `d70e0ed3-f889-4c01-a035-e65547e468de` finished with provider `deterministic-v1`; this
verifies transport and artifact persistence, not production AI reasoning.
The watcher uses pagination compatible with the VPS version of `gh`.

### Production verification (#9, 2026-10-21)

Live [production input](https://github.com/DmitryGusenko1/100print/issues/8#issuecomment-6315465409)
→ task `14c7501c-c251-4b16-ba92-e155fada3593` →
[production CHATGPT_OUT](https://github.com/DmitryGusenko1/100print/issues/8#issuecomment-6315696202).
Provider `production-codex-v1`, model `gpt-6.1-sol`, `demonstration=false`, confidence
0.85. Marketing, Sales, Finance and Critic produced independent initial positions;
55 production calls yielded 73 durable checkpoints and 66 project-memory artifacts.
Five checkpoints survived an intentional own-worker crash unchanged; the task
resumed and completed on attempt 2. The actual authenticated localhost #6 API
returned the identical persisted result.

The recommendation preserves baseline prices pending an evidence-based controlled
test. It distinguishes the +17.65% volume required to preserve revenue after a
15% discount from the contribution-profit threshold: at an **assumed** 40% initial
contribution margin, +60% volume is needed before additional costs. Growth versus
margin/cash is recorded as a tradeoff; the conflict map is honestly empty because
the departments' recommendations align. Critic challenges and alternative
hypotheses remain in the result; shared recommendations do not remove evidence gaps.

Recheck persisted production evidence without creating another inference task:

```sh
.venv/bin/python scripts/verify_production.py
.venv/bin/python -m unittest discover -s tests -t . -q
```

The test suite explicitly injects mocks for fixture analysis and tests the live
queue/restarts separately. Production verification uses real Codex outputs.
Limitations: no verified business cost/demand metrics were supplied; confidence
is a model assessment, not measured forecast accuracy. Department independence
means separate context-isolated initial calls using the same model, not model
diversity. CLI latency, authorization and upstream availability affect execution.
Telegram's shared-provider path is tested, but live Telegram delivery remains
unverified because the project's token and chat allowlist are absent.

### FINAL #10: production + Voice

Bridge #8 и API #6 используют ProductionCodexProvider (Codex CLI под ceoorch),
структурированные JSON-контракты, timeout и fail-closed без deterministic fallback.
Постоянный bridge теперь поддерживает `CONTEXT` и `DECISION` в поле message:
контекст и подтверждённые пользователем решения доступны через тот же GitHub plugin.
Короткий текст для Project Instructions: [инструкции](docs/CHATGPT_PROJECT_INSTRUCTIONS.md).
Контракт и одна фраза для нового Voice-чата: [Voice bridge](docs/VOICE_BRIDGE.md).

Проверка нового acceptance: `.venv/bin/python scripts/verify_production.py --session issue10-acceptance-v2 --snapshot data/issue10-v2-before-restart.json`.
Результат и проверенные ограничения: [acceptance #10](docs/ISSUE10_ACCEPTANCE.md).
