import unittest
import uuid
from unittest.mock import patch
from app import github_bridge as bridge
from app.db import connect


class BridgeTests(unittest.TestCase):
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
        result = LocalBrainProvider().execute(task)
        with connect() as conn, conn.cursor() as cur:
            memory.persist_analysis(cur, task, result)
            cur.execute("UPDATE tasks SET status='done',result=%s WHERE id=%s", (Json(result), tid))
        posted = []
        def post(path, body):
            item = {'id': comment['id']-1, 'body': body, 'user': {'login': bridge.OWNER}}
            posted.append(item)
            return item
        with patch.object(bridge, 'api', side_effect=post), patch.object(bridge.memory, 'append', side_effect=RuntimeError('crash after POST')):
            with self.assertRaises(RuntimeError):
                bridge.deliver([])
        self.assertEqual(len(posted), 1)
        # Fresh delivery recovers the reply marker and never sends a second POST.
        with patch.object(bridge, 'api', side_effect=AssertionError('duplicate POST')):
            bridge.deliver(posted)
        with connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT delivered_at FROM chatgpt_bridge_comments WHERE comment_id=%s', (comment['id'],))
            self.assertIsNotNone(cur.fetchone()['delivered_at'])
