"""Hermes openai-codex OAuth schema/refresh, implemented without importing Hermes.

Canonical auth.json is shared with the legacy gateway, using Hermes' auth.lock.
Never restore old refresh tokens from backups. No model tools are executed here.
"""
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import time
from urllib.parse import urlencode
from protocol import request, UpstreamHTTPError

CLIENT_ID = 'app_EMoamEEZ73f0CkXaXp7hrann'
BASE_URL = 'https://chatgpt.com/backend-api/codex'
TOKEN_URL = 'https://auth.openai.com/oauth/token'
AUTH = Path('/oauth/auth.json')


def claims(token):
    try:
        part = token.split('.')[1]
        return json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)))
    except (ValueError, IndexError, TypeError):
        raise ValueError('OAuth access token is not a supported JWT') from None


def tokens_from(store):
    if not isinstance(store, dict) or store.get('version') != 1:
        raise ValueError('unsupported Hermes auth store version')
    provider = store.get('providers', {}).get('openai-codex', {})
    tokens = provider.get('tokens', {})
    if not all(isinstance(tokens.get(key), str) and tokens[key] for key in ('access_token', 'refresh_token')):
        raise ValueError('existing Hermes openai-codex OAuth is missing')
    claim = claims(tokens['access_token'])
    if not isinstance(claim.get('exp'), (int, float)):
        raise ValueError('OAuth JWT has no expiration')
    if not isinstance(claim.get('https://api.openai.com/auth', {}).get('chatgpt_account_id'), str):
        raise ValueError('OAuth JWT has no ChatGPT account binding')
    return tokens


@contextmanager
def locked(path=AUTH):
    # Match hermes_cli.auth._auth_store_lock: auth.json -> auth.lock, flock EX.
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077:
        raise ValueError('unsafe canonical OAuth file')
    try:
        fd = os.open(path.with_suffix('.lock'), os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        if os.geteuid() == 0:
            os.fchown(fd, info.st_uid, info.st_gid)
    except FileExistsError:
        fd = os.open(path.with_suffix('.lock'), os.O_RDWR | os.O_NOFOLLOW)
    auth_owner = info.st_uid
    with os.fdopen(fd, 'a+') as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != auth_owner or info.st_mode & 0o022:
            raise ValueError('unsafe canonical OAuth lock')
        deadline = time.monotonic() + 65
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise RuntimeError('OAuth lock timeout')
                time.sleep(0.05)
        yield


def atomic_store(path, store):
    fd, temporary = tempfile.mkstemp(prefix='.100print-oauth-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(store, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sync_directory(path):
    fd = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def private_bytes(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077:
            raise ValueError('unsafe private OAuth state')
        raw = handle.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError('OAuth state too large')
        return raw


def generation(tokens):
    return hashlib.sha256((tokens['access_token'] + '\0' + tokens['refresh_token']).encode()).hexdigest()


def recover_intent(path, tokens):
    intent = path.parent / '.100print-refresh-pending'
    if not intent.exists() and not intent.is_symlink():
        return False
    pending = json.loads(private_bytes(intent))
    if not isinstance(pending, dict) or not isinstance(pending.get('generation'), str):
        raise ValueError('invalid OAuth refresh intent')
    if pending['generation'] == generation(tokens):
        return True
    # A rotated generation is already durably committed; finish a crash-after-save.
    intent.unlink()
    sync_directory(path.parent)
    return False


def refresh_pending(path):
    with locked(path):
        return recover_intent(path, tokens_from(json.loads(private_bytes(path))))


def access_token(path=AUTH):
    with locked(path):
        store = json.loads(private_bytes(path))
        tokens = tokens_from(store)
        if recover_intent(path, tokens):
            raise RuntimeError('previous OAuth refresh outcome unknown; automatic replay denied')
        if claims(tokens['access_token'])['exp'] > time.time() + 120:
            return tokens['access_token']
        # Persist an intent BEFORE the single-use grant is sent. A lost response must
        # never cause a blind replay of the same refresh token after a restart.
        intent = path.parent / '.100print-refresh-pending'
        if intent.exists():
            raise RuntimeError('previous OAuth refresh outcome unknown; automatic replay denied')
        fd = os.open(intent, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as handle:
            json.dump({'generation': generation(tokens)}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        sync_directory(path.parent)
        try:
            response = request('auth.openai.com', '/oauth/token', urlencode({
                'grant_type': 'refresh_token', 'refresh_token': tokens['refresh_token'],
                'client_id': CLIENT_ID}).encode(), form=True)
        except UpstreamHTTPError as error:
            if error.status in (400, 401, 403, 429):
                intent.unlink()
                sync_directory(path.parent)
            raise
        if not isinstance(response.get('access_token'), str) or not response['access_token']:
            raise ValueError('OAuth refresh returned no access token')
        previous = dict(tokens)
        updated = dict(tokens, access_token=response['access_token'],
                       refresh_token=response.get('refresh_token') or tokens['refresh_token'])
        tokens_from({'version': 1, 'providers': {'openai-codex': {'tokens': updated}}})
        original_identity = claims(previous['access_token'])
        refreshed_identity = claims(updated['access_token'])
        if (original_identity['https://api.openai.com/auth']['chatgpt_account_id']
                != refreshed_identity['https://api.openai.com/auth']['chatgpt_account_id']
                or original_identity.get('sub') != refreshed_identity.get('sub')):
            raise ValueError('OAuth refresh changed principal')
        stamp = datetime.now(timezone.utc).isoformat()
        store['providers']['openai-codex'].update(tokens=updated, last_refresh=stamp)
        # Match native Hermes singleton aliases; preserve independent pool accounts.
        for entry in store.get('credential_pool', {}).get('openai-codex', []):
            if isinstance(entry, dict) and (entry.get('source') == 'device_code'
                    or entry.get('source') == 'manual:device_code'
                    and entry.get('access_token') == previous['access_token']):
                entry.update(access_token=updated['access_token'], refresh_token=updated['refresh_token'],
                             last_refresh=stamp)
                for field in ('last_status', 'last_status_at', 'last_error_code', 'last_error_reason',
                              'last_error_message', 'last_error_reset_at', 'status_cleared_at'):
                    if field in entry:
                        entry[field] = None
        store['updated_at'] = stamp
        atomic_store(path, store)
        intent.unlink()
        sync_directory(path.parent)
        return updated['access_token']
