"""Explicit live checks against ceo_orchestrator only, with durable checkpoints."""
import unittest
from app.db import ROOT, connect, enqueue, Json
from app.organization.engine import Organization
from app.organization.registry import Registry
from app.organization.store import PostgresStore
from tests.test_organization import CountingBrain
from tests.test_runtime import row


class PostgresOrganizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with connect() as conn, conn.cursor() as cur:
            cur.execute((ROOT/'config/schema.sql').read_text())
            Registry().sync(cur)

    def test_levels_registry_and_persisted_rounds(self):
        for level, departments in [('L1',['seo']),('L2',['finance']),
                                    ('L3',['marketing','finance']),('L4',['strategy'])]:
            with self.subTest(level=level):
                payload={'level':level,'departments':departments}
                with connect() as conn, conn.cursor() as cur:
                    task_id=enqueue(cur,'Organization integration '+level,'ai-task',payload,'integration-test')
                    cur.execute("UPDATE tasks SET status='waiting' WHERE id=%s",(task_id,))
                # Test/mock provider is explicit; never invoke paid production inference in fixtures.
                task=row(task_id)
                result=Organization(CountingBrain(),PostgresStore()).execute(task)
                with connect() as conn, conn.cursor() as cur:
                    cur.execute("UPDATE tasks SET status='done',result=%s WHERE id=%s",(Json(result),task_id))
                task=row(task_id)
                self.assertEqual(task['result']['routing']['level'],level)
                with connect() as conn, conn.cursor() as cur:
                    cur.execute('SELECT step_key FROM organization_steps WHERE task_id=%s',(task_id,))
                    keys={r['step_key'] for r in cur.fetchall()}
                    self.assertIn('manifest',keys)
                    if level in ('L3','L4'):
                        self.assertTrue({f'round/{i}' for i in range(7)} <= keys)
                        self.assertTrue(task['result']['critic_challenge']['blocking'])
        with connect() as conn, conn.cursor() as cur:
            cur.execute('SELECT count(*) AS n FROM skills_registry')
            self.assertEqual(cur.fetchone()['n'],62)
            cur.execute('SELECT count(*) AS n FROM organization_roles')
            self.assertEqual(cur.fetchone()['n'],29)

    def test_resume_from_fresh_postgres_store_after_interruption(self):
        with connect() as conn, conn.cursor() as cur:
            task_id=enqueue(cur,'Persisted restart verification','ai-task',{},'integration-test')
            # Prevent the running worker claiming this test-owned task.
            cur.execute("UPDATE tasks SET status='waiting' WHERE id=%s",(task_id,))
        task={'id':task_id,'title':'Restart','type':'council','payload':{}}
        first=CountingBrain(fail_at=12)
        with self.assertRaises(RuntimeError): Organization(first,PostgresStore()).execute(task)
        resumed=CountingBrain()
        result=Organization(resumed,PostgresStore()).execute(task)
        replay=CountingBrain()
        self.assertEqual(Organization(replay,PostgresStore()).execute(task),result)
        self.assertEqual(replay.calls,[])
        with connect() as conn, conn.cursor() as cur:
            cur.execute("UPDATE tasks SET status='done',result=%s,finished_at=now() WHERE id=%s",
                        (Json(result),task_id))
