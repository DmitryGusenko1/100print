"""Single-project, durable GitHub executor. No third-party dependencies."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time

try:
    from .progress import Progress, STAGES, now
except ImportError:
    from progress import Progress, STAGES, now

ROOT = Path('/opt/ceo-orchestrator')
REPO = 'DmitryGusenko1/100print'
OWNER = 'DmitryGusenko1'
INTERVAL = 30


def run(args, timeout=120):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def gh(*args):
    result = run(['gh', *args, '--repo', REPO])
    if result.returncode:
        raise RuntimeError('GitHub request failed; check project gh authentication')
    return result.stdout


def eligible(issue):
    labels = {x['name'].lower() for x in issue.get('labels', [])}
    return (issue.get('author') or {}).get('login') == OWNER and not labels.intersection({'no-codex', 'manual'})


def priority(issue):
    words = (issue['title'] + ' ' + ' '.join(x['name'] for x in issue.get('labels', []))).upper()
    return 0 if 'URGENT' in words else 1 if 'FINAL' in words else 2


class Queue:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        (self.root / 'data').mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / 'data/worker_queue.sqlite3', timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=FULL;
        CREATE TABLE IF NOT EXISTS tasks (
          issue_id INTEGER PRIMARY KEY, issue_number INTEGER UNIQUE NOT NULL,
          title TEXT NOT NULL, body TEXT NOT NULL, priority INTEGER NOT NULL,
          status TEXT NOT NULL DEFAULT 'QUEUED', attempt INTEGER NOT NULL DEFAULT 0,
          started_at TEXT, heartbeat TEXT, completed_at TEXT, last_progress TEXT,
          commit_hash TEXT, result TEXT, user_action TEXT, readiness TEXT,
          retry_at REAL NOT NULL DEFAULT 0, synthetic INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS events (
          marker TEXT PRIMARY KEY, issue_number INTEGER, body TEXT NOT NULL,
          delivered INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        ''')

    def meta(self, key, value=None):
        if value is not None:
            with self.db:
                self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (key, str(value)))
        row = self.db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        return row[0] if row else None

    def task(self, number):
        row = self.db.execute('SELECT * FROM tasks WHERE issue_number=?', (number,)).fetchone()
        return dict(row) if row else None

    def update(self, number, **fields):
        with self.db:
            self.db.execute('UPDATE tasks SET ' + ','.join(k+'=?' for k in fields) + ' WHERE issue_number=?', (*fields.values(), number))

    def ingest(self, issues):
        with self.db:
            for issue in issues:
                if not eligible(issue):
                    continue
                self.db.execute('''INSERT INTO tasks(issue_id,issue_number,title,body,priority)
                  VALUES (?,?,?,?,?) ON CONFLICT(issue_number) DO UPDATE SET
                  title=excluded.title,body=excluded.body,priority=excluded.priority''',
                  (issue.get('id', issue['number']), issue['number'], issue['title'], issue.get('body') or '', priority(issue)))

    def event(self, number, key, body):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,0)', (f'ceo-worker:{number}:{key}', number, body))

    def flush(self):
        rows = self.db.execute('SELECT * FROM events WHERE delivered=0 ORDER BY rowid').fetchall()
        for row in rows:
            task = self.task(row['issue_number'])
            if task is None:
                continue
            if task['synthetic']:
                with self.db:
                    self.db.execute('UPDATE events SET delivered=1 WHERE marker=?', (row['marker'],))
                continue
            marker = '<!-- '+row['marker']+' -->'
            # Retry-safe outbox: reconcile before every POST, including after a lost response.
            # gh api has no --repo option.
            response = run(['gh', 'api', f'repos/{REPO}/issues/{row["issue_number"]}/comments?per_page=100', '--paginate', '--jq', '.[] | .body | @json'])
            if response.returncode:
                raise RuntimeError('GitHub comments unavailable')
            comments = [json.loads(line) for line in response.stdout.splitlines() if line.strip()]
            if not any(marker in c for c in comments):
                gh('issue', 'comment', str(row['issue_number']), '--body', row['body']+'\n\n'+marker)
            with self.db:
                self.db.execute('UPDATE events SET delivered=1 WHERE marker=?', (row['marker'],))

    def migrate(self):
        if self.meta('migrated'):
            return
        legacy = self.root / 'data/worker_state.json'
        done = json.loads(legacy.read_text()).get('done', []) if legacy.exists() else []
        for number in done:
            if self.task(int(number)):
                self.update(int(number), status='DONE', completed_at=now(), result='Imported legacy completion (not independently verified)')
        # #11's executor explicitly reported incomplete DoD, despite legacy exit=0.
        if self.task(11) and '11' in done:
            self.update(11, status='WAITING_USER', completed_at=None,
                        user_action='Безопасно завершите мастер: sudo python3 /opt/ceo-orchestrator/scripts/setup_telegram.py',
                        readiness='telegram', result='Recovered incomplete LIVE DoD from legacy false DONE')
            self.update(11, last_progress=json.dumps(dict(issue_number=11, stage='commit/push', percent=90, started_at=now(), updated_at=now(), last_action='Recovered legacy incomplete LIVE DoD', current_subtask='Ожидание Telegram LIVE readiness', eta_optional=None)))
            self.event(11, 'recovered-waiting', 'RECOVERY: старый DONE был ошибочным: LIVE DoD не выполнен.\nSTATUS: WAITING_USER\nUSER_ACTION: Безопасно завершите мастер: `sudo python3 /opt/ceo-orchestrator/scripts/setup_telegram.py`.\nПосле успешной проверки готовности очередь продолжит задачу автоматически.')
        self.meta('migrated', now())

    def claim(self, synthetic_only=False):
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute('''SELECT * FROM tasks WHERE
              (status='RUNNING' OR (status IN ('QUEUED','RETRY') AND retry_at<=?))
              AND (?=0 OR synthetic=1)
              ORDER BY CASE WHEN status='RUNNING' THEN -1 ELSE priority END,issue_number LIMIT 1''',
              (time.time(), int(synthetic_only))).fetchone()
            if not row:
                return None
            self.db.execute("UPDATE tasks SET status='RUNNING',attempt=attempt+1,started_at=COALESCE(started_at,?),heartbeat=? WHERE issue_number=?", (now(), now(), row['issue_number']))
        return self.task(row['issue_number'])

    def health(self):
        beat = self.meta('heartbeat')
        return dict(heartbeat=beat, pid=self.meta('pid'), last_poll=self.meta('last_poll'),
                    last_error=self.meta('last_error'), deployment=self.meta('deployment'), status=self.meta('status'), user_action=self.meta('user_action'),
                    tasks=[dict(r) for r in self.db.execute('SELECT issue_number,status,attempt,started_at,heartbeat,completed_at,last_progress,commit_hash FROM tasks ORDER BY priority,issue_number')])


def readiness(task):
    if task['readiness'] == 'telegram':
        result = run([str(ROOT/'.venv/bin/python'), str(ROOT/'scripts/telegram_preflight.py')], 45)
        active = run(['systemctl', 'is-active', 'ceo-telegram-bot.service'], 10)
        return result.returncode == active.returncode == 0
    if task['readiness'] == 'codex':
        return run(['codex', 'login', 'status'], 20).returncode == 0
    if task['readiness'] == 'github':
        return run(['gh', 'auth', 'status'], 20).returncode == 0
    # Generic executor-defined readiness uses explicit project-local file existence only.
    if task['readiness'] and task['readiness'].startswith('file:'):
        path = (ROOT / task['readiness'][5:]).resolve()
        return path.is_relative_to(ROOT) and path.is_file()
    return False


def sync_progress(queue, number, progress):
    state = progress.read(number)
    if state and state['issue_number'] == number:
        queue.update(number, heartbeat=now(), last_progress=json.dumps(state, ensure_ascii=False))
        queue.event(number, 'progress-'+str(state['percent']), f"PROGRESS: {state['percent']}% / {state['stage']}\n{state['current_subtask']}")


def execute(queue, task):
    number = task['issue_number']
    progress = Progress(queue.root / 'data/synthetic-runtime' if task['synthetic'] else queue.root)
    progress.path.parent.mkdir(parents=True, exist_ok=True)
    if task['last_progress']:
        state = json.loads(task['last_progress'])
        # Restore a per-task stage when another task used the global display.
        with progress.lock.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            temporary = progress.path.with_suffix('.restore')
            temporary.write_text(json.dumps(state))
            os.replace(temporary, progress.path)
    else:
        progress.update(number, 'analysis', 'Анализ задачи', 'START')
    queue.event(number, 'start', f'START: issue #{number}; attempt {task["attempt"]}; recovery preserves completed stages.')
    sync_progress(queue, number, progress)
    if task['synthetic']:
        for stage in STAGES:
            if stage != 'done':
                progress.update(number, stage, 'Synthetic queue acceptance', 'No project mutations')
                sync_progress(queue, number, progress)
        finish(queue, task, {'status': 'DONE', 'summary': 'Synthetic task automatically picked up and completed'}, progress)
        return
    if run(['codex', 'login', 'status'], 20).returncode != 0:
        finish(queue, task, dict(status='WAITING_USER', summary='Codex authorization is unavailable', user_action='Восстановите project-local авторизацию Codex.', readiness='codex'), progress)
        return
    result_path = queue.root / f'data/executor-result-{number}.json'
    # If the old worker died while its executor survived, wait rather than duplicate it.
    prior_pid = queue.meta(f'executor-{number}')
    prior_identity = queue.meta(f'executor-identity-{number}')
    if prior_pid and alive(prior_pid) and process_identity(prior_pid) == prior_identity:
        queue.update(number, status='RETRY', retry_at=time.time()+30)
        return
    if task['attempt'] > 1 and result_path.exists():
        recovered = json.loads(result_path.read_text())
        if recovered.get('status') == 'DONE':
            finish(queue, task, recovered, progress)
            return
    result_path.unlink(missing_ok=True)
    final_path = queue.root / f'data/executor-final-{number}.txt'
    final_path.unlink(missing_ok=True)
    prompt = f'''Ты исполнитель CEO Orchestrator. Выполни issue #{number} {REPO}.
TITLE: {task['title']}
BODY:\n{task['body']}
Работать только в /opt/ceo-orchestrator. Не читать чужие .env, не трогать другие проекты/пользователей.
Только сервисы ceo-* / ai-business-brain-* и БД ceo_orchestrator / ai_brain разрешены.
Сначала прочитай scripts/progress.py и сохранённый progress. Не уменьшай этап.
Обновляй фактический этап: python3 scripts/progress.py --issue {number} --stage STAGE --current "подзадача" --action "действие".
Этапы analysis, planning, implementation, integration, tests, commit/push; done выставляет только worker.
При изменениях выполнить tests, git add/commit/push. Финал DONE/CHANGED/TESTED/NEXT.
ОБЯЗАТЕЛЬНО запиши {result_path} JSON: {{"status":"DONE","summary":"проверенный результат"}} ТОЛЬКО при полном DoD.
Если нужны token/OAuth/UI/права: прекрати зависимое выполнение, запиши JSON
{{"status":"WAITING_USER","summary":"причина","user_action":"ровно одно простое действие","readiness":"telegram или github или file:data/имя-маркера"}}.
Для Telegram readiness=telegram. Для общего UI подтверждения попроси создать указанный project-local marker только после подтверждения.
Не помещай секреты, логи команд и hidden reasoning в JSON или финал. Exit 0 без DONE JSON не означает успех.
'''
    log_path = queue.root / f'logs/executor-{number}.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('a') as output:
        process = subprocess.Popen(['codex', 'exec', '--skip-git-repo-check', '--dangerously-bypass-approvals-and-sandbox', '--output-last-message', str(final_path), prompt], cwd=ROOT, stdout=output, stderr=output, start_new_session=True)
        queue.meta(f'executor-{number}', process.pid)
        queue.meta(f'executor-identity-{number}', process_identity(process.pid))
        deadline = time.monotonic() + 3600
        try:
            while process.poll() is None:
                sync_progress(queue, number, progress)
                queue.meta('heartbeat', time.time())
                try:
                    queue.flush()
                except Exception as error:
                    queue.meta('last_error', str(error))
                if time.monotonic() > deadline:
                    raise TimeoutError('Executor exceeded one-hour limit')
                time.sleep(5)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
    if process.returncode != 0 or not result_path.exists():
        queue.update(number, status='RETRY', retry_at=time.time()+300, result='Executor failed or did not supply a verified result')
        return
    result = json.loads(result_path.read_text())
    finish(queue, task, result, progress)


def finish(queue, task, result, progress):
    number = task['issue_number']
    summary = result.get('summary', '')[:6000]
    if result.get('status') == 'WAITING_USER':
        action, probe = result.get('user_action'), result.get('readiness')
        if not action or not probe or '\n' in action:
            raise ValueError('WAITING_USER requires one action and readiness probe')
        queue.update(number, status='WAITING_USER', result=summary, user_action=action, readiness=probe)
        queue.event(number, 'waiting-'+str(task['attempt']), f'STATUS: WAITING_USER\n{summary}\nUSER_ACTION: {action}')
        return
    if result.get('status') != 'DONE':
        raise ValueError('Missing explicit executor completion')
    if not task['synthetic']:
        check = run(['git', 'status', '--porcelain'])
        pushed = run(['git', 'rev-parse', '@{upstream}'])
        head = run(['git', 'rev-parse', 'HEAD'])
        if check.returncode or check.stdout.strip() or pushed.returncode or head.stdout != pushed.stdout:
            raise ValueError('DONE requires clean committed and pushed worktree')
    else:
        head = run(['git', 'rev-parse', 'HEAD'])
    progress.update(number, 'done', 'DONE', 'Verified executor completion')
    sync_progress(queue, number, progress)
    queue.update(number, status='DONE', completed_at=now(), result=summary, commit_hash=head.stdout.strip())
    queue.event(number, 'done', f'DONE: {summary}\nCOMMIT: {head.stdout.strip()}\nUSER_ACTION: NONE')


def process_identity(pid):
    try:
        return Path(f'/proc/{int(pid)}/stat').read_text().rsplit(')', 1)[1].split()[19]
    except (OSError, ValueError):
        return ''


def alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, ValueError, TypeError):
        return False


def tick(queue, handoff=None):
    queue.meta('heartbeat', time.time())
    try:
        raw = gh('issue', 'list', '--state', 'open', '--limit', '1000', '--json', 'number,title,body,author,labels')
    except RuntimeError:
        if run(['gh', 'auth', 'status'], 20).returncode != 0:
            queue.meta('status', 'WAITING_USER')
            queue.meta('user_action', 'Восстановите project-local авторизацию GitHub CLI.')
            for row in queue.db.execute("SELECT * FROM tasks WHERE status IN ('QUEUED','RETRY') AND synthetic=0").fetchall():
                queue.update(row['issue_number'], status='WAITING_USER', readiness='github', user_action=queue.meta('user_action'))
                queue.event(row['issue_number'], 'github-auth', 'STATUS: WAITING_USER\nUSER_ACTION: '+queue.meta('user_action'))
        raise
    queue.meta('status', 'READY')
    queue.meta('user_action', '')
    queue.ingest(json.loads(raw))
    queue.migrate()
    queue.meta('last_poll', now())
    if handoff and alive(handoff) and queue.task(12):
        state = Progress().read(12) or Progress().read()
        queue.update(12, status='RUNNING', attempt=max(1, queue.task(12)['attempt']), started_at=state.get('started_at') if state else now(), heartbeat=now())
        sync_progress(queue, 12, Progress())
    for row in queue.db.execute("SELECT * FROM tasks WHERE status='WAITING_USER'").fetchall():
        if readiness(dict(row)):
            queue.update(row['issue_number'], status='QUEUED', user_action=None)
    legacy = handoff and alive(handoff)
    task = queue.claim(synthetic_only=bool(legacy))
    if task:
        try:
            execute(queue, task)
        except Exception as error:
            queue.update(task['issue_number'], status='RETRY', retry_at=time.time()+300, result=type(error).__name__)
            raise
    queue.flush()
    queue.meta('last_error', '')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--health', action='store_true')
    parser.add_argument('--handoff', type=int, help='Legacy worker PID; no real execution until legacy completes current task')
    parser.add_argument('--synthetic', action='store_true', help='Enqueue local acceptance task, without restarting worker')
    args = parser.parse_args()
    queue = Queue()
    if args.health:
        health = queue.health()
        health['healthy'] = bool(health['heartbeat'] and time.time()-float(health['heartbeat']) < 120 and alive(health['pid']) and not health['last_error'])
        print(json.dumps(health, ensure_ascii=False, indent=2))
        return 0 if health['healthy'] else 1
    if args.synthetic:
        number = -int(time.time()*1000)
        with queue.db:
            queue.db.execute('INSERT INTO tasks(issue_id,issue_number,title,body,priority,synthetic) VALUES (?,?,?, ?, -2,1)', (number,number,'Synthetic acceptance','No mutations'))
        print(number)
        return 0
    with (ROOT/'data/worker.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        queue.meta('pid', os.getpid())
        service_pid = run(['systemctl', 'show', 'ceo-github-worker.service', '--property=MainPID', '--value'], 10)
        if service_pid.stdout.strip() == str(os.getpid()):
            verification = dict(pid=os.getpid(), at=now(),
                active=run(['systemctl', 'is-active', 'ceo-github-worker.service'], 10).stdout.strip(),
                enabled=run(['systemctl', 'is-enabled', 'ceo-github-worker.service'], 10).stdout.strip(),
                restart=run(['systemctl', 'show', 'ceo-github-worker.service', '--property=Restart', '--value'], 10).stdout.strip())
            queue.meta('deployment', json.dumps(verification))
            if queue.task(12) and queue.task(12)['status'] == 'DONE':
                queue.event(12, 'deployment-verified', 'LIVE: deployed worker loaded under ceo-github-worker.service.\n' + json.dumps(verification) + '\nUSER_ACTION: NONE')
        while True:
            try:
                if args.handoff:
                    legacy = ROOT/'data/worker_state.json'
                    done = json.loads(legacy.read_text()).get('done', []) if legacy.exists() else []
                    if '12' in done:
                        # The current executor has returned; let Restart=always activate deployed code.
                        if queue.task(12):
                            queue.update(12, status='DONE', completed_at=now(), result='Deployment completed by legacy executor', commit_hash=run(['git','rev-parse','HEAD']).stdout.strip())
                        os.kill(args.handoff, signal.SIGTERM)
                        return 0
                tick(queue, args.handoff)
            except Exception as error:
                queue.meta('last_error', f'{type(error).__name__}: {error}')
            time.sleep(INTERVAL)


if __name__ == '__main__':
    sys.exit(main())
