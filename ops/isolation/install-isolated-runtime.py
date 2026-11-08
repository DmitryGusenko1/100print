#!/usr/bin/env python3
"""Provision the 100print isolation baseline. Does NOT enable Hermes or workers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import stat
import subprocess
import sys
import tempfile

BASE = Path('/var/lib/100print-isolation')
UNIT = '100print-isolation-check.service'
IDENTITY = 'ceo-w2p-agent'
ATTEMPT_STARTED = False

SMOKE = r'''import ctypes, json, os, socket, subprocess, uuid
from pathlib import Path
checks = {}
checks['unprivileged'] = os.geteuid() != 0
checks['workspace_writable'] = False
p = Path('/workspace/probe-' + uuid.uuid4().hex)
p.write_text('isolated')
checks['workspace_writable'] = p.read_text() == 'isolated'
p.unlink()
checks['host_canary_hidden'] = not Path('/var/lib/100print-isolation/host-only-canary').exists()
checks['host_project_hidden'] = not Path('/opt/ceo-orchestrator').exists()
checks['host_home_hidden'] = not Path('/home').exists()
checks['credentials_absent'] = not any(Path(x).exists() for x in ['/root/.ssh', '/root/.codex', '/run/docker.sock', '/project/.env'])
try:
    Path('/app/forbidden-write').write_text('no')
    checks['policy_read_only'] = False
except OSError:
    checks['policy_read_only'] = True
try:
    socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    checks['tcp_denied'] = False
except OSError:
    checks['tcp_denied'] = True
try:
    socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    checks['ipv6_denied'] = False
except OSError:
    checks['ipv6_denied'] = True
link = Path('/workspace/host-link-' + uuid.uuid4().hex)
link.symlink_to('/var/lib/100print-isolation/host-only-canary')
try:
    link.read_text()
    checks['symlink_escape_denied'] = False
except OSError:
    checks['symlink_escape_denied'] = True
finally:
    link.unlink()
child_code = 'import socket;\ntry: socket.socket(socket.AF_INET)\nexcept OSError: raise SystemExit(77)\nraise SystemExit(0)'
child = subprocess.run(['/usr/bin/python3', '-I', '-c', child_code], capture_output=True, timeout=5)
checks['child_inherits_network_denial'] = child.returncode == 77
checks['no_new_privileges'] = ctypes.CDLL(None).prctl(39, 0, 0, 0, 0) == 1
print(json.dumps({'checks': checks, 'passed': all(checks.values())}, sort_keys=True), flush=True)
raise SystemExit(0 if all(checks.values()) else 1)
'''


def run(argv, **kwargs):
    kwargs.setdefault('timeout', 60)
    return subprocess.run(argv, check=True, text=True, **kwargs)


def protected_directory(path, mode=0o755):
    """Refuse pre-existing attacker-controlled state, including symlink ancestors."""
    for item in reversed((path, *path.parents)):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                raise RuntimeError(f'Unsafe root-owned directory: {item}')
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(mode)


def write_root_file(path, content, mode=0o644):
    protected_directory(path.parent)
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1:
            raise RuntimeError(f'Unsafe existing file: {path}')
    fd, temporary = tempfile.mkstemp(prefix='.isolation-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def unit_text():
    mounts = ['BindReadOnlyPaths=/usr']
    # Keep distribution symlink layout: /bin, /lib and /lib64 often point into /usr.
    for name in ('bin', 'lib', 'lib64'):
        source = Path('/') / name
        if source.exists() and not source.is_symlink():
            mounts.append('BindReadOnlyPaths=/' + name)
    return '\n'.join([
        '# Managed by 100print isolation installer; baseline test ONLY.',
        '[Unit]', 'Description=100print confined runtime baseline check',
        '[Service]', 'Type=oneshot', f'User={IDENTITY}', f'Group={IDENTITY}',
        f'RootDirectory={BASE}/rootfs', 'WorkingDirectory=/workspace',
        *mounts, f'BindPaths={BASE}/workspace:/workspace',
        'ExecStart=/usr/bin/python3 -I /app/smoke.py',
        'Environment=HOME=/workspace', 'Environment=ISOLATION_BASELINE=1',
        'NoNewPrivileges=yes', 'CapabilityBoundingSet=', 'AmbientCapabilities=',
        'PrivateDevices=yes', 'PrivateTmp=yes', 'PrivateNetwork=yes',
        'ProtectSystem=strict', 'ProtectHome=yes', 'ProtectKernelTunables=yes',
        'ProtectKernelModules=yes', 'ProtectControlGroups=yes',
        'RestrictSUIDSGID=yes', 'RestrictNamespaces=yes',
        'RestrictAddressFamilies=AF_UNIX', 'LockPersonality=yes',
        'ReadWritePaths=/workspace', 'UMask=0077',
        'StandardOutput=journal', 'StandardError=journal', 'Restart=no',
        'TimeoutStartSec=30s', 'TimeoutStopSec=5s', '',
    ])


def verify_source():
    source = Path(__file__).absolute()
    info = source.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o022:
        raise RuntimeError('Installer must be a regular non-group/world-writable file')
    return hashlib.sha256(source.read_bytes()).hexdigest()


def install():
    global ATTEMPT_STARTED
    if os.geteuid() != 0:
        raise RuntimeError('Run with sudo python3; --self-test needs no sudo')
    digest = verify_source()
    protected_directory(BASE)
    write_root_file(BASE / 'baseline-evidence.json', json.dumps({
        'status': 'IN_PROGRESS_NOT_READY', 'installer_sha256': digest}) + '\n')
    ATTEMPT_STARTED = True
    if not Path('/run/systemd/system').is_dir():
        raise RuntimeError('Requires a systemd Linux host; no service/runtime provisioning performed')
    for command in ('systemctl', 'systemd-analyze', 'useradd'):
        if not shutil.which(command):
            raise RuntimeError('Missing host command: ' + command)
    if not Path('/usr/bin/python3').is_file():
        raise RuntimeError('Requires /usr/bin/python3; no packages installed automatically')
    try:
        account = pwd.getpwnam(IDENTITY)
        if account.pw_uid == 0 or account.pw_shell not in ('/usr/sbin/nologin', '/sbin/nologin'):
            raise RuntimeError('Existing identity is not a dedicated nologin system identity')
        if set(os.getgrouplist(IDENTITY, account.pw_gid)) != {account.pw_gid}:
            raise RuntimeError('Existing identity has supplementary groups; review required')
    except KeyError:
        run(['useradd', '--system', '--user-group', '--no-create-home', '--home-dir', '/nonexistent', '--shell', '/usr/sbin/nologin', IDENTITY])
        account = pwd.getpwnam(IDENTITY)
    protected_directory(BASE)
    protected_directory(BASE / 'rootfs')
    for name in ('usr', 'app', 'workspace', 'etc', 'tmp'):
        protected_directory(BASE / 'rootfs' / name)
    for name in ('bin', 'lib', 'lib64'):
        source = Path('/') / name
        destination = BASE / 'rootfs' / name
        if source.is_symlink():
            target = os.readlink(source)
            if destination.is_symlink():
                if os.readlink(destination) != target:
                    raise RuntimeError('Rootfs system symlink differs: ' + name)
            elif destination.exists():
                raise RuntimeError('Rootfs path conflicts with distribution symlink: ' + name)
            else:
                destination.symlink_to(target)
        elif source.exists():
            protected_directory(destination)
    workspace = BASE / 'workspace'
    # Existing workspace may be writable only by our dedicated UID; never follow a link.
    if workspace.exists() or workspace.is_symlink():
        info = workspace.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != account.pw_uid or info.st_mode & 0o077:
            raise RuntimeError('Unsafe existing workspace')
    else:
        workspace.mkdir(mode=0o700)
        os.chown(workspace, account.pw_uid, account.pw_gid)
    write_root_file(BASE / 'rootfs/app/smoke.py', SMOKE)
    write_root_file(BASE / 'host-only-canary', 'NONSECRET isolation test fixture\n', 0o600)
    unit = Path('/etc/systemd/system') / UNIT
    content = unit_text()
    if unit.exists() and unit.read_text() != content:
        raise RuntimeError('Existing baseline unit differs; not overwriting automatically')
    write_root_file(unit, content)
    run(['systemd-analyze', 'verify', str(unit)])
    run(['systemctl', 'daemon-reload'])
    run(['systemctl', 'start', UNIT])
    # Exit status is recorded by systemd, not by an agent-writable workspace receipt.
    status = run(['systemctl', 'show', UNIT, '-p', 'Result', '-p', 'ExecMainStatus'], capture_output=True).stdout
    if 'Result=success' not in status or 'ExecMainStatus=0' not in status:
        raise RuntimeError('Isolation smoke test did not pass')
    evidence = {'status': 'HOST_BASELINE_READY_NOT_HERMES_READY', 'installer_sha256': digest,
                'unit_status': status, 'missing': ['trusted LLM/project resource brokers',
                'isolated Hermes/Codex executor integration', 'real Hermes+executor E2E',
                'reviewed dispatch re-enable after E2E']}
    write_root_file(BASE / 'baseline-evidence.json', json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence, indent=2))
    print('Business guards remain paused. No existing website, bot, database or shared service was changed.')


def self_test():
    import unittest
    class Tests(unittest.TestCase):
        def test_guard_and_network(self):
            text = unit_text()
            for setting in ('User=ceo-w2p-agent', 'PrivateNetwork=yes', 'NoNewPrivileges=yes',
                            'RestrictAddressFamilies=AF_UNIX', 'ProtectSystem=strict'):
                self.assertIn(setting, text)
            self.assertNotIn('/opt/ceo-orchestrator', text)
            self.assertNotIn('docker.sock', text)
            self.assertNotIn('[Install]', text)
        def test_smoke_compiles(self):
            compile(SMOKE, '<smoke>', 'exec')
        def test_unsafe_directory(self):
            with tempfile.TemporaryDirectory() as root:
                path = Path(root) / 'link'
                path.symlink_to('/tmp')
                with self.assertRaises(RuntimeError):
                    protected_directory(path)
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    arguments = parser.parse_args()
    if arguments.self_test:
        sys.exit(self_test())
    try:
        install()
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        if ATTEMPT_STARTED:
            write_root_file(BASE / 'baseline-evidence.json', json.dumps({
                'status': 'FAILED_CLOSED_NOT_READY', 'error': str(error)}) + '\n')
        print('FAILED_CLOSED: ' + str(error), file=sys.stderr)
        print('Hermes/business execution was not enabled.', file=sys.stderr)
        sys.exit(1)
