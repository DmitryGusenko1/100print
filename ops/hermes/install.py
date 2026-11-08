#!/usr/bin/env python3
"""Install isolated Hermes using existing canonical Hermes OAuth; retain containment."""
import argparse
import ast
import ctypes
import platform
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time

SOURCE = Path(__file__).resolve().parent
sys.path.insert(0, str(SOURCE))
import oauth
import transport
from protocol import rpc

BASE = Path('/var/lib/100print-isolation')
UNITS = Path('/etc/systemd/system')
LEGACY = Path('/opt/ceo-orchestrator')
LEGACY_HOME = LEGACY / 'ai-team/runtime/hermes-home'
TRANSPORT_STATE = Path('/var/lib/100print-hermes-transport')
MODEL_STATE = Path('/var/lib/100print-hermes-model')
CONFIG = BASE / 'hermes-config'
CONTROL = BASE / 'hermes-control'
OLD = 'ceo-ai-team-hermes-gateway.service'
SYSTEM_OLD = 'ceo-telegram-bot.service'
NAMES = ('100print-hermes-model.service', '100print-hermes-broker.service', '100print-hermes-agent.service')
FILES = ('broker.py', 'transport.py', 'oauth.py', 'protocol.py', 'runtime.py', 'probe.py')


def run(args, **kwargs):
    return subprocess.run(args, check=True, text=True, timeout=60, **kwargs)


def safe(path, directory=False):
    for parent in reversed(path.parents):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise RuntimeError('unsafe policy ancestor: ' + str(parent))
    info = path.lstat()
    kind = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1
    if not kind or info.st_uid != 0 or info.st_mode & 0o022:
        raise RuntimeError('unsafe policy path: ' + str(path))


def directory(path, mode=0o755):
    safe(path.parent, True)
    if not path.exists():
        path.mkdir(mode=mode)
    safe(path, True)


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
        fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def identity(name):
    try:
        account = pwd.getpwnam(name)
    except KeyError:
        run(['useradd', '--system', '--user-group', '--no-create-home', '--home-dir',
             '/nonexistent', '--shell', '/usr/sbin/nologin', name])
        account = pwd.getpwnam(name)
    if (account.pw_uid == 0 or account.pw_shell not in ('/usr/sbin/nologin', '/sbin/nologin')
            or set(os.getgrouplist(name, account.pw_gid)) != {account.pw_gid}):
        raise RuntimeError('identity must have no login or extra groups: ' + name)
    return account


def old_command(*args):
    account = pwd.getpwnam('ceoorch')
    return ['runuser', '-u', 'ceoorch', '--', 'env',
            'XDG_RUNTIME_DIR=/run/user/' + str(account.pw_uid),
            'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/' + str(account.pw_uid) + '/bus',
            'systemctl', '--user', *args, OLD]


def state(command):
    result = subprocess.run(command, text=True, capture_output=True, timeout=20)
    values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    if result.returncode and values.get('LoadState') != 'not-found':
        raise RuntimeError('cannot inspect service manager')
    return values


def service_state(name=None, old=False):
    properties = ['show', '-p', 'LoadState', '-p', 'ActiveState', '-p', 'UnitFileState', '-p', 'MainPID']
    return state(old_command(*properties) if old else ['systemctl', *properties, name])


def active(name):
    return service_state(name).get('ActiveState') == 'active'


def stop_service(name):
    if service_state(name).get('LoadState') != 'not-found':
        run(['systemctl', 'stop', name])
    if service_state(name).get('ActiveState') not in ('inactive', 'failed'):
        raise RuntimeError('service did not stop: ' + name)


def stop_old():
    status = service_state(old=True)
    if status.get('LoadState') != 'not-found':
        run(old_command('stop'))
    if service_state(old=True).get('ActiveState') not in ('inactive', 'failed'):
        raise RuntimeError('legacy gateway did not stop')


def env_values(path):
    result = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'(?:export\s+)?([A-Z_][A-Z_0-9]*)\s*=\s*(.*)', line)
        if not match:
            continue
        value = match[2].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        result[match[1]] = value
    return result


def legacy_file(path, owner, private=True):
    # Read only declared project files. Never import project code or follow links.
    for parent in path.parents:
        if parent.is_symlink():
            raise RuntimeError('legacy credential ancestor is a symlink')
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != owner or info.st_mode & (0o077 if private else 0o022):
        raise RuntimeError('legacy credential must be owner-only regular file: ' + path.name)


def discover(owner):
    for path in (LEGACY_HOME / '.env', LEGACY_HOME / 'auth.json', LEGACY_HOME / 'config.yaml',
                 LEGACY / 'config/telegram.env'):
        legacy_file(path, owner, private=path.name != 'config.yaml')
    native = env_values(LEGACY_HOME / '.env')
    project = env_values(LEGACY / 'config/telegram.env')
    credentials = transport.validate({'telegram_token': native.get('TELEGRAM_BOT_TOKEN', ''),
                                      'owner': native.get('TELEGRAM_ALLOWED_USERS', '')})
    if (native.get('TELEGRAM_ALLOW_ALL_USERS', '').lower() in ('1', 'true', 'yes')
            or project.get('CEO_TELEGRAM_TOKEN') != credentials['telegram_token']
            or project.get('CEO_TELEGRAM_ALLOWED_CHATS') != credentials['owner']
            or project.get('CEO_TELEGRAM_ALLOWED_USERS', credentials['owner']) != credentials['owner']):
        raise RuntimeError('existing Telegram ownership/configuration disagrees')
    text = (LEGACY_HOME / 'config.yaml').read_text()
    # Parse only the known scalar model subsection; no YAML constructors/imports.
    block = re.search(r'(?m)^model:\s*\n((?:[ \t]+[^\n]*\n|\s*\n)*)', text + '\n')
    if not block:
        raise RuntimeError('Hermes model config must have a recognizable model subsection')
    default = re.search(r'(?m)^\s+default:\s*[\"\']?([A-Za-z0-9._/-]+)[\"\']?\s*(?:#.*)?$', block[1])
    provider = re.search(r'(?m)^\s+provider:\s*[\"\']?([A-Za-z0-9_-]+)[\"\']?\s*(?:#.*)?$', block[1])
    if not default or not provider or provider[1] != 'openai-codex':
        raise RuntimeError('existing active provider must be Hermes openai-codex OAuth')
    model = default[1].removeprefix('openai-codex/').removeprefix('openai/')
    from broker import validate
    validate({'model': model})
    store = json.loads(oauth.private_bytes(LEGACY_HOME / 'auth.json'))
    oauth.tokens_from(store)
    if oauth.refresh_pending(LEGACY_HOME / 'auth.json'):
        raise RuntimeError('previous OAuth refresh outcome is unknown')
    return credentials, model


def provider_contract(runtime):
    files = [runtime / 'hermes_cli' / name for name in ('auth.py', 'auth_codex.py', 'auth_constants.py')]
    available = [path for path in files if path.is_file()]
    constants, texts = {}, []
    for path in available:
        text = path.read_text()
        texts.append(text)
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = node.value.value
    expected = {'AUTH_STORE_VERSION': 1, 'CODEX_OAUTH_CLIENT_ID': oauth.CLIENT_ID,
                'CODEX_OAUTH_TOKEN_URL': oauth.TOKEN_URL, 'DEFAULT_CODEX_BASE_URL': oauth.BASE_URL}
    if any(constants.get(key) != value for key, value in expected.items()):
        raise RuntimeError('installed Hermes OAuth constants do not match supported provider')
    combined = '\n'.join(texts)
    if any(name not in combined for name in ('def _read_codex_tokens', 'def _save_codex_tokens',
                                              'def _auth_store_lock', 'with_suffix(".lock")')):
        raise RuntimeError('installed Hermes OAuth store/locking interface differs')
    return {str(path.relative_to(runtime)): hashlib.sha256(path.read_bytes()).hexdigest() for path in available}


def units(release):
    common = ['NoNewPrivileges=yes', 'CapabilityBoundingSet=', 'AmbientCapabilities=',
              'ProtectSystem=strict', 'ProtectHome=yes', 'PrivateTmp=yes', 'PrivateDevices=yes',
              'ProtectKernelTunables=yes', 'ProtectKernelModules=yes', 'ProtectControlGroups=yes',
              'RestrictSUIDSGID=yes', 'RestrictNamespaces=yes', 'LockPersonality=yes',
              'UMask=0077', 'TasksMax=64', 'MemoryMax=1G', 'CPUQuota=100%',
              'Restart=on-failure', 'RestartSec=5', 'TimeoutStopSec=15', 'KillMode=control-group',
              'LimitCORE=0', 'StandardOutput=null', 'StandardError=null']
    distro = ['BindReadOnlyPaths=/usr']
    for name in ('bin', 'lib', 'lib64'):
        if (Path('/') / name).exists() and not (Path('/') / name).is_symlink():
            distro.append('BindReadOnlyPaths=/' + name)
    internet = ['RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6',
                'IPAddressDeny=localhost link-local multicast',
                'IPAddressDeny=10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 100.64.0.0/10 fc00::/7']
    resolver = '/run/systemd/resolve/resolv.conf' if Path('/run/systemd/resolve/resolv.conf').is_file() else '/etc/resolv.conf'
    credentials = [f'LoadCredential=capability-key:{CONFIG}/capability.key',
                   f'LoadCredential=identities:{CONFIG}/identities.json']
    model = ['[Unit]', 'Description=100print model-only Hermes OAuth broker', '[Service]',
             'User=ceoorch', 'Group=ceo-w2p-agent', f'RootDirectory={BASE}/rootfs',
             'WorkingDirectory=/', 'Environment=PYTHONPATH=', 'Environment=HOME=/model-state',
             *distro, f'BindReadOnlyPaths={release}:/app/hermes',
             f'BindPaths={LEGACY_HOME}:/oauth',
             'BindPaths=/var/lib/100print-hermes-model:/model-state',
             'BindPaths=/run/100print-hermes-model:/model-run',
             'BindReadOnlyPaths=/etc/ssl/certs', f'BindReadOnlyPaths={resolver}:/etc/resolv.conf',
             'BindReadOnlyPaths=-/etc/hosts', 'BindReadOnlyPaths=-/etc/nsswitch.conf',
             'ReadWritePaths=/oauth /model-state /model-run',
             f'LoadCredential=model-config:{CONFIG}/model.json', *credentials,
             'StateDirectory=100print-hermes-model', 'StateDirectoryMode=0700',
             'RuntimeDirectory=100print-hermes-model', 'RuntimeDirectoryMode=0750',
             'ExecStart=/usr/bin/python3 /app/hermes/broker.py', *internet, *common,
             '[Install]', 'WantedBy=multi-user.target', '']
    telegram = ['[Unit]', 'Description=100print private owner Telegram transport',
                'Requires=' + NAMES[0], 'After=' + NAMES[0], '[Service]',
                'User=ceo-w2p-transport', 'Group=ceo-w2p-agent', 'Environment=PYTHONPATH=',
                f'LoadCredential=telegram-config:{CONFIG}/telegram.json', *credentials,
                'StateDirectory=100print-hermes-transport', 'StateDirectoryMode=0700',
                'RuntimeDirectory=100print-hermes', 'RuntimeDirectoryMode=0750',
                'ReadWritePaths=/var/lib/100print-hermes-transport /run/100print-hermes',
                f'BindReadOnlyPaths={resolver}:/etc/resolv.conf',
                f'ExecStart=/usr/bin/python3 {release}/transport.py', *internet, *common,
                'RestartPreventExitStatus=78',
                '[Install]', 'WantedBy=multi-user.target', '']
    agent = ['[Unit]', 'Description=100print isolated Hermes tool executor',
             'Requires=' + ' '.join(NAMES[:2]), 'After=' + ' '.join(NAMES[:2]), '[Service]',
             'User=ceo-w2p-agent', 'Group=ceo-w2p-agent', f'RootDirectory={BASE}/rootfs',
             'WorkingDirectory=/workspace', *distro,
             f'BindReadOnlyPaths={release}:/app/hermes',
             f'BindReadOnlyPaths={BASE}/hermes-runtime:/runtime',
             'BindReadOnlyPaths=/run/100print-hermes:/broker',
             'BindReadOnlyPaths=/run/100print-hermes-model:/model',
             f'BindPaths={BASE}/hermes-workspace:/workspace',
             'ReadWritePaths=/workspace', 'PrivateNetwork=yes', 'RestrictAddressFamilies=AF_UNIX AF_INET',
             'Environment=PYTHONPATH=/runtime', 'Environment=HOME=/workspace/hermes',
             'ExecStartPre=/usr/bin/python3 -I /app/hermes/probe.py',
             'ExecStart=/usr/bin/python3 /app/hermes/runtime.py', *common,
             '[Install]', 'WantedBy=multi-user.target', '']
    return dict(zip(NAMES, map('\n'.join, (model, telegram, agent))))


def capture():
    previous = {'services': {}, 'files': {}, 'old': service_state(old=True)}
    for name in NAMES:
        path = UNITS / name
        if path.exists() or path.is_symlink():
            safe(path)
        previous['services'][name] = {'text': path.read_text() if path.exists() else None, **service_state(name)}
    for path in (CONFIG / 'model.json', CONFIG / 'telegram.json', CONFIG / 'capability.key',
                 CONFIG / 'identities.json', BASE / 'telegram-enabled'):
        if path.exists() or path.is_symlink():
            safe(path)
        previous['files'][str(path)] = path.read_text() if path.exists() else None
    for settings in [previous['old'], *previous['services'].values()]:
        if settings.get('ActiveState') not in ('active', 'inactive', 'failed'):
            raise RuntimeError('service state is transitional/unknown')
        if settings.get('UnitFileState', '') not in ('enabled', 'disabled', 'static', 'not-found', ''):
            raise RuntimeError('service enablement is not a supported stable state')
    return previous


def verify_bpf(name):
    cgroup = run(['systemctl', 'show', name, '-p', 'ControlGroup', '--value'], capture_output=True).stdout.strip()
    if not cgroup.startswith('/system.slice/') or '..' in cgroup:
        raise RuntimeError('unexpected trusted service cgroup')
    # Kernel BPF_PROG_QUERY avoids installing bpftool/packages on the host.
    number = {'x86_64': 321, 'aarch64': 280, 'riscv64': 280}.get(platform.machine())
    if number is None:
        raise RuntimeError('unsupported architecture for cgroup BPF verification')
    class Query(ctypes.Structure):
        _fields_ = [('target_fd', ctypes.c_uint32), ('attach_type', ctypes.c_uint32),
                    ('query_flags', ctypes.c_uint32), ('attach_flags', ctypes.c_uint32),
                    ('prog_ids', ctypes.c_uint64), ('prog_cnt', ctypes.c_uint32),
                    ('padding', ctypes.c_uint32), ('prog_attach_flags', ctypes.c_uint64)]
    fd = os.open('/sys/fs/cgroup' + cgroup, os.O_DIRECTORY | os.O_RDONLY)
    try:
        for attach_type in (0, 1):  # BPF_CGROUP_INET_INGRESS / EGRESS
            query = Query(target_fd=fd, attach_type=attach_type, query_flags=1)
            result = ctypes.CDLL(None, use_errno=True).syscall(number, 16, ctypes.byref(query), ctypes.sizeof(query))
            if result != 0 or query.prog_cnt < 1:
                raise RuntimeError('required cgroup IP filters missing/unverifiable')
    finally:
        os.close(fd)


def worker_command(arguments):
    account = pwd.getpwnam('ceo-w2p-agent')
    pid = service_state(NAMES[2]).get('MainPID', '')
    if not pid.isdecimal() or int(pid) <= 1:
        raise RuntimeError('isolated worker not running')
    return ['nsenter', '-t', pid, '-m', '-n', '--root', '--wd=/workspace',
            '/usr/bin/setpriv', '--reuid', str(account.pw_uid), '--regid', str(account.pw_gid),
            '--clear-groups', '--no-new-privs', '/usr/bin/python3', '-I', *arguments]


def queue_db():
    connection = sqlite3.connect('file:' + str(TRANSPORT_STATE / 'queue.db') + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def submit_probe(prompt):
    # Let the transport write its own SQLite journal under its own UID.
    return rpc('/run/100print-hermes/control.sock', {'op': 'submit', 'prompt': prompt})['id']


def wait_socket(path, timeout=30):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        try:
            if stat.S_ISSOCK(path.lstat().st_mode):
                return
        except FileNotFoundError:
            pass
        time.sleep(1)
    raise RuntimeError('trusted service socket did not appear')


def await_telegram(expected, started, timeout):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        with queue_db() as connection:
            row = connection.execute("SELECT value FROM metadata WHERE key='telegram_e2e'").fetchone()
        if row:
            receipt = json.loads(row['value'])
            if receipt['at'] > started and receipt['prompt'] == expected:
                return
        if not all(active(name) for name in NAMES):
            raise RuntimeError('new service failed during Telegram acceptance')
        time.sleep(2)
    raise RuntimeError('no genuine owner Telegram/model/delivered-answer acceptance')


def await_job(identifier, timeout=240):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        with queue_db() as connection:
            row = connection.execute('SELECT state,model_calls,answer FROM jobs WHERE id=?', (identifier,)).fetchone()
        if row and row[0] in ('done', 'failed'):
            if row[0] != 'done' or row[1] < 2 or 'ISOLATED_HERMES_OK' not in (row[2] or ''):
                raise RuntimeError('real isolated Hermes/model test failed')
            return
        time.sleep(2)
    raise RuntimeError('real isolated Hermes test timed out')


def assert_no_other_pollers():
    if service_state(SYSTEM_OLD).get('ActiveState') not in ('inactive', 'failed'):
        raise RuntimeError('system Telegram consumer is active/unknown')
    if service_state(old=True).get('ActiveState') not in ('inactive', 'failed'):
        raise RuntimeError('legacy user Telegram consumer is active/unknown')
    # Inspect command-line metadata only for this project's UID; no secrets/output.
    owner = pwd.getpwnam('ceoorch').pw_uid
    for process in Path('/proc').iterdir():
        if not process.name.isdecimal():
            continue
        try:
            if process.stat().st_uid != owner:
                continue
            if not (process / 'cwd').resolve().is_relative_to(LEGACY):
                continue
            argv = (process / 'cmdline').read_bytes().split(b'\0')
            if b'app.telegram_bot' in argv or any(Path(part.decode(errors='replace')).name == 'hermes' for part in argv) and b'gateway' in argv and b'run' in argv:
                raise RuntimeError('unexpected same-project Telegram consumer still running')
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue


def restore(snapshot):
    safe(snapshot)
    previous = json.loads(snapshot.read_text())
    (BASE / 'telegram-enabled').unlink(missing_ok=True)
    # All new pollers are stopped and verified BEFORE any old poller can restart.
    for name in reversed(NAMES):
        stop_service(name)
        if service_state(name).get('LoadState') != 'not-found':
            run(['systemctl', 'disable', name])
    # Canonical auth always retains the latest refreshed tokens; never replay backup.
    if (LEGACY_HOME / '.100print-refresh-pending').exists() and oauth.refresh_pending(LEGACY_HOME / 'auth.json'):
        stop_old()
        write(BASE / 'hermes-evidence.json', json.dumps({'status': 'FAILED_CLOSED_OAUTH_REFRESH_OUTCOME_UNKNOWN'}) + '\n')
        raise RuntimeError('OAuth refresh outcome unknown; pollers stopped, rollback snapshot retained')
    for path, content in previous['files'].items():
        path = Path(path)
        if content is None:
            path.unlink(missing_ok=True)
        else:
            write(path, content, 0o600)
    for name, settings in previous['services'].items():
        path = UNITS / name
        if settings['text'] is None:
            path.unlink(missing_ok=True)
        else:
            write(path, settings['text'])
    run(['systemctl', 'daemon-reload'])
    for name, settings in previous['services'].items():
        if settings.get('UnitFileState') == 'enabled':
            run(['systemctl', 'enable', name])
        if settings.get('ActiveState') == 'active':
            run(['systemctl', 'start', name])
    if previous['old'].get('UnitFileState') == 'enabled':
        run(old_command('enable'))
    if previous['old'].get('ActiveState') == 'active':
        run(old_command('start'))
    write(BASE / 'hermes-evidence.json', json.dumps({'status': 'ROLLED_BACK_NOT_NEW_HERMES_READY'}) + '\n')
    snapshot.unlink()


def install(args):
    safe(BASE, True)
    snapshot = BASE / 'hermes-rollback'
    if snapshot.exists():
        raise RuntimeError('unfinished transaction: invoke this installer with --rollback')
    safe(BASE / 'rootfs', True)
    safe(UNITS, True)
    for command in ('systemctl', 'systemd-analyze', 'runuser', 'useradd', 'nsenter'):
        if not shutil.which(command):
            raise RuntimeError('missing host command: ' + command)
    owner = pwd.getpwnam('ceoorch')
    if owner.pw_uid == 0 or set(os.getgrouplist('ceoorch', owner.pw_gid)) != {owner.pw_gid}:
        raise RuntimeError('legacy OAuth identity has unexpected privilege/groups')
    credentials, model = discover(owner.pw_uid)
    runtime = BASE / 'hermes-runtime'
    if not runtime.exists():
        spec = importlib.util.spec_from_file_location('prepare_runtime', SOURCE / 'prepare-runtime.py')
        exporter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(exporter)
        exporter.prepare(runtime)
    safe(runtime, True)
    for path in runtime.rglob('*'):
        safe(path, path.is_dir())
    provider = provider_contract(runtime)
    agent, telegram_account = identity('ceo-w2p-agent'), identity('ceo-w2p-transport')
    run(['systemctl', 'start', '100print-isolation-check.service'])
    baseline = state(['systemctl', 'show', '100print-isolation-check.service', '-p', 'Result', '-p', 'ExecMainStatus'])
    if baseline != {'Result': 'success', 'ExecMainStatus': '0'}:
        raise RuntimeError('baseline isolation test failed')
    for path in (CONFIG, CONTROL, BASE / 'hermes-releases', BASE / 'hermes-backups'):
        directory(path)
    workspace = BASE / 'hermes-workspace'
    if not workspace.exists():
        workspace.mkdir(mode=0o700)
        os.chown(workspace, agent.pw_uid, agent.pw_gid)
    info = workspace.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != agent.pw_uid or info.st_mode & 0o077:
        raise RuntimeError('unsafe isolated workspace')
    digest = hashlib.sha256(model.encode() + b''.join((SOURCE / name).read_bytes() for name in (*FILES, 'install.py', 'prepare-runtime.py'))).hexdigest()
    release = BASE / 'hermes-releases' / digest
    directory(release)
    for name in FILES:
        write(release / name, (SOURCE / name).read_bytes())
    write(release / 'agent-config.json', json.dumps({'model': {'default': model,
        'provider': 'custom', 'base_url': 'http://127.0.0.1:8719/v1', 'api_key': 'broker-only',
        'openai_runtime': 'auto', 'api_mode': 'chat_completions'},
        'platform_toolsets': {'cli': ['terminal', 'file']},
        'terminal': {'backend': 'local'}}))
    previous = capture()
    if previous['old'].get('ActiveState') == 'active' and previous['services'][NAMES[1]].get('ActiveState') == 'active':
        raise RuntimeError('two existing Telegram consumers detected; refusing mutation')
    backup = BASE / 'hermes-backups' / (str(time.time_ns()) + '-' + digest[:12])
    directory(backup, 0o700)
    # Read the auth store under Hermes' own lock; root backup never gets restored
    # after rotation. Credentials stay at the canonical path throughout migration.
    with oauth.locked(LEGACY_HOME / 'auth.json'):
        write(backup / 'auth.json', oauth.private_bytes(LEGACY_HOME / 'auth.json'), 0o600)
    for name in ('.env', 'config.yaml'):
        write(backup / ('legacy-' + name.lstrip('.')), (LEGACY_HOME / name).read_bytes(), 0o600)
    previous['backup'] = str(backup)
    write(snapshot, json.dumps(previous), 0o600)
    write(backup / 'transaction.json', json.dumps(previous), 0o600)
    write(BASE / 'hermes-evidence.json', json.dumps({'status': 'INSTALLING_NOT_READY'}) + '\n')
    try:
        (BASE / 'telegram-enabled').unlink(missing_ok=True)
        for name in reversed(NAMES):
            stop_service(name)
        write(CONFIG / 'telegram.json', json.dumps(credentials), 0o600)
        write(CONFIG / 'model.json', json.dumps({'model': model}), 0o600)
        # Stable signing key across re-runs; never exposed to the agent.
        if not (CONFIG / 'capability.key').exists():
            write(CONFIG / 'capability.key', secrets.token_hex(32), 0o600)
        write(CONFIG / 'identities.json', json.dumps({'agent': agent.pw_uid, 'transport': telegram_account.pw_uid}), 0o600)
        content = units(release)
        for name, text in content.items():
            write(UNITS / name, text)
        run(['systemd-analyze', 'verify', *[str(UNITS / name) for name in NAMES]])
        run(['systemctl', 'daemon-reload'])
        run(['systemctl', 'start', NAMES[0]])
        wait_socket(Path('/run/100print-hermes-model/model.sock'))
        verify_bpf(NAMES[0])
        run(['systemctl', 'start', NAMES[1]])
        wait_socket(Path('/run/100print-hermes/control.sock'))
        verify_bpf(NAMES[1])
        run(['systemctl', 'start', NAMES[2]])
        run(worker_command(['/app/hermes/probe.py']))
        # No polling by new transport yet. Stop the old transport BEFORE model
        # refresh: an ambiguous single-use grant must never race a legacy retry.
        stop_old()
        assert_no_other_pollers()
        transport.STATE = TRANSPORT_STATE
        nonce = secrets.token_hex(16)
        prompt = ('Use the local terminal or file tool to create acceptance.txt in the current workspace '
                  'containing exactly ' + nonce + '. Then use a local tool to verify that '
                  '/opt/ceo-orchestrator and /home are absent, and that reading '
                  '/workspace/../opt/ceo-orchestrator/README.md fails. Do not use network tools. '
                  'Reply ISOLATED_HERMES_OK after these checks.')
        identifier = submit_probe(prompt)
        await_job(identifier)
        # Independent file verification runs as agent inside the real worker mount
        # and network namespaces; root never follows a worker-controlled host path.
        verify = ('import os,pathlib,stat,sys; p=pathlib.Path("/workspace/jobs")/sys.argv[1]/"acceptance.txt"; '
                  'assert not p.parent.is_symlink() and not p.parent.parent.is_symlink(); '
                  's=p.lstat(); assert stat.S_ISREG(s.st_mode) and s.st_nlink==1; '
                  'assert p.read_text().strip()==sys.argv[2]; '
                  'assert not pathlib.Path("/opt/ceo-orchestrator").exists(); '
                  'assert not pathlib.Path("/home").exists()')
        run(worker_command(['-c', verify, identifier, nonce]))
        assert_no_other_pollers()
        started = time.time()
        write(BASE / 'telegram-enabled', digest + '\n')
        e2e_nonce = secrets.token_hex(8)
        expected = 'Проверка изолированного Hermes ' + e2e_nonce
        print('В @hundredprintbot отправьте: /hermes ' + expected, flush=True)
        await_telegram(expected, started, args.telegram_timeout)
        if previous['old'].get('UnitFileState') == 'enabled':
            run(old_command('disable'))
        run(['systemctl', 'enable', *NAMES])
        write(BASE / 'hermes-evidence.json', json.dumps({
            'status': 'HOST_HERMES_OAUTH_TELEGRAM_VERIFIED_LEGACY_EXECUTION_PAUSED',
            'verified_at': time.time(), 'release_sha256': digest, 'installed_oauth_source_sha256': provider,
            'checks': ['host_baseline', 'live_worker_namespace_denials', 'real_oauth_model',
                       'hermes_tool_created_workspace_file', 'independent_workspace_file_verification',
                       'owner_private_telegram_inbound_and_delivered_answer'],
            'legacy_containment_removed': False, 'business_dispatch_enabled': False}, indent=2) + '\n')
        write(BASE / 'hermes-last-rollback.json', snapshot.read_bytes(), 0o600)
        snapshot.unlink()
        print('Host acceptance passed. Existing OAuth retained. Legacy containment unchanged.')
    except BaseException:
        restore(snapshot)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rollback', action='store_true')
    parser.add_argument('--telegram-timeout', type=int, default=300)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('run on the VPS with sudo python3')
    def interrupted(*_):
        raise RuntimeError('installation interrupted')
    for signum in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, interrupted)
    safe(BASE, True)
    lockpath = BASE / 'hermes-install.lock'
    if lockpath.exists() or lockpath.is_symlink():
        safe(lockpath)
    with os.fdopen(os.open(lockpath, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600), 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.rollback:
            snapshot = BASE / 'hermes-rollback'
            if not snapshot.exists():
                write(snapshot, (BASE / 'hermes-last-rollback.json').read_bytes(), 0o600)
            restore(snapshot)
        else:
            install(args)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Do not print upstream errors, environments, OAuth values, or prompts.
        print('INSTALL FAILED: ' + type(error).__name__ + ': ' + str(error), file=sys.stderr)
        sys.exit(1)
