# Issue 18 acceptance — 2026-11-07

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
