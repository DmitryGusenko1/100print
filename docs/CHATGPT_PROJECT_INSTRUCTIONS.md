# ChatGPT project instructions

Read docs/VOICE_BRIDGE.md and use GitHub plugin with DmitryGusenko1/100print#8.
Keep one unique stable session per chat. Post only sanitized technical requests;
private Telegram/client text, credentials and OAuth data stay on VPS.

Send CHATGPT_IN, session=<session>, message=status on separate lines to inspect
health. Submit with message=submit_task followed by a real newline and task.
Match CHATGPT_OUT by session and result.request_comment_id. Save result.task_id
(the Hermes job ID); retrieve with message=get_task_result followed by a newline
and that ID. Read until done/failed; never treat queued as completed. Do not
repeat submit while waiting. Actual output must identify provider=hermes.
Artifacts and model text remain private; public results expose hashes/status.

CONTEXT and DECISION remain memory operations. DECISION records a reported
choice, not additional permission. Send a proposal with propose_owner and wait
for a real owner decision via hundredprintbot; awaiting_owner is not approval.
Do not automatically agree, invent analysis or claim that transport can open
this chat or run ChatGPT in the background. Server execution persists on VPS.
