#!/usr/bin/env python3
"""Privately install the owner-selected Telegram credential; executor resumes launch."""
import getpass
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone

BASE = Path('/opt/ceo-orchestrator')
TARGET = 'WebToPrintISbot'


def identity(token):
    try:
        with urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getMe', timeout=20) as response:
            result = json.load(response)
        if result.get('ok') is not True:
            raise ValueError()
        return result['result']['username']
    except Exception:
        raise ValueError('getMe failed; no configuration changed') from None


def replace_token(content, key, token):
    pattern = rf'(?m)^\s*(?:export\s+)?{re.escape(key)}\s*=.*$'
    if len(re.findall(pattern, content)) > 1:
        raise ValueError('Duplicate token settings; no configuration changed')
    line = f'{key}={token}'
    return re.sub(pattern, lambda _: line, content) if re.search(pattern, content) else content.rstrip() + '\n' + line + '\n'


def atomic(path, content):
    fd, temporary = tempfile.mkstemp(prefix='.telegram-env-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def install(token, base=BASE, check=identity):
    if not re.fullmatch(r'\d{6,15}:[A-Za-z0-9_-]{30,50}', token):
        raise ValueError('Invalid token format; no configuration changed')
    if check(token) != TARGET:
        raise ValueError('Token is not for WebToPrintISbot; no configuration changed')
    project = base / 'config/telegram.env'
    native = base / 'ai-team/runtime/hermes-home/.env'
    # Reuse the existing strict private-owner mapping without changing any allowlist.
    spec = importlib.util.spec_from_file_location('prepare', BASE / 'ai-team/ops/prepare-telegram.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from dotenv import dotenv_values
    _, owner = module.credentials(dotenv_values(project))
    values = dotenv_values(native)
    if values.get('TELEGRAM_ALLOWED_USERS') != owner or values.get('TELEGRAM_ALLOW_ALL_USERS', '').lower() in ('true', '1'):
        raise ValueError('Owner allowlist mismatch; no configuration changed')
    originals = {p: p.read_text() for p in (project, native)}
    updates = {project: replace_token(originals[project], 'CEO_TELEGRAM_TOKEN', token),
               native: replace_token(originals[native], 'TELEGRAM_BOT_TOKEN', token)}
    backup = base / 'ai-team/runtime/secrets' / ('telegram-backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    backup.mkdir(mode=0o700, parents=True)
    for index, path in enumerate(originals):
        saved = backup / f'{index}.env'
        shutil.copyfile(path, saved)
        saved.chmod(0o600)
    try:
        for path, content in updates.items():
            atomic(path, content)
    except Exception:
        for path, content in originals.items():
            atomic(path, content)
        raise ValueError('Configuration write failed; originals restored') from None


def main():
    os.umask(0o077)
    if os.getuid() != 999 or Path.cwd().resolve() != BASE:
        raise SystemExit('Run as ceoorch from /opt/ceo-orchestrator')
    if not sys.stdin.isatty():
        raise SystemExit('Interactive terminal required for hidden token entry')
    try:
        install(getpass.getpass('Token @WebToPrintISbot (hidden): ').strip())
    except ValueError as error:
        raise SystemExit(str(error)) from None
    print('getMe=WebToPrintISbot; configurations saved. Executor must verify exclusive transport, restart gateway and test inference/E2E. Services have not been restarted.')


if __name__ == '__main__':
    main()
