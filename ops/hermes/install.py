#!/usr/bin/env python3
"""Transactional host installer. Never removes issue23 execution interlocks."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time

BASE = Path('/var/lib/100print-isolation')
UNITS = Path('/etc/systemd/system')
NAMES = ('100print-hermes-broker.service', '100print-hermes-agent.service')
SOURCE = Path(__file__).resolve().parent
CONFIG_FILE = Path('/etc/100print-hermes.json')
TRANSPORT_STATE = Path('/var/lib/100print-hermes-transport')
BROKER_SOCKET = Path('/run/100print-hermes/control.sock')
OLD = 'ceo-ai-team-hermes-gateway.service'


def run(args, **kwargs):
    return subprocess.run(args, check=True, text=True, timeout=60, **kwargs)


def safe(path, directory=False):
    """All policy ancestors must be root owned and immutable to other identities."""
    for parent in reversed(path.parents):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise RuntimeError('unsafe policy ancestor: ' + str(parent))
    info = path.lstat()
    kind = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1
    if not kind or info.st_uid != 0 or info.st_mode & 0o022:
        raise RuntimeError('unsafe policy path: ' + str(path))


def write(path, data, mode=0o644):
    safe(path.parent, True)
    if path.exists() or path.is_symlink():
        safe(path)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.hermes-')
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data if isinstance(data, bytes) else data.encode())
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY | os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def units(release, pythonpath):
    common = ['NoNewPrivileges=yes', 'CapabilityBoundingSet=', 'AmbientCapabilities=',
              'ProtectSystem=strict', 'ProtectHome=yes', 'PrivateTmp=yes', 'PrivateDevices=yes',
              'ProtectKernelTunables=yes', 'ProtectKernelModules=yes', 'ProtectControlGroups=yes',
              'RestrictSUIDSGID=yes', 'RestrictNamespaces=yes', 'LockPersonality=yes',
              'UMask=0077', 'TasksMax=64', 'MemoryMax=1G', 'CPUQuota=100%',
              'Restart=on-failure', 'RestartSec=5', 'TimeoutStopSec=10', 'KillMode=control-group',
              'LimitCORE=0', 'StandardOutput=null', 'StandardError=null']
    broker = ['[Unit]', 'Description=100print trusted Hermes model and owner transport',
              '[Service]', 'User=ceo-w2p-transport', 'Group=ceo-w2p-agent',
              'LoadCredential=config:/etc/100print-hermes.json',
              'StateDirectory=100print-hermes-transport', 'StateDirectoryMode=0700',
              'RuntimeDirectory=100print-hermes', 'RuntimeDirectoryMode=0750',
              'ReadWritePaths=/var/lib/100print-hermes-transport /run/100print-hermes',
              f'ExecStart=/usr/bin/python3 -I {release}/broker.py',
              'RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6',
              'IPAddressDeny=localhost link-local multicast',
              'BindReadOnlyPaths=-/run/systemd/resolve/resolv.conf:/etc/resolv.conf',
              'IPAddressDeny=10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 100.64.0.0/10 fc00::/7',
              *common, '[Install]', 'WantedBy=multi-user.target', '']
    agent = ['[Unit]', 'Description=100print isolated Hermes worker',
             'Requires=' + NAMES[0], 'After=' + NAMES[0], '[Service]',
             'User=ceo-w2p-agent', 'Group=ceo-w2p-agent',
             f'RootDirectory={BASE}/rootfs', 'WorkingDirectory=/workspace',
             'BindReadOnlyPaths=/usr',
             f'BindReadOnlyPaths={release}:/app/hermes',
             f'BindReadOnlyPaths={BASE}/hermes-runtime:/runtime',
             'BindReadOnlyPaths=/run/100print-hermes:/broker',
             f'BindPaths={BASE}/hermes-workspace:/workspace',
             'ReadWritePaths=/workspace', 'PrivateNetwork=yes',
             'RestrictAddressFamilies=AF_UNIX AF_INET',
             'Environment=PYTHONPATH=' + pythonpath,
             'Environment=HOME=/workspace/hermes',
             'ExecStart=/usr/bin/python3 /app/hermes/runtime.py',
             'ExecStartPre=/usr/bin/python3 -I /app/hermes/probe.py',
             *common, '[Install]', 'WantedBy=multi-user.target', '']
    # Same distro layout as the baseline, including non-usrmerged hosts.
    for name in ('bin', 'lib', 'lib64'):
        if (Path('/') / name).exists() and not (Path('/') / name).is_symlink():
            agent.insert(agent.index('BindReadOnlyPaths=/usr') + 1, 'BindReadOnlyPaths=/' + name)
    return dict(zip(NAMES, ('\n'.join(broker), '\n'.join(agent))))


def identity(name):
    try:
        account = pwd.getpwnam(name)
    except KeyError:
        run(['useradd', '--system', '--user-group', '--no-create-home', '--home-dir',
             '/nonexistent', '--shell', '/usr/sbin/nologin', name])
        account = pwd.getpwnam(name)
    if (account.pw_uid == 0 or account.pw_shell not in ('/usr/sbin/nologin', '/sbin/nologin')
            or set(os.getgrouplist(name, account.pw_gid)) != {account.pw_gid}):
        raise RuntimeError('identity must have no login or supplementary groups: ' + name)
    return account


def old_command(*args):
    account = pwd.getpwnam('ceoorch')
    return ['runuser', '-u', 'ceoorch', '--', 'env',
            'XDG_RUNTIME_DIR=/run/user/' + str(account.pw_uid),
            'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/' + str(account.pw_uid) + '/bus',
            'systemctl', '--user', *args, OLD]


def active(command):
    return subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          timeout=20).returncode == 0


def service_exists(name):
    result = subprocess.run(['systemctl', 'show', name, '-p', 'LoadState', '--value'],
                            text=True, capture_output=True, timeout=20)
    if result.stdout.strip() == 'not-found':
        return False
    if result.returncode:
        raise RuntimeError('cannot inspect systemd service: ' + name)
    return True


def stop_service(name):
    if service_exists(name):
        run(['systemctl', 'stop', name])


def await_job(identifier, timeout=240):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        with sqlite3.connect('file:' + str(TRANSPORT_STATE / 'queue.db') + '?mode=ro', uri=True) as connection:
            row = connection.execute('SELECT state,model_calls,answer FROM jobs WHERE id=?', (identifier,)).fetchone()
        if row and row[0] in ('done', 'failed'):
            if row[0] != 'done' or row[1] < 1 or 'ISOLATED_HERMES_OK' not in row[2]:
                raise RuntimeError('real confined Hermes inference failed')
            return
        time.sleep(2)
    raise RuntimeError('confined Hermes inference timed out')


def install(args):
    if os.geteuid() != 0:
        raise RuntimeError('host installation requires sudo python3')
    safe(BASE, True)
    if (BASE / 'hermes-rollback').exists():
        raise RuntimeError('unfinished transaction; run --rollback first')
    safe(BASE / 'rootfs', True)
    safe(UNITS, True)
    safe(CONFIG_FILE)
    if CONFIG_FILE.stat().st_mode & 0o077:
        raise RuntimeError('/etc/100print-hermes.json must have mode 0600')
    # Only stdlib from this reviewed checkout is loaded; no project/venv import as root.
    spec = importlib.util.spec_from_file_location('transport', SOURCE / 'broker.py')
    transport = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(transport)
    transport.validate(json.loads(CONFIG_FILE.read_text()))
    runtime = BASE / 'hermes-runtime'
    if not runtime.exists():
        spec = importlib.util.spec_from_file_location('prepare_runtime', SOURCE / 'prepare-runtime.py')
        exporter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(exporter)
        exporter.prepare(runtime)
    safe(runtime, True)
    # Runtime must be a flattened, curated Python import tree. No host links/sockets.
    for path in runtime.rglob('*'):
        if path.is_symlink():
            raise RuntimeError('runtime symlinks are forbidden: ' + str(path))
        safe(path, path.is_dir())
    if not (runtime / 'hermes_cli/main.py').is_file():
        raise RuntimeError('curated Hermes runtime missing hermes_cli/main.py')
    for command in ('systemctl', 'systemd-analyze', 'runuser', 'useradd', 'nsenter', 'bpftool'):
        if not shutil.which(command):
            raise RuntimeError('missing command: ' + command)
    agent = identity('ceo-w2p-agent')
    identity('ceo-w2p-transport')
    run(['systemctl', 'start', '100print-isolation-check.service'])
    status = run(['systemctl', 'show', '100print-isolation-check.service',
                  '-p', 'Result', '-p', 'ExecMainStatus'], capture_output=True).stdout
    if set(status.splitlines()) != {'Result=success', 'ExecMainStatus=0'}:
        raise RuntimeError('baseline failed')
    workspace = BASE / 'hermes-workspace'
    if not workspace.exists():
        workspace.mkdir(mode=0o700)
        os.chown(workspace, agent.pw_uid, agent.pw_gid)
    info = workspace.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != agent.pw_uid or info.st_mode & 0o077:
        raise RuntimeError('unsafe agent workspace')
    releases = BASE / 'hermes-releases'
    releases.mkdir(exist_ok=True)
    safe(releases, True)
    model = json.loads(CONFIG_FILE.read_text())['model']
    digest = hashlib.sha256(model.encode() + b''.join((SOURCE / name).read_bytes() for name in
                                    ('install.py', 'runtime.py', 'broker.py', 'probe.py', 'prepare-runtime.py'))).hexdigest()
    release = releases / digest
    release.mkdir(exist_ok=True)
    safe(release, True)
    for name in ('runtime.py', 'broker.py', 'probe.py'):
        write(release / name, (SOURCE / name).read_bytes())
    write(release / 'agent-config.json', json.dumps({'model': {'default': model,
        'provider': 'custom', 'base_url': 'http://127.0.0.1:8719/v1',
        'api_key': 'broker-only'}, 'toolsets': ['terminal', 'file']}))
    content = units(release, '/runtime')
    snapshot = BASE / 'hermes-rollback'
    switch = BASE / 'telegram-enabled'
    if snapshot.exists():
        raise RuntimeError('unfinished transaction; run --rollback first')
    previous = {}
    for name in NAMES:
        path = UNITS / name
        if path.exists() or path.is_symlink():
            safe(path)
        previous[name] = {'text': path.read_text() if path.exists() else None,
                          'active': active(['systemctl', 'is-active', '--quiet', name]),
                          'enabled': active(['systemctl', 'is-enabled', '--quiet', name])}
    try:
        pwd.getpwnam('ceoorch')
    except KeyError:
        old_active = False
        previous['old_enabled'] = False
    else:
        run(old_command('show', '-p', 'LoadState'), capture_output=True)
        old_active = active(old_command('is-active', '--quiet'))
        previous['old_enabled'] = active(old_command('is-enabled', '--quiet'))
    previous['old_active'] = old_active
    previous['switch'] = switch.read_text() if switch.exists() else None
    write(snapshot, json.dumps(previous), 0o600)
    write(BASE / 'hermes-evidence.json', json.dumps({'status': 'INSTALLING_NOT_READY'}) + '\n')
    try:
        switch.unlink(missing_ok=True)
        for name in reversed(NAMES):
            stop_service(name)
        for name, text in content.items():
            write(UNITS / name, text)
        run(['systemd-analyze', 'verify', *[str(UNITS / name) for name in NAMES]])
        run(['systemctl', 'daemon-reload'])
        run(['systemctl', 'start', NAMES[0]])
        # Broker startup verifies getMe and absence of webhook without polling.
        for _ in range(20):
            if BROKER_SOCKET.exists():
                break
            time.sleep(1)
        else:
            raise RuntimeError('model broker did not start (check credentials/public DNS)')
        cgroup = run(['systemctl', 'show', NAMES[0], '-p', 'ControlGroup', '--value'],
                     capture_output=True).stdout.strip()
        if not cgroup.startswith('/system.slice/') or '..' in cgroup:
            raise RuntimeError('unexpected broker cgroup')
        filters = json.loads(run(['bpftool', '-j', 'cgroup', 'show', '/sys/fs/cgroup' + cgroup],
                                 capture_output=True).stdout)
        attached = {item.get('attach_type') for item in filters}
        if not {'ingress', 'egress'} <= attached and not {'cgroup_inet_ingress', 'cgroup_inet_egress'} <= attached:
            raise RuntimeError('broker IP deny filters are not attached; refusing network fallback')
        run(['systemctl', 'start', NAMES[1]])
        # Probe executes in EXACT worker namespace/UID, not on host as root.
        pid = run(['systemctl', 'show', NAMES[1], '-p', 'MainPID', '--value'], capture_output=True).stdout.strip()
        if not pid.isdecimal() or int(pid) <= 1:
            raise RuntimeError('worker not running')
        run(['nsenter', '-t', pid, '-m', '-n', '--root', '--wd=/workspace',
             '/usr/bin/setpriv', '--reuid', str(agent.pw_uid), '--regid', str(agent.pw_gid),
             '--clear-groups', '--no-new-privs', '/usr/bin/python3', '-I', '/app/hermes/probe.py'])
        transport.STATE = TRANSPORT_STATE
        identifier = transport.submit('Reply with exactly ISOLATED_HERMES_OK. Do not use tools.')
        await_job(identifier)
        # Only now stop the legacy transport; all legacy executor guards stay intact.
        if old_active:
            run(old_command('stop'))
        if active(['systemctl', 'is-active', '--quiet', 'ceo-telegram-bot.service']):
            raise RuntimeError('legacy system Telegram bot is active; refusing a second poller')
        write(switch, digest + '\n')
        print('В @hundredprintbot отправьте: /hermes Проверка нового изолированного Hermes', flush=True)
        started = time.time()
        until = time.monotonic() + args.telegram_timeout
        while time.monotonic() < until:
            with transport.db() as connection:
                row = connection.execute("SELECT value FROM metadata WHERE key='telegram_e2e'").fetchone()
            if row and float(row['value']) > started:
                break
            if not all(active(['systemctl', 'is-active', '--quiet', name]) for name in NAMES):
                raise RuntimeError('new service stopped during Telegram acceptance')
            time.sleep(2)
        else:
            raise RuntimeError('no real owner Telegram -> Hermes -> delivered answer; rollback')
        if previous['old_enabled']:
            run(old_command('disable'))
        run(['systemctl', 'enable', *NAMES])
        write(BASE / 'hermes-evidence.json', json.dumps({
            'status': 'HOST_HERMES_TELEGRAM_VERIFIED_LEGACY_EXECUTION_PAUSED',
            'release_sha256': digest, 'verified_at': time.time(),
            'tests': ['baseline', 'worker_namespace_negative', 'real_hermes_inference',
                      'owner_private_telegram_inbound_and_delivered_answer'],
            'business_dispatch_enabled': False}, indent=2) + '\n')
        write(BASE / 'hermes-last-rollback.json', snapshot.read_bytes(), 0o600)
        snapshot.unlink()
        print('Hermes/Telegram verified on host. Legacy execution interlocks retained.')
    except BaseException:
        restore(snapshot)
        raise


def restore(snapshot):
    safe(snapshot)
    previous = json.loads(snapshot.read_text())
    (BASE / 'telegram-enabled').unlink(missing_ok=True)
    for name in reversed(NAMES):
        if service_exists(name):
            run(['systemctl', 'stop', name])
            run(['systemctl', 'disable', name])
    for name in NAMES:
        if previous[name]['text'] is None:
            (UNITS / name).unlink(missing_ok=True)
        else:
            write(UNITS / name, previous[name]['text'])
    run(['systemctl', 'daemon-reload'])
    if previous['switch'] is not None:
        write(BASE / 'telegram-enabled', previous['switch'])
    for name in NAMES:
        if previous[name]['enabled']:
            run(['systemctl', 'enable', name])
        if previous[name]['active']:
            run(['systemctl', 'start', name])
    if previous.get('old_enabled'):
        run(old_command('enable'))
    if previous['old_active']:
        run(old_command('start'))
    write(BASE / 'hermes-evidence.json', json.dumps({'status': 'ROLLED_BACK_NOT_NEW_HERMES_READY'}) + '\n')
    snapshot.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rollback', action='store_true')
    parser.add_argument('--telegram-timeout', type=int, default=300)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('run on host with sudo python3')
    for signum in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, lambda *_: (_ for _ in ()).throw(RuntimeError('installation interrupted')))
    safe(BASE, True)
    lockpath = BASE / 'hermes-install.lock'
    if lockpath.exists() or lockpath.is_symlink():
        safe(lockpath)
    fd = os.open(lockpath, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.rollback:
            pending = BASE / 'hermes-rollback'
            if not pending.exists():
                write(pending, (BASE / 'hermes-last-rollback.json').read_bytes(), 0o600)
            restore(pending)
        else:
            install(args)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('INSTALL FAILED: ' + type(error).__name__ + ': ' + str(error), file=sys.stderr)
        sys.exit(1)
