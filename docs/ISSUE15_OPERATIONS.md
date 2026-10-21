# Issue 15 operational intelligence

Application-role migration: `.venv/bin/python scripts/intelligence.py migrate`.
Read-only management views: `scripts/intelligence.py snapshot` and `metrics`.
`seed` creates explicitly unverified strategic starting hypotheses, never facts.
The worker records structured decision/action/hypothesis/risk artifacts on completion;
its maintenance loop produces deduplicated review events. All writes share the task
completion transaction. Decisions are proposals, not spending authorization.
Review defaults to seven days; relative source deadlines remain in the structured
body until a validated absolute deadline is supplied. No relative date is invented.

Telegram commands: `/snapshot`, `/metrics`, `/details UUID`, `/decision UUID`,
`/snooze UUID`, `/close UUID`. Snooze is one day. `/decision` marks pending for
review; it does not authorize execution. Existing result formatter keeps default
answers concise. A daily review digest uses the durable outbox and explicit
chat/user allowlists. Ambiguous sends remain quarantined; Telegram offers no
transactional idempotency key. Digest content is capped to five items.

Memory has typed operational artifacts, provenance, confidence, importance,
entity/topic fields, bounded full-text/concept retrieval and explicit artifact and
memory relations. Embeddings are model-keyed arrays. VectorProvider accepts a
compatible embedding callable and uses installed pgvector; unsupported vector
queries roll back to a savepoint and use full-text retrieval. No extension is
installed and no external embedding credentials are assumed. Retrieval observations
report hit ratio, not measured semantic correctness.

Metrics expose task/artifact status, hypothesis types, unresolved questions,
latency, failures, Council levels and Telegram delivery counts. These include
integration-test tasks; filter by source for business-only reports. Strategic
snapshot reports evidence states rather than claiming verified business outcomes.

## Future administrator helper installation (prepared, not applied)

`project_service_helper.py` accepts only status/restart of four fixed project units.
Never grant root execution of its project-writable source. A future administrator
installer must copy the reviewed helper into a root-owned, non-writable path,
verify every component is root-owned, then grant ceoorch only that fixed executable
via a dedicated sudoers entry. Unit files and all root-executed hooks must also be
root-owned; helper permissions do not authorize arbitrary deployments or shell
commands. The GitHub worker is deliberately excluded to avoid killing its executor.
No installer or root changes have been applied by issue 15.

Live acceptance requires real Telegram input and persisted production output.
Use `scripts/verify_telegram.py`; a successful credential preflight alone does not
prove E2E. Full issue completion must not be asserted until every block is verified.

Prepared installer: `scripts/install_project_helper.sh` (syntax checked only).
A future root reviewer runs it once after reviewing the helper. It refuses an
existing installation, installs a root-owned snapshot and validates a dedicated
sudoers rule. It grants no arbitrary unit or command execution. This optional
future step does not block application-level operation.

The default HybridConceptProvider now uses installed pgvector for local six-axis
multilingual business-concept embeddings (`business-concepts-v1`), merged after
full-text matches to preserve exact recall. Existing concept-bearing memory is
backfilled; new memory is indexed transactionally. This is a small explicit
concept representation, not a neural embedding model. Compatible neural embeddings
can be supplied through VectorProvider without changing business logic.
