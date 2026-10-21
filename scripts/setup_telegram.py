#!/usr/bin/env python3
"""Project-only privileged installer; secrets are entered through the terminal."""
import getpass
import grp
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import tempfile

ROOT = Path('/opt/ceo-orchestrator')


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run: sudo python3 /opt/ceo-orchestrator/scripts/setup_telegram.py')
    target = ROOT / 'config/telegram.env'
    if not target.exists():
        if not sys.stdin.isatty():
            raise SystemExit('Use an interactive terminal for secret entry')
        token = getpass.getpass('Telegram bot token (hidden): ').strip()
        chats = input('Allowed Telegram chat IDs (comma separated; blank if user-only): ').strip()
        users = input('Allowed Telegram user IDs (comma separated; blank if chat-only): ').strip()
        if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+', token):
            raise SystemExit('Invalid token format; nothing installed')
        if not (chats or users) or any(value and not re.fullmatch(r'-?\d+(\s*,\s*-?\d+)*', value) for value in (chats, users)):
            raise SystemExit('Explicit numeric allowlist required; nothing installed')
        chats = ','.join(value.strip() for value in chats.split(','))
        users = ','.join(value.strip() for value in users.split(','))
        # Atomic owner-only file; no secrets in argv, stdout or repository.
        fd, temporary = tempfile.mkstemp(dir=target.parent, prefix='.telegram-env-')
        try:
            with os.fdopen(fd, 'w') as output:
                output.write(f'CEO_TELEGRAM_TOKEN={token}\nCEO_TELEGRAM_ALLOWED_CHATS={chats}\nCEO_TELEGRAM_ALLOWED_USERS={users}\n')
                output.flush()
                os.fsync(output.fileno())
            os.chown(temporary, pwd.getpwnam('ceoorch').pw_uid, grp.getgrnam('ceoorch').gr_gid)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    subprocess.run(['runuser', '-u', 'ceoorch', '--', str(ROOT/'.venv/bin/python'), str(ROOT/'scripts/telegram_preflight.py')], check=True)
    subprocess.run(['systemd-analyze', 'verify', str(ROOT/'config/systemd/ceo-telegram-bot.service')], check=True)
    subprocess.run(['install', '-m', '0644', str(ROOT/'config/systemd/ceo-telegram-bot.service'), '/etc/systemd/system/ceo-telegram-bot.service'], check=True)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', '--now', 'ceo-telegram-bot.service'], check=True)
    subprocess.run(['systemctl', 'is-active', 'ceo-telegram-bot.service'], check=True)
    print('Send a real business question to the bot. Waiting up to 15 minutes for production E2E evidence.')
    subprocess.run([str(ROOT/'.venv/bin/python'), str(ROOT/'scripts/verify_telegram.py'), '--wait', '900', '--restart'], check=True)


if __name__ == '__main__':
    main()
