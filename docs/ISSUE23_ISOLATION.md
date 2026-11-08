# Issue 23 — containment and host review (2026-11-08)

Status: WAITING_USER. Full isolation DoD is NOT met. No autonomous business work is authorized.
The owner override in #22 supersedes its earlier acceptance report. Prompt/cwd/MCP
allowlists and this interlock do not establish an OS security boundary.

## Applied inside /opt/ceo-orchestrator

* Github executor no longer contains any real Codex process launch, including the
  previous sandbox bypass. Every real job becomes WAITING_USER; synthetic queue
  acceptance remains local. Owner-review markers cannot enable mutation capability.
  A surviving executor is tracked, never duplicated. The active issue23 executor
  is the maintenance exception already running before this change.
* CodexRunner, production Codex (including its internal response entry), business
  provider and Hermes bridge execution deny before starting tools/processes.
  Main task claim returns no work. Hermes bridge keeps queued requests unclaimed;
  Telegram proposals/status transports remain available.
* Durable project DB triggers reject INSERT/UPDATE into tasks.processing and
  hermes_bridge_jobs.running, including from already loaded old worker code.
  Existing project agents were disabled; previous enabled IDs saved locally in
  data/issue23-enabled-agents-before.json. No host/shared role revocation occurred.
* Project Hermes CLI entrypoint loads hermes-containment.py before main: model
  tool dispatch returns executed=false; cron tick and direct/external jobs are
  blocked; native Codex app-server transport refuses startup. Codex wrapper denies
  all arguments with exit 77. Installed only into this project's venv; reproduce
  using ai-team/ops/install-containment.py after a package reinstall.
* Existing user gateway restarted, active PID 3376872 observed after restart.
  Telegram polling/status transport is retained; agent/model replies are paused.
  No Telegram delivery/E2E test or external user message was sent for this issue.

## Evidence and limits

48 focused unittest tests passed before applying durable DB admission triggers
(including existing Hermes bridge transport tests); 24 containment/worker/progress
checks passed again after DB triggers; the final combined provider/containment
run passed 28 tests. Nine provider/containment checks also passed.
Python compilation and diff whitespace checks passed. Host-aware systemd unit
verification could not complete due to denied access to a host unit; no unit was
installed and no host settings were changed. Local draft-unit parsing passed. Production provider contract tests explicitly
mock the guard to validate dormant internals; isolation tests do not mock the guard.
Live task crash/recovery/business workload tests were deliberately not run because
those start jobs and restart the service while mutation capability is prohibited.

ai-team/evidence/issue23-hermes-negative.json uses actual installed Hermes module
implementations with the installed startup interlock (no mocked tool/cron transport).
issue23-hermes-cli.json records a real CLI invocation and containment refusal,
NOT a successful LLM tool-based isolation E2E. test_isolation exercises the real
GitHub execute function using a disposable project-local SQLite queue and asserts
no child process spawn. Real wrapper accepts no CLI override. Safe project-local
canaries verify symlink/traversal denial in project_read; no neighboring file was read.
issue23-db-negative.json records real PostgreSQL trigger refusals, rolled-back
synthetic fixtures, and zero processing tasks/running Hermes jobs at inspection.

Own identity: ceoorch UID 999, group ceoorch only as returned by id. Allowed system
services ceo-orchestrator and ceo-github-worker were active with PrivateNetwork=no,
ProtectSystem=no, NoNewPrivileges=no. No host config, other user data, neighboring
project data or private network management endpoints were inspected. Own DB role
ceo_orchestrator has no superuser/createDB/createRole/bypassRLS flags. This does
NOT prove repo token scope, cross-DB denial, role memberships or every credential's
scope; no credential values were printed or published.

## Remaining bypasses — not protected by this change

The shared UID can rewrite project Python, wrappers, venv and DB triggers (table
owner); a marker/signature stored under that UID cannot prove enforcement.
Direct /usr/bin/codex, direct Hermes source imports, another interpreter, tools
called below model_tools, and alternative entrypoints are NOT OS-confined by this
patch. Existing host shell, filesystem permissions, sockets, SSH/token files and
private/management network access remain unproven. No claim of mount, sudo,
Docker socket, credential, host-route or delegated identity isolation is made.
Project registry sync may re-enable agent rows, but application+DB gates continue
to deny dispatch. A package reinstall can replace the Hermes CLI entrypoint;
wrapper denial remains, but the CLI interlock must be reinstalled and verified.
Resident GitHub worker must reload after this executor returns; project helper
watches issue23 WAITING_USER and zero RUNNING tasks before signalling only its
verified same-UID MainPID. Restart=always is existing service behavior. Receipt:
data/issue23-worker-reload-requested (not claimed until it exists).

## Minimal host change for separate approval — NOT applied

Review artifact: ops/isolation-review/ceo-w2p-agent.service. It defines a NEW
identity/runtime, no changes to existing shared services or accounts. It is a
staging unit, not a deployable completion claim: rootfs, curated source export and
isolated_executor.py broker client must be provisioned/reviewed first. Never
bind-mount the whole project root, gateway home, .env, .codex, SSH, Docker socket,
/run or host /etc into the agent. No sudo, extra groups or host service helper.

Required owner approval scope:

1. Create dedicated ceo-w2p-agent identity without login/sudo/supplementary groups;
   prepare minimal immutable rootfs and curated read-only source, separate writable
   workspace with no host hardlinks/sockets. Agent cannot edit policy/broker/units.
2. Split trusted Telegram/status transport from untrusted agents. Give agents no
   raw Telegram, GitHub, DB or SSH credentials. Create repo-only installation token
   for DmitryGusenko1/100print and non-owner DB role restricted to ceo_orchestrator /
   ai_brain as actually needed, via trusted narrowly authorized brokers. Do not
   revoke or alter credentials used by other services; migrate this project only.
3. Keep agent network namespace private. Provide only an authenticated public-web
   research broker through a dedicated AF_UNIX socket; block loopback, RFC1918,
   link-local/metadata, IPv6 local, management hosts/routes and redirect/DNS rebinding
   to these ranges on EVERY hop/connect. No raw TCP, CONNECT, arbitrary unix sockets,
   host shell or caller-chosen endpoint. Public internet research remains an approved
   capability, but is paused with tools until this broker is implemented and tested.
4. Broker enforces project+role+operation+task binding, non-replayable owner approvals
   and bounded artifacts. Scheduler, bridge, worker and every delegated child use
   the same isolation; no fallback to shared identity or unrestricted subprocess.
5. Validate via real Hermes AND executor with safe external canaries, direct and
   delegated path traversal/symlink/hardlink/socket/mount probes, unrelated repo/DB
   refusals using synthetic identities, and controlled private network fixture,
   IPv4/IPv6, redirect/DNS rebinding refusals. Never probe actual neighboring secrets.
   Verify Telegram/status and permitted public research separately. Only then
   review a new code change to remove the interlocks/triggers and enable narrowly
   approved mutations. An approval marker alone never enables anything.

For review acknowledgement only, after explicit owner approval of this scope,
create /opt/ceo-orchestrator/data/issue23-host-review-approved. It authorizes no
business job and proves no enforcement. Host provisioning is still outstanding.

## Team setup after enforcement — draft, no execution

Hermes coordinates within one Web-to-Print project. Research/strategy roles get
sanitized read-only context; development works on disposable branches/workspaces;
QA reviews artifacts; financial/production/commercial mutations require separate
owner decisions. Department heads route bounded tasks; no role grants new tools
or credentials. Owner approval binds exact plan version, action and expiry.
Memory is project-only, separates facts/assumptions/approvals, excludes secrets,
and has retention and owner-visible changes. Control uses immutable broker audit,
quotas, queue pause, artifact review and negative regression checks. Department
plans and business activity remain drafts until separately approved.
