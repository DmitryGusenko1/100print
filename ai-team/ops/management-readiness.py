#!/usr/bin/env python3
"""Read-only readiness for the isolated management transport, without polling."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import urllib.request
from dotenv import dotenv_values

BASE = Path('/opt/ceo-orchestrator')
HOME = BASE / 'ai-team/runtime/hermes-home'
TARGET = 'hundredprintbot'


def exclusive_consumer(expected_pid):
    consumers = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != os.getuid() or not (proc / 'cwd').resolve().is_relative_to(BASE):
                continue
            argv = (proc / 'cmdline').read_bytes().split(b'\0')
            # Match argv elements, never the command text of a diagnostic shell.
            hermes = any(Path(a.decode(errors='replace')).name == 'hermes' for a in argv)
            gateway = hermes and b'gateway' in argv and b'run' in argv
            legacy = b'app.telegram_bot' in argv
            if gateway or legacy:
                consumers.append(proc.name)
        except (PermissionError, FileNotFoundError, ProcessLookupError):
            continue
    return consumers == [str(expected_pid)]


def check(e2e=False):
    values = dotenv_values(HOME / '.env')
    project = dotenv_values(BASE / 'config/telegram.env')
    token = values.get('TELEGRAM_BOT_TOKEN')
    owner = values.get('TELEGRAM_ALLOWED_USERS', '')
    if not token or token != project.get('CEO_TELEGRAM_TOKEN') or not owner.isdecimal():
        return False
    if project.get('CEO_TELEGRAM_ALLOWED_CHATS') != owner or values.get('TELEGRAM_ALLOW_ALL_USERS', '').lower() in ('true', '1'):
        return False
    env = dict(os.environ, XDG_RUNTIME_DIR=f'/run/user/{os.getuid()}')
    env['DBUS_SESSION_BUS_ADDRESS'] = f"unix:path={env['XDG_RUNTIME_DIR']}/bus"
    for state in ('is-active', 'is-enabled'):
        if subprocess.run(['systemctl', '--user', state, '--quiet', 'ceo-ai-team-hermes-gateway'], env=env).returncode:
            return False
    if subprocess.run(['systemctl', 'is-active', '--quiet', 'ceo-telegram-bot']).returncode == 0:
        return False
    for method in ('getMe', 'getWebhookInfo'):
        with urllib.request.urlopen(f'https://api.telegram.org/bot{token}/{method}', timeout=15) as response:
            data = json.load(response)
        if not data.get('ok'):
            return False
        if method == 'getMe' and data['result'].get('username') != TARGET:
            return False
        if method == 'getWebhookInfo' and data['result'].get('url'):
            return False
    state = json.loads((HOME / 'gateway_state.json').read_text())
    pid = subprocess.check_output(['systemctl', '--user', 'show', 'ceo-ai-team-hermes-gateway', '-p', 'MainPID', '--value'], env=env, text=True).strip()
    if not exclusive_consumer(pid):
        return False
    if str(state.get('pid')) != pid or state.get('platforms', {}).get('telegram', {}).get('state') != 'connected':
        return False
    if not e2e:
        return True
    sent = json.loads((BASE / 'ai-team/runtime/owner-launch-hundredprintbot.json').read_text())
    if sent.get('bot_username') != TARGET:
        return False
    # Only genuine private Telegram sessions after this launch's owner message.
    # No owner content is printed or exported.
    with sqlite3.connect(f'file:{HOME / "state.db"}?mode=ro', uri=True) as db:
        row = db.execute('''SELECT 1 FROM sessions s JOIN messages u ON u.session_id=s.id
          JOIN messages a ON a.session_id=s.id
          WHERE s.source='telegram' AND s.user_id=? AND s.chat_id=?
          AND u.role='user' AND u.timestamp>? AND a.role='assistant'
          AND a.timestamp>u.timestamp AND length(trim(a.content))>0
          AND s.api_call_count>0 LIMIT 1''', (owner, owner, sent['date'])).fetchone()
    return bool(row)


if __name__ == '__main__':
    try:
        ready = check('--e2e' in sys.argv)
    except Exception:
        ready = False
    print('Management readiness: ' + ('verified' if ready else 'pending'))
    raise SystemExit(0 if ready else 1)
