Current issue #20 execution: target @WebToPrintISbot is blocked on its missing
credential; prior hundredprintbot readiness does not satisfy this switch.
See [issue 20 report](../docs/ISSUE20_STATUS.md). Independent #19 bridge work remains unblocked.

# Current operating status — 2026-11-08

Hermes management on @hundredprintbot is active/enabled and genuine owner/model
Telegram E2E is verified, including history persistence after gateway restart.
OAuth is complete. Do not repeat obsolete authentication or handoff steps below.
Paperclip is authenticated/private on loopback 3180; human bootstrap remains
pending. Complete personal registration with the private bootstrap link, then
create `data/ai-team-paperclip-owner-ready` to resume the worker. Night work still
requires explicit owner approval. See the current acceptance section for evidence.

## Historical installation instructions (states superseded above)

# 100print AI-team foundation

Status: **WAITING_USER**, installation partially verified. See
[acceptance report](../docs/ai-team/acceptance-2026-11-07.md).

Current update 18:14 UTC: administrator bootstrap completed; Paperclip/Postgres
are active and the ceoorch user bus is available. Historical initial-install
limitations below are superseded by the acceptance report. Telegram gateway is
enabled but safely gated/inactive. Hermes requires separate OAuth: run
`bash /opt/ceo-orchestrator/ai-team/ops/authorize-hermes.sh` over SSH and finish
sign-in. It preserves existing Codex authorization and writes the worker's
readiness marker only after successful credential verification.

`ops/prepare-telegram.py` runs with `runtime/hermes-venv/bin/python`; it reads
only the project Telegram file, validates the private owner mapping, writes
native isolated Hermes secrets, installs local skills and checks getMe/webhook.
It never starts polling or sends messages. Gateway handoff must follow successful
bounded inference; require old bot inactive before starting the new consumer.
Use XDG_RUNTIME_DIR=/run/user/999 and
DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/999/bus for user systemctl.
Do not create the inference marker based only on OAuth or successful CLI exit.

All application code downloads, dependencies, runtime data, credentials, backups,
and private logs are inside this directory. Only `ops/`, sanitized `evidence/`,
and the organization manifest are tracked. The executor result and readiness
marker use the explicitly requested project `data/` directory.

## Start through systemd

The current user cannot install units and has no usable user systemd bus.
An administrator must run this single command:

```sh
sudo /bin/sh /opt/ceo-orchestrator/ai-team/ops/install-services.sh
```

The script stops only the temporary AI-team process and its isolated database,
installs/enables `ceo-ai-team-postgres.service` and
`ceo-ai-team-paperclip.service`, and waits for authenticated health before creating
`data/ai-team-services-ready`. It does not restart existing services. Both real
application processes use Restart=on-failure, journald, ceoorch, and umask 0077.
No placeholder Hermes daemon is needed: the supported `hermes_local` adapter
starts the CLI on demand. No Telegram gateway is started.

## Private panel and owner

Paperclip binds **127.0.0.1:3180**, authenticated/private. From your own computer:

```sh
ssh -N -L 3180:127.0.0.1:3180 YOUR_SSH_VPS
```

Open `http://localhost:3180`. The owner must complete Paperclip's standard
bootstrap registration personally. The one-time URL is stored locally in
`runtime/secrets/owner-bootstrap.txt` (0600); view it privately over SSH. Never
paste it into an issue. If expired, regenerate with the pinned CLI:

```sh
PATH=/opt/ceo-orchestrator/ai-team/runtime/node/node_modules/node/bin:$PATH \
PAPERCLIP_HOME=/opt/ceo-orchestrator/ai-team/runtime/paperclip-home \
/opt/ceo-orchestrator/ai-team/runtime/paperclip/node_modules/.bin/paperclipai \
  auth bootstrap-ceo \
  --config /opt/ceo-orchestrator/ai-team/runtime/paperclip-config.json \
  > /opt/ceo-orchestrator/ai-team/runtime/secrets/owner-bootstrap.txt
```

This grants no approval on behalf of Дмитрий Гусенко. The Board is a human
account. `organization.json` is a **prepared manifest, not persisted profiles**.
After bootstrap, apply via the supported company/agent/project APIs, resolve
reportsTo references, and pause all seven heads. Administration and Hermes have
no AI reportsTo parent; their human accountability is Board metadata. Six main
heads report to Hermes; Codex reports to Production as an executor. Keep global
heartbeats disabled and do not configure schedules, initiative loops, models or
budgets without owner input. API defaults are not owner-approved budgets.

## Persistent state

- `runtime/pgdata`: dedicated PostgreSQL 16 cluster, TCP loopback 55438;
  application database **ceo_orchestrator**. No shared cluster is used.
- `runtime/paperclip-config.json`, `runtime/service.env`, `runtime/secrets/`:
  database credential, authentication secrets, encryption key and bootstrap.
- `runtime/storage`, `runtime/paperclip-home`: files and Paperclip state.
- `runtime/hermes-home`: separate Hermes config, memory and history.
- `runtime/sandbox`: isolated acceptance workspace; never use a guessed website path.
- `runtime/logs`: private installation and smoke output; do not publish.

The protected socket directory allows local trust only within this owned
cluster; TCP requires SCRAM. The key must travel with encrypted storage backups.
The wrapper sources only its newly generated AI-team service.env.

## Backup and restore

Run as ceoorch while the isolated database is available:

```sh
python3 /opt/ceo-orchestrator/ai-team/ops/backup-restore.py
```

Rebuildable Hermes `installs/` environments are excluded because their absolute
venv symlinks are rejected by safe extraction. Recreate those environments with
the pinned runner when needed. Live SQLite databases use online snapshots and
restored integrity checks.

This creates a timestamped 0700 directory under `backups/`, a custom-format
pg_dump and state archive (0600), SHA256 checksums, and immediately restores to a
throwaway cluster under `runtime/` (Unix socket only, port 55439). It compares
schema, entity counts, configuration and key bytes, then stops/removes that
cluster. It never drops or overwrites an existing database. For active-agent
operation, stop only `ceo-ai-team-paperclip` before capturing state, ensure
Hermes calls have ended, then restart it after backup. Initial verification was
performed before any Board/company/agent existed; repeat with real histories.

For actual disaster recovery: stop only the new units, preserve the damaged
runtime, verify backup checksums, provision a fresh empty cluster under ai-team
with the same binary distribution and database name `ceo_orchestrator`, restore
`database.dump` with `pg_restore --exit-on-error`, and extract `state.tar.gz`
into its new runtime with umask 077. Restore configuration, service.env and
secrets together; use a temporary configuration if restoring elsewhere.
Reapply ownership ceoorch and 0700/0600 modes. Validate with the temporary
restore procedure first, then switch only the AI-team units to recovered data.
Never point a restore at the existing orchestrator socket on 55433.

Backups remain local to this VPS; no off-host recovery is claimed. There is no
automatic backup timer at this stage.

## Versions and installation

Pinned official sources are in `evidence/releases.json`. Source checkouts are
ignored under `src/`. Paperclip uses the official npm `paperclipai@2026.1106.0`
package including its bundled `hermes_local` and `codex_local` adapters.
Node 24.15.0 is installed locally (dependency engine floor); global Node remains
22.23.1. Hermes v0.23.0 uses its checked-in uv.lock and `uv sync --frozen
--no-dev` with a local Python 3.14.10 environment. Plain `uv pip install -e`
failed because it ignores upstream uv overrides; frozen project sync succeeded.
Use `UV_CACHE_DIR=.../ai-team/cache/uv`, `UV_PYTHON_INSTALL_DIR=.../ai-team/runtime/python`,
`UV_PROJECT_ENVIRONMENT=.../ai-team/runtime/hermes-venv` and npm's
`--cache .../ai-team/cache/npm` for subsequent operations. Use `uv python install
--no-bin` to avoid creating a default user Python link. No global runtime was
upgraded. Existing Codex CLI 0.163.0 and its current user's authorization remain
in place; no cross-user credential copying was performed.

## Remaining acceptance

Owner registration, persisted organization/profiles/project, both adapter task
lifecycles, QA rejection, pending approval nonexecution, and service restart
continuity must still be verified. Hermes has no configured provider in its
isolated home. Do not silently import/rotate the existing Codex refresh token
into Hermes: preserve the working Codex authorization. The Codex standalone
smoke authenticated but could not create a sandbox namespace under the current
executor restrictions. Test again under the installed service; do not disable
sandboxing to turn this into a pass.

The inspected project configuration contains neither website URL nor deployment
workspace. Website availability is unverified. The existing Telegram unit
remains active with its original PID; no outbound messages or bot configuration
changes were made. Service state alone is not bot E2E acceptance.
