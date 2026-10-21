import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.github_worker import Queue, execute, tick, finish, eligible, priority
from app.progress import Progress


def issue(number, title='task'):
    return dict(number=number, title=title, body='', author={'login':'DmitryGusenko1'}, labels=[])


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.queue = Queue(self.temp.name)
        self.addCleanup(self.queue.db.close)

    def test_priority_dedup_recovery(self):
        q = self.queue
        q.ingest([issue(4), issue(3, 'FINAL task'), issue(2, 'URGENT second'), issue(1, 'URGENT first')])
        q.ingest([issue(1, 'URGENT updated')])
        self.assertEqual(4, len(q.health()['tasks']))
        task = q.claim()
        self.assertEqual(1, task['issue_number'])
        self.assertEqual(1, task['attempt'])
        q2 = Queue(self.temp.name)
        self.addCleanup(q2.db.close)
        recovered = q2.claim()
        self.assertEqual(1, recovered['issue_number'])
        self.assertEqual(2, recovered['attempt'])
        for number in [1, 2, 3, 4]:
            self.assertEqual(number, q.claim()['issue_number'])
            q.update(number, status='DONE')
        self.assertIsNone(q.claim())

    def test_filter(self):
        self.assertTrue(eligible(issue(1)))
        other = issue(2)
        other['author']['login'] = 'someone-else'
        self.assertFalse(eligible(other))
        manual = issue(3)
        manual['labels'] = [{'name':'manual'}]
        self.assertFalse(eligible(manual))

    def test_migrate_false_done(self):
        q = self.queue
        q.ingest([issue(11), issue(10)])
        (q.root/'data/worker_state.json').write_text(json.dumps({'done':['10','11']}))
        q.migrate()
        self.assertEqual('WAITING_USER', q.task(11)['status'])
        self.assertEqual(90, json.loads(q.task(11)['last_progress'])['percent'])
        self.assertEqual('DONE', q.task(10)['status'])
        q.migrate()
        self.assertEqual(1, q.db.execute('SELECT COUNT(*) FROM events').fetchone()[0])

    def test_wait_resume_and_one_notice(self):
        q = self.queue
        q.ingest([issue(1)])
        task = q.claim()
        p = Progress(q.root)
        p.update(1, 'implementation')
        result = dict(status='WAITING_USER',summary='auth needed', user_action='Complete OAuth',readiness='github')
        finish(q, task, result, p)
        finish(q, task, result, p)
        self.assertEqual(1,q.db.execute("SELECT COUNT(*) FROM events WHERE marker LIKE '%waiting%'").fetchone()[0])
        self.assertIsNone(q.claim())
        q.meta('migrated','yes')
        with patch('app.github_worker.gh', return_value='[]'), patch('app.github_worker.readiness',return_value=True), patch('app.github_worker.execute') as executor, patch.object(q,'flush'):
            tick(q)
            self.assertEqual(1,executor.call_args.args[1]['issue_number'])

    def test_synthetic_no_restart_and_no_duplicate(self):
        q = self.queue
        q.ingest([issue(-1)])
        q.update(-1, synthetic=1)
        execute(q, q.claim())
        self.assertEqual('DONE', q.task(-1)['status'])
        self.assertEqual(100,json.loads(q.task(-1)['last_progress'])['percent'])
        self.assertIsNone(q.claim())
        self.assertEqual(9,q.db.execute('SELECT COUNT(*) FROM events').fetchone()[0])

    def test_outbox_reconciles_lost_response(self):
        q = self.queue
        q.ingest([issue(1)])
        q.event(1,'start','START')
        from subprocess import CompletedProcess
        marker = '<!-- ceo-worker:1:start -->'
        with patch('app.github_worker.run',return_value=CompletedProcess([],0,json.dumps(marker)+'\n','')), patch('app.github_worker.gh') as github:
            q.flush()
            github.assert_not_called()
        self.assertEqual(1,q.db.execute('SELECT delivered FROM events').fetchone()[0])

    def test_progress_survives_another_task_and_persists_all_stages(self):
        q = self.queue
        q.ingest([issue(1),issue(2)])
        p = Progress(q.root)
        p.update(1,'integration')
        p.update(2,'analysis')
        p.update(1, action='resume')
        self.assertEqual(60,p.read()['percent'])
        self.assertEqual(60,json.loads(q.task(1)['last_progress'])['percent'])
        with self.assertRaises(ValueError):
            p.update(1,'analysis')

    def test_surviving_executor_is_not_duplicated(self):
        q = self.queue
        q.ingest([issue(1)])
        task = q.claim()
        q.meta('executor-1', 123)
        q.meta('executor-identity-1', 'same-process')
        from subprocess import CompletedProcess
        with patch('app.github_worker.run', return_value=CompletedProcess([],0,'','')), patch('app.github_worker.alive',return_value=True), patch('app.github_worker.process_identity',return_value='same-process'), patch('app.github_worker.subprocess.Popen') as spawn:
            execute(q, task)
            spawn.assert_not_called()
        self.assertEqual('RETRY',q.task(1)['status'])

    def test_auth_waits_instead_of_claiming_done(self):
        q = self.queue
        q.ingest([issue(1)])
        from subprocess import CompletedProcess
        with patch('app.github_worker.run', return_value=CompletedProcess([],1,'','')), patch('app.github_worker.subprocess.Popen') as spawn:
            execute(q, q.claim())
            spawn.assert_not_called()
        self.assertEqual('WAITING_USER',q.task(1)['status'])
        self.assertEqual('codex',q.task(1)['readiness'])

    def test_done_requires_explicit_result(self):
        q = self.queue
        q.ingest([issue(1)])
        with self.assertRaises(ValueError):
            finish(q,q.claim(),dict(status='FAILED'),Progress(q.root))
        self.assertNotEqual('DONE',q.task(1)['status'])


if __name__ == '__main__':
    unittest.main()
