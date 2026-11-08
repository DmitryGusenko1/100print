# Issue 19 — independent Hermes bridge accepted

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


## Final independent acceptance — 2026-11-08 06:44 UTC

The former Telegram E2E prerequisite is satisfied by the genuine owner/model
exchange verified in #21 at 06:33:21 UTC. Paperclip bootstrap and approval of the
night plan remain separate and do not block this bridge. No approval is inferred.

Fresh input #8/6718364671, session `issue19-acceptance-20261108-final`, produced
queued OUT 6718365906 and job `62c4a83d-7f98-49a8-ab08-05c6a6a56542`.
Hermes completed one real API call at 06:44:15.978235 UTC. Its exact response
was saved in the isolated workspace by the adapter and checked against the test
marker: 29 bytes, SHA256
`8e772a5b281518913c6d891a12eaa20fc7a9893dcf1ce9d6765eaae65e2c9679`.
Retrieval input 6718368636 produced done OUT 6718369035, read through the
GitHub connector. Replaying the identical input twice retained exactly one job.
Fresh management health at 06:44:06 UTC was verified.

The earlier actual bridge-only restart evidence was revalidated: distinct old/new
PID, both completed jobs, their artifacts and the same native session still exist.
A redundant restart during this final pass was denied because sudo requires a
password; no bypass or additional service restart was attempted. Restart acceptance
uses the earlier successful real test, rather than claiming a fresh restart.

Final checks: 15 bridge/progress/scheduler tests passed. No implementation behavior
changed in this acceptance pass; the implementation and tests were already pushed
in 4f6c69f. Existing unrelated working-tree changes were preserved.

Live proposal input 6718373154 created job
`f5c5d84a-2223-4d4e-87a1-2feb9dbc4dfc`; the existing management Telegram
accepted its delivery at 06:45:06.859942 UTC. It remains `awaiting_owner`,
`approval_granted=false`. No actual owner approval was simulated or required
for this transport delivery check.
