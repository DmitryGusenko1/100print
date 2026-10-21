#!/usr/bin/env python3
"""Verify a real 100-printshops Telegram reply from the current formatter."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import connect, ROOT
from app.telegram_presentation import render_result


def main():
    with connect() as conn, conn.cursor() as cur:
        cur.execute('''SELECT i.update_id,t.payload,t.result FROM telegram_inbox i
            JOIN tasks t ON t.id=i.task_id WHERE t.status='done'
            AND t.payload->>'problem' LIKE '%%100%%'
            AND t.payload->>'problem' ILIKE '%%типограф%%'
            AND i.created_at > to_timestamp(%s)
            ORDER BY i.created_at DESC LIMIT 1''',
            ((ROOT/'app/telegram_presentation.py').stat().st_mtime,))
        row = cur.fetchone()
        assert row, 'Send a new real Telegram question about the idea of 100 printshops'
        result = row['result']
        assert result.get('provider') == 'production-codex-v1' and result.get('demonstration') is False
        cur.execute("SELECT text,state,telegram_message_id FROM telegram_outbox WHERE update_id=%s AND kind='final' ORDER BY part", (row['update_id'],))
        parts = cur.fetchall()
        assert parts and all(p['state'] == 'sent' and p['telegram_message_id'] for p in parts), 'Final delivery not confirmed'
        text = ''.join(p['text'] for p in parts)
        assert text == render_result(result, row['payload']['problem']), 'Delivered reply uses an older formatter'
        assert '**Вывод**' in text and not text.lstrip().startswith('{'), 'Executive format missing'
    print('Real Telegram executive reply and unchanged structured result verified')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('E2E not verified: new real 100-printshops executive reply required') from None
