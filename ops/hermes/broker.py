#!/usr/bin/env python3
"""Trusted transport: fixed Telegram owner, fixed OpenAI endpoint, no host tools."""
import argparse
import grp
import http.client
import json
import os
from pathlib import Path
import re
import socket
import socketserver
import sqlite3
import ssl
import threading
import time
import uuid

LIMIT = 2_000_000
STATE = Path('/var/lib/100print-hermes-transport')
LOCK = threading.RLock()
CONFIG = {}


def validate(config):
    required = {'telegram_token', 'owner', 'model_api_key', 'model'}
    if set(config) != required:
        raise ValueError('config requires exactly: ' + ', '.join(sorted(required)))
    if not all(isinstance(value, str) and value for value in config.values()):
        raise ValueError('configuration values must be nonempty strings')
    if not re.fullmatch(r'[1-9][0-9]*', config['owner']):
        raise ValueError('one private owner required')
    if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', config['telegram_token']):
        raise ValueError('invalid Telegram token')
    if not re.fullmatch(r'[A-Za-z0-9._-]{1,100}', config['model']):
        raise ValueError('invalid model')
    return config


def https(host, path, body):
    # No caller-supplied URL, proxy environment, redirects, or bearer destination.
    connection = http.client.HTTPSConnection(host, timeout=45, context=ssl.create_default_context())
    try:
        headers = {'Content-Type': 'application/json'}
        if host == 'api.openai.com':
            headers['Authorization'] = 'Bearer ' + CONFIG['model_api_key']
        connection.request('POST', path, json.dumps(body).encode(), headers)
        response = connection.getresponse()
        raw = response.read(LIMIT + 1)
        if len(raw) > LIMIT or response.status != 200:
            raise RuntimeError('upstream refused request')
        return json.loads(raw)
    finally:
        connection.close()


def telegram(method, body):
    return https('api.telegram.org', '/bot' + CONFIG['telegram_token'] + '/' + method, body)


def preflight():
    me = telegram('getMe', {})
    webhook = telegram('getWebhookInfo', {})
    if (not me.get('ok') or me.get('result', {}).get('username') != 'hundredprintbot'
            or not webhook.get('ok') or webhook['result'].get('url')):
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
          telegram INTEGER NOT NULL DEFAULT 0, sent INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT);
        ''')
        # Never replay an interrupted inference: model/tool effects may be unknown.
        connection.execute("UPDATE jobs SET state='failed' WHERE state='running'")


def submit(prompt, telegram_job=False):
    identifier = uuid.uuid4().hex
    with db() as connection:
        connection.execute('INSERT INTO jobs(id,prompt,state,telegram) VALUES(?,?,?,?)',
                           (identifier, prompt, 'queued', int(telegram_job)))
    return identifier


def operation(message):
    with LOCK, db() as connection:
        op = message.get('op')
        if op == 'next':
            if connection.execute("SELECT 1 FROM jobs WHERE state='running'").fetchone():
                return {}
            row = connection.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY rowid LIMIT 1").fetchone()
            if not row:
                return {}
            connection.execute("UPDATE jobs SET state='running' WHERE id=?", (row['id'],))
            return {'id': row['id'], 'prompt': row['prompt']}
        running = connection.execute("SELECT * FROM jobs WHERE state='running'").fetchone()
        if not running:
            raise ValueError('no active task')
        if op == 'model':
            if running['model_calls'] >= 12:
                raise ValueError('task model budget exhausted')
            body = message['body']
            if not isinstance(body, dict) or body.get('stream'):
                raise ValueError('only bounded nonstreaming completion supported')
            # Reject caller-controlled URL/media fetches and oversized context.
            messages = body.get('messages')
            if not isinstance(messages, list) or len(messages) > 100:
                raise ValueError('invalid messages')
            for item in messages:
                if not isinstance(item, dict) or not isinstance(item.get('content'), (str, type(None))):
                    raise ValueError('text messages only')
            payload = {key: body[key] for key in ('messages', 'tools', 'tool_choice', 'temperature') if key in body}
            payload.update(model=CONFIG['model'], max_completion_tokens=4096, stream=False)
            answer = https('api.openai.com', '/v1/chat/completions', payload)
            connection.execute('UPDATE jobs SET model_calls=model_calls+1 WHERE id=?', (running['id'],))
            return {'status': 200, 'body': answer}
        if op == 'result' and message.get('id') == running['id']:
            ok = message.get('ok') is True and running['model_calls'] > 0
            text = message.get('text', '')
            if not isinstance(text, str) or len(text) > 12000:
                raise ValueError('invalid result')
            connection.execute('UPDATE jobs SET state=?,answer=?,api_calls=? WHERE id=?',
                               ('done' if ok else 'failed', text, int(message.get('api_calls', 0)), running['id']))
            return {'accepted': True}
        raise ValueError('operation denied')


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(240)
        try:
            raw = self.rfile.readline(LIMIT + 1)
            if len(raw) > LIMIT or not raw.endswith(b'\n'):
                raise ValueError('invalid frame')
            answer = operation(json.loads(raw))
        except Exception:
            answer = {'error': 'broker_refused'}
        self.wfile.write(json.dumps(answer).encode() + b'\n')


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    request_queue_size = 4


def poll_once():
    with db() as connection:
        row = connection.execute("SELECT value FROM metadata WHERE key='offset'").fetchone()
        offset = int(row['value']) if row else 0
    updates = telegram('getUpdates', {'offset': offset, 'timeout': 5, 'limit': 20,
                                      'allowed_updates': ['message']})
    if not updates.get('ok'):
        raise RuntimeError('poll failed')
    for update in updates['result']:
        with db() as connection:
            # Admission and offset committed together; crash cannot replay a task.
            connection.execute("INSERT OR REPLACE INTO metadata VALUES('offset',?)", (str(update['update_id'] + 1),))
            message = update.get('message', {})
            chat = message.get('chat', {})
            if (str(message.get('from', {}).get('id')) != CONFIG['owner']
                    or str(chat.get('id')) != CONFIG['owner'] or chat.get('type') != 'private'):
                continue
            text = message.get('text', '')
            if not isinstance(text, str) or not text.startswith('/hermes ') or len(text) > 4000:
                continue
            # Limit backlog and do not consume historic commands on first launch.
            if message.get('date', 0) < time.time() - 120:
                continue
            count = connection.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]
            if count >= 3:
                continue
            connection.execute('INSERT INTO jobs(id,prompt,state,telegram) VALUES(?,?,?,1)',
                               (uuid.uuid4().hex, text[8:], 'queued'))
    with db() as connection:
        rows = connection.execute("SELECT * FROM jobs WHERE telegram=1 AND state IN ('done','failed') AND sent=0").fetchall()
    for row in rows:
        with db() as connection:
            connection.execute('UPDATE jobs SET sent=1 WHERE id=?', (row['id'],))
        # At most one send attempt. An ambiguous failure is never auto-retried.
        text = row['answer'] if row['state'] == 'done' else 'Hermes: выполнение не удалось; повтор автоматически не запускается.'
        sent = telegram('sendMessage', {'chat_id': CONFIG['owner'], 'text': text[-3900:]})
        if sent.get('ok') and row['state'] == 'done':
            with db() as connection:
                connection.execute("INSERT OR REPLACE INTO metadata VALUES('telegram_e2e',?)", (str(time.time()),))


def main():
    global CONFIG
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    CONFIG = validate(json.loads((Path(os.environ['CREDENTIALS_DIRECTORY']) / 'config').read_text()))
    preflight()
    if args.check:
        print('getMe=hundredprintbot; webhook absent. No Telegram delivery tested.')
        return
    initialize()
    path = Path('/run/100print-hermes/control.sock')
    path.unlink(missing_ok=True)
    with Server(str(path), Handler) as server:
        os.chmod(path, 0o660)
        os.chown(path, -1, grp.getgrnam('ceo-w2p-agent').gr_gid)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        while True:
            try:
                # Root-owned switch created only after confined inference passes.
                if Path('/var/lib/100print-isolation/telegram-enabled').is_file():
                    poll_once()
            except Exception:
                time.sleep(5)
            time.sleep(1)


if __name__ == '__main__':
    main()
