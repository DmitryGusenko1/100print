# Issue 17: Telegram silence investigation

ROOT_CAUSE: The reported fresh missing update cannot yet be identified. The latest
retained real update (27208783) already has confirmed ACK and final delivery.
getUpdates at the durable cursor (27208784) returned no pending updates. No second
loaded ceo-* / ai-business-brain-* Telegram service was found. Historical accepted
messages have session mappings, completed production tasks and confirmed finals.
This evidence does not establish the cause of the reported new incident.

Confirmed code defects: every send exception, including explicit Telegram rejection,
was quarantined forever; assistant-memory failure after successful send erased the
confirmed-delivery state. Optional review errors could prevent intake altogether.

FIX: Explicit structured API rejection now schedules a retry with retry_after and
stores a sanitized API receipt. Non-JSON HTTP failures and ambiguous network sends
remain quarantined to avoid duplicate finals. Confirmed receipts commit before
assistant-memory persistence. An ambiguous send queues one distinct user-visible
error notice. Optional review runs outside the intake/delivery transaction. Incoming
update audit distinguishes accepted, unsupported and allowlist-rejected updates;
accepted raw updates are retained transactionally with intake and cursor advancement.
No allowlist was widened and no cursor was reset.

ACK: Internal synthetic update -1700000001 in the existing allowed private chat
received confirmed ACK in 6.130134 seconds.
FINAL_DELIVERY: The synthetic question «Что такое тираж?» routed to production L1
and received a confirmed final in 12.637569 seconds, once. Historical real final
was already sent and was not duplicated. Synthetic negative update IDs are excluded
from verify_telegram.py real-user acceptance.
QUEUE: The internal synthetic task completed using production-codex-v1. No historical
pending or uncertain outbox entries required recovery at initial inspection.
TESTED: Targeted transactional transport/formatter tests, real Telegram credential
and private-chat checks, production queue/provider roundtrip, existing real-update
and formatter acceptance verifiers. Final test counts are in the executor report.
USER_ACTION: After internal checks pass, one new question to the same bot is needed
to identify and verify a fresh real inbound update. Existing available user updates
have already been answered; the reported missing update is not available in polling.
LIMITATIONS: Telegram cannot replay acknowledged updates through getUpdates and has
no sendMessage idempotency key. Ambiguous external effects cannot be safely resent
as finals automatically. A blocked bot/chat or invalid credentials cannot be cured
by retry. No claim of full incident resolution is made before fresh real evidence.

The E2E readiness verifier also honors data/telegram-e2e-baseline.json
(after_update_id). This prevents an old successful delivery from immediately
releasing WAITING_USER for a new incident. For issue 17 the baseline is 27208783.
A Telegram 400 retry falls back to plain text, bypassing formatter/HTML errors.

Final validation: sequential full discovery passed 72 tests; final transport and
presentation checks passed 19 tests. Initial overlapping restart-test runs failed
on transient DB shutdown and were replaced with the sequential passing run.
Preflight, historical real-update evidence and formatter verification passed.
Synthetic final is 167 characters. ACK/final IDs survived restarts; outstanding
outbox count is zero. Fresh-update baseline was tested to reject both historical
and synthetic evidence. Result remains WAITING_USER, not DONE.
