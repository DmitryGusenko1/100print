import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location('isolated_' + name, ROOT / 'ops/hermes' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


broker = load('broker')
installer = load('install')


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.patch = patch.object(broker, 'STATE', Path(self.temp.name))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.config = patch.object(broker, 'CONFIG', dict(telegram_token='123:fake', owner='42',
                                                       model_api_key='private-key', model='gpt-4.1-mini'))
        self.config.start()
        self.addCleanup(self.config.stop)
        broker.initialize()

    def row(self, identifier):
        with broker.db() as connection:
            return dict(connection.execute('SELECT * FROM jobs WHERE id=?', (identifier,)).fetchone())

    def test_single_claim_and_no_fake_success_without_model(self):
        identifier = broker.submit('first')
        broker.submit('second')
        self.assertEqual(broker.operation({'op': 'next'})['id'], identifier)
        self.assertEqual(broker.operation({'op': 'next'}), {})
        broker.operation({'op': 'result', 'id': identifier, 'ok': True, 'text': 'fake'})
        self.assertEqual(self.row(identifier)['state'], 'failed')

    def test_restart_marks_inflight_unknown_no_replay(self):
        identifier = broker.submit('do not repeat')
        broker.operation({'op': 'next'})
        broker.initialize()
        self.assertEqual(self.row(identifier)['state'], 'failed')
        self.assertEqual(broker.operation({'op': 'next'}), {})

    def test_fixed_model_endpoint_strips_caller_options(self):
        identifier = broker.submit('hello')
        broker.operation({'op': 'next'})
        with patch.object(broker, 'https', return_value={'choices': []}) as request:
            broker.operation({'op': 'model', 'body': {'model': 'attacker',
                'messages': [{'role': 'user', 'content': 'hello'}],
                'base_url': 'http://169.254.169.254', 'max_completion_tokens': 999999}})
        host, route, payload = request.call_args.args
        self.assertEqual((host, route), ('api.openai.com', '/v1/chat/completions'))
        self.assertEqual(payload['model'], 'gpt-4.1-mini')
        self.assertEqual(payload['max_completion_tokens'], 4096)
        self.assertNotIn('base_url', payload)
        self.assertEqual(self.row(identifier)['model_calls'], 1)

    def test_multimodal_fetch_stream_and_unknown_operations_denied(self):
        broker.submit('test')
        broker.operation({'op': 'next'})
        with patch.object(broker, 'https') as network:
            for message in ({'op': 'shell', 'command': 'id'},
                            {'op': 'model', 'body': {'stream': True}},
                            {'op': 'model', 'body': {'messages': [{'content': [{'image_url': 'http://private'}]}]}}):
                with self.subTest(message=message), self.assertRaises(ValueError):
                    broker.operation(message)
            network.assert_not_called()

    def test_wrong_bot_and_webhook_refused_without_polling(self):
        for username, webhook in (('anotherbot', ''), ('hundredprintbot', 'https://webhook')):
            with patch.object(broker, 'telegram', side_effect=[
                {'ok': True, 'result': {'username': username}},
                {'ok': True, 'result': {'url': webhook}}]) as api:
                with self.assertRaises(RuntimeError):
                    broker.preflight()
                self.assertEqual([call.args[0] for call in api.call_args_list], ['getMe', 'getWebhookInfo'])

    def test_only_private_owner_commands_and_offset_are_durable(self):
        import time
        updates = []
        for index, (owner, chat, kind) in enumerate(((42, 42, 'private'), (99, 42, 'private'),
                                                   (42, -42, 'group'), (42, 99, 'private'))):
            updates.append({'update_id': index, 'message': {'from': {'id': owner},
                'chat': {'id': chat, 'type': kind}, 'date': time.time(), 'text': '/hermes hello'}})
        with patch.object(broker, 'telegram', return_value={'ok': True, 'result': updates}):
            broker.poll_once()
        with broker.db() as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM jobs').fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT value FROM metadata WHERE key='offset'").fetchone()[0], '4')

    def test_ambiguous_send_not_replayed(self):
        identifier = broker.submit('hello', True)
        with broker.db() as connection:
            connection.execute("UPDATE jobs SET state='done',answer='private reply',model_calls=1 WHERE id=?", (identifier,))
        with patch.object(broker, 'telegram', side_effect=[{'ok': True, 'result': []}, TimeoutError()]):
            with self.assertRaises(TimeoutError):
                broker.poll_once()
        with patch.object(broker, 'telegram', return_value={'ok': True, 'result': []}) as api:
            broker.poll_once()
            self.assertEqual([call.args[0] for call in api.call_args_list], ['getUpdates'])
        with broker.db() as connection:
            self.assertIsNone(connection.execute("SELECT value FROM metadata WHERE key='telegram_e2e'").fetchone())

    def test_config_has_no_arbitrary_endpoint(self):
        config = dict(broker.CONFIG, base_url='http://localhost')
        with self.assertRaises(ValueError):
            broker.validate(config)
        for owner in ('-42', '42,43', '0', 'everyone'):
            with self.assertRaises(ValueError):
                broker.validate(dict(broker.CONFIG, owner=owner))


class InstallerTests(unittest.TestCase):
    def test_units_keep_secrets_out_of_worker_and_no_host_project_mount(self):
        units = installer.units(Path('/var/lib/100print-isolation/hermes-releases/test'), '/runtime')
        agent = units[installer.NAMES[1]]
        transport = units[installer.NAMES[0]]
        for setting in ('RootDirectory=/var/lib/100print-isolation/rootfs', 'User=ceo-w2p-agent',
                        'PrivateNetwork=yes', 'NoNewPrivileges=yes', 'ProtectSystem=strict',
                        'KillMode=control-group', 'RestrictNamespaces=yes'):
            self.assertIn(setting, agent)
        for secret in ('LoadCredential', 'api_key', '/opt/', '/home/', 'docker.sock'):
            self.assertNotIn(secret, agent)
        self.assertIn('LoadCredential=config:/etc/100print-hermes.json', transport)
        self.assertIn('IPAddressDeny=10.0.0.0/8', transport)

    def test_symlink_policy_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'policy'
            path.symlink_to('/etc/passwd')
            with self.assertRaises(RuntimeError):
                installer.safe(path)

    def test_restore_removes_new_units_before_restart_legacy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            units = root / 'units'
            units.mkdir()
            state = {'old_active': True, 'switch': None}
            for name in installer.NAMES:
                state[name] = {'text': None, 'active': False, 'enabled': False}
                (units / name).write_text('new unit')
            snapshot = root / 'rollback'
            snapshot.write_text(json.dumps(state))
            (root / 'telegram-enabled').write_text('new')
            events = []
            with patch.object(installer, 'BASE', root), patch.object(installer, 'UNITS', units), \
                 patch.object(installer, 'safe'), patch.object(installer, 'service_exists', return_value=True), patch.object(installer, 'write', side_effect=lambda p, d, *a: p.write_text(d)), \
                 patch.object(installer, 'run', side_effect=lambda command: events.append(command)), \
                 patch.object(installer, 'old_command', side_effect=lambda *args: ['old', *args]):
                installer.restore(snapshot)
            self.assertFalse(snapshot.exists())
            self.assertFalse((root / 'telegram-enabled').exists())
            self.assertFalse(any(units.iterdir()))
            self.assertEqual(events[-1], ['old', 'start'])
            self.assertEqual(json.loads((root / 'hermes-evidence.json').read_text())['status'], 'ROLLED_BACK_NOT_NEW_HERMES_READY')

    def test_sources_compile(self):
        for path in (ROOT / 'ops/hermes').glob('*.py'):
            compile(path.read_text(), str(path), 'exec')

class RuntimeAdapterTests(unittest.TestCase):
    def test_sse_adapter_preserves_text_tools_usage_and_finish(self):
        runtime = load('runtime')
        body = {'id': 'test', 'model': 'fixed', 'created': 1, 'choices': [{
            'index': 0, 'message': {'role': 'assistant', 'content': None,
            'tool_calls': [{'id': 'call1', 'type': 'function',
                            'function': {'name': 'terminal', 'arguments': '{}'}}]},
            'finish_reason': 'tool_calls'}], 'usage': {'total_tokens': 12}}
        data = runtime.completion_data(body, True).decode()
        frames = data.strip().split('\n\n')
        self.assertEqual(frames[-1], 'data: [DONE]')
        chunks = [json.loads(frame[6:]) for frame in frames[:-1]]
        self.assertEqual(chunks[0]['choices'][0]['delta']['tool_calls'][0]['index'], 0)
        self.assertEqual(chunks[1]['choices'][0]['finish_reason'], 'tool_calls')
        self.assertEqual(chunks[2]['usage']['total_tokens'], 12)
        self.assertEqual(json.loads(runtime.completion_data(body, False)), body)

    def test_export_rejects_symlinks_and_omits_private_state(self):
        exporter = load('prepare-runtime')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, dest = root / 'source', root / 'dest'
            source.mkdir()
            dest.mkdir()
            (source / '.env').write_text('private')
            (source / 'auth.json').write_text('private')
            (source / 'ignore.pth').write_text('import dangerous')
            (source / 'module.py').write_text('value=1')
            exporter.copy_tree(source, dest)
            self.assertEqual([p.name for p in dest.iterdir()], ['module.py'])
            (source / 'escape').symlink_to(root)
            with self.assertRaises(RuntimeError):
                exporter.copy_tree(source, dest)


class TransactionFailureTests(unittest.TestCase):
    def test_unit_verification_failure_restores_previous_files_and_old_gateway(self):
        import os
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'rootfs').mkdir()
            runtime = base / 'hermes-runtime/hermes_cli'
            runtime.mkdir(parents=True)
            (runtime / 'main.py').write_text('# synthetic runtime')
            units = base / 'units'
            units.mkdir()
            prior = units / installer.NAMES[0]
            prior.write_text('previous reviewed unit')
            config = base / 'config.json'
            config.write_text(json.dumps(dict(telegram_token='123:fake', owner='42',
                                             model_api_key='fake', model='model')))
            config.chmod(0o600)
            account = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid())
            events = []
            def command(argv, **kwargs):
                events.append(argv)
                if argv[0] == 'systemd-analyze':
                    raise RuntimeError('synthetic verification fault')
                return SimpleNamespace(stdout='Result=success\nExecMainStatus=0\n')
            def write(path, data, mode=0o644):
                path.write_bytes(data if isinstance(data, bytes) else data.encode())
            from contextlib import ExitStack
            with ExitStack() as stack:
                for name, value in {'BASE': base, 'UNITS': units, 'CONFIG_FILE': config}.items():
                    stack.enter_context(patch.object(installer, name, value))
                stack.enter_context(patch.object(installer.os, 'geteuid', return_value=0))
                stack.enter_context(patch.object(installer, 'safe'))
                stack.enter_context(patch.object(installer, 'identity', return_value=account))
                stack.enter_context(patch.object(installer.pwd, 'getpwnam', return_value=account))
                stack.enter_context(patch.object(installer, 'write', side_effect=write))
                stack.enter_context(patch.object(installer, 'run', side_effect=command))
                stack.enter_context(patch.object(installer, 'service_exists', return_value=True))
                stack.enter_context(patch.object(installer, 'active', side_effect=lambda cmd: cmd[0] == 'old'))
                stack.enter_context(patch.object(installer, 'old_command', side_effect=lambda *args: ['old', *args]))
                with self.assertRaisesRegex(RuntimeError, 'synthetic verification fault'):
                    installer.install(SimpleNamespace(rollback=False, telegram_timeout=0))
            self.assertEqual(prior.read_text(), 'previous reviewed unit')
            self.assertFalse((units / installer.NAMES[1]).exists())
            self.assertFalse((base / 'hermes-rollback').exists())
            self.assertIn(['old', 'start'], events)
            self.assertNotIn(['old', 'stop'], events)
            self.assertNotIn(['old', 'disable'], events)
            self.assertEqual(json.loads((base / 'hermes-evidence.json').read_text())['status'],
                             'ROLLED_BACK_NOT_NEW_HERMES_READY')


if __name__ == '__main__':
    unittest.main()
