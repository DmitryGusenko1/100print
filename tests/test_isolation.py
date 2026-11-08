import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from app.isolation import IsolationRequired
from app.github_worker import Queue, execute
from app.progress import Progress

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('issue23_access', ROOT/'ai-team/ops/project-access.py')
access = importlib.util.module_from_spec(spec)
spec.loader.exec_module(access)


class IsolationTests(unittest.TestCase):
    def test_real_worker_refuses_without_spawning(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as tmp:
            q = Queue(tmp)
            self.addCleanup(q.db.close)
            q.ingest([dict(number=23,title='probe',body='ignored',author={'login':'DmitryGusenko1'},labels=[])])
            task = q.claim()
            with patch('app.github_worker.subprocess.Popen') as spawn:
                execute(q, task)
            spawn.assert_not_called()
            self.assertEqual(q.task(23)['status'], 'WAITING_USER')
            # Owner approval is not an enforcement receipt and cannot enable execution.
            (Path(tmp)/'data/issue23-host-review-approved').touch()
            execute(q, q.task(23))
            self.assertEqual(q.task(23)['status'], 'WAITING_USER')

    def test_direct_and_delegated_adapters_deny_before_effect(self):
        from app.hermes_bridge import execute as hermes_execute
        from app.organization.codex import ProductionCodexProvider
        from app.codex_runner import CodexRunner
        from app.providers import LocalBrainProvider
        with patch('subprocess.Popen') as spawn:
            for call in (lambda: hermes_execute({}),
                         lambda: ProductionCodexProvider.__new__(ProductionCodexProvider).respond({}),
                         lambda: CodexRunner.__new__(CodexRunner).run('probe', '../escape'),
                         lambda: LocalBrainProvider().execute({'type':'ai-task'}),
                         lambda: access.executor_probe('submit')):
                with self.assertRaises(IsolationRequired): call()
            spawn.assert_not_called()

    def test_symlink_fixture_and_traversal_denied(self):
        # All fixtures belong to this project; no adjacent project is inspected.
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as tmp:
            root=Path(tmp)
            (root/'allowed').mkdir()
            (root/'private-fixture').write_text('synthetic canary')
            (root/'allowed/link.md').symlink_to(root/'private-fixture')
            with patch.object(access,'ROOT',root), patch.object(access,'allowed_files',return_value=['allowed/link.md']):
                for path in ('allowed/link.md','allowed/../private-fixture','../neighbor','/etc/passwd'):
                    with self.subTest(path=path), self.assertRaises(ValueError): access.project_read(path)

    def test_real_wrapper_cannot_be_overridden(self):
        for args in ([],['app-server'],['exec','--dangerously-bypass-approvals-and-sandbox']):
            result=subprocess.run([str(ROOT/'ai-team/ops/hermes-codex-project.sh'),*args],capture_output=True)
            self.assertEqual(result.returncode,77)

    def test_claim_preserves_status_without_db_mutation(self):
        from app.main import claim
        with patch('app.main.connect') as connect:
            self.assertIsNone(claim(None))
            connect.assert_not_called()
