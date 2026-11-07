#!/usr/bin/env python3
"""Prepare isolated Hermes transport. Never stop or start a Telegram consumer."""
import json
import os
import shutil
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

BASE = Path('/opt/ceo-orchestrator')
TEAM = BASE / 'ai-team'


def credentials(values):
    token = values.get('CEO_TELEGRAM_TOKEN', '')
    chats = {v.strip() for v in values.get('CEO_TELEGRAM_ALLOWED_CHATS', '').split(',') if v.strip()}
    users = {v.strip() for v in values.get('CEO_TELEGRAM_ALLOWED_USERS', '').split(',') if v.strip()}
    # A private Telegram chat id equals its user's id. Never turn a group into an owner.
    if not token or len(chats) != 1 or not all(v.isdecimal() and int(v) > 0 for v in chats):
        raise ValueError('Need exactly one configured private owner chat; no group or guessed owner')
    owner = next(iter(chats))
    if users and users != {owner}:
        raise ValueError('Configured owner chat and user allowlists disagree')
    return token, owner


def main():
    os.umask(0o077)
    token, owner = credentials(dotenv_values(BASE / 'config/telegram.env'))
    home = TEAM / 'runtime/hermes-home'
    home.mkdir(mode=0o700, exist_ok=True)
    secret = home / '.env'
    if secret.exists():
        raise SystemExit('Refusing to overwrite existing Hermes secrets')
    secret.write_text(f'TELEGRAM_BOT_TOKEN={token}\nTELEGRAM_ALLOWED_USERS={owner}\n')
    secret.chmod(0o600)
    for skill in (TEAM / 'skills').iterdir():
        if skill.is_dir():
            shutil.copytree(skill, home / 'skills' / skill.name, dirs_exist_ok=True)
    evidence = {'owner_allowlist_prepared': True, 'consumer_started': False}
    for method in ('getMe', 'getWebhookInfo'):
        try:
            with urllib.request.urlopen(f'https://api.telegram.org/bot{token}/{method}', timeout=15) as r:
                data = json.load(r)
            evidence[method + '_ok'] = data.get('ok') is True
            if method == 'getWebhookInfo':
                evidence['webhook_present'] = bool(data.get('result', {}).get('url'))
        except Exception:
            evidence[method + '_ok'] = False
    # Public evidence contains no ids, token, bot identity, URL, or API response.
    (TEAM / 'evidence/telegram-preparation.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
