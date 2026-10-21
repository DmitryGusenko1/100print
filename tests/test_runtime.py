"""Live integration checks against ONLY this project's private database/service.

Run explicitly: .venv/bin/python -m unittest tests.test_runtime -v
Includes intentional SIGKILL of ceo-orchestrator.service's own MainPID.
"""
import os
from pathlib import Path
import signal
import subprocess
import time
import unittest
import psycopg2
from app.db import ROOT, connect, enqueue, Json
from app.main import maintenance
from app.codex_runner import CodexRunner


def row(task_id):
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT * FROM tasks WHERE id=%s',(task_id,));return cur.fetchone()


def wait_for(fn, seconds=45):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        try:
            value=fn()
            if value:return value
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            pass # Own PostgreSQL may be restarting with the unit.
        time.sleep(.25)
    raise AssertionError('Timed out waiting for condition')

class RuntimeTests(unittest.TestCase):
    def add(self,kind='echo',payload=None):
        with connect() as conn, conn.cursor() as cur:
            return enqueue(cur,'Integration verification',kind,payload,'integration-test')

    def test_01_task_result_and_audit(self):
        task=self.add(payload={'check':'durable result'})
        wait_for(lambda:row(task)['status']=='done')
        self.assertEqual(row(task)['result']['echo']['check'],'durable result')
        with connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT status FROM agent_runs WHERE task_id=%s',(task,))
            self.assertEqual(cur.fetchone()['status'],'done')

    def test_02_bounded_retry(self):
        with connect() as conn, conn.cursor() as cur:
            task=enqueue(cur,'Expected unsupported handler','unsupported',source='integration-test')
            cur.execute('UPDATE tasks SET max_attempts=2 WHERE id=%s',(task,))
        wait_for(lambda:row(task)['status']=='failed')
        self.assertEqual(row(task)['attempts'],2)
        self.assertIn('No handler',row(task)['error'])

    def test_03_scheduler_and_handoff_deduplication(self):
        task=self.add()
        wait_for(lambda:row(task)['status']=='done')
        with connect() as conn, conn.cursor() as cur:
            cur.execute("UPDATE tasks SET status='waiting',updated_at=now()-interval '2 hours' WHERE id=%s",(task,))
            cur.execute("INSERT INTO handoffs(task_id,updated_at) VALUES (%s,now()-interval '10 minutes') RETURNING id",(task,))
            handoff=cur.fetchone()['id']
            cur.execute("DELETE FROM scheduler_state WHERE name IN ('hourly','maintenance','daily')")
            maintenance(cur,None)
            cur.execute("DELETE FROM scheduler_state WHERE name IN ('hourly','maintenance')")
            maintenance(cur,None)
            cur.execute("SELECT count(*) AS n FROM tasks WHERE dedupe_key=%s",(f'followup:{task}',))
            self.assertEqual(cur.fetchone()['n'],1)
            cur.execute('SELECT status FROM handoffs WHERE id=%s',(handoff,))
            self.assertEqual(cur.fetchone()['status'],'waiting')
            cur.execute('SELECT count(*) AS n FROM reports');self.assertGreater(cur.fetchone()['n'],0)
            cur.execute("UPDATE tasks SET status='done',updated_at=now() WHERE id=%s",(task,))

    def test_04_crash_recovery_and_heartbeat(self):
        task=self.add(payload={'delay_seconds':8,'check':'crash recovery'})
        wait_for(lambda:row(task)['status']=='processing')
        pid=int(subprocess.check_output(['systemctl','show','ceo-orchestrator.service','-p','MainPID','--value']))
        self.assertEqual(Path(f'/proc/{pid}').stat().st_uid,os.getuid())
        os.kill(pid,signal.SIGKILL)
        wait_for(lambda:row(task)['status']=='done',60)
        self.assertEqual(row(task)['attempts'],2)
        self.assertEqual(row(task)['result']['echo']['check'],'crash recovery')
        with connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT status FROM agent_runs WHERE task_id=%s ORDER BY id',(task,))
            self.assertEqual([r['status'] for r in cur.fetchall()],['interrupted','done'])
            cur.execute("SELECT extract(epoch from now()-updated_at) AS age FROM heartbeats WHERE id='orchestrator'")
            self.assertLess(cur.fetchone()['age'],10)
            cur.execute('SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user')
            self.assertFalse(any(cur.fetchone().values()))

    def test_05_codex_path_policy(self):
        runner=CodexRunner('/opt/ceo-orchestrator/app/main.py')
        for path in ('/opt',ROOT,ROOT/'data',ROOT/'.config'):
            with self.assertRaises(ValueError):runner.run('test',path)
        link=ROOT/'jobs/workspaces/escape-test'
        link.symlink_to('/opt',target_is_directory=True)
        try:
            with self.assertRaises(ValueError):runner.run('test',link)
        finally:link.unlink()

if __name__=='__main__':unittest.main()
