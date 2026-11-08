# Update for issue 18 — 2026-11-08 06:33 UTC

Genuine owner inbound/model E2E is now VERIFIED in management session
`20261108_063045_dc3d9b5b`, including after isolated gateway restart. Owner
requested a proposal; night plan remains DRAFT. For #18 the next blocker is
personal Paperclip owner bootstrap (`bootstrap_pending`), with readiness
`file:data/ai-team-paperclip-owner-ready`. Historical pending-E2E statements
below are superseded for #18. See current acceptance report.

# Issue 21 — management restored, owner E2E pending

Checked 2026-11-08 UTC. Management target: `hundredprintbot`.
Customer target: `WebToPrintISbot`, disabled by owner policy.

Fresh bounded Hermes inference succeeded through the existing authorization:
one real model call, `HERMES_INFERENCE_OK`. The persistent user gateway is
active/enabled, its current PID matches connected Telegram runtime state,
and one project Telegram consumer was found. The legacy project poller is
inactive. Live management getMe matches; its webhook is absent (polling).
The existing private owner allowlist and model configuration were preserved.
The owner readiness message was delivered successfully through hundredprintbot;
the private delivery receipt remains on the VPS. No service reinstall or restart
was needed. Existing website and unrelated working changes were preserved.

Project settings audit found one distinct Telegram token, for hundredprintbot,
and no configured client poller, webhook route, sender job or Hermes binding
for WebToPrintISbot. There was no client integration to disable in this scope.
Without its token, its global Telegram webhook cannot be checked or deleted.
No token, account, pending updates or history was removed. If such a token is
later found, deleteWebhook must retain pending updates. This does not block
management. Audit scope and independent results are recorded in
[bot audit](../ai-team/evidence/issue21-bot-audit.json).

The launch evidence distinguishes actual gateway active/enabled from aggregate
transport verification. Current technical receipt is VERIFIED; this is not
acceptance of the whole team. No real inbound Telegram session exists yet.
Night plan approval and the remaining #18/#19 acceptance criteria are pending.
The worker now probes Hermes for #18/#20/#21 Telegram readiness, keeping legacy
readiness unchanged for other tasks. Its E2E probe requires an owner Telegram
message after the readiness send and a subsequent assistant/model turn, without
polling or synthesizing updates. It does not infer plan approval.

#18/#20 wait on `telegram-e2e`, replacing the obsolete credential mismatch.
#19 is queued for independent bridge work with no client token dependency;
no bridge implementation or acceptance is claimed here.

Validation: live getMe/getWebhookInfo, real bounded inference, systemd/runtime
checks, project consumer inspection, successful sendMessage; 12 worker tests,
2 credential helper tests, 2 owner mapping tests, and git diff whitespace check.
Full DoD remains WAITING_USER until the owner's genuine inbound E2E. Send one
real message to @hundredprintbot. Approve the night plan separately when ready.
