#!/usr/bin/env python3
"""Deliver the authorized issue22 plan/setup once to the verified private owner."""
import json
import os
from pathlib import Path
import re
import sqlite3
import urllib.parse
import urllib.request
from dotenv import dotenv_values

ROOT = Path('/opt/ceo-orchestrator')
HOME = ROOT / 'ai-team/runtime/hermes-home'


def main():
    os.umask(0o077)
    native = dotenv_values(HOME / '.env')
    project = dotenv_values(ROOT / 'config/telegram.env')
    token, owner = native.get('TELEGRAM_BOT_TOKEN'), native.get('TELEGRAM_ALLOWED_USERS', '')
    if not owner.isdecimal() or int(owner) <= 0 or project.get('CEO_TELEGRAM_ALLOWED_CHATS') != owner or token != project.get('CEO_TELEGRAM_TOKEN'):
        raise ValueError('Private owner binding mismatch')

    def api(method, payload=None):
        data = urllib.parse.urlencode(payload).encode() if payload else None
        with urllib.request.urlopen(f'https://api.telegram.org/bot{token}/{method}', data=data, timeout=20) as response:
            result = json.load(response)
        if not result.get('ok'):
            raise ValueError('Telegram request failed')
        return result['result']

    if api('getMe').get('username') != 'hundredprintbot':
        raise ValueError('Wrong management bot')
    chat = api('getChat', {'chat_id': owner})
    if chat.get('type') != 'private' or str(chat.get('id')) != owner:
        raise ValueError('Not the confirmed private owner chat')
    with sqlite3.connect(f'file:{HOME / "state.db"}?mode=ro', uri=True) as db:
        if not db.execute("SELECT 1 FROM sessions WHERE source='telegram' AND user_id=? AND chat_id=? AND api_call_count>0", (owner, owner)).fetchone():
            raise ValueError('Real owner session missing')

    bootstrap = (ROOT / 'ai-team/runtime/secrets/owner-bootstrap.txt').read_text()
    links = re.findall(r'http://localhost:3180/invite/[^\s\x1b]+', bootstrap)
    if len(links) != 1:
        raise ValueError('Expected one private owner invitation')
    health = json.load(urllib.request.urlopen('http://127.0.0.1:3180/api/health', timeout=10))
    if health.get('bootstrapStatus') != 'bootstrap_pending' or not health.get('bootstrapInviteActive'):
        raise ValueError('Bootstrap state changed; recheck before delivery')
    # Verify the actual panel route is served; never redeem/register as the owner.
    if urllib.request.urlopen(links[0], timeout=10).status != 200:
        raise ValueError('Owner flow unavailable')

    setup = ('Issue22: Paperclip работает, нужна ваша личная регистрация. '
             'Панель приватная, на loopback VPS. Через ваш обычный SSH-доступ откройте туннель '
             'с локальным портом 3180 на 127.0.0.1:3180 VPS '
             '(ssh -N -L 3180:127.0.0.1:3180 <ваш-SSH-VPS>). '
             'На своём компьютере откройте личное приглашение: ' + links[0] +
             '\nСсылку не публикуйте. После реальной регистрации создайте '
             '/opt/ceo-orchestrator/data/issue22-owner-ready для продолжения серверной настройки. '
             'Это не утверждение рабочего плана.')
    plan = ('Issue22: чтение плана из Hermes исправлено без отключения глобальных approvals; '
            'личный home channel подтверждён; реальный Telegram E2E проверен. '
            'Очередь исполняет безопасную echo-пробу; функциональный исполнитель сайта ещё не подтверждён.\n\n' +
            (ROOT / 'ai-team/roles/day-plan-2026-11-08.md').read_text())
    receipts = ROOT / 'data/issue22-owner-delivery.json'
    saved = json.loads(receipts.read_text()) if receipts.exists() else {}
    for label, text in (('setup', setup), ('plan', plan)):
        if label in saved:
            continue
        if len(text) > 4096:
            raise ValueError('Message exceeds Telegram text limit')
        result = api('sendMessage', {'chat_id': owner, 'text': text, 'disable_web_page_preview': 'true'})
        saved[label] = {'message_id': result['message_id'], 'date': result['date'],
                        'bot': 'hundredprintbot', 'plan_id': 'DAY-2026-11-08-v1'}
        receipts.write_text(json.dumps(saved, indent=2) + '\n')
        receipts.chmod(0o600)
    print('Private owner setup and plan delivery verified; no approval inferred.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Owner delivery failed; private configuration requires local inspection') from None
