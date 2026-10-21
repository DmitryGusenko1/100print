import unittest
from datetime import datetime, timedelta, timezone
from app.db import connect
from app.intelligence import migrate, put, transition, review, record_analysis, snapshot, metrics
from app.retrieval import FullTextProvider, VectorProvider

class IntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.conn=connect()
        self.cur=self.conn.cursor()
        migrate(self.cur)
    def tearDown(self):
        self.conn.rollback()
        self.cur.close()
        self.conn.close()
    def test_dedup_history_review_and_snooze(self):
        row=put(self.cur,'hypothesis','integration hypothesis',key='issue15:test',review_at=datetime.now(timezone.utc)-timedelta(days=1))
        self.assertEqual(row['id'],put(self.cur,'hypothesis','integration hypothesis',key='issue15:test')['id'])
        review(self.cur); review(self.cur)
        self.cur.execute('SELECT count(*) AS n FROM project_events WHERE artifact_id=%s',(row['id'],))
        self.assertEqual(self.cur.fetchone()['n'],1)
        transition(self.cur,str(row['id']),'closed','issue15:close')
        transition(self.cur,str(row['id']),'closed','issue15:close')
        self.cur.execute('SELECT count(*) AS n FROM artifact_history WHERE artifact_id=%s',(row['id'],))
        self.assertEqual(self.cur.fetchone()['n'],1)
        with self.assertRaises(ValueError): put(self.cur,'hypothesis','different',key='issue15:test')
    def test_analysis_links_snapshot_metrics(self):
        task={'id':'00000000-0000-0000-0000-000000000015'}
        result={'provider':'production-codex-v1','final':{'decision':'Validate portal demand','action_plan':[{'action':'Interview customers','owner':'sales','deadline':'7 days'}]}}
        record_analysis(self.cur,task,result); record_analysis(self.cur,task,result)
        self.cur.execute('SELECT count(*) AS n FROM artifact_links WHERE relation=\'follow_up\' AND source IN (SELECT id FROM project_artifacts WHERE dedupe_key LIKE %s)',('decision-review:%',))
        self.assertGreaterEqual(self.cur.fetchone()['n'],1)
        self.assertIn('decision_needed',snapshot(self.cur))
        self.assertIn('council_usage',metrics(self.cur))
    def test_fulltext_provider(self):
        self.assertIsInstance(FullTextProvider().search(self.cur,'типография',3),list)
        with self.assertRaises(ValueError): VectorProvider(lambda q:[float('nan')],'test').search(self.cur,'query')

class HelperTests(unittest.TestCase):
    def test_fixed_actions(self):
        from scripts.project_service_helper import command
        self.assertEqual(command(['restart','ceo-orchestrator.service'])[0],'/usr/bin/systemctl')
        for args in (['restart','ssh.service'],['restart','ceo-github-worker.service'],['shell','ceo-orchestrator.service']):
            with self.assertRaises(ValueError): command(args)

class SemanticTests(IntelligenceTests):
    def test_vector_and_missing_extension_fallback(self):
        from app.retrieval import VectorProvider, concept_embedding, CONCEPT_MODEL, index_memory
        from unittest.mock import Mock, patch
        self.cur.execute('SELECT id FROM project_memory LIMIT 1')
        row=self.cur.fetchone()
        if row:
            index_memory(self.cur,row['id'],'маржа pricing')
            hits=VectorProvider(concept_embedding,CONCEPT_MODEL).search(self.cur,'маржа pricing',5)
            self.assertTrue(hits)
        fake=Mock()
        fake.fetchone.return_value={'available':False}
        embed=Mock(side_effect=AssertionError('Embedding must not run without vector'))
        with patch('app.retrieval.FullTextProvider.search',return_value=['fallback']):
            self.assertEqual(VectorProvider(embed,'unavailable').search(fake,'query'),['fallback'])
        embed.assert_not_called()
