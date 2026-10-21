# Issue #11 — Telegram LIVE acceptance

Verified on 2026-10-21 against the existing 100print deployment.

- `ceo-telegram-bot.service`: active, enabled, User=ceoorch, Restart=always.
- Project-only credentials pass Telegram getMe, polling ownership, shared memory
  and production worker preflight. The ignored EnvironmentFile is owned by
  ceoorch with mode 0600; no credentials are included here.
- Real inbound update 27208783 completed task
  `193280ec-e716-4f65-aef2-b2b5d2d1c94b` using `production-codex-v1`,
  `demonstration=false`. ACK was confirmed after 3.481367 seconds. ACK, progress
  and final reply parts have confirmed Telegram message IDs.
- The verifier matched the user message and every delivered assistant part in
  shared PostgreSQL memory. Structured artifacts include four specialist results,
  forty Council artifacts and a decision, with analytical/Critic checkpoints and
  Council rounds 0–6.
- Restart verification used SIGTERM on the service's verified, ceoorch-owned
  MainPID. systemd automatically started a different PID; the service remained
  active/enabled and all delivery evidence remained identical. Direct systemctl
  restart requires administrative authentication in this executor environment.

Reproduce the read-only checks with:

```sh
.venv/bin/python scripts/telegram_preflight.py
.venv/bin/python scripts/verify_telegram.py
.venv/bin/python -m unittest discover -s tests -t . -q
```

Existing transactional inbox/session/task keys and unique outbox entries provide
retry deduplication. Tests cover repeated intake/collection and interrupted sends.
Telegram has no sendMessage idempotency key: ambiguous sends are quarantined as
`uncertain` and require reconciliation rather than automatic resend. Absolute
exactly-once delivery across Telegram and PostgreSQL cannot be guaranteed.

This acceptance supersedes the earlier waiting-for-E2E state. No additional token,
allowlist, UI confirmation or user message is needed for issue #11.

Validation: all 69 tests passed (143.888 seconds). The runtime restart test now
also tolerates psycopg2 InterfaceError while its intentionally killed worker and
private PostgreSQL recover; previously this secondary disconnect error escaped
the retry loop and caused subsequent database checks to fail during shutdown.
