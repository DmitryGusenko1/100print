Backup/restore follow-up 2026-11-08: first attempt safely rejected absolute
Python links in rebuildable Hermes runner environments. Excluded only
`hermes-home/installs/`; retained safe extraction. Repeated isolated restore
**PASSED**: 301 public tables, pre-owner entity counts match, config/key and
Hermes auth/config match, SQLite integrity ok, 9 sessions and 25 messages restored.
See [restore evidence](../../ai-team/evidence/restore.json). Existing SQLite
snapshot work was preserved and exercised with this fix. This remains pre-owner
Paperclip recovery, not full organization/task continuity.

# Current acceptance — 2026-11-08 06:33 UTC

**CHANGED / WAITING_USER; full DoD incomplete.** This section supersedes all
historical blockers, bot targets and service states below.

- **VERIFIED:** management `hundredprintbot`; fresh bounded inference, one API
  call, exact control response, session recorded in
  [inference evidence](../../ai-team/evidence/issue18-resume-inference.json).
  Existing Codex login remains authenticated; credentials were preserved.
- **VERIFIED:** genuine owner inbound and subsequent Hermes/model answer,
  session `20261108_063045_dc3d9b5b`. Owner requested status and a work proposal;
  this is **not approval**. No owner message was synthesized. Sanitized
  [E2E evidence](../../ai-team/evidence/issue18-owner-e2e.json) excludes content.
- **VERIFIED:** exclusive management consumer, owner allowlist, absent webhook,
  active/enabled persistent gateway, previous readiness delivery. Restarted
  only ceo-ai-team-hermes-gateway: PID 2623798 -> 3347678; 9 sessions and
  25 messages retained. Telegram reconnected and E2E rechecked after restart.
  [Restart evidence](../../ai-team/evidence/issue18-gateway-restart.json).
- Customer `WebToPrintISbot`: no configured integrations found in the scoped
  project audit; token/data preserved. Its global webhook cannot be checked
  without its token, which does not block management or GitHub bridge #19.
- **CREATED only:** organization manifest and role instructions. Paperclip
  authenticated/private health is ok but reports `bootstrap_pending`.
  Organization/project/agents, native adapter tasks, QA return, owner approval
  pending/nonexecution and full entity continuity remain unverified.
- Night plan remains DRAFT; no night tasks were launched. Website/test URL
  remains unconfirmed. No website availability claim is made.

**Required human action:** complete personal Paperclip owner registration using
its private one-time bootstrap URL (`ai-team/runtime/secrets/owner-bootstrap.txt`)
through the SSH tunnel to `http://localhost:3180`. After successful registration,
confirm it by creating project marker `data/ai-team-paperclip-owner-ready`.
Do not publish the bootstrap URL. Executor readiness is this marker; Telegram
E2E is already verified and is no longer the blocker. The marker does not grant
owner approval; the next executor must verify authenticated bootstrap state.

Validation: 21 bridge/worker tests, 2 owner mapping tests, 2 Telegram preparation
tests; live inference, transport/E2E, Codex login and private Paperclip health.
Existing unrelated uncommitted changes are preserved.

# Current owner correction — 2026-11-08

Management is `hundredprintbot`; `WebToPrintISbot` is the disabled future customer bot.
The old credential mismatch and token requests below are superseded.
See [current issue 21 facts](../ISSUE21_STATUS.md).
#19 is queued independently; #18/#20 await genuine management inbound E2E.

## Historical evidence (superseded target)

# Issue 18 acceptance — 2026-11-07

## Issue 20 update — 2026-11-08

Current status: WAITING_USER, readiness `telegram`. This update supersedes the
old instruction to manually replace only config/telegram.env. Expanded permitted
search covered config/, ai-team/runtime/secrets/, isolated Hermes settings and
backups, ai-team/config/, .hermes settings and the project root bot configuration.
65 settings files yielded one distinct Telegram token; getMe succeeded as
hundredprintbot. No target token was found and no API check failed.

@WebToPrintISbot: **not found, not configured, not started, no reply**.
Existing gateway is active/enabled for hundredprintbot; no service was restarted
and no readiness message was sent. Model evidence remains historical from #18;
no fresh inference or Telegram E2E is claimed. Target webhook/poller checks are
blocked on its credential. No owner message or approval was simulated.

One owner action, in a ceoorch terminal at /opt/ceo-orchestrator:
`.venv/bin/python ai-team/ops/set-owner-telegram.py`, then paste the target token
into the hidden prompt. It verifies exact getMe username before writes, validates
and preserves owner allowlists and model settings, creates 0700/0600 private
backups, and replaces each configuration atomically with rollback on write failure.
It does not restart services. On readiness `telegram`, resume exclusive consumer
and webhook checks, controlled project-only handoff if necessary, user gateway
restart, fresh inference, exact getMe, conflict checks and target readiness delivery.
Then wait for a real owner message using readiness `telegram-e2e`.

The wrong-token blocker remains factual; it cannot be marked resolved before a
correct credential exists. Historical outbound evidence no longer counts toward
required-bot readiness. The verifier uses a separate target-specific delivery
receipt. #19 independent bridge implementation and offline tests may proceed
immediately; target Telegram credentials gate only its Telegram integration/E2E.

## Historical acceptance — 22:08 UTC (supersedes historical states below)

**WAITING_USER; full DoD is not complete.** Fresh issue body fetched and
[LIVE_PREFLIGHT](https://github.com/DmitryGusenko1/100print/issues/18#issuecomment-6713646128)
published. Stage remains commit/push, 90%; no stage reduction.

**VERIFIED model:** fresh bounded Hermes inference succeeded, one actual model
API call, exact control reply, existing Codex ChatGPT login retained. Evidence:
[bounded inference](../../ai-team/evidence/hermes-inference-current.json).

**CONNECTED transport, wrong bot:** permitted project `config/telegram.env`
returns `getMe.username=hundredprintbot`, whereas the owner's urgent requirement
is `WebToPrintISbot`. No other credentials were searched. Gateway PID 2623798
is active, enabled, Restart=on-failure, NRestarts=0, user Linger=yes. Previous
`ceo-telegram-bot` is inactive; webhook absent; private owner allowlist matches.
Paperclip/PostgreSQL units remain active. No services were restarted this turn.
The prior owner readiness message exists, but proves delivery only to the
configured bot, not to the required bot and not a model reply in Telegram.

**BLOCKED required Telegram:** verifier now requires the exact username and a
recent successful inference from persisted session history. The previous
VERIFIED receipt accepted any bot id and is superseded by atomic BLOCKED for
launch request `e85c07cf-d641-44f1-b5fa-f85b6fb7fa6d`; model_inference=true,
gateway_active=false (required bot), owner_allowlist=true,
outbound_owner_message=true (historical configured bot). Evidence:
[transport checks](../../ai-team/evidence/telegram-launch.json).
No Telegram-source model session is present; inbound E2E is NOT_RUN, owner plan
remains DRAFT, no owner approval has been impersonated. No new readiness message
was sent to the wrong bot this turn. Night work was not started.

**One required action:** replace `CEO_TELEGRAM_TOKEN` in project-local
`/opt/ceo-orchestrator/config/telegram.env` with the token for `@WebToPrintISbot`.
Do not post the token in GitHub. Executor result uses readiness `telegram`;
only after correct credentials can the gateway be reconfigured and inbound E2E
requested. Paperclip bootstrap, organization, adapter acceptance, QA/approval,
full continuity/restore and website checks remain outstanding and deferred per
the urgent priority. Website URL is not guessed. Panel remains loopback
`http://localhost:3180`, SSH tunnel and personal human bootstrap required.

Validation this turn: successful bounded real inference, read-only Codex auth
status, Telegram getMe/webhook/allowlist, systemd active/enabled/lingering checks,
owner credential mapping tests and Python compilation. Existing uncommitted
backup/unit/config/role changes were preserved and excluded from this commit.


## Resumption at 18:14 UTC — current state supersedes initial blockers below

**WAITING_USER, not DONE.** Expanded issue body fetched again. New LIVE_PREFLIGHT:
https://github.com/DmitryGusenko1/100print/issues/18#issuecomment-6711147766.
The administrative bootstrap has now supplied launch request
`e85c07cf-d641-44f1-b5fa-f85b6fb7fa6d`; user manager is running at
`/run/user/999/bus`. Paperclip and PostgreSQL system units are **VERIFIED active**,
Restart=on-failure, PIDs 2610196 / 2610195 after administrative installation.
Authenticated/private health is ok, owner remains `bootstrap_pending`.

Hermes Telegram unit is **CREATED**, enabled in the ceoorch user manager,
**not CONNECTED or VERIFIED**: inactive, ConditionResult=no. Conditions require
both successful inference evidence and the controlled old-bot handoff. No handoff
request was made. Old `ceo-telegram-bot` remains active, same PID 3815479.
Rollback after a future handoff: stop the new user gateway first, then an
administrator starts `ceo-telegram-bot`; never run both consumers together.

Credentials were taken only from project `config/telegram.env`; the configured
single positive private chat id was validated and mapped to the native
`TELEGRAM_ALLOWED_USERS`. No group id or guessed user was authorized.
Native `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_USERS` were verified in pinned
gateway source. Secret file is isolated and mode 0600. `getMe` and
`getWebhookInfo` succeeded; webhook absent. No polling or outbound send was
attempted. **Inbound owner E2E and owner approval remain unverified.**

Two bounded Hermes launches failed before model inference. The configured
native `codex_app_server` attempt returned: `No Codex credentials stored` and
requested `hermes auth add openai-codex --type oauth`. Existing `codex login status`
still reports ChatGPT login; no credentials were copied or refreshed by Hermes.
Pinned Hermes deliberately stores its OAuth independently to avoid competing
refresh-token rotation. No model or budget has been assigned to the team.

**One necessary action:** over SSH run
`bash /opt/ceo-orchestrator/ai-team/ops/authorize-hermes.sh` and complete the
offered OpenAI sign-in. The script writes `data/ai-team-hermes-auth-ready` only
after read-only credential verification. Executor readiness uses that marker;
subsequent inference, gateway handoff and owner dialogue are still required.
Bootstrap received an atomic **BLOCKED**, with matching request id and all four
technical readiness booleans false. No fictitious VERIFIED receipt was produced.

The 20 role definitions and nine project instructions from main revision
`0d74a4e` were staged under `ai-team/roles` and `ai-team/skills`; native
`hermes skills list` detects all nine as enabled/local in the isolated home.
This verifies discovery, not employee execution or Paperclip profiles.
The overnight plan remains [DRAFT](../../ai-team/roles/overnight-draft.md):
website client journey and confirmed test-environment fixes, plus three competitors.
Website URL is still unknown; no guessed endpoint or scheduled work was launched.

Validation: two owner mapping tests (including five refusal cases) pass;
shell syntax and Python compilation pass. User manager loads the gateway unit
and refuses to start it while conditions are unmet. A fresh backup and independent
restore at 18:13:24 UTC passed: 301 tables, company/agent/project/issue/run/approval
counts all zero, one invite, config/key match. This is pre-owner continuity only.
Evidence: [launch](../../ai-team/evidence/launch-resume.json),
[Telegram preparation](../../ai-team/evidence/telegram-preparation.json),
[restore](../../ai-team/evidence/restore.json). No task/run/approval IDs exist.
Panel remains `http://localhost:3180` through SSH tunnel; human bootstrap is
still required and was not impersonated. Remaining full DoD in the initial
report remains outstanding.

**WAITING_USER — full DoD is not met.** Evidence collected on the VPS between
17:55 and 18:04 UTC. [LIVE_PREFLIGHT](https://github.com/DmitryGusenko1/100print/issues/18#issuecomment-6710979859)
was posted before installing application components.

## CREATED / CONNECTED / VERIFIED

| Component | CREATED | CONNECTED | VERIFIED |
|---|---|---|---|
| Paperclip 2026.1106.0 | Installed locally; persistent config, key, storage | Dedicated PostgreSQL ceo_orchestrator, loopback 55438 | Health 200, authenticated/private, UI 200, anonymous company API 403 |
| Hermes v0.23.0 | Frozen local installation; isolated home | No inference provider connected | CLI version verified; no task acceptance |
| Codex CLI 0.163.0 | Existing installation preserved | Existing same-user ChatGPT login reports authenticated | Two bounded standalone smoke calls failed to write; sandbox namespace permission denied |
| Hermes and codex_local adapters | Official packages 2026.1106.0 installed | No persisted agents yet | Read pinned implementations/docs; no adapter run verified |
| Organization 100print, project, 7 department heads, Hermes coordinator, Codex developer | Manifest prepared only | **Not created in Paperclip** | No company/agent/project/issue/run IDs exist |
| Human owner | Standard one-time bootstrap invite persisted privately | Registration pending | Executor did not register or approve as Дмитрий |
| New services | Two ceo-ai-team unit files prepared | Not installed/enabled | systemd-analyze verify passes; foreground startup/restart only |
| Backup | 0700 directory, 0600 dump/state/checksums | Local backup only | Temporary independent restore passed: 301 public tables, config/key byte match |

Official stable versions matched the issue:
[Paperclip v2026.1106.0](https://github.com/paperclipai/paperclip/releases/tag/v2026.1106.0),
[Hermes v0.23.0](https://github.com/NousResearch/hermes-agent/releases/tag/v0.23.0).
Source pins: Paperclip `d69631b01b9c658f80bf8bed389863dce82643e1`,
Hermes `2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19`.
The installed official npm packages report 2026.1106.0. Health's `commit` field
reported the enclosing orchestrator repository HEAD `ebe308d...`, so it is not
used as proof of the Paperclip source revision.

System: Ubuntu 24.04.4, 4 CPU, 24033 MiB RAM, initially 17 GiB disk free;
11 GiB free after installation. Global Node v22.23.1/Python 3.12.3 retained.
Local Node v24.15.0 and Python 3.14.10 added; PostgreSQL binary is 16.15
(Ubuntu 16.15-0ubuntu0.24.04.1), systemd 255. pnpm absent; official npm package
used instead of a source build.

## Evidence and limitations

Sanitized evidence: [inventory](../../ai-team/evidence/inventory.json),
[HTTP gate](../../ai-team/evidence/http-preflight.json),
[restore](../../ai-team/evidence/restore.json),
[foreground restart](../../ai-team/evidence/restart.json).

At 18:04:04 UTC, after restarting only the new temporary Paperclip process,
health was ok, bootstrap_pending, invite active. Counts remained company=0,
agent=0, invite=1. Restore verified the pre-owner database only; task/run/history
continuity and service restart continuity are **not verified**. No task, run or
approval IDs can be reported. QA return and pending approval nonexecution have
not been exercised; no approval was granted by the executor.

Both bounded Codex calls completed a model turn; neither created proof.txt.
The retry with an explicit writable directory failed when creating the sandbox
namespace (Permission denied). Exit 0 is not treated as successful execution.
Hermes status reported no providers connected; its profile cannot be described
as an executor. No new paid provider or model/budget policy was selected.

The seven heads are described in [organization manifest](../../ai-team/organization.json).
They are intended as paused profiles with schedules off. Administration and
Hermes are directly accountable to the human Board; six main heads report to
Hermes; Codex is a production development executor. No owner AI profile exists.

The existing ceo-orchestrator, ceo-telegram-bot, ceo-github-worker and
ceo-github-watcher remain active with identical before/after PIDs
3815350 / 3815479 / 1386597 / 1387067. No existing service was restarted,
no bot tokens, webhook/polling or nginx settings were modified. Bot E2E is not
claimed. No website URL/workspace was found in inspected project configuration;
website availability remains unverified instead of probing guessed sites.

## Panel and next action

Temporary foreground panel: **http://localhost:3180**, bound only to
127.0.0.1. Connect with `ssh -N -L 3180:127.0.0.1:3180 YOUR_SSH_VPS`.
Authentication is required; owner registration remains pending. The standard
bootstrap URL is stored in local `ai-team/runtime/secrets/owner-bootstrap.txt`
(0600); it is intentionally absent from GitHub. Foreground lifetime is not
accepted as persistent service operation.

**Current blocker:** ceoorch has neither passwordless sudo nor a usable user
systemd bus. One necessary administrator action:

```sh
sudo /bin/sh /opt/ceo-orchestrator/ai-team/ops/install-services.sh
```

Only after authenticated service health passes does this create
`data/ai-team-services-ready`, allowing the worker to resume. Subsequent owner
registration must be performed personally; it has not been bypassed. The next
executor turn must preserve the current progress stage, finish native
organization creation after Board bootstrap, address Hermes authentication and
the sandbox restriction, then complete both adapter tasks, QA/approval checks,
full-state restore and service restart acceptance before claiming completion.

[Operations and recovery](../../ai-team/README.md) covers storage, start,
bootstrap, private access, backup and isolated restoration. Private logs,
credentials, downloaded runtimes and backups are excluded from git.
