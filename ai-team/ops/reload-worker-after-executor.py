#!/usr/bin/env python3
"""Load worker code only after the active executor has returned; no root required."""
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import time

BASE = Path('/opt/ceo-orchestrator')


def main():
    pid = int(subprocess.check_output(['systemctl', 'show', 'ceo-github-worker.service', '-p', 'MainPID', '--value'], text=True))
    proc = Path('/proc') / str(pid)
    if pid <= 1 or proc.stat().st_uid != os.getuid():
        raise SystemExit('Worker identity mismatch')
    argv = (proc / 'cmdline').read_bytes().split(b'\0')
    if str(BASE / 'app/github_worker.py').encode() not in argv:
        raise SystemExit('Worker command mismatch')
    identity = (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19]
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        with sqlite3.connect(f'file:{BASE}/data/worker_queue.sqlite3?mode=ro', uri=True) as db:
            row = db.execute('SELECT status FROM tasks WHERE issue_number=21').fetchone()
            running = db.execute("SELECT count(*) FROM tasks WHERE status='RUNNING'").fetchone()[0]
        if row and row[0] == 'WAITING_USER' and running == 0:
            if (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19] != identity:
                raise SystemExit('Worker process changed')
            # Restart=always is already configured. No active executor is killed.
            os.kill(pid, signal.SIGTERM)
            (BASE / 'data/issue21-worker-reload-requested').write_text('Worker idle; reload requested after executor returned.\n')
            return
        time.sleep(2)
    raise SystemExit('Worker was not idle; no signal sent')


if __name__ == '__main__':
    main()
