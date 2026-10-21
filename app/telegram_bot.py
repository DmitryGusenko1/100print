"""Project Telegram transport with transactional inbox and conservative outbox.

Telegram sendMessage has no idempotency key: ambiguous sends are quarantined,
never automatically resent. This prevents duplicates but can require reconciliation.
"""
import json
import logging
import os
import time
import urllib.request
from app.db import ROOT, connect
from app import project_memory as memory


def api(method, body):
    request = urllib.request.Request(
        'https://api.telegram.org/bot'+os.environ['CEO_TELEGRAM_TOKEN']+'/'+method,
        data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=40) as response:
        result = json.load(response)
    if not result.get('ok'):
        raise RuntimeError('Telegram API rejected request')
    return result['result']


def allowed(message):
    chats = {s.strip() for s in os.getenv('CEO_TELEGRAM_ALLOWED_CHATS', '').split(',') if s.strip()}
    users = {s.strip() for s in os.getenv('CEO_TELEGRAM_ALLOWED_USERS', '').split(',') if s.strip()}
    return (bool(chats or users) and
            (not chats or str(message.get('chat', {}).get('id')) in chats) and
            (not users or str(message.get('from', {}).get('id')) in users))


def queue_reply(cur, update_id, text):
    # UTF-16 units stay below Telegram's limit even for non-BMP characters.
    for part, start in enumerate(range(0, len(text), 1800)):
        cur.execute('INSERT INTO telegram_outbox(update_id,part,text) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING',
                    (update_id, part, text[start:start+1800]))


def health(cur):
    from app.providers import business_brain
    provider = business_brain()
    cur.execute("SELECT updated_at > now()-interval '60 seconds' AS healthy FROM heartbeats WHERE id='orchestrator'")
    row = cur.fetchone()
    return ('100print | provider='+provider.identity+
            ' | demonstration='+str(provider.identity != 'production-codex-v1').lower()+
            ' | memory=ceo_orchestrator/shared OK | worker='+('OK' if row and row['healthy'] else 'STALE'))


def ingest(cur, update):
    message = update.get('message', {})
    if not isinstance(message.get('text'), str) or not message['text'].strip() or not allowed(message):
        return
    uid = update['update_id']
    cur.execute('SELECT pg_advisory_xact_lock(310011)')
    cur.execute('SELECT 1 FROM telegram_inbox WHERE update_id=%s', (uid,))
    if cur.fetchone():
        return
    chat, user = str(message['chat']['id']), str(message['from']['id'])
    cur.execute('SELECT conversation_id FROM telegram_sessions WHERE chat_id=%s AND user_id=%s', (chat, user))
    session = cur.fetchone()
    command = message['text'].split()[0].split('@')[0]
    if session and command != '/new':
        cid = str(session['conversation_id'])
    else:
        cid = str(memory.resume(cur, 'telegram', f'{chat}:{user}:{uid}')['id'])
        cur.execute('''INSERT INTO telegram_sessions VALUES (%s,%s,%s)
            ON CONFLICT(chat_id,user_id) DO UPDATE SET conversation_id=excluded.conversation_id''', (chat,user,cid))
    memory.append(cur, cid, message['text'], request_id=f'telegram:update:{uid}',
                  metadata={'telegram_user_id': user, 'telegram_message_id': message['message_id']})
    cur.execute('INSERT INTO telegram_inbox(update_id,chat_id,user_id,conversation_id) VALUES (%s,%s,%s,%s)', (uid,chat,user,cid))
    replies = {'/start': 'Бот подключён к AI-команде 100print: общая память, специалисты, Critic и Council. Отправьте вопрос. /new — новая сессия; /status — состояние.',
               '/new': 'Новая сессия создана. Общая память 100print доступна.'}
    if command == '/status':
        queue_reply(cur, uid, health(cur))
    elif command in replies:
        queue_reply(cur, uid, replies[command])
    else:
        task = memory.create_task(cur, cid, message['text'], f'telegram:update:{uid}')
        cur.execute('UPDATE telegram_inbox SET task_id=%s WHERE update_id=%s', (task['task_id'],uid))


def collect(cur):
    cur.execute('''SELECT i.update_id,t.id,t.status,t.result FROM telegram_inbox i JOIN tasks t ON t.id=i.task_id
        WHERE t.status IN ('done','failed') AND NOT EXISTS
        (SELECT 1 FROM telegram_outbox o WHERE o.update_id=i.update_id)''')
    for row in cur.fetchall():
        result = row['result'] or {}
        if row['status'] == 'failed':
            text = 'Анализ не завершён. Задача '+str(row['id'])+'. Попробуйте новый запрос.'
        elif result.get('provider') != 'production-codex-v1' or result.get('demonstration') is not False:
            text = 'Production provider недоступен; демонстрационный ответ заблокирован. Задача '+str(row['id'])
        else:
            text = json.dumps(result.get('final') or result.get('analysis') or result, ensure_ascii=False)
        queue_reply(cur, row['update_id'], text)


def deliver_completed():
    with connect() as conn, conn.cursor() as cur:
        collect(cur)
        cur.execute('''SELECT o.*,i.chat_id,i.user_id,i.conversation_id FROM telegram_outbox o
            JOIN telegram_inbox i ON i.update_id=o.update_id WHERE o.state='pending'
            AND NOT EXISTS (SELECT 1 FROM telegram_outbox earlier WHERE earlier.update_id=o.update_id
                AND earlier.part<o.part AND earlier.state!='sent') ORDER BY o.id LIMIT 10 FOR UPDATE OF o SKIP LOCKED''')
        rows = list(cur.fetchall())
        for row in rows:
            if not allowed({'chat': {'id': row['chat_id']}, 'from': {'id': row['user_id']}}):
                continue
            cur.execute("UPDATE telegram_outbox SET state='sending' WHERE id=%s", (row['id'],))
            conn.commit()  # Durable intent BEFORE the external effect.
            try:
                sent = api('sendMessage', {'chat_id': row['chat_id'], 'text': row['text']})
                memory.append(cur, str(row['conversation_id']), row['text'], role='assistant',
                              request_id=f'telegram:outbox:{row["id"]}')
                cur.execute("UPDATE telegram_outbox SET state='sent',telegram_message_id=%s WHERE id=%s", (sent['message_id'],row['id']))
                conn.commit()
            except Exception:
                conn.rollback()
                cur.execute("UPDATE telegram_outbox SET state='uncertain' WHERE id=%s", (row['id'],))
                conn.commit()
                logging.warning('Telegram delivery uncertain; automatic resend disabled')


def recover_outbox(cur):
    cur.execute("UPDATE telegram_outbox SET state='uncertain' WHERE state='sending'")


def main():
    if not os.getenv('CEO_TELEGRAM_TOKEN') or not (os.getenv('CEO_TELEGRAM_ALLOWED_CHATS') or os.getenv('CEO_TELEGRAM_ALLOWED_USERS')):
        raise RuntimeError('Project Telegram credentials and explicit allowlist required')
    singleton = connect()
    singleton.autocommit = True
    with singleton.cursor() as cur:
        cur.execute('SELECT pg_try_advisory_lock(310012) AS locked')
        if not cur.fetchone()['locked']:
            raise RuntimeError('Telegram transport already running')
    with connect() as conn, conn.cursor() as cur:
        cur.execute((ROOT/'config/telegram_schema.sql').read_text())
        recover_outbox(cur)
        cur.execute("INSERT INTO scheduler_state(name,last_run) VALUES ('telegram-offset',to_timestamp(0)) ON CONFLICT DO NOTHING")
    while True:
        # Losing this connection loses exclusivity: exit so systemd can reacquire it.
        with singleton.cursor() as cur:
            cur.execute('SELECT 1')
        try:
            with connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT extract(epoch FROM last_run)::bigint AS offset FROM scheduler_state WHERE name='telegram-offset'")
                offset = cur.fetchone()['offset']
            for update in api('getUpdates', {'offset': offset, 'timeout': 10, 'allowed_updates': ['message']}):
                with connect() as conn, conn.cursor() as cur:
                    ingest(cur, update)
                    cur.execute("UPDATE scheduler_state SET last_run=to_timestamp(%s) WHERE name='telegram-offset'", (update['update_id']+1,))
            deliver_completed()
        except Exception:
            logging.warning('Telegram transport failed; durable state retained')
            time.sleep(5)


if __name__ == '__main__':
    main()
