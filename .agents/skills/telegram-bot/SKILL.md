---
name: telegram-bot
description: Implements reliable Telegram bot flows for 100print with authorization, deduplication, persistent project selection, and failure-safe processing.
---

# Telegram Bot

Use for Telegram commands, message handling, polling/webhooks, and bot UX.

## Required behavior
- Authorize the Telegram user before reading or saving protected data.
- Persist the active project on the server, not only in process memory.
- Deduplicate repeated Telegram deliveries using stable external IDs.
- Processing order: authorize -> persist inbound message -> load context -> call AI -> persist verified response -> send response.
- If AI fails, keep the inbound message and surface an accurate failure state.
- If Telegram send fails after persistence, do not regenerate a different answer automatically without idempotency protection.

## Commands
For the memory bot, support at minimum `/start`, `/projects`, `/project`, and `/status` unless requirements change.

## Operations
Only one polling process may consume a production bot token. Log operational metadata without logging secrets or private message text by default.
