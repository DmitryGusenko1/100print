# Telegram acknowledgement and queued delivery

Issue #13 adds independent durable `ack`, `progress`, and `final` outbox entries.
Existing outbox entries migrate as `final`; task and inbox identities are preserved.
ACK is enqueued transactionally with intake and delivered before the next poll.
The collector backfills accepted pending tasks and creates one progress notice after
30 seconds from acceptance. Final collection no longer mistakes ACK for completion.
Confirmed sends persist assistant messages and Telegram message IDs in one transaction.
L1 has a separate worker slot and skips additional Critic/analytical calls; significant
questions keep existing L2-L4 execution and Critic/Council artifacts.

Observed cause: the only business worker was executing a long sequence of production
checkpoints for the first Telegram question; the next question remained `new` behind it.
Worker heartbeat and advancing checkpoints showed ongoing inference, not lost intake.

Activation requires restarting only `ceo-orchestrator.service` and
`ceo-telegram-bot.service`. The bot applies its additive schema migration on startup.
No pending task should be deleted or recreated. Worker recovery resumes durable
checkpoints after interruption, within the existing bounded retry policy.

After activation send a real allowed Telegram question, e.g. «Что такое тираж?».
Run `.venv/bin/python scripts/verify_telegram.py --wait 60 --restart` with service
management permission. It checks production identity, ACK <=10 seconds, confirmed
final delivery, persisted user/assistant messages, artifacts, and stable IDs after
transport restart. Old questions backfilled with ACK cannot prove the <=10 second
acceptance criterion; a newly received question is required.

Limit: Telegram sendMessage offers no idempotency key. An ambiguous network send or
crash after external delivery is quarantined as `uncertain`, never blindly resent.
It needs reconciliation; absolute exactly-once delivery across this boundary cannot
be asserted. Uncertain notification entries do not block final answer delivery.

LIVE follow-up (2026-10-21): both original Telegram tasks are `done` with
`production-codex-v1`, and all eight historical final outbox parts are `sent`.
There are no `new`/`processing` tasks at this check. Credentials, polling ownership,
worker heartbeat and shared memory pass preflight. `/status` now also names the
active task IDs (or reports none).

The transport was restarted successfully by sending SIGTERM to its own verified
systemd MainPID under `Restart=always`; direct systemctl restart requires separate
authorization. Runtime tests also verified worker crash recovery. Historical
messages predate ACK deployment and cannot establish the ACK latency criterion.
A fresh real inbound Telegram question is still required for full E2E acceptance;
no complete LIVE acceptance is claimed yet.

Final issue #13 verification (2026-10-21): the previously pending LIVE gate is now
satisfied by real inbound update 27208783, task
`193280ec-e716-4f65-aef2-b2b5d2d1c94b`. The current verifier confirms ACK latency
3.481367 seconds, provider `production-codex-v1`, confirmed final delivery and
persisted user/assistant messages, with L4 Council and Critic artifacts. Exactly
one ACK and one progress notice were sent for this update. All three accepted
Telegram tasks are done; all historical final parts are sent; pending queue and
duplicate outbox parts are zero. A fresh restart of the Telegram service through
its own MainPID and systemd Restart=always preserved the complete evidence and
Telegram message IDs. Machine-readable local evidence is in
`data/issue13-live-evidence.json`. No further user action is required.

`/status` reports zero queued tasks, no active task, a healthy worker and provider
readiness as unknown when there has been no production checkpoint in ten minutes;
this idle-time state is intentional and does not claim a fresh provider probe.
The Telegram API ambiguity limitation above still applies; the observed LIVE
acceptance has no uncertain sends or duplicate replies.
