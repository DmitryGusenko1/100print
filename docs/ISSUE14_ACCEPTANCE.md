# Issue 14 acceptance

Telegram now presents public business fields through `app/telegram_presentation.py`.
Default: conclusion, up to three ideas, two risks and three actions, confidence when
provided. Normal replies are capped at 1200 characters, L1 at 600, Council at 1800.
Short answers stay short. Omitted content is signposted with the detail offer.
Explicit «подробно», «детально», «разбери» enables a longer business report including
assumptions, KPI, owners and deadlines. Internal fields are never serialized.
Telegram uses escaped HTML with bold headings; transport chunking remains durable.
Full task results, organization artifacts, ChatGPT API and bridge are unchanged.
Status and failures use short user-facing language without task IDs or metadata.

LIVE: ceo-telegram-bot.service restarted under its existing owner using SIGTERM
and the configured systemd Restart=always policy (systemctl management required
interactive authentication). The new process is active/running; project Telegram
preflight confirms credentials, allowlist and production-worker readiness.
Verified on 2026-10-21: a new real user question about 100 printshops received a
confirmed final Telegram delivery matching the current formatter exactly. The reply
is 998 characters and includes conclusion, main ideas, Critic and next actions.
Verify with:

```
.venv/bin/python scripts/verify_telegram_format.py
.venv/bin/python scripts/verify_telegram.py
```

The format verifier requires a new real inbox entry after formatter modification,
a confirmed final Telegram delivery, and exact equality with the current presenter.
Old Telegram deliveries and simulated sends do not count as LIVE E2E.

TESTED: acceptance verifiers `verify_telegram_format.py`, `verify_telegram.py` and
`telegram_preflight.py` passed on 2026-10-21. Full unittest discovery passed
(69 tests). Coverage includes detailed request
routing, HTML escaping, confirmed delivery, unknown-field suppression and
unchanged structured DB results. `git diff --check` passed.

FORMAT: executive summary, bounded length and escaped HTML verified.
LIVE: active production Telegram bot; credentials and worker readiness verified.
E2E: real 100-printshops reply delivered; shared memory and artifacts verified.
USER_ACTION: NONE
LIMITATIONS: detailed reports remain longer when explicitly requested.
