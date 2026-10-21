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
A new real user question about the idea of 100 printshops remains required.
Verify with:

```
.venv/bin/python scripts/verify_telegram_format.py
.venv/bin/python scripts/verify_telegram.py
```

The format verifier requires a new real inbox entry after formatter modification,
a confirmed final Telegram delivery, and exact equality with the current presenter.
Old Telegram deliveries and simulated sends do not count as LIVE E2E.

TESTED: full unittest discovery passed (58 tests); final presenter/transport suite
passed separately (14 tests), including detailed request routing, HTML escaping,
confirmed delivery, unknown-field suppression and unchanged structured DB result.
A concurrent targeted run collided with the full suite's intentional DB restart;
the isolated final rerun passed. `git diff --check` passed.

FORMAT: implemented. LIVE: active. E2E: waiting for a new real Telegram question.
USER_ACTION: send «Оцени идею 100 типографий» to the existing Telegram bot.
LIMITATIONS: real delivery of the new format has not yet been verified.
