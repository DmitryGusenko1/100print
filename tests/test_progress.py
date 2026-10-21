import json
from pathlib import Path
import tempfile
import threading
import unittest

from app.progress import Progress, STAGES, format_progress


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.progress = Progress(self.temp.name)

    def test_stages_survive_restart(self):
        self.assertIn('idle', format_progress(self.progress.read()))
        for stage, percent in STAGES.items():
            state = self.progress.update(7, stage, 'subtask', 'action')
            self.assertEqual(percent, state['percent'])
            self.assertEqual(state, Progress(self.temp.name).read())
        self.assertEqual('issue #7 | 100% | done | current: subtask', format_progress(state))
        with self.assertRaises(ValueError):
            self.progress.update(7, 'analysis')
        next_state = self.progress.update(8, 'analysis')
        self.assertEqual(10, next_state['percent'])

    def test_heartbeat_preserves_stage_and_start(self):
        state = self.progress.update(7, 'integration', 'bridge tests', 'testing')
        stop = threading.Event()
        thread = threading.Thread(target=self.progress.heartbeat, args=(7, stop, .01))
        thread.start()
        try:
            for _ in range(100):
                if self.progress.read()['updated_at'] != state['updated_at']:
                    break
                stop.wait(.01)
        finally:
            stop.set()
            thread.join(1)
        restored = self.progress.read()
        self.assertNotEqual(state['updated_at'], restored['updated_at'])
        for key in ('percent', 'stage', 'started_at', 'last_action', 'current_subtask'):
            self.assertEqual(state[key], restored[key])
        events = [json.loads(line) for line in self.progress.log.read_text().splitlines()]
        self.assertTrue(any(event['event'] == 'heartbeat' for event in events))
        self.progress.update(8, 'analysis')
        self.assertIsNone(self.progress.update(7, heartbeat=True))
        self.assertEqual(8, self.progress.read()['issue_number'])

    def test_failure_keeps_real_stage(self):
        self.progress.update(7, 'tests', 'running tests')
        state = self.progress.update(7, action='executor failed: exit 1')
        self.assertEqual(75, state['percent'])
        self.assertIn('failed', state['last_action'])


if __name__ == '__main__':
    unittest.main()
