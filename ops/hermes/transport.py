#!/usr/bin/env python3
"""Trusted owner Telegram transport/queue. Never executes agent commands or tools."""
import argparse
import json
import os
from pathlib import Path
import re
import socket
import socketserver
import sqlite3
import struct
import threading
import time
import uuid
from protocol import UpstreamHTTPError, LIMIT, capability, credential, request, rpc

STATE = Path('/var/lib/100print-hermes-transport')
CONFIG = {}
KEY = b''
AGENT_UID = -1
LOCK = threading.RLock()
MODEL_SOCKET = '/run/100print-hermes-model/model.sock'
SWITCH = Path('/var/lib/100print-isolation/telegram-enabled')


def validate(config):
    if set(config) != {'telegram_token', 'owner'}:
        raise ValueError('transport config requires only Telegram token and owner')
    if not isinstance(config['owner'], str) or not re.fullmatch(r'[1-9][0-9]*', config['owner']):
        raise ValueError('one private owner required')
    if not isinstance(config['telegram_token'], str) or not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', config['telegram_token']):
        raise ValueError('invalid management bot token')
    return config


def telegram(method, body):
    if method not in ('getMe', 'getWebhookInfo', 'getUpdates', 'sendMessage'):
        raise ValueError('Telegram method denied')
    return request('api.telegram.org', '/bot' + CONFIG['telegram_token'] + '/' + method, body)


def preflight():
    me, webhook = telegram('getMe', {}), telegram('getWebhookInfo', {})
    if (not me.get('ok') or me.get('result', {}).get('username') != 'hundredprintbot'
            or not webhook.get('ok') or webhook.get('result', {}).get('url')):
        raise RuntimeError('wrong management bot or active webhook')


def db():
    connection = sqlite3.connect(STATE / 'queue.db', timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize():
    with db() as connection:
        connection.executescript('''CREATE TABLE IF NOT EXISTS jobs(
          id TEXT PRIMARY KEY, prompt TEXT NOT NULL, state TEXT NOT NULL,
          answer TEXT, api_calls INTEGER DEFAULT 0, model_calls INTEGER DEFAULT 0,
          telegram INTEGER NOT NULL DEFAULT 0, sent INTEGER NOT NULL DEFAULT 0,
          expires INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT);
        ''')
        if 'expires' not in {row[1] for row in connection.execute('PRAGMA table_info(jobs)')}:
            connection.execute('ALTER TABLE jobs ADD COLUMN expires INTEGER NOT NULL DEFAULT 0')
        connection.execute("UPDATE jobs SET state='failed' WHERE state='running'")


def submit(prompt, telegram_job=False):
    identifier = uuid.uuid4().hex
    with db() as connection:
        connection.execute('INSERT INTO jobs(id,prompt,state,telegram) VALUES(?,?,?,?)',
                           (identifier, prompt, 'queued', int(telegram_job)))
    return identifier


def grant(identifier, expires):
    return {'id': identifier, 'expires': expires, 'capability': capability(KEY, identifier, expires)}


def operation(message):
    with LOCK, db() as connection:
        op = message.get('op')
        if op == 'next':
            connection.execute("UPDATE jobs SET state='failed',answer='' WHERE state='running' AND expires<?", (int(time.time()),))
            if connection.execute("SELECT 1 FROM jobs WHERE state='running'").fetchone():
                return {}
            row = connection.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY rowid LIMIT 1").fetchone()
            if not row:
                return {}
            expires = int(time.time()) + 300
            connection.execute("UPDATE jobs SET state='running',expires=? WHERE id=?", (expires, row['id']))
            return dict(grant(row['id'], expires), prompt=row['prompt'])
        row = connection.execute("SELECT * FROM jobs WHERE state='running' AND id=?", (message.get('id'),)).fetchone()
        if op != 'result' or not row:
            raise ValueError('operation denied')
        text = message.get('text', '')
        if not isinstance(text, str) or len(text) > 12000:
            raise ValueError('invalid result')
        # Successful model usage is independently recorded by the model broker;
        # a worker's api_calls/ok fields alone can never establish model success.
        receipt = rpc(MODEL_SOCKET, dict(grant(row['id'], row['expires']), op='receipt'))
        ok = message.get('ok') is True and receipt['successful'] > 0 and bool(text.strip())
        connection.execute('UPDATE jobs SET state=?,answer=?,api_calls=?,model_calls=? WHERE id=?',
                           ('done' if ok else 'failed', text, receipt['successful'], receipt['successful'], row['id']))
        return {'accepted': True}


def handle_message(message, uid):
    if uid == 0 and message.get('op') == 'submit':
        prompt = message.get('prompt')
        if not isinstance(prompt, str) or not 0 < len(prompt) <= 4000:
            raise ValueError('invalid installation probe')
        return {'id': submit(prompt)}
    if uid != AGENT_UID:
        raise ValueError('worker peer denied')
    return operation(message)


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(180)
        try:
            uid = struct.unpack('3i', self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
            raw = self.rfile.readline(LIMIT + 1)
            if len(raw) > LIMIT or not raw.endswith(b'\n'):
                raise ValueError('invalid frame')
            result = handle_message(json.loads(raw), uid)
        except Exception:
            result = {'error': 'transport_refused'}
        self.wfile.write(json.dumps(result).encode() + b'\n')


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    request_queue_size = 4


def poll_once():
    with db() as connection:
        row = connection.execute("SELECT value FROM metadata WHERE key='offset'").fetchone()
        offset = int(row['value']) if row else 0
    updates = telegram('getUpdates', {'offset': offset, 'timeout': 5, 'limit': 20, 'allowed_updates': ['message']})
    if not updates.get('ok'):
        raise RuntimeError('poll failed')
    for update in updates['result']:
        with db() as connection:
            connection.execute("INSERT OR REPLACE INTO metadata VALUES('offset',?)", (str(update['update_id'] + 1),))
            message = update.get('message', {})
            chat = message.get('chat', {})
            if (str(message.get('from', {}).get('id')) != CONFIG['owner']
                    or str(chat.get('id')) != CONFIG['owner'] or chat.get('type') != 'private'):
                continue
            text = message.get('text', '')
            if (not isinstance(text, str) or not text.startswith('/hermes ') or len(text) > 4000
                    or message.get('date', 0) < time.time() - 120):
                continue
            count = connection.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]
            if count < 3:
                connection.execute('INSERT INTO jobs(id,prompt,state,telegram) VALUES(?,?,?,1)',
                                   (uuid.uuid4().hex, text[8:], 'queued'))
    with db() as connection:
        rows = connection.execute("SELECT * FROM jobs WHERE telegram=1 AND state IN ('done','failed') AND sent=0").fetchall()
    for row in rows:
        with db() as connection:
            changed = connection.execute('UPDATE jobs SET sent=1 WHERE id=? AND sent=0', (row['id'],)).rowcount
        if not changed:
            continue
        text = row['answer'] if row['state'] == 'done' else 'Hermes: выполнение не удалось; автоматически не повторяется.'
        sent = telegram('sendMessage', {'chat_id': CONFIG['owner'], 'text': text[-3900:]})
        if sent.get('ok') and row['state'] == 'done':
            with db() as connection:
                connection.execute("INSERT OR REPLACE INTO metadata VALUES('telegram_e2e',?)", (json.dumps({
                    'at': time.time(), 'job': row['id'], 'prompt': row['prompt']}),))


def main():
    global CONFIG, KEY, AGENT_UID
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    CONFIG = validate(json.loads(credential('telegram-config')))
    KEY = credential('capability-key')
    AGENT_UID = json.loads(credential('identities'))['agent']
    preflight()
    if args.check:
        print('getMe=hundredprintbot; webhook absent; no delivery test performed')
        return
    initialize()
    path = Path('/run/100print-hermes/control.sock')
    path.unlink(missing_ok=True)
    with Server(str(path), Handler) as server:
        os.chmod(path, 0o660)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        while True:
            try:
                if SWITCH.is_file():
                    poll_once()
            except UpstreamHTTPError as error:
                if error.status == 409:
                    raise SystemExit(78)  # Never restart a conflicting poller automatically.
                time.sleep(5)
            except Exception:
                time.sleep(5)
            time.sleep(1)


if __name__ == '__main__':
    main()
