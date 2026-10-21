import unittest
import uuid
from unittest.mock import patch
from app import github_bridge as bridge
from app.db import connect
from app.organization.brain import DeterministicBrainProvider


class BridgeTests(unittest.TestCase):
    def test_context_and_decision_receipts_are_atomic_and_replay_safe(self):
        bridge.migrate()
        session = 'controls-' + uuid.uuid4().hex
        decision = 'Сохранять цены до проверки маржи ' + session
        for index, text in enumerate(('DECISION\n' + decision, 'CONTEXT\n' + session)):
            comment = {'id': -int(uuid.uuid4().int % 10**15),
                       'user': {'login': bridge.OWNER},
                       'body': f'CHATGPT_IN\nsession={session}\nmessage={text}'}
            with patch.object(bridge.memory, 'create_task', side_effect=AssertionError('control ran inference')):
                bridge.ingest(comment)
                bridge.ingest(comment)
            with connect() as conn, conn.cursor() as cur:
                cur.execute('''SELECT t.status,t.result,t.error FROM tasks t JOIN
                    chatgpt_bridge_comments b ON b.task_id=t.id WHERE b.comment_id=%s''', (comment['id'],))
                receipt = bridge.brief(cur.fetchone())
                self.assertEqual(receipt['status'], 'done')
                if index == 0:
                    self.assertTrue(receipt['saved'])
                    cur.execute('SELECT count(*) AS n FROM project_memory WHERE text=%s AND kind=\'decision\'', (decision,))
                    self.assertEqual(cur.fetchone()['n'], 1)
                else:
                    self.assertTrue(any(r['text'] == decision for r in receipt['context']['relevant_memory']))
            # Do not leave synthetic receipts for later delivery tests.
            with connect() as conn, conn.cursor() as cur:
                cur.execute('UPDATE chatgpt_bridge_comments SET delivered_at=now() WHERE comment_id=%s', (comment['id'],))

    def test_legacy_gh_pagination(self):
        from types import SimpleNamespace
        with patch.object(bridge.subprocess, 'run', return_value=SimpleNamespace(stdout='[{"id":1}]\n[{"id":2}]\n')) as run:
            self.assertEqual([c['id'] for c in bridge.comments()], [1, 2])
            self.assertNotIn('--slurp', run.call_args.args[0])

    def test_contract_and_author(self):
        valid = {'user': {'login': bridge.OWNER}, 'body': 'CHATGPT_IN\nsession=voice\nmessage=first\nsecond'}
        self.assertEqual(bridge.parse(valid), ('voice', 'first\nsecond'))
        for body in ['CHATGPT_OUT\nsession=x\nmessage=x', 'CHATGPT_IN\nsession=\nmessage=x', 'CHATGPT_IN\nsession=x\nmessage=   ']:
            self.assertIsNone(bridge.parse({**valid, 'body': body}))
        self.assertIsNone(bridge.parse({**valid, 'user': {'login': 'stranger'}}))
        with self.assertRaises(ValueError):
            bridge.api('repos/foreign/project/issues/8/comments')
        for suffix in ['/../comments', '/123', '?per_page=100&other=1']:
            with self.assertRaises(ValueError):
                bridge.api(f'repos/{bridge.REPO}/issues/{bridge.ISSUE}/comments'+suffix)

    def test_postgres_replay_and_delivery_crash(self):
        bridge.migrate()
        # Negative IDs cannot collide with actual GitHub IDs.
        comment = {'id': -int(uuid.uuid4().int % 10**15), 'user': {'login': bridge.OWNER},
                   'body': 'CHATGPT_IN\nsession=test-'+uuid.uuid4().hex+'\nmessage=Проверь метатеги'}
        create_task=bridge.memory.create_task
        def paused_task(cur,*args,**kwargs):
            result=create_task(cur,*args,**kwargs)
            # Pause inside intake's transaction, before the live production worker can claim it.
            cur.execute("UPDATE tasks SET status='waiting' WHERE id=%s",(result['task_id'],))
            return result
        with patch.object(bridge.memory,'create_task',side_effect=paused_task):
            bridge.ingest(comment)
            bridge.ingest(comment)
        with connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT * FROM chatgpt_bridge_comments WHERE comment_id=%s', (comment['id'],))
            row = cur.fetchone()
            tid = str(row['task_id'])
            cur.execute("UPDATE tasks SET status='waiting' WHERE id=%s", (tid,))
            cur.execute('SELECT count(*) AS n FROM project_memory WHERE conversation_id=%s AND role=\'user\'', (row['conversation_id'],))
            self.assertEqual(cur.fetchone()['n'], 1)
        from app.providers import LocalBrainProvider
        from app import project_memory as memory
        from app.db import Json
        with connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT * FROM tasks WHERE id=%s', (tid,))
            task = dict(cur.fetchone())
        with patch('app.providers.business_brain',return_value=DeterministicBrainProvider()):
            result = LocalBrainProvider().execute(task)
        with connect() as conn, conn.cursor() as cur:
            memory.persist_analysis(cur, task, result)
            cur.execute("UPDATE tasks SET status='done',result=%s WHERE id=%s", (Json(result), tid))
        with patch.object(bridge,'api',side_effect=AssertionError('synthetic delivery escaped test')):
            bridge.deliver([])
        posted = []
        def post(path, body):
            item = {'id': comment['id']-1, 'body': body, 'user': {'login': bridge.OWNER}}
            posted.append(item)
            return item
        with patch.object(bridge, 'api', side_effect=post), patch.object(bridge.memory, 'append', side_effect=RuntimeError('crash after POST')):
            with self.assertRaises(RuntimeError):
                bridge.deliver([], test_only=True)
        self.assertEqual(len(posted), 1)
        self.assertIn('"request_comment_id":' + str(comment['id']), posted[0]['body'])
        # Fresh delivery recovers the reply marker and never sends a second POST.
        with patch.object(bridge, 'api', side_effect=AssertionError('duplicate POST')):
            bridge.deliver(posted, test_only=True)
        with connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT delivered_at FROM chatgpt_bridge_comments WHERE comment_id=%s', (comment['id'],))
            self.assertIsNotNone(cur.fetchone()['delivered_at'])
