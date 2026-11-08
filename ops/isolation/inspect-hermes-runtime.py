#!/usr/bin/env python3
"""Read-only, secret-free inventory for completing the isolated Hermes migration."""
import json
import os
from pathlib import Path
import pwd
import subprocess

ROOT = Path('/opt/ceo-orchestrator')
BASE = Path('/var/lib/100print-isolation')
PROPERTIES = ['LoadState', 'ActiveState', 'SubState', 'Result', 'ExecMainStatus',
              'User', 'Group', 'RootDirectory', 'NoNewPrivileges', 'PrivateNetwork',
              'ProtectHome', 'ProtectSystem', 'RestrictAddressFamilies']

def service(name, user=False):
    command = ['systemctl']
    if user:
        account = pwd.getpwnam('ceoorch')
        command = ['runuser', '-u', 'ceoorch', '--', 'env',
                   'HOME=' + str(ROOT), 'XDG_RUNTIME_DIR=/run/user/' + str(account.pw_uid),
                   'systemctl', '--user']
    command += ['show', name, '--no-pager']
    for prop in PROPERTIES:
        command += ['-p', prop]
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=15)
        # Never include journal, environment, command arguments or raw stderr.
        return {'returncode': result.returncode,
                'properties': dict(line.split('=', 1) for line in result.stdout.splitlines()
                                   if '=' in line and line.split('=', 1)[0] in PROPERTIES)}
    except (OSError, subprocess.TimeoutExpired, KeyError) as error:
        return {'unavailable': type(error).__name__}

def main():
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo python3.')
    runtime = ROOT / 'ai-team/runtime'
    report = {'purpose': 'READ_ONLY_INVENTORY_NOT_LAUNCH',
              'baseline': service('100print-isolation-check.service'),
              'gateway': service('ceo-ai-team-hermes-gateway.service', user=True),
              'runtime_directories': [],
              'markers_present': {}}
    if runtime.is_dir():
        report['runtime_directories'] = sorted(p.name for p in runtime.iterdir()
                                               if p.is_dir() and not p.name.startswith('.'))
    for relative in ('ai-team/runtime/hermes-inference-verified',
                     'data/ai-team-telegram-handover-done',
                     'data/ai-team-hermes-auth-ready'):
        report['markers_present'][relative] = (ROOT / relative).is_file()
    evidence = BASE / 'baseline-evidence.json'
    if evidence.is_file():
        try:
            parsed = json.loads(evidence.read_text())
            report['baseline_receipt_status'] = parsed.get('status')
        except (OSError, ValueError):
            report['baseline_receipt_status'] = 'UNREADABLE'
    # Read metadata only; never import or execute project-owned Python as root.
    report['hermes_metadata'] = []
    venv = runtime / 'hermes-venv/lib'
    if venv.is_dir():
        for metadata in venv.glob('python*/site-packages/*hermes*.dist-info/METADATA'):
            selected = {}
            for line in metadata.read_text(errors='replace').splitlines():
                for field in ('Name', 'Version'):
                    if line.startswith(field + ': '):
                        selected[field] = line[len(field) + 2:]
            report['hermes_metadata'].append(selected)
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
