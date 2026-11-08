# ChatGPT ↔ Hermes bridge #8

Transport: https://github.com/DmitryGusenko1/100print/issues/8.
Only comments authored by DmitryGusenko1 are accepted. Public repository: send
only sanitized technical instructions. Never post Telegram conversations,
customer context, credentials, OAuth links/codes or private artifacts.

```
CHATGPT_IN
session=<stable unique chat session>
message=submit_task
<sanitized task>
```

Supported message operations (each argument starts on the next real line):

- `status`: last verified management health with checked_at and job counts.
- `submit_task\n<task>`: durable queued job; ordinary text is an alias.
- `get_task_result\n<task UUID>`: same session only; queued/running/awaiting_owner/done/failed.
- `propose_owner\n<sanitized proposal>`: send to the existing management Telegram,
  leaving awaiting_owner. This never approves or executes the proposal.
- `CONTEXT\n<query>`: compatible context receipt; private text stays on VPS,
  public response contains memory counts.
- `DECISION\n<explicit user decision>`: saved reported decision with memory_id;
  approval_granted=false. Passing information grants no additional permission.

Responses start CHATGPT_OUT, followed by session, task_id and result JSON.
Match result.request_comment_id to the input comment ID. The outer task_id is
the receipt ID; result.task_id is the durable Hermes job ID for retrieval.
Do not resubmit while waiting: reread comments, then request get_task_result.
A done result reports provider=hermes, actual API call count, completion time,
and artifact hashes/sizes. Model text and full artifacts remain private on VPS.
There is no legacy provider fallback. Do not invent an answer from a queued receipt.

The existing ceo-github-watcher runs both intake and a serial durable worker.
Hermes uses its installed `-z --usage-file --resume` interface, preserving native
session IDs by bridge session. Workspaces and private outputs: data/hermes-bridge/.
Queued jobs survive restart. Interrupted running jobs recover a saved completion
receipt or fail with effect_unknown; they are never blindly rerun. GitHub delivery
uses markers, rereads and at most five send attempts. Telegram proposals have one
send attempt; unknown delivery needs reconciliation, never automatic replay.
Awaiting_owner requires actual owner interaction; no approval is simulated.

Management bot: hundredprintbot. Future customer bot WebToPrintISbot is disabled
by project policy and is not a bridge prerequisite. Health verification checks
the real existing management gateway, allowlist and exclusive consumer. It is
not proof of genuine inbound Telegram E2E or approval of any plan.

Long tasks live on VPS after ChatGPT's response ends. This bridge cannot open
this chat or start ChatGPT in the background. ChatGPT reads the bridge only in
an active dialogue or a separately configured scheduled task.

`done` certifies a completed inference and saved response artifact, not independent
verification of every action requested in prose. Native Codex file tools currently
fail closed in unattended Hermes sessions. The E2E artifact is the exact model
response saved by the adapter; no native tool permission was broadened. Do not
claim that an arbitrary requested file edit succeeded from this receipt alone.
