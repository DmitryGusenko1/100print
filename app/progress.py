"""Durable, stage-based GitHub worker progress (stdlib only)."""
import fcntl
import json
import os
from pathlib import Path
import threading
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
STAGES = {"analysis": 10, "planning": 25, "implementation": 40,
          "integration": 60, "tests": 75, "commit/push": 90, "done": 100}


def now():
    return datetime.now(timezone.utc).isoformat()


class Progress:
    def __init__(self, root=ROOT):
        self.path = Path(root) / "data/progress.json"
        self.lock = Path(root) / "data/progress.lock"
        self.log = Path(root) / "logs/github_worker.log"

    def read(self, issue=None):
        try:
            return json.loads((self.path if issue is None else self.path.parent / f"progress-{int(issue)}.json").read_text())
        except FileNotFoundError:
            return None

    def update(self, issue, stage=None, current=None, action=None, eta=None, heartbeat=False):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = self.read()
            fresh = not state or state["issue_number"] != int(issue)
            if fresh and not heartbeat:
                saved = self.read(issue)
                if saved:
                    state = saved
                    fresh = False
            if fresh:
                if heartbeat:
                    return None
                state = dict(issue_number=int(issue), stage="analysis", percent=10,
                             started_at=now(), last_action="started", current_subtask="analysis",
                             eta_optional=None)
            if stage is not None:
                if stage not in STAGES:
                    raise ValueError("Unknown stage: " + stage)
                if not fresh and STAGES[stage] < state["percent"]:
                    raise ValueError("Progress cannot move backwards")
                state.update(stage=stage, percent=STAGES[stage])
            if current is not None:
                state["current_subtask"] = current
            if action is not None:
                state["last_action"] = action
            if eta is not None:
                state["eta_optional"] = eta
            state["updated_at"] = now()
            temporary = self.path.with_suffix(".tmp")
            with temporary.open("w") as output:
                json.dump(state, output, ensure_ascii=False)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
            snapshot = self.path.parent / f"progress-{int(issue)}.json"
            temporary = snapshot.with_suffix('.tmp')
            with temporary.open('w') as output:
                json.dump(state, output, ensure_ascii=False)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, snapshot)
            # Persist actual stage transitions immediately, even between worker polls.
            database = self.path.parent / 'worker_queue.sqlite3'
            if database.exists():
                import sqlite3
                with sqlite3.connect(database, timeout=30) as conn:
                    conn.execute('UPDATE tasks SET last_progress=?,heartbeat=? WHERE issue_number=?',
                                 (json.dumps(state, ensure_ascii=False), now(), int(issue)))
                    if not heartbeat:
                        conn.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,0)',
                                     (f"ceo-worker:{int(issue)}:progress-{state['percent']}", int(issue),
                                      f"PROGRESS: {state['percent']}% / {state['stage']}\n{state['current_subtask']}"))
            self.log.parent.mkdir(parents=True, exist_ok=True)
            with self.log.open("a") as output:
                output.write(json.dumps(dict(event="heartbeat" if heartbeat else "progress", **state), ensure_ascii=False) + "\n")
            return state

    def heartbeat(self, issue, stop, interval=30):
        while not stop.wait(interval):
            self.update(issue, heartbeat=True)

    def start_heartbeat(self, issue):
        stop = threading.Event()
        thread = threading.Thread(target=self.heartbeat, args=(issue, stop), daemon=True)
        thread.start()
        return stop, thread


def format_progress(state):
    if not state:
        return "idle | no issue progress recorded"
    return (f"issue #{state['issue_number']} | {state['percent']}% | {state['stage']} | "
            f"current: {state['current_subtask']}")
