# Issue 21 — management verified; plan approval pending

Fresh verification on 2026-11-08: management_bot=hundredprintbot.
Existing Hermes authorization and private configuration were preserved.
Bounded inference completed within 90 seconds with one real API call and
HERMES_INFERENCE_OK. Persistent user gateway is active/enabled and connected;
its PID matches runtime state. Exactly one project consumer, legacy poller
inactive, management webhook absent, private owner allowlist preserved.
No reinstall or gateway restart was necessary in this execution.

The existing successful owner readiness delivery receipt was retained to avoid
repeated notifications. Genuine private owner inbound followed by model reply
passes the live E2E gate. No inbound message or approval was synthesized.
Night plan is still DRAFT; transport readiness does not establish team readiness.

Customer_bot=WebToPrintISbot is disabled by project policy. The scoped settings,
Hermes cron and project service definitions contain no client binding, route,
poller or sender job. One distinct token returns hundredprintbot. No client
integration was available to disable. Without a client token its global webhook
cannot be verified or deleted; this does not block management. No token, history
or pending updates were deleted. See ai-team/evidence/issue21-bot-audit.json.

All management target helpers now expect hundredprintbot. #18 retains its
Paperclip owner bootstrap marker requirement; its Telegram checks pass. #19 is
resumed for independent bridge acceptance with current management health and no
client dependency. #20 is superseded and its stale token blocker removed.

Validation: worker, bridge and progress unit tests, credential/preparation tests,
live identity/webhook, bounded inference, systemd/consumer/allowlist and inbound
E2E checks. Existing unrelated working tree changes excluded from commit.
Full #21 remains WAITING_USER for explicit owner plan approval. After actual
approval, confirmation marker: data/issue21-owner-plan-approved.

Issue22 follow-up: the 06:30–06:31 UTC private owner exchange confirms E2E.
There is no remaining telegram-e2e wait in #21; its owner-plan wait is valid.
Current proposal is DAY-2026-11-08-v1, delivered privately by hundredprintbot.
The status request was not approval. See [issue22](ISSUE22_STATUS.md).
