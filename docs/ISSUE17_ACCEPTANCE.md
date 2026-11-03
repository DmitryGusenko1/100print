# Issue 17: Telegram silence — live acceptance

ROOT_CAUSE: Investigation found explicit Telegram send rejections were quarantined
forever, successful delivery receipts could be lost after assistant-memory failure,
and optional review failures could prevent intake. These defects were fixed in
3e670c1. The originally reported missing update was not retained, so its specific
failure cannot be attributed retrospectively. Historical update 27208783 was
already answered and was not resent.

FIX: Structured API rejection schedules retry with retry_after and a sanitized
receipt; HTTP 400 retries use plain text. Confirmed send receipts commit before
memory persistence. Optional review errors do not block polling. Accepted raw
updates, inbox and cursor advancement are transactional. Ambiguous sends produce
one distinct visible delivery-error notice rather than duplicate finals.

ACK: Fresh real private-chat update 27208785 was ingested 0.071 seconds after its
Telegram timestamp. Confirmed ACK message 25 arrived 4.298309 seconds after intake.

FINAL_DELIVERY: The same real update completed through production-codex-v1,
non-demonstration mode. Final message 27 was confirmed exactly once, 342.384553
seconds after intake. Progress message 26 was confirmed. API receipts retain
ok=true, destination and message ID. The latest real request routed to L3;
the simple synthetic question routed to L1, with a 167-character final and
ACK in 6.130134 seconds (data/issue17-synthetic-evidence.json).

QUEUE: Real update has inbox, session, shared memory, production task and completed
provider artifacts. Cursor is 27208786, beyond the accepted update. No pending,
sending or uncertain outbox entries remain. No replay or extra send was necessary.

TESTED: Current preflight, real E2E verifier and formatter acceptance passed.
Full unittest discovery results are recorded below. Live E2E evidence is retained
in data/issue17-live-evidence.json. Prior transport tests cover rejection retry,
receipt durability, recovery, allowlist and duplicate suppression.

USER_ACTION: None. A fresh real update is now available and already answered;
no additional user test is required.

LIMITATIONS: Telegram provides no acknowledged-update replay or sendMessage
idempotency key. Ambiguous external effects cannot safely be automatically resent.
An API receipt confirms Telegram acceptance, not that a human read the reply.
Restart verification was not repeated: service-management authorization is absent;
the existing Telegram and orchestrator services are active. No restart was needed
for this acceptance-only change. The original unavailable update's exact cause
remains unproven.

Current full discovery: 76 tests, 74 passed, 2 failures in inherited
IntelligenceTests/SemanticTests.test_dedup_history_review_and_snooze. Both expect
a newly inserted artifact to be reviewed immediately; production has 210 eligible
artifacts and review selects only 100. This unrelated review selection limitation
is recorded without expanding the Telegram blocker scope.
Targeted Telegram transport and presentation: all 19 tests passed. Current
preflight and real formatter acceptance were rerun successfully after the full
suite. Both permitted production services are active.
