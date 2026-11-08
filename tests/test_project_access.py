import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('project_access', Path(__file__).resolve().parents[1] / 'ai-team/ops/project-access.py')
access = importlib.util.module_from_spec(spec)
spec.loader.exec_module(access)


class ProjectAccessTests(unittest.TestCase):
    def test_plan_is_readable(self):
        result = access.project_read('ai-team/roles/overnight-draft.md')
        self.assertIn('DRAFT', result['content'])

    def test_private_paths_and_traversal_are_denied(self):
        for path in ('.env', 'config/telegram.env', 'ai-team/runtime/hermes-home/auth.json',
                     '../other/README.md', 'docs/../README.md', '/etc/passwd'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                access.project_read(path)

    def test_unlisted_probe_action_is_denied(self):
        with self.assertRaises(ValueError):
            access.executor_probe('deploy')
