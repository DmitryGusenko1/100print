#!/usr/bin/env python3
"""Check only project credentials, suppressing token-bearing HTTP errors."""
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from app.db import ROOT, connect
from app.telegram_bot import api


def main():
    load_dotenv(ROOT/'config/telegram.env', override=True)
    if not os.getenv('CEO_TELEGRAM_TOKEN') or not any(os.getenv(k, '').strip() for k in ('CEO_TELEGRAM_ALLOWED_USERS', 'CEO_TELEGRAM_ALLOWED_CHATS')):
        raise SystemExit('Project token and explicit allowlist required')
    try:
        api('getMe', {})
        if api('getWebhookInfo', {}).get('url'):
            raise SystemExit('Existing webhook detected; resolve transport ownership before polling')
        with connect() as conn, conn.cursor() as cur:
            from app.telegram_bot import health
            status = health(cur)
            if 'provider=production-codex-v1' not in status or 'worker=OK' not in status:
                raise SystemExit('Production worker is not ready')
    except Exception:
        raise SystemExit('Project Telegram API or shared memory preflight failed; secrets suppressed') from None
    print('Project Telegram credentials, polling mode, production worker and shared memory verified')


if __name__ == '__main__':
    main()
