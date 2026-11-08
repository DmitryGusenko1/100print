# Issue 22 — operating access repaired; owner/bootstrap and site source pending

Verified on 2026-11-08. Management is exclusively hundredprintbot;
WebToPrintISbot remains disabled in project configuration. No client credentials,
production data or other projects were accessed.

The real private Telegram exchange at 06:30–06:31 UTC (11:30–11:31 Almaty)
contains inbound, a model API call and outbound delivery. The exact tool failure
at 06:30:54 was `bwrap: Creating new namespace failed: Permission denied`.
The retry at 06:30:58 returned `Rejected("rejected by user")`: the unattended
Hermes Codex approval adapter fails closed. This was not a Unix file permission
failure. Cwd was the empty project runtime sandbox; the absolute plan path was
correct. Private transcripts stay local; no chat identifiers/content are exported.

A per-Hermes Codex wrapper now exposes two bounded local MCP methods:
`project_read` lists/reads tracked Markdown/Python/JSON in explicit project
subdirectories; credentials, runtime, traversal, symlinks and oversized files
are denied. `executor_probe` submits/reads one deduplicated fixed echo task in
the real ceo_orchestrator queue. Only these two MCP tools have explicit approve
policy. Shell/file approvals, workspace-write sandbox and global config are
unchanged. This avoids the unavailable namespace mechanism for these bounded
operations without enabling arbitrary host shell execution. The failed initial
MCP acceptance was corrected with per-tool policy and rechecked in a real
Hermes local session through the running gateway, not just a shell read.

Reapply with `python3 ai-team/ops/configure-project-access.py`, then restart only
the ceo-ai-team-hermes-gateway user service. SOUL points Hermes to these tools
instead of asking the owner to copy documents. The original night draft remains
DRAFT. Day plan DAY-2026-11-08-v1 defines artifacts, dependencies and acceptance
criteria; status requests confer no approval.

Native `/sethome` is supported. Existing home configuration already matches
exactly the one positive private user/chat in the owner allowlist and the real
Telegram session. No group was chosen, no binding change or owner command needed.
Fresh management-readiness --e2e passes after gateway reload. #21 already waits
for the owner-plan marker, not telegram-e2e; that distinction is retained.

Environment discovery: this repository contains the orchestrator, Hermes and
Paperclip deployment, but no customer website source/vhost/container deployment
mapping. Scoped systemd services show the orchestrator and private Paperclip;
there is no site/staging unit among permitted ceo-*/ai-business-brain-* units.
No matching project nginx/compose/deploy file was found. Candidate
https://web2print.almaunion.com fails VPS DNS resolution (name not known) and
could not be opened by the web tool. It is not confirmed production. System
nginx/docker presence and listening ports do not establish ownership; their
external configs/other projects are outside the authorized filesystem boundary.
No global container enumeration or foreign .env read was performed.
A private staging-preparation directory and environment inventory were created;
they are NOT a running website or a substitute application. A real staging build
is blocked by absent website source and deploy mapping. Minimal unblock: make
the site's source/deploy checkout available under ai-team/tasks/site-source
within this workspace (or explicitly authorize its precise existing location).
No production changes, customer records, payments or integrations were used.

Paperclip health is authenticated/private on 127.0.0.1:3180, bootstrap_pending,
bootstrapInviteActive=true. Server/Postgres are active; heartbeat scheduling
stays disabled. The existing private bootstrap invitation is available in the
0600 runtime secret file. The owner must personally register via the loopback
panel through an SSH tunnel; no user account, company or agent was fabricated.
The private owner flow is sent only to the verified personal hundredprintbot chat.
After personal registration, marker data/issue22-owner-ready can resume #22;
this marker does not approve a work plan. Server profile application remains
blocked until that real human registration.

ceo-github-worker, ceo-github-watcher and ceo-orchestrator are active, with a fresh
orchestrator heartbeat. The MCP probe was submitted by Hermes and the actual
worker completed it. This proves a bounded queue/result route, not a website
coding executor or autonomous Paperclip team. Those functional routes still
require implementation/acceptance after genuine owner approval and source access.
Do not promise unsupervised functional website work on the strength of echo.

Policy basis for narrow per-tool grants: [official OpenAI documentation](https://developers.openai.com/plugins/build/plugins).

Acceptance completed: 15 unit tests passed (project access boundaries, progress,
and durable Hermes bridge). A second real Hermes session retrieved the finished
queue probe and read the exact day-plan heading. Usage receipts show completed
model calls; underlying queue has status done and the expected fixed echo result.
Telegram getMe/getChat verified management identity and private target before
both messages were delivered; local receipts persist without exporting IDs or
bootstrap URLs. Owner setup invitation route returns HTTP 200. No approval was
inferred from these technical tests or deliveries.

Remaining status is WAITING_USER, not DONE: personal Paperclip registration,
website source/deployment access, genuine plan approval and functional executor
acceptance remain outstanding. The first resumable UI gate is the owner marker
created only after real registration; other blockers must still be resolved on
resume. A pre-existing unrelated gateway unit modification is excluded.
