#!/usr/bin/env python3
"""Hand off only the temporary AI-team foreground process to systemd."""
import os, signal, time
from pathlib import Path
needle=b'/opt/ceo-orchestrator/ai-team/runtime/paperclip/node_modules/paperclipai/dist/index.js'
pids=[]
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit() or int(proc.name)==os.getpid(): continue
    try:
        if proc.stat().st_uid != os.getuid(): continue
        args=(proc/'cmdline').read_bytes().split(b'\0')
        if needle in args and b'run' in args: pids.append(int(proc.name))
    except (FileNotFoundError,PermissionError,ProcessLookupError): pass
for pid in pids: os.kill(pid,signal.SIGTERM)
for _ in range(100):
    if all(not Path(f'/proc/{pid}').exists() for pid in pids): break
    time.sleep(.1)
else: raise SystemExit('Temporary Paperclip did not stop; no service start attempted')
