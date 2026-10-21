#!/usr/bin/env python3
"""Verify real Telegram delivery, shared artifacts and optional service restart.

No synthetic Telegram updates or sends are produced by this verifier.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import connect


def evidence():
    with connect() as conn, conn.cursor() as cur:
        cur.execute('''SELECT i.*,t.result,t.status FROM telegram_inbox i
            JOIN tasks t ON t.id=i.task_id
            WHERE t.status='done' ORDER BY i.created_at DESC LIMIT 1''')
        item = cur.fetchone()
        assert item, 'No completed real Telegram task'
        uid, cid = item['update_id'], str(item['conversation_id'])
        result = item['result']
        assert result['provider'] == 'production-codex-v1' and result['demonstration'] is False
        cur.execute('SELECT id,state,telegram_message_id,text FROM telegram_outbox WHERE update_id=%s ORDER BY part', (uid,))
        outbox = cur.fetchall()
        assert outbox and all(r['state'] == 'sent' and r['telegram_message_id'] for r in outbox), 'Telegram reply not confirmed'
        cur.execute("SELECT role,dedupe_key,text FROM project_memory WHERE conversation_id=%s AND kind='message'", (cid,))
        messages = {r['dedupe_key']: r for r in cur.fetchall()}
        assert messages[f'telegram:update:{uid}']['role'] == 'user'
        for part in outbox:
            message = messages[f'telegram:outbox:{part["id"]}']
            assert message['role'] == 'assistant' and message['text'] == part['text']
        cur.execute('SELECT step_key FROM organization_steps WHERE task_id=%s', (item['task_id'],))
        keys = sorted(r['step_key'] for r in cur.fetchall())
        assert 'analytical/v1' in keys and (any('critic' in key for key in keys) or 'round/5' in keys), 'Missing Critic artifacts'
        cur.execute('SELECT kind,count(*) AS n FROM project_memory WHERE task_id=%s GROUP BY kind', (item['task_id'],))
        artifacts = {r['kind']:r['n'] for r in cur.fetchall()}
        assert artifacts.get('specialist_result', 0) and artifacts.get('decision', 0)
        if result.get('routing', {}).get('level') == 'L4':
            assert artifacts.get('council_round', 0) and all(f'round/{i}' in keys for i in range(7))
        return {'update_id':uid, 'task_id':str(item['task_id']), 'provider':result['provider'],
                'demonstration':False, 'outbox_ids':[r['id'] for r in outbox],
                'telegram_message_ids':[r['telegram_message_id'] for r in outbox],
                'artifacts':artifacts, 'checkpoints':keys}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait', type=int, default=0)
    parser.add_argument('--restart', action='store_true', help='Requires service-management permission')
    args = parser.parse_args()
    deadline = time.monotonic()+args.wait
    while True:
        try:
            before = evidence()
            break
        except Exception:
            # Never print database errors or environment values.
            if time.monotonic() >= deadline:
                raise SystemExit('E2E not verified: completed Telegram delivery/artifacts missing') from None
            time.sleep(3)
    subprocess.run(['systemctl', 'is-active', '--quiet', 'ceo-telegram-bot.service'], check=True)
    subprocess.run(['systemctl', 'is-enabled', '--quiet', 'ceo-telegram-bot.service'], check=True)
    if args.restart:
        subprocess.run(['systemctl', 'restart', 'ceo-telegram-bot.service'], check=True)
        time.sleep(15)
        assert evidence() == before, 'Evidence changed across restart; inspect before declaring success'
        subprocess.run(['systemctl', 'is-active', '--quiet', 'ceo-telegram-bot.service'], check=True)
    print(json.dumps(dict(before, restart_verified=args.restart), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
