"""Small shared wire protocol. No project imports or command execution."""
import hashlib
import hmac
import http.client
import ipaddress
import json
import os
from pathlib import Path
import socket
import ssl
import time

LIMIT = 2_000_000
MODEL_SOCKET = '/model/model.sock'


class UpstreamHTTPError(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__('upstream HTTP ' + str(status))


def credential(name):
    return (Path(os.environ['CREDENTIALS_DIRECTORY']) / name).read_bytes()


def capability(key, identifier, expires):
    return hmac.new(key, f'{identifier}:{expires}'.encode(), hashlib.sha256).hexdigest()


def authorized(key, message):
    identifier, expires = message.get('id'), message.get('expires')
    if (not isinstance(identifier, str) or len(identifier) != 32
            or any(c not in '0123456789abcdef' for c in identifier)
            or type(expires) is not int or not time.time() < expires <= time.time() + 600
            or not isinstance(message.get('capability'), str)
            or not hmac.compare_digest(capability(key, identifier, expires), message['capability'])):
        raise ValueError('invalid task capability')
    return identifier


def rpc(path, message):
    raw = json.dumps(message).encode() + b'\n'
    if len(raw) > LIMIT:
        raise ValueError('request too large')
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(180)
        connection.connect(str(path))
        connection.sendall(raw)
        line = connection.makefile('rb').readline(LIMIT + 1)
    if len(line) > LIMIT or not line.endswith(b'\n'):
        raise ValueError('invalid response frame')
    answer = json.loads(line)
    if 'error' in answer:
        raise RuntimeError('broker refused')
    return answer


class PublicHTTPS(http.client.HTTPSConnection):
    """Pin each TLS connection to a validated public IP, retaining hostname SNI."""
    def connect(self):
        addresses = socket.getaddrinfo(self.host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise RuntimeError('nonpublic upstream address refused')
        last_error = None
        for family, kind, proto, _, address in addresses:
            sock = socket.socket(family, kind, proto)
            try:
                sock.settimeout(self.timeout)
                sock.connect(address)
                self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
                return
            except OSError as error:
                sock.close()
                last_error = error
        raise RuntimeError('upstream connection failed') from last_error


def request(host, path, body, headers=None, form=False, event_stream=False):
    if (host, path) not in {
        ('chatgpt.com', '/backend-api/codex/responses'),
        ('auth.openai.com', '/oauth/token'),
    } and not (host == 'api.telegram.org' and path.startswith('/bot')):
        raise ValueError('upstream route denied')
    connection = PublicHTTPS(host, timeout=60, context=ssl.create_default_context())
    try:
        data = body if form else json.dumps(body).encode()
        safe_headers = {'Content-Type': 'application/x-www-form-urlencoded' if form else 'application/json',
                        'Accept': 'text/event-stream' if event_stream else 'application/json',
                        'User-Agent': '100print-isolated-hermes/2'}
        safe_headers.update(headers or {})
        connection.request('POST', path, data, safe_headers)
        response = connection.getresponse()
        if response.status != 200:
            # Never propagate upstream bodies, URLs or OAuth diagnostics to an agent.
            raise UpstreamHTTPError(response.status)
        deadline = time.monotonic() + 120
        if event_stream:
            total = 0
            event_data = []
            completed = None
            while True:
                if time.monotonic() > deadline:
                    raise RuntimeError('upstream total deadline')
                line = response.readline(LIMIT + 1)
                total += len(line)
                if total > LIMIT:
                    raise ValueError('upstream stream too large')
                if not line:
                    break
                if line.strip() == b'':
                    if event_data:
                        raw = b'\n'.join(event_data)
                        event_data = []
                        if raw == b'[DONE]':
                            break
                        event = json.loads(raw)
                        if event.get('type') in ('error', 'response.failed', 'response.incomplete'):
                            raise RuntimeError('model response failed')
                        if event.get('type') == 'response.completed':
                            completed = event['response']
                            break
                elif line.startswith(b'data:'):
                    event_data.append(line[5:].strip())
            if not completed or completed.get('status') != 'completed':
                raise RuntimeError('model stream ended without completed response')
            return completed
        raw = response.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError('upstream body too large')
        return json.loads(raw)
    finally:
        connection.close()
