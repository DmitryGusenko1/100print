import json
import unittest
import uuid
from unittest.mock import patch
from app import github_bridge as bridge, hermes_bridge as hermes
from app.db import connect, Json


class HermesBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bridge.migrate()

    def comment(self, message, session=None):
        return {'id': -int(uuid.uuid4().int % 10**15), 'user': {'login': bridge.OWNER},
                'body': 'CHATGPT_IN\nsession=' + (session or uuid.uuid4().hex) + '\nmessage=' + message}

    def test_intake_replay_does_not_create_legacy_analysis(self):
        comment = self.comment('submit_task\nCreate a test artifact')
        with patch.object(bridge.memory, 'create_task', side_effect=AssertionError('legacy provider')):
            bridge.ingest(comment)
            bridge.ingest(comment)
        with connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT t.result FROM tasks t JOIN chatgpt_bridge_comments b ON b.task_id=t.id WHERE comment_id=%s', (comment['id'],))
            receipt = cur.fetchone()['result']
            cur.execute('SELECT t.status,j.status AS job_status FROM tasks t JOIN hermes_bridge_jobs j ON j.task_id=t.id WHERE t.id=%s', (receipt['task_id'],))
            row = cur.fetchone()
            self.assertEqual((row['status'], row['job_status']), ('waiting', 'queued'))
            # Isolate synthetic jobs from live inference worker.
            cur.execute("UPDATE hermes_bridge_jobs SET status='failed' WHERE task_id=%s", (receipt['task_id'],))
            cur.execute('UPDATE chatgpt_bridge_comments SET delivered_at=now() WHERE comment_id=%s', (comment['id'],))

    def test_result_session_boundary_and_private_fields(self):
        with connect() as conn, conn.cursor() as cur:
            tid = hermes.submit(cur, 'private-session', 'private prompt', uuid.uuid4().hex)
            cur.execute("UPDATE hermes_bridge_jobs SET status='done',result=%s WHERE task_id=%s", (Json({'artifacts': []}), tid))
            self.assertEqual(hermes.result(cur, 'other-session', tid)['error'], 'task_not_found')
            public = hermes.result(cur, 'private-session', tid)
            self.assertNotIn('prompt', json.dumps(public))
            self.assertEqual(public['status'], 'done')

    def test_crash_after_github_post_recovers_without_duplicate(self):
        comment = self.comment('status')
        bridge.ingest(comment)
        posted = []
        def post(path, body):
            item = {'id': comment['id'] - 1, 'body': body, 'user': {'login': bridge.OWNER}}
            posted.append(item)
            return item
        with patch.object(bridge, 'api', side_effect=post), patch.object(bridge.memory, 'append', side_effect=RuntimeError('crash')):
            with self.assertRaises(RuntimeError):
                bridge.deliver([], test_only=True)
        with patch.object(bridge, 'api', side_effect=AssertionError('duplicate POST')):
            bridge.deliver(posted, test_only=True)
        self.assertEqual(len(posted), 1)

    def test_decision_is_reported_without_approval(self):
        comment = self.comment('DECISION\nExample decision')
        bridge.ingest(comment)
        with connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT result FROM tasks t JOIN chatgpt_bridge_comments b ON b.task_id=t.id WHERE comment_id=%s', (comment['id'],))
            result = cur.fetchone()['result']
            self.assertEqual(result['decision_status'], 'reported')
            self.assertFalse(result['approval_granted'])
            cur.execute('UPDATE chatgpt_bridge_comments SET delivered_at=now() WHERE comment_id=%s', (comment['id'],))

    def test_public_result_never_exports_legacy_private_analysis(self):
        public = bridge.brief({'status': 'done', 'result': {'synthesis': 'PRIVATE', 'error': 'SECRET'}})
        self.assertNotIn('PRIVATE', json.dumps(public))
        self.assertNotIn('SECRET', json.dumps(public))

    def test_restart_fails_unknown_effect_without_reexecution(self):
        with connect() as conn, conn.cursor() as cur:
            tid = hermes.submit(cur, uuid.uuid4().hex, 'must not rerun', uuid.uuid4().hex)
            cur.execute("UPDATE hermes_bridge_jobs SET status='running' WHERE task_id=%s", (tid,))
        with patch.object(hermes, 'execute', side_effect=AssertionError('replayed effect')):
            hermes.work_once()
        with connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT status,result FROM hermes_bridge_jobs WHERE task_id=%s', (tid,))
            row = cur.fetchone()
            self.assertEqual(row['status'], 'failed')
            self.assertEqual(row['result']['error'], 'interrupted_effect_unknown_no_automatic_replay')

    def test_legacy_context_is_not_exported(self):
        public = bridge.brief({'status': 'done', 'result': {'operation': 'CONTEXT', 'context': {'relevant_memory': [{'text': 'PRIVATE CUSTOMER'}]}}})
        self.assertNotIn('PRIVATE CUSTOMER', json.dumps(public))

    def test_ambiguous_proposal_delivery_never_resends_or_approves(self):
        with connect() as conn, conn.cursor() as cur:
            tid = hermes.submit(cur, uuid.uuid4().hex, 'sanitized test proposal', uuid.uuid4().hex)
            cur.execute("UPDATE hermes_bridge_jobs SET status='awaiting_owner' WHERE task_id=%s RETURNING *", (tid,))
            job = dict(cur.fetchone())
        with patch('dotenv.dotenv_values', return_value={'TELEGRAM_BOT_TOKEN': 'test-placeholder', 'TELEGRAM_ALLOWED_USERS': '123'}), patch('urllib.request.urlopen', side_effect=TimeoutError('uncertain send')) as send:
            hermes.send_proposal(job)
            hermes.send_proposal(job)
            self.assertEqual(send.call_count, 1)
        with connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT status,result FROM hermes_bridge_jobs WHERE task_id=%s', (tid,))
            row = cur.fetchone()
            self.assertEqual(row['status'], 'awaiting_owner')
            self.assertEqual(row['result']['delivery'], 'unknown')
            self.assertFalse(row['result']['approval_granted'])
            cur.execute("UPDATE hermes_bridge_jobs SET status='failed' WHERE task_id=%s", (tid,))

    def test_scheduler_does_not_create_legacy_followup_for_bridge(self):
        from app.main import maintenance
        with connect() as conn, conn.cursor() as cur:
            tid = hermes.submit(cur, uuid.uuid4().hex, 'scheduler isolation', uuid.uuid4().hex)
            cur.execute("UPDATE tasks SET updated_at=now()-interval '2 hours' WHERE id=%s", (tid,))
            with patch('app.main.due', side_effect=lambda cur, name, seconds: name == 'hourly'):
                maintenance(cur, None)
            cur.execute('SELECT count(*) AS n FROM tasks WHERE dedupe_key=%s', ('followup:' + tid,))
            self.assertEqual(cur.fetchone()['n'], 0)
            cur.execute("UPDATE hermes_bridge_jobs SET status='failed' WHERE task_id=%s", (tid,))
            cur.execute("UPDATE tasks SET status='failed' WHERE id=%s", (tid,))
