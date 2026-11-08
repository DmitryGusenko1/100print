# Issue 19 — Hermes bridge verified; owner Telegram E2E pending

Checked 2026-11-08 UTC. Existing ceo-github-watcher / issue #8 now routes new
ordinary/submit_task requests to installed Hermes, without a legacy provider
fallback, extra orchestrator, Telegram poller or public server. Native CLI
`-z --in --usage-file --resume` was checked against the installed implementation.
Management health verified at 2026-11-08T04:50:54Z: hundredprintbot gateway,
allowlist, exclusive consumer and webhook checks pass. WebToPrintISbot is not
a prerequisite; #18/#20 instructions and #21 correction were read first.

Durable PostgreSQL job/session state and private VPS outputs support status,
submit_task, get_task_result and propose_owner. GitHub results expose only
technical receipts and artifact hashes/sizes. CONTEXT returns counts without
private memory text; DECISION saves a reported choice, approval_granted=false.
Proposals use the existing owner Telegram configuration, remain awaiting_owner,
and never execute or approve themselves. Ambiguous sends are not automatically
repeated. Real owner agreement has not been simulated or claimed.

## Sanitized live evidence

- Input #8 comment 6717405371, session issue19-e2e-20261108-v3.
- Queued OUT 6717406140; durable job f7cba20e-6d60-41f4-b1d6-07179215b886.
- Real Hermes inference: one API call, completed 2026-11-08T04:49:11Z.
- Exact model response saved by adapter as an isolated workspace artifact:
  20 bytes, SHA256 3cc37a194aaea543886ecf232a3d7043a7b161aa01955f43298c966bc7fe9230.
  Expected test marker content verified locally; private outputs stay on VPS.
- Retrieval input 6717411603, done OUT 6717412629; read back via GitHub connector.
- Twice replaying input 6717405371 leaves exactly one job and no repeated effect.
- Restarted only ceo-github-watcher; completed result and native session survived.
- Continuity input 6717416714, job 23b4089f-6cb5-4754-b25d-c1f574883d1c:
  one real API call, completed 2026-11-08T04:50:26Z. Resumed the same native
  Hermes session and reproduced the previous marker without it in the new prompt.

Earlier probes were not acceptance: an advertised CLI flag was rejected by the
installed gateway launcher; removed after source verification. A later model
inference completed but native file writes were denied by its sandbox/approval
policy. No permissions were broadened. The accepted artifact above is a saved
model response, not a claim of successful native shell/file tool execution.
`done` reports inference completion, not independent validation of every prose task.

Recovery preserves queued jobs. Interrupted running jobs recover a saved completion
receipt or fail with effect_unknown, without blind reexecution. GitHub delivery
uses markers and bounded attempts; an uncertain Telegram proposal uses one send
attempt and retains unknown status for reconciliation. Scheduler excludes Hermes
jobs from legacy followups; bridge heartbeat also protects the still-running
legacy scheduler without restarting it.

Validation: 15 focused bridge/progress/scheduler tests passed, Python compilation
and git whitespace checks. Tests cover intake replay, post-delivery crash,
unknown-effect restart, session isolation, private legacy context filtering,
reported decisions, ambiguous proposal send and legacy scheduler isolation.
Proposal transport tests use mocks; no real approval or real inbound Telegram
E2E is claimed. Health is technical transport readiness, not owner acceptance.

Current #21 recheck supersedes the old E2E blocker: genuine owner inbound/model
E2E passes on hundredprintbot and current bridge health is verified. #19 is
requeued for its independent remaining acceptance; no client token or Paperclip
bootstrap dependency is imposed. Plan approval remains a separate owner action.
