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
