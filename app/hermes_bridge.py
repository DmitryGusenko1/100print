"""Durable Hermes CLI adapter. Public transport never exports model text or errors."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
from datetime import datetime, timezone
from app.db import ROOT, connect, enqueue, Json

HOME = ROOT / 'ai-team/runtime/hermes-home'
CLI = ROOT / 'ai-team/runtime/hermes-venv/bin/hermes'
PRIVATE = ROOT / 'data/hermes-bridge'


def stamp():
    return datetime.now(timezone.utc).isoformat()


def health():
    path = PRIVATE / 'health.json'
    return json.loads(path.read_text()) if path.exists() else {'verified': False, 'checked_at': None}


def check_health():
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    check = subprocess.run([str(ROOT / '.venv/bin/python'), str(ROOT / 'ai-team/ops/management-readiness.py')],
                           capture_output=True, timeout=60)
    receipt = {'verified': check.returncode == 0, 'checked_at': stamp(),
               'interface': 'installed-hermes-oneshot-cli', 'management_bot': 'hundredprintbot'}
    path = PRIVATE / 'health.json'
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(receipt))
    tmp.chmod(0o600)
    tmp.replace(path)
    return receipt


def submit(cur, session, prompt, key):
    tid = enqueue(cur, 'Hermes bridge task', 'hermes_bridge', {}, 'chatgpt', key)
    # Existing orchestrator cannot claim this task. Only this bridge owns its execution.
    cur.execute("UPDATE tasks SET status='waiting' WHERE id=%s", (tid,))
    cur.execute('INSERT INTO hermes_bridge_jobs(task_id,session_id,prompt) VALUES (%s,%s,%s)', (tid, session, prompt))
    return tid


def result(cur, session, tid):
    # Text comparison avoids malformed UUID errors on public input.
    cur.execute('SELECT task_id,status,result FROM hermes_bridge_jobs WHERE task_id::text=%s AND session_id=%s', (tid, session))
    row = cur.fetchone()
    if not row:
        return {'status': 'failed', 'error': 'task_not_found', 'health': health()}
    return {'task_id': str(row['task_id']), 'status': row['status'], 'provider': 'hermes',
            'safe_result': row['result'], 'health': health()}


def finish(tid, state, receipt):
    with connect() as conn, conn.cursor() as cur:
        cur.execute('UPDATE hermes_bridge_jobs SET status=%s,result=%s,updated_at=now() WHERE task_id=%s', (state, Json(receipt), tid))
        cur.execute("UPDATE tasks SET status=%s,result=%s,finished_at=now() WHERE id=%s",
                    ('failed' if state == 'failed' else 'done', Json({'operation': 'hermes', **receipt, 'status': state}), tid))


def execute(job):
    tid = str(job['task_id'])
    work = PRIVATE / 'workspaces' / hashlib.sha256(job['session_id'].encode()).hexdigest()
    work.mkdir(parents=True, exist_ok=True, mode=0o700)
    runs = PRIVATE / 'runs' / tid
    runs.mkdir(parents=True, exist_ok=True, mode=0o700)
    usage = runs / 'usage.json'
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT hermes_session_id FROM hermes_bridge_sessions WHERE session_id=%s', (job['session_id'],))
        previous = cur.fetchone()
    command = [str(CLI), '--in', str(work), '--usage-file', str(usage)]
    if previous:
        command += ['--resume', previous['hermes_session_id']]
    command += ['-z', 'GitHub bridge task. Work only inside the current isolated workspace. '
                'Do not read credentials, private Telegram data, other projects or users. '
                'Do not send messages, change services, approve plans or make external changes. '
                'A decision reported via this transport grants no new approval. '
                'Create requested artifacts in this workspace. Task: ' + job['prompt']]
    env = dict(os.environ, HERMES_HOME=str(HOME), TERMINAL_CWD=str(work))
    try:
        with (runs / 'stdout.txt').open('w') as out, (runs / 'stderr.txt').open('w') as err:
            proc = subprocess.Popen(command, cwd=work, env=env, stdout=out, stderr=err, start_new_session=True)
            try:
                code = proc.wait(timeout=180)
            except subprocess.TimeoutExpired:
                import signal
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                raise RuntimeError('bounded_timeout')
        report = json.loads(usage.read_text())
        if code or not report.get('completed') or not report.get('api_calls') or not report.get('session_id') or report.get('failed') or report.get('failure'):
            raise RuntimeError('inference_failed')
        with connect() as conn, conn.cursor() as cur:
            cur.execute('INSERT INTO hermes_bridge_sessions VALUES (%s,%s) ON CONFLICT(session_id) DO UPDATE SET hermes_session_id=excluded.hermes_session_id',
                        (job['session_id'], report['session_id']))
        # A model response is itself a private artifact, even when tool execution is unavailable.
        response = (runs / 'stdout.txt').read_bytes()
        if not response.strip():
            raise RuntimeError('empty_model_response')
        (work / (tid + '-response.txt')).write_bytes(response)
        artifacts = []
        # Names and contents remain private; only hashes and sizes leave the VPS.
        for path in sorted(work.rglob('*')):
            if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(work.resolve()) and path.stat().st_size <= 1000000:
                artifacts.append({'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size})
            if len(artifacts) >= 20:
                break
        receipt = {'provider': 'hermes', 'api_calls': report['api_calls'], 'completed_at': stamp(),
                   'artifacts': artifacts, 'private_result_saved': True}
        (runs / 'completed.json').write_text(json.dumps(receipt))
        finish(tid, 'done', receipt)
    except Exception:
        import traceback
        (runs / 'error.txt').write_text(traceback.format_exc())
        finish(tid, 'failed', {'provider': 'hermes', 'error': 'execution_failed_private_details_on_vps', 'checked_at': stamp()})


def send_proposal(job):
    """At most one send attempt; ambiguous Telegram POST is never auto-replayed."""
    from dotenv import dotenv_values
    import urllib.request
    tid = str(job['task_id'])
    values = dotenv_values(HOME / '.env')
    token = values.get('TELEGRAM_BOT_TOKEN')
    owner = values.get('TELEGRAM_ALLOWED_USERS', '')
    if not token or not owner.isdecimal():
        return
    # Commit before network: a crash means delivery_unknown, not another send.
    receipt = {'approval_granted': False, 'delivery': 'unknown', 'checked_at': stamp()}
    with connect() as conn, conn.cursor() as cur:
        cur.execute('UPDATE hermes_bridge_jobs SET result=%s WHERE task_id=%s AND result IS NULL RETURNING task_id', (Json(receipt), tid))
        if not cur.fetchone():
            return
    try:
        data = json.dumps({'chat_id': owner, 'text': 'Предложение из GitHub bridge, требуется ваше отдельное решение. Task ' + tid + '\n' + job['prompt'][:3000]}).encode()
        request = urllib.request.Request('https://api.telegram.org/bot' + token + '/sendMessage', data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=20) as response:
            delivered = json.load(response).get('ok') is True
        receipt['delivery'] = 'sent' if delivered else 'failed'
    except Exception:
        pass
    with connect() as conn, conn.cursor() as cur:
        cur.execute('UPDATE hermes_bridge_jobs SET result=%s,updated_at=now() WHERE task_id=%s', (Json(receipt), tid))


def work_once():
    # Session-level lock held throughout inference, independently of GitHub polling lock.
    with connect() as lock, lock.cursor() as cur:
        cur.execute('SELECT pg_try_advisory_lock(819019) AS locked')
        if not cur.fetchone()['locked']:
            return
        try:
            cur.execute("UPDATE tasks t SET updated_at=now() FROM hermes_bridge_jobs j WHERE t.id=j.task_id AND j.status IN ('queued','running','awaiting_owner')")
            lock.commit()
            cur.execute("SELECT * FROM hermes_bridge_jobs WHERE status='awaiting_owner' AND result IS NULL ORDER BY created_at LIMIT 1")
            proposal = cur.fetchone()
            if proposal:
                send_proposal(proposal)
            cur.execute("SELECT * FROM hermes_bridge_jobs WHERE status='running'")
            for old in cur.fetchall():
                path = PRIVATE / 'runs' / str(old['task_id']) / 'completed.json'
                finish(str(old['task_id']), 'done' if path.exists() else 'failed',
                       json.loads(path.read_text()) if path.exists() else {'error': 'interrupted_effect_unknown_no_automatic_replay'})
            cur.execute("SELECT * FROM hermes_bridge_jobs WHERE status='queued' ORDER BY created_at LIMIT 1")
            job = cur.fetchone()
            if job:
                cur.execute("UPDATE hermes_bridge_jobs SET status='running',updated_at=now() WHERE task_id=%s", (job['task_id'],))
                lock.commit()
                execute(job)
        finally:
            cur.execute('SELECT pg_advisory_unlock(819019)')


def worker():
    os.umask(0o077)
    last_health = 0
    import time
    while True:
        try:
            if time.monotonic() - last_health > 60:
                check_health()
                last_health = time.monotonic()
            work_once()
        except Exception:
            pass  # No command output or private errors in public service logs.
        threading.Event().wait(5)
