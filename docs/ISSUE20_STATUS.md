# Issue 20 — superseded target corrected by issue 21

Current owner instruction: management_bot=hundredprintbot;
customer_bot=WebToPrintISbot (disabled by project policy).
The old request for a client token and credential mismatch blocker are withdrawn.

Fresh 2026-11-08 verification: getMe=hundredprintbot, bounded real Hermes
inference (one API call), gateway active/enabled, connected runtime, exclusive
project consumer, absent management webhook, preserved owner allowlist.
Owner readiness delivery exists and genuine inbound/model E2E passes.
Client integrations were not found in scoped project settings; global client
webhook cannot be checked without its token. No token is requested or deleted.

See ISSUE21_STATUS.md and ai-team/evidence/telegram-launch.json. Night plan
approval remains separate; Paperclip bootstrap blocks full #18 acceptance only.
