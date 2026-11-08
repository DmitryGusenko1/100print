#!/usr/bin/env python3
"""Untrusted Hermes worker. Its only host connection is the model/task broker."""
import http.server
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from protocol import rpc as wire_rpc

ACTIVE_TASK = {}
SOCKET = '/broker/control.sock'
LIMIT = 2_000_000


def rpc(message):
    return wire_rpc(SOCKET, message)

def completion_data(body, stream):
    if not stream:
        return json.dumps(body).encode()
    # Hermes can request SDK streaming. Upstream remains one bounded completion;
    # return compatible SSE chunks, including tool-call indexes and usage.
    header = {key: body[key] for key in ('id', 'created', 'model') if key in body}
    header['object'] = 'chat.completion.chunk'
    chunks = []
    for choice in body.get('choices', []):
        delta = dict(choice['message'])
        for index, call in enumerate(delta.get('tool_calls', [])):
            call['index'] = index
        chunks.append(dict(header, choices=[{'index': choice['index'], 'delta': delta,
                                             'finish_reason': None}]))
        chunks.append(dict(header, choices=[{'index': choice['index'], 'delta': {},
                                             'finish_reason': choice['finish_reason']}]))
    if body.get('usage'):
        chunks.append(dict(header, choices=[], usage=body['usage']))
    return (''.join('data: ' + json.dumps(chunk) + '\n\n' for chunk in chunks)
            + 'data: [DONE]\n\n').encode()


class Model(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        try:
            if self.path != '/v1/chat/completions':
                raise ValueError('unsupported route')
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= LIMIT:
                raise ValueError('invalid size')
            body = json.loads(self.rfile.read(size))
            stream = body.get('stream') is True
            body['stream'] = False
            result = wire_rpc('/model/model.sock', dict(ACTIVE_TASK, op='model', body=body))
            data = completion_data(result['body'], stream)
            self.send_response(result['status'])
            self.send_header('Content-Type', 'text/event-stream' if stream else 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self.send_error(502, 'model broker refused request')


def execute(task):
    global ACTIVE_TASK
    ACTIVE_TASK = {key: task[key] for key in ('id', 'expires', 'capability')}
    job = task['id']
    # Broker-generated hex identifiers only; never interpolate user paths.
    if len(job) != 32 or any(c not in '0123456789abcdef' for c in job):
        raise ValueError('invalid task id')
    jobs = Path('/workspace/jobs')
    if jobs.is_symlink():
        raise ValueError('workspace job root must not be a symlink')
    work = jobs / job
    work.mkdir(parents=True, exist_ok=False, mode=0o700)
    usage = work / 'usage.json'
    env = dict(os.environ, HERMES_HOME='/workspace/hermes', TERMINAL_CWD=str(work),
               OPENAI_BASE_URL='http://127.0.0.1:8719/v1', OPENAI_API_KEY='broker-only',
               NO_PROXY='127.0.0.1', HOME='/workspace/hermes')
    env.pop('HTTP_PROXY', None)
    env.pop('HTTPS_PROXY', None)
    command = ['/usr/bin/python3', '-m', 'hermes_cli.main', '--in', str(work),
               '--usage-file', str(usage), '-z', task['prompt']]
    with (work / 'output').open('w') as output:
        process = subprocess.Popen(command, cwd=work, env=env, stdout=output,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            code = process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            import signal
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise RuntimeError('inference timeout')
    report = json.loads(usage.read_text())
    if code or not report.get('completed') or not report.get('api_calls') or report.get('failed') or report.get('failure'):
        raise RuntimeError('Hermes inference failed')
    answer = (work / 'output').read_text()[-12000:]
    if not answer.strip():
        raise RuntimeError('empty answer')
    return {'op': 'result', 'id': job, 'ok': True, 'text': answer,
            'api_calls': report['api_calls']}


def main():
    os.umask(0o077)
    # Agent-owned paths are touched only AFTER entering the confined service.
    home = Path('/workspace/hermes')
    home.mkdir(exist_ok=True, mode=0o700)
    (home / 'config.yaml').write_text(Path('/app/hermes/agent-config.json').read_text())
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 8719), Model)
    server.timeout = 10
    threading.Thread(target=server.serve_forever, daemon=True).start()
    while True:
        try:
            task = rpc({'op': 'next'})
            if task.get('id'):
                try:
                    result = execute(task)
                except Exception:
                    result = {'op': 'result', 'id': task['id'], 'ok': False}
                rpc(result)
        except Exception:
            time.sleep(2)
        time.sleep(1)


if __name__ == '__main__':
    main()
