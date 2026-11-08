#!/usr/bin/env python3
"""Real namespace probes using synthetic paths and documentation IP addresses."""
import ctypes
import json
import os
from pathlib import Path
import socket
import subprocess
import uuid


def probe():
    checks = {'unprivileged': os.geteuid() != 0,
              'no_new_privileges': ctypes.CDLL(None).prctl(39, 0, 0, 0, 0) == 1}
    for name, path in {'host_project': '/opt/ceo-orchestrator', 'host_home': '/home',
                       'host_canary': '/var/lib/100print-isolation/host-only-canary',
                       'credentials': '/etc/100print-hermes.json', 'docker': '/run/docker.sock',
                       'host_proc': '/proc/1/root'}.items():
        checks[name + '_hidden'] = not Path(path).exists()
    for path in ('/app/hermes/forbidden', '/runtime/forbidden'):
        try:
            Path(path).write_text('probe')
            checks[path + '_read_only'] = False
        except OSError:
            checks[path + '_read_only'] = True
    root = Path('/workspace') / ('probe-' + uuid.uuid4().hex)
    root.mkdir()
    try:
        (root / 'ok').write_text('fixture')
        checks['workspace_writable'] = (root / 'ok').read_text() == 'fixture'
        (root / 'link').symlink_to('/var/lib/100print-isolation/host-only-canary')
        try:
            (root / 'link').read_bytes()
            checks['symlink_escape_denied'] = False
        except OSError:
            checks['symlink_escape_denied'] = True
        try:
            os.link('/app/hermes/runtime.py', root / 'hardlink')
            checks['policy_hardlink_denied'] = False
        except OSError:
            checks['policy_hardlink_denied'] = True
        for family, address in ((socket.AF_INET, ('192.0.2.1', 443)),
                                (socket.AF_INET, ('169.254.169.254', 80)),
                                (socket.AF_INET, ('10.0.0.1', 443)),
                                (socket.AF_INET6, ('2001:db8::1', 443))):
            try:
                with socket.socket(family) as connection:
                    connection.settimeout(1)
                    connection.connect(address)
                checks[str(address) + '_denied'] = False
            except OSError:
                checks[str(address) + '_denied'] = True
        child = subprocess.run(['/usr/bin/python3', '-I', '-c',
                                'from pathlib import Path; '
                                'raise SystemExit(Path("/opt/ceo-orchestrator").exists())'], timeout=5)
        checks['child_confined'] = child.returncode == 0
    finally:
        for item in root.iterdir():
            item.unlink()
        root.rmdir()
    return checks


if __name__ == '__main__':
    checks = probe()
    print(json.dumps(checks, sort_keys=True))
    raise SystemExit(0 if all(checks.values()) else 1)
