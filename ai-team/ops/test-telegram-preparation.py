"""Verify owner mapping cannot authorize a group, extra user, or missing token."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('prepare', Path(__file__).with_name('prepare-telegram.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OwnerMapping(unittest.TestCase):
    def test_private_owner(self):
        self.assertEqual(module.credentials({'CEO_TELEGRAM_TOKEN': 'test', 'CEO_TELEGRAM_ALLOWED_CHATS': '123'}), ('test', '123'))

    def test_unsafe_inputs(self):
        for chats, users, token in [('-123', '', 'test'), ('123,456', '', 'test'), ('123', '456', 'test'), ('123', '', ''), ('', '123', 'test')]:
            with self.subTest(chats=chats, users=users, token=token):
                with self.assertRaises(ValueError):
                    module.credentials({'CEO_TELEGRAM_TOKEN': token, 'CEO_TELEGRAM_ALLOWED_CHATS': chats, 'CEO_TELEGRAM_ALLOWED_USERS': users})


if __name__ == '__main__':
    unittest.main()
