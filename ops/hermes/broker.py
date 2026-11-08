#!/usr/bin/env python3
"""Model-only trusted broker: Hermes OAuth -> fixed Codex Responses endpoint.

No subprocess, tools, Telegram, arbitrary URLs, imports from Hermes or host RPC.
Function calls are inert JSON; their execution belongs to the confined worker.
"""
import json
import os
from pathlib import Path
import re
import socket
import socketserver
import sqlite3
import struct
import time
from oauth import access_token, claims, tokens_from
from protocol import LIMIT, authorized, credential, request

STATE = Path('/model-state')
CONFIG = {}
KEY = b''
AGENT_UID = -1
TRANSPORT_UID = -1


def validate(config):
    if set(config) != {'model'} or not isinstance(config['model'], str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,100}', config['model']):
        raise ValueError('model broker config requires only a fixed model')
    return config


def responses_payload(body, model):
    if not isinstance(body, dict) or body.get('stream'):
        raise ValueError('only bounded completions accepted')
    messages = body.get('messages')
    if not isinstance(messages, list) or not 1 <= len(messages) <= 100:
        raise ValueError('invalid messages')
    instructions, inputs = [], []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError('invalid message')
        role, content = message.get('role'), message.get('content')
        if content is not None and not isinstance(content, str):
            raise ValueError('text content only; remote media denied')
        if role in ('system', 'developer'):
            instructions.append(content or '')
        elif role == 'tool':
            call_id = message.get('tool_call_id')
            if not isinstance(call_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', call_id):
                raise ValueError('invalid tool call id')
            inputs.append({'type': 'function_call_output', 'call_id': call_id, 'output': content or ''})
        elif role in ('user', 'assistant'):
            if content:
                inputs.append({'role': role, 'content': [{'type': 'input_text' if role == 'user' else 'output_text', 'text': content}]})
            calls = message.get('tool_calls', [])
            if not isinstance(calls, list) or len(calls) > 32 or calls and role != 'assistant':
                raise ValueError('invalid function calls')
            for call in calls:
                function = call.get('function', {})
                if call.get('type') != 'function' or not isinstance(function.get('arguments'), str):
                    raise ValueError('only inert custom function calls supported')
                name = function.get('name', '')
                identifier = call.get('id', '')
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', identifier):
                    raise ValueError('invalid function identity')
                inputs.append({'type': 'function_call', 'call_id': identifier,
                               'name': name, 'arguments': function['arguments']})
        else:
            raise ValueError('message role denied')
    tools = body.get('tools', [])
    if not isinstance(tools, list) or len(tools) > 100:
        raise ValueError('invalid tool definitions')
    functions = []
    for tool in tools:
        # Never expose native shell, computer, web_search, MCP, hosted files/tools.
        if not isinstance(tool, dict) or tool.get('type') != 'function':
            raise ValueError('hosted tools denied')
        function = tool.get('function', {})
        name = function.get('name', '')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name):
            raise ValueError('invalid function definition')
        if not isinstance(function.get('parameters', {}), dict):
            raise ValueError('invalid function schema')
        functions.append({'type': 'function', 'name': name,
                          'description': str(function.get('description', ''))[:5000],
                          'parameters': function.get('parameters', {}), 'strict': False})
    payload = {'model': model, 'instructions': '\n\n'.join(instructions) or 'You are Hermes for the isolated 100print workspace.',
               'input': inputs, 'store': False, 'stream': True, 'parallel_tool_calls': False,
               'reasoning': {'effort': 'low'}}
    if functions:
        payload['tools'] = functions
        choice = body.get('tool_choice', 'auto')
        if choice not in ('auto', 'none', 'required'):
            raise ValueError('tool choice denied')
        payload['tool_choice'] = choice
    return payload


def completion(response):
    text, calls = [], []
    for item in response.get('output', []):
        if item.get('type') == 'message':
            for part in item.get('content', []):
                if part.get('type') == 'output_text':
                    text.append(part['text'])
        elif item.get('type') == 'function_call':
            calls.append({'id': item['call_id'], 'type': 'function',
                          'function': {'name': item['name'], 'arguments': item['arguments']}})
        elif item.get('type') != 'reasoning':
            raise ValueError('unexpected hosted model output')
    if not text and not calls:
        raise ValueError('empty model completion')
    message = {'role': 'assistant', 'content': '\n'.join(text) or None}
    if calls:
        message['tool_calls'] = calls
    usage = response.get('usage', {})
    return {'id': response['id'], 'object': 'chat.completion', 'created': int(time.time()),
            'model': CONFIG['model'], 'choices': [{'index': 0, 'message': message,
            'finish_reason': 'tool_calls' if calls else 'stop'}], 'usage': {
            'prompt_tokens': usage.get('input_tokens', 0), 'completion_tokens': usage.get('output_tokens', 0),
            'total_tokens': usage.get('total_tokens', 0)}}


def db():
    connection = sqlite3.connect(STATE / 'usage.db', timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize():
    with db() as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS usage(id TEXT PRIMARY KEY, attempts INTEGER NOT NULL, successful INTEGER NOT NULL)')
    # Validate the existing canonical OAuth shape without refreshing or importing it.
    tokens_from(json.loads(Path('/oauth/auth.json').read_text()))


def operation(message, uid):
    identifier = authorized(KEY, message)
    with db() as connection:
        if message.get('op') == 'receipt' and uid in (0, TRANSPORT_UID):
            row = connection.execute('SELECT attempts,successful FROM usage WHERE id=?', (identifier,)).fetchone()
            return dict(row) if row else {'attempts': 0, 'successful': 0}
        if message.get('op') != 'model' or uid != AGENT_UID:
            raise ValueError('operation/peer denied')
        payload = responses_payload(message.get('body'), CONFIG['model'])
        connection.execute('INSERT OR IGNORE INTO usage VALUES(?,0,0)', (identifier,))
        row = connection.execute('SELECT attempts FROM usage WHERE id=?', (identifier,)).fetchone()
        if row['attempts'] >= 12:
            raise ValueError('model budget exhausted')
        # Bound attempts too; crashes and upstream failures cannot reset the quota.
        connection.execute('UPDATE usage SET attempts=attempts+1 WHERE id=?', (identifier,))
        connection.commit()
        token = access_token()
        identity = claims(token)['https://api.openai.com/auth']
        headers = {'Authorization': 'Bearer ' + token, 'ChatGPT-Account-Id': identity['chatgpt_account_id'],
                   'OpenAI-Beta': 'responses=experimental', 'originator': 'hermes-agent'}
        residency = identity.get('chatgpt_data_residency') or identity.get('chatgpt_compute_residency')
        if isinstance(residency, str) and residency.strip():
            headers['x-openai-internal-codex-residency'] = residency.strip()
        response = request('chatgpt.com', '/backend-api/codex/responses', payload,
                           headers=headers,
                           event_stream=True)
        answer = completion(response)
        connection.execute('UPDATE usage SET successful=successful+1 WHERE id=?', (identifier,))
        return {'status': 200, 'body': answer}


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(180)
        try:
            uid = struct.unpack('3i', self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
            raw = self.rfile.readline(LIMIT + 1)
            if len(raw) > LIMIT or not raw.endswith(b'\n'):
                raise ValueError('invalid frame')
            answer = operation(json.loads(raw), uid)
        except Exception:
            answer = {'error': 'model_broker_refused'}
        self.wfile.write(json.dumps(answer).encode() + b'\n')


def main():
    global CONFIG, KEY, AGENT_UID, TRANSPORT_UID
    os.umask(0o077)
    CONFIG = validate(json.loads(credential('model-config')))
    KEY = credential('capability-key')
    identities = json.loads(credential('identities'))
    AGENT_UID, TRANSPORT_UID = identities['agent'], identities['transport']
    initialize()
    path = Path('/model-run/model.sock')
    path.unlink(missing_ok=True)
    with socketserver.UnixStreamServer(str(path), Handler) as server:
        os.chmod(path, 0o660)
        # UID owns canonical auth; group is the dedicated agent group supplied by systemd.
        server.serve_forever(poll_interval=1)


if __name__ == '__main__':
    main()
