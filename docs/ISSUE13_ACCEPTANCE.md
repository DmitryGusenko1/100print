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

LIVE activation and real E2E were blocked by missing systemctl/sudo authorization
in the executor account; no LIVE acceptance is claimed by this document.
