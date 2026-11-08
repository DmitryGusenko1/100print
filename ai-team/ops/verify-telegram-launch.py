#!/usr/bin/env python3
"""Verify technical launch; send only to the configured private project owner."""
import datetime
import json
import os
import subprocess
import sqlite3
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import dotenv_values
import importlib.util

BASE = Path('/opt/ceo-orchestrator')
TEAM = BASE / 'ai-team'


def atomic(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def main():
    os.umask(0o077)
    spec = importlib.util.spec_from_file_location('preparation', TEAM / 'ops/prepare-telegram.py')
    preparation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preparation)
    token, owner = preparation.credentials(dotenv_values(BASE / 'config/telegram.env'))
    configured = dotenv_values(TEAM / 'runtime/hermes-home/.env')

    def api(method, payload=None):
        body = urllib.parse.urlencode(payload).encode() if payload else None
        with urllib.request.urlopen(f'https://api.telegram.org/bot{token}/{method}', data=body, timeout=20) as response:
            result = json.load(response)
        if result.get('ok') is not True:
            raise RuntimeError('Telegram method did not succeed')
        return result['result']

    environment = dict(os.environ, XDG_RUNTIME_DIR=f'/run/user/{os.getuid()}')
    environment['DBUS_SESSION_BUS_ADDRESS'] = f"unix:path={environment['XDG_RUNTIME_DIR']}/bus"
    pid = subprocess.check_output(['systemctl', '--user', 'show', 'ceo-ai-team-hermes-gateway', '-p', 'MainPID', '--value'], env=environment, text=True).strip()
    active = subprocess.run(['systemctl', '--user', 'is-active', '--quiet', 'ceo-ai-team-hermes-gateway'], env=environment).returncode == 0
    old_inactive = subprocess.run(['systemctl', 'is-active', '--quiet', 'ceo-telegram-bot'], stdout=subprocess.DEVNULL).returncode != 0
    state = json.loads((TEAM / 'runtime/hermes-home/gateway_state.json').read_text())
    platform = state.get('platforms', {}).get('telegram', {})
    connected = platform.get('state') == 'connected' and str(state.get('pid')) == pid
    with sqlite3.connect(f"file:{TEAM / 'runtime/hermes-home/state.db'}?mode=ro", uri=True) as db:
        row = db.execute("SELECT s.api_call_count,m.content,m.timestamp FROM sessions s JOIN messages m ON m.session_id=s.id WHERE s.source='oneshot' AND m.role='assistant' ORDER BY m.timestamp DESC LIMIT 1").fetchone()
    now = datetime.datetime.now(datetime.timezone.utc)
    inference = bool(row and row[0] > 0 and row[1].strip() == 'HERMES_INFERENCE_OK'
                     and 0 <= now.timestamp() - row[2] < 600)
    allowlist = configured.get('TELEGRAM_ALLOWED_USERS') == owner and configured.get('TELEGRAM_BOT_TOKEN') == token
    allowlist = allowlist and configured.get('TELEGRAM_ALLOW_ALL_USERS', '').lower() not in ('true', '1')
    identity = api('getMe')
    getme = bool(identity.get('id')) and identity.get('username') == 'WebToPrintISbot'
    no_webhook = not api('getWebhookInfo').get('url')
    gateway = active and connected and old_inactive and no_webhook and getme
    sent_path = TEAM / 'runtime/owner-launch-WebToPrintISbot.json'
    if inference and gateway and allowlist and getme and not sent_path.exists():
        sent = api('sendMessage', {'chat_id': owner, 'text': 'Дмитрий, Hermes подключён: модель отвечает, постоянный Telegram gateway запущен. Это техническая готовность к диалогу; полный DoD Paperclip ещё не завершён.\n\nЧерновик ночного плана: 1) проверить клиентский сценарий сайта в тестовой среде; 2) исправить только подтверждённые ошибки там и проверить результат; 3) исследовать трёх конкурентов. До вашего утверждения работы не запускаются. Утренний отчёт — Asia/Almaty, только по реальным артефактам.\n\nОтветьте мне здесь, чтобы проверить диалог, и укажите URL сайта/тестовую среду. Если согласны с этим планом, явно напишите «Утверждаю ночной план». Регистрация владельца Paperclip остаётся отдельным шагом.'})
        atomic(sent_path, {'message_id': sent['message_id'], 'date': sent['date'], 'bot_username': identity['username']})
    request = json.loads((BASE / 'data/ai-team-launch-request.json').read_text())
    receipt = {'request_id': request['request_id'], 'model_inference': inference, 'gateway_active': gateway,
               'owner_allowlist': allowlist, 'outbound_owner_message': getme and sent_path.exists(),
               'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    verified = all(receipt[k] for k in ('model_inference', 'gateway_active', 'owner_allowlist', 'outbound_owner_message'))
    receipt['status'] = 'VERIFIED' if verified else 'BLOCKED'
    if not verified:
        receipt['public_reason'] = ('Configured Telegram bot is not WebToPrintISbot; update project credentials.'
                                    if not getme else 'Technical launch checks incomplete; see individual booleans.')
    atomic(BASE / 'data/ai-team-telegram-ready.json', receipt)
    atomic(TEAM / 'evidence/telegram-launch.json', dict(receipt, gateway_pid=int(pid), getMe=getme, bot_username=identity.get('username'),
           webhook_absent=no_webhook, previous_consumer_inactive=old_inactive,
           inbound_e2e='NOT_RUN', owner_approval='DRAFT', paperclip_owner='bootstrap_pending'))
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
