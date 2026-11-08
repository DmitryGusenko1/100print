import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('owner_telegram', Path(__file__).with_name('set-owner-telegram.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
TOKEN = '123456789:' + 'x' * 35  # synthetic, never sent to Telegram


class OwnerCredentialTests(unittest.TestCase):
    def test_reject_other_bot_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with self.assertRaisesRegex(ValueError, 'not for hundredprintbot'):
                m.install(TOKEN, base, lambda _: 'WebToPrintISbot')
            self.assertEqual(list(base.iterdir()), [])

    def test_install_preserves_allowlist_and_auth_and_private_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project = base / 'config/telegram.env'
            native = base / 'ai-team/runtime/hermes-home/.env'
            project.parent.mkdir(parents=True)
            native.parent.mkdir(parents=True)
            old_project = 'CEO_TELEGRAM_TOKEN=old\nCEO_TELEGRAM_ALLOWED_CHATS=123\nCEO_TELEGRAM_ALLOWED_USERS=123\n'
            old_native = 'TELEGRAM_BOT_TOKEN=old\nTELEGRAM_ALLOWED_USERS=123\nMODEL_AUTH=unchanged\n'
            project.write_text(old_project)
            native.write_text(old_native)
            m.install(TOKEN, base, lambda _: m.TARGET)
            self.assertEqual(project.read_text(), old_project.replace('=old', '=' + TOKEN))
            self.assertEqual(native.read_text(), old_native.replace('=old', '=' + TOKEN))
            backups = list((base / 'ai-team/runtime/secrets').glob('*/*.env'))
            self.assertEqual(len(backups), 2)
            self.assertEqual({p.read_text() for p in backups}, {old_project, old_native})
            for p in [project, native, *backups]:
                self.assertEqual(p.stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
