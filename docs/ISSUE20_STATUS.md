# Issue 20 — WAITING_USER: target credential absent

Current execution follows the explicit request to switch Hermes to @WebToPrintISbot.
It supersedes the previous hundredprintbot target for this switch only.

Fresh scoped audit on 2026-11-08 checked 151 project settings files under config/,
ai-team/runtime/secrets/, isolated Hermes settings, ai-team/config/, .hermes/,
and the project root bot environment. One distinct token was checked with getMe:
hundredprintbot. No file-read or API errors. No foreign settings were read.
Sanitized evidence: ai-team/evidence/issue20-token-discovery.json.

Target: **not found / not configured / not started / no reply verified**.
Target webhook/exclusive-poller checks cannot be completed without its credential.
No service restarted; allowlists, model authorization and bot secrets unchanged.
Earlier inference/E2E evidence on hundredprintbot does not verify the target.

One owner action, in a ceoorch terminal from /opt/ceo-orchestrator:

```sh
.venv/bin/python ai-team/ops/set-owner-telegram.py
```

Paste the WebToPrintISbot token into the hidden prompt. The installer rejects
hundredprintbot before writes, validates allowlists, backs up both configurations
privately, and replaces them atomically per file with rollback. It does not
restart a consumer. Exact target checks and target-specific outbound/E2E receipts
prevent historical hundredprintbot activity from satisfying this request.

Executor result: WAITING_USER, readiness=telegram. After credentials, resume
controlled project-only consumer/webhook handoff, user gateway restart, fresh
inference, target identity/active/enabled/conflict checks and owner readiness send.
Then await a genuine owner message with readiness=telegram-e2e. Never fabricate
inbound messages or approvals. No DONE claimed. Paperclip acceptance remains separate.

#19 independent bridge implementation, inference, artifacts and replay tests remain
independent of Telegram credentials. Only target Telegram integration/E2E waits.
Worker credential readiness now checks the installed target credential independently
of a running target gateway, avoiding a resume deadlock; this code takes effect
when the existing worker next loads it. The live worker was not restarted.

Validation: 25 worker/bridge/progress tests and 4 credential/preparation tests pass;
Python compilation and git diff whitespace checks pass. Secrets/runtime and
pre-existing unrelated changes excluded from commit.
