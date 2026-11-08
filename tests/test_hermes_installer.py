"""Local only: synthetic credentials/upstreams; never use VPS credentials or Telegram."""
import ast
import base64
from contextlib import ExitStack
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ops/hermes'))
import broker
import oauth
import protocol
import transport


def load(name):
    spec = importlib.util.spec_from_file_location('isolated_' + name, ROOT / 'ops/hermes' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


installer = load('install')


def jwt(expires=None, account='synthetic-account', residency=None):
    auth = {'chatgpt_account_id': account}
    if residency:
        auth['chatgpt_data_residency'] = residency
    body = json.dumps({'exp': expires or time.time() + 3600, 'https://api.openai.com/auth': auth}).encode()
    return 'test.' + base64.urlsafe_b64encode(body).decode().rstrip('=') + '.not-a-real-token'


def auth_store(token=None):
    return {'version': 1, 'providers': {'openai-codex': {
        'tokens': {'access_token': token or jwt(), 'refresh_token': 'synthetic-refresh'}}}}


class OAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'auth.json'
        self.path.write_text(json.dumps(auth_store()))
        self.path.chmod(0o600)

    def test_valid_canonical_token_no_refresh(self):
        with patch.object(oauth, 'request') as network:
            self.assertEqual(oauth.access_token(self.path), json.loads(self.path.read_text())['providers']['openai-codex']['tokens']['access_token'])
            network.assert_not_called()

    def test_refresh_updates_canonical_and_singleton_aliases_only(self):
        old = jwt(time.time() - 1)
        store = auth_store(old)
        store['providers']['other-provider'] = {'secret': 'keep'}
        store['credential_pool'] = {'openai-codex': [
            {'source': 'device_code', 'access_token': old},
            {'source': 'manual:device_code', 'access_token': old},
            {'source': 'manual:device_code', 'access_token': 'independent'}]}
        self.path.write_text(json.dumps(store))
        new = jwt()
        with patch.object(oauth, 'request', return_value={'access_token': new, 'refresh_token': 'rotated'}) as request:
            self.assertEqual(oauth.access_token(self.path), new)
        args, kwargs = request.call_args
        self.assertEqual(args[:2], ('auth.openai.com', '/oauth/token'))
        self.assertIn(b'grant_type=refresh_token', args[2])
        self.assertTrue(kwargs['form'])
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved['providers']['openai-codex']['tokens']['refresh_token'], 'rotated')
        self.assertEqual(saved['providers']['other-provider'], {'secret': 'keep'})
        self.assertEqual([row['access_token'] for row in saved['credential_pool']['openai-codex']], [new, new, 'independent'])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.path.parent / '.100print-refresh-pending').exists())
        with patch.object(oauth, 'request') as request:
            oauth.access_token(self.path)
            request.assert_not_called()

    def test_lost_refresh_response_persists_no_replay_intent(self):
        self.path.write_text(json.dumps(auth_store(jwt(time.time() - 1))))
        before = self.path.read_bytes()
        with patch.object(oauth, 'request', side_effect=TimeoutError()):
            with self.assertRaises(TimeoutError):
                oauth.access_token(self.path)
        self.assertEqual(self.path.read_bytes(), before)
        with patch.object(oauth, 'request') as request:
            with self.assertRaisesRegex(RuntimeError, 'unknown'):
                oauth.access_token(self.path)
            request.assert_not_called()

    def test_incompatible_store_symlink_and_public_permissions_refused(self):
        for store in ({'version': 2}, {'version': 1, 'providers': {}}, auth_store('opaque')):
            with self.assertRaises(ValueError):
                oauth.tokens_from(store)
        link = self.path.parent / 'link.json'
        link.symlink_to(self.path)
        with self.assertRaises(ValueError), oauth.locked(link):
            pass
        self.path.chmod(0o644)
        with self.assertRaises(ValueError):
            oauth.access_token(self.path)

    def test_auth_lock_is_same_native_path_and_preserves_owner(self):
        with oauth.locked(self.path):
            lock = self.path.with_suffix('.lock')
            self.assertTrue(lock.is_file())
            self.assertEqual(lock.stat().st_uid, self.path.stat().st_uid)
            import fcntl
            with lock.open('a+') as another:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(another, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_committed_rotation_recovers_crash_before_intent_removal(self):
        old = auth_store(jwt(time.time() - 1))
        pending = self.path.parent / '.100print-refresh-pending'
        pending.write_text(json.dumps({'generation': oauth.generation(oauth.tokens_from(old))}))
        pending.chmod(0o600)
        self.path.write_text(json.dumps(auth_store(jwt())))
        with patch.object(oauth, 'request') as network:
            self.assertFalse(oauth.refresh_pending(self.path))
            oauth.access_token(self.path)
            network.assert_not_called()
        self.assertFalse(pending.exists())

    def test_known_refresh_429_does_not_leave_ambiguous_intent(self):
        self.path.write_text(json.dumps(auth_store(jwt(time.time() - 1))))
        with patch.object(oauth, 'request', side_effect=protocol.UpstreamHTTPError(429)):
            with self.assertRaises(protocol.UpstreamHTTPError):
                oauth.access_token(self.path)
        self.assertFalse((self.path.parent / '.100print-refresh-pending').exists())

    def test_concurrent_refreshes_share_one_rotating_grant(self):
        from concurrent.futures import ThreadPoolExecutor
        self.path.write_text(json.dumps(auth_store(jwt(time.time() - 1))))
        fresh = jwt()
        def upstream(*args, **kwargs):
            time.sleep(0.1)
            return {'access_token': fresh, 'refresh_token': 'rotated-once'}
        with patch.object(oauth, 'request', side_effect=upstream) as request:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: oauth.access_token(self.path), range(2)))
            self.assertEqual(results, [fresh, fresh])
            self.assertEqual(request.call_count, 1)


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in {'STATE': Path(self.temp.name), 'CONFIG': {'model': 'fixed-model'},
                            'KEY': b'synthetic-signing-key', 'AGENT_UID': 1234, 'TRANSPORT_UID': 1235}.items():
            self.stack.enter_context(patch.object(broker, name, value))
        with broker.db() as connection:
            connection.execute('CREATE TABLE usage(id TEXT PRIMARY KEY, attempts INTEGER, successful INTEGER)')
        self.identifier = 'a' * 32
        self.expires = int(time.time()) + 300
        self.grant = {'id': self.identifier, 'expires': self.expires,
                      'capability': protocol.capability(broker.KEY, self.identifier, self.expires)}

    def request(self, **kwargs):
        return dict(self.grant, op='model', body={'messages': [{'role': 'user', 'content': 'synthetic'}]}, **kwargs)

    def test_chat_and_tool_history_translate_to_responses_without_execution(self):
        payload = broker.responses_payload({'messages': [
            {'role': 'system', 'content': 'policy'}, {'role': 'user', 'content': 'write a file'},
            {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'call1', 'type': 'function',
                'function': {'name': 'terminal', 'arguments': '{"command":"touch result"}'}}]},
            {'role': 'tool', 'tool_call_id': 'call1', 'content': 'done'}],
            'tools': [{'type': 'function', 'function': {'name': 'terminal', 'parameters': {'type': 'object'}}}],
            'base_url': 'http://private', 'model': 'attacker', 'previous_response_id': 'foreign',
            'store': True}, 'fixed')
        self.assertEqual(payload['model'], 'fixed')
        self.assertFalse(payload['store'])
        self.assertTrue(payload['stream'])
        self.assertEqual(payload['instructions'], 'policy')
        self.assertEqual(payload['input'][-1]['type'], 'function_call_output')
        self.assertEqual(payload['tools'][0]['type'], 'function')
        self.assertNotIn('base_url', payload)
        self.assertNotIn('previous_response_id', payload)

    def test_hosted_tools_media_and_wrong_roles_are_refused(self):
        for body in ({'messages': [{'role': 'user', 'content': [{'image_url': 'http://metadata'}]}]},
                     {'messages': [{'role': 'user', 'content': 'x'}], 'tools': [{'type': 'shell'}]},
                     {'messages': [{'role': 'user', 'content': 'x'}], 'tools': [{'type': 'web_search'}]},
                     {'messages': [{'role': 'function', 'content': 'x'}]}, {'stream': True}):
            with self.subTest(body=body), self.assertRaises(ValueError):
                broker.responses_payload(body, 'fixed')

    def test_live_adapter_uses_only_fixed_oauth_endpoint_and_inert_tools(self):
        upstream = {'id': 'r1', 'output': [{'type': 'function_call', 'call_id': 'call1',
                    'name': 'terminal', 'arguments': '{"command":"touch result"}'}],
                    'usage': {'input_tokens': 2, 'output_tokens': 3, 'total_tokens': 5}}
        with patch.object(broker, 'access_token', return_value=jwt(residency='eu')), \
             patch.object(broker, 'request', return_value=upstream) as network:
            answer = broker.operation(self.request(), 1234)
        self.assertEqual(network.call_args.args[:2], ('chatgpt.com', '/backend-api/codex/responses'))
        headers = network.call_args.kwargs['headers']
        self.assertEqual(headers['ChatGPT-Account-Id'], 'synthetic-account')
        self.assertEqual(headers['x-openai-internal-codex-residency'], 'eu')
        self.assertEqual(answer['body']['choices'][0]['finish_reason'], 'tool_calls')
        receipt = broker.operation(dict(self.grant, op='receipt'), 1235)
        self.assertEqual(receipt, {'attempts': 1, 'successful': 1})

    def test_wrong_peers_capabilities_expiry_and_host_commands_denied(self):
        with patch.object(broker, 'request') as network:
            cases = [(self.request(), 1235), (dict(self.request(), capability='forged'), 1234),
                     (dict(self.request(), expires=1), 1234), (dict(self.grant, op='shell', command='id'), 1234),
                     (dict(self.grant, op='receipt'), 1234)]
            for message, uid in cases:
                with self.subTest(message=message), self.assertRaises(ValueError):
                    broker.operation(message, uid)
            network.assert_not_called()

    def test_failed_calls_also_consume_persistent_budget(self):
        with patch.object(broker, 'access_token', return_value=jwt()), \
             patch.object(broker, 'request', side_effect=RuntimeError('synthetic upstream failure')) as request:
            for _ in range(12):
                with self.assertRaises(RuntimeError):
                    broker.operation(self.request(), 1234)
            with self.assertRaisesRegex(ValueError, 'budget'):
                broker.operation(self.request(), 1234)
            self.assertEqual(request.call_count, 12)
        self.assertEqual(broker.operation(dict(self.grant, op='receipt'), 0), {'attempts': 12, 'successful': 0})

    def test_broker_has_no_host_execution_or_telegram_dependencies(self):
        tree = ast.parse((ROOT / 'ops/hermes/broker.py').read_text())
        imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        imported |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        self.assertTrue(imported.isdisjoint({'subprocess', 'runpy', 'hermes_cli', 'transport'}))
        self.assertNotIn('telegram', (ROOT / 'ops/hermes/broker.py').read_text().lower().split('import json')[1])


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in {'STATE': Path(self.temp.name), 'CONFIG': {'telegram_token': '123:synthetic', 'owner': '42'},
                            'KEY': b'synthetic-key'}.items():
            self.stack.enter_context(patch.object(transport, name, value))
        transport.initialize()

    def test_single_claim_and_no_worker_asserted_fake_success(self):
        identifier = transport.submit('first')
        transport.submit('second')
        task = transport.operation({'op': 'next'})
        self.assertEqual(task['id'], identifier)
        protocol.authorized(transport.KEY, task)
        self.assertEqual(transport.operation({'op': 'next'}), {})
        with patch.object(transport, 'rpc', return_value={'attempts': 0, 'successful': 0}):
            transport.operation({'op': 'result', 'id': identifier, 'ok': True, 'api_calls': 100, 'text': 'fake'})
        with transport.db() as connection:
            self.assertEqual(connection.execute('SELECT state FROM jobs WHERE id=?', (identifier,)).fetchone()[0], 'failed')

    def test_probe_submission_is_root_only_and_worker_cannot_enqueue(self):
        with patch.object(transport, 'AGENT_UID', 1234):
            for uid in (1234, 1235):
                with self.assertRaises(ValueError):
                    transport.handle_message({'op': 'submit', 'prompt': 'synthetic'}, uid)
            identifier = transport.handle_message({'op': 'submit', 'prompt': 'synthetic'}, 0)['id']
            self.assertEqual(transport.operation({'op': 'next'})['id'], identifier)

    def test_restart_no_replay_and_schema_upgrade(self):
        identifier = transport.submit('do not repeat')
        transport.operation({'op': 'next'})
        transport.initialize()
        self.assertEqual(transport.operation({'op': 'next'}), {})
        with transport.db() as connection:
            self.assertEqual(connection.execute('SELECT state FROM jobs WHERE id=?', (identifier,)).fetchone()[0], 'failed')

    def test_wrong_bot_webhook_and_config_refused(self):
        for username, webhook in (('otherbot', ''), ('hundredprintbot', 'https://webhook')):
            with patch.object(transport, 'telegram', side_effect=[{'ok': True, 'result': {'username': username}},
                 {'ok': True, 'result': {'url': webhook}}]) as api:
                with self.assertRaises(RuntimeError):
                    transport.preflight()
                self.assertEqual([call.args[0] for call in api.call_args_list], ['getMe', 'getWebhookInfo'])
        with self.assertRaises(ValueError):
            transport.validate(dict(transport.CONFIG, model_api_key='forbidden'))
        with self.assertRaises(ValueError):
            transport.telegram('exec', {})

    def test_private_owner_only_and_durable_offset(self):
        updates = []
        for index, (user, chat, kind) in enumerate(((42, 42, 'private'), (99, 42, 'private'),
                                                   (42, -42, 'group'), (42, 99, 'private'))):
            updates.append({'update_id': index, 'message': {'from': {'id': user}, 'chat': {'id': chat, 'type': kind},
                'date': time.time(), 'text': '/hermes synthetic'}})
        with patch.object(transport, 'telegram', return_value={'ok': True, 'result': updates}):
            transport.poll_once()
        with transport.db() as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM jobs').fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT value FROM metadata WHERE key='offset'").fetchone()[0], '4')

    def test_ambiguous_send_never_replayed_or_counted_as_acceptance(self):
        identifier = transport.submit('synthetic', True)
        with transport.db() as connection:
            connection.execute("UPDATE jobs SET state='done',answer='reply',model_calls=1 WHERE id=?", (identifier,))
        with patch.object(transport, 'telegram', side_effect=[{'ok': True, 'result': []}, TimeoutError()]):
            with self.assertRaises(TimeoutError):
                transport.poll_once()
        with patch.object(transport, 'telegram', return_value={'ok': True, 'result': []}) as api:
            transport.poll_once()
            self.assertEqual([call.args[0] for call in api.call_args_list], ['getUpdates'])
        with transport.db() as connection:
            self.assertIsNone(connection.execute("SELECT value FROM metadata WHERE key='telegram_e2e'").fetchone())


class ProtocolTests(unittest.TestCase):
    def test_dns_private_ipv4_ipv6_mixed_and_rebinding_pinned(self):
        for address in ('127.0.0.1', '10.1.2.3', '169.254.169.254', '::1', 'fc00::1'):
            with self.subTest(address=address), patch.object(protocol.socket, 'getaddrinfo', return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 6, '', (address, 443))]), patch.object(protocol.socket, 'socket') as connect:
                with self.assertRaisesRegex(RuntimeError, 'nonpublic'):
                    protocol.PublicHTTPS('chatgpt.com').connect()
                connect.assert_not_called()
        with patch.object(protocol.socket, 'getaddrinfo', return_value=[
             (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443))]) as dns, \
             patch.object(protocol.socket, 'socket') as socket_factory:
            connection = protocol.PublicHTTPS('chatgpt.com')
            with patch.object(connection._context, 'wrap_socket') as tls:
                connection.connect()
                socket_factory.return_value.connect.assert_called_once_with(('8.8.8.8', 443))
                tls.assert_called_once_with(socket_factory.return_value, server_hostname='chatgpt.com')
                dns.assert_called_once()

    def test_sse_requires_completed_and_refuses_failed_truncated_large_or_redirect(self):
        response = SimpleNamespace(status=200)
        completed = {'type': 'response.completed', 'response': {'id': 'r1', 'status': 'completed', 'output': []}}
        streams = [(b'data: ' + json.dumps(completed).encode() + b'\n\n', True),
                   (b'data: {"type":"response.failed"}\n\n', False), (b'data: [DONE]\n\n', False),
                   (b'data: {}\n\n', False)]
        for raw, success in streams:
            response.readline = io.BytesIO(raw).readline
            with patch.object(protocol, 'PublicHTTPS') as https:
                https.return_value.getresponse.return_value = response
                if success:
                    self.assertEqual(protocol.request('chatgpt.com', '/backend-api/codex/responses', {}, event_stream=True)['id'], 'r1')
                else:
                    with self.assertRaises(RuntimeError):
                        protocol.request('chatgpt.com', '/backend-api/codex/responses', {}, event_stream=True)
        response.status = 302
        with patch.object(protocol, 'PublicHTTPS') as https:
            https.return_value.getresponse.return_value = response
            with self.assertRaisesRegex(RuntimeError, 'HTTP 302'):
                protocol.request('chatgpt.com', '/backend-api/codex/responses', {})
        with self.assertRaises(ValueError):
            protocol.request('localhost', '/shell', {})

    def test_worker_sse_completion_adapter(self):
        runtime = load('runtime')
        body = {'id': 'test', 'model': 'fixed', 'created': 1, 'choices': [{'index': 0, 'message': {
                'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'c1', 'type': 'function',
                'function': {'name': 'terminal', 'arguments': '{}'}}]}, 'finish_reason': 'tool_calls'}],
                'usage': {'total_tokens': 12}}
        frames = runtime.completion_data(body, True).decode().strip().split('\n\n')
        self.assertEqual(frames[-1], 'data: [DONE]')
        chunks = [json.loads(frame[6:]) for frame in frames[:-1]]
        self.assertEqual(chunks[0]['choices'][0]['delta']['tool_calls'][0]['index'], 0)
        self.assertEqual(chunks[-1]['usage']['total_tokens'], 12)


class InstallerTests(unittest.TestCase):
    def test_units_separate_oauth_telegram_and_untrusted_tools(self):
        units = installer.units(Path('/var/lib/100print-isolation/hermes-releases/test'))
        model, telegram, agent = [units[name] for name in installer.NAMES]
        self.assertIn('User=ceoorch', model)
        self.assertIn('RootDirectory=/var/lib/100print-isolation/rootfs', model)
        self.assertIn(':/oauth', model)
        self.assertNotIn('telegram-config', model)
        self.assertNotIn('model-config', telegram)
        for setting in ('User=ceo-w2p-agent', 'PrivateNetwork=yes', 'NoNewPrivileges=yes',
                        'ProtectSystem=strict', 'KillMode=control-group', 'RestrictNamespaces=yes'):
            self.assertIn(setting, agent)
        for forbidden in ('LoadCredential', ':/oauth', '/opt/', '/home/', 'docker.sock', 'capability.key'):
            self.assertNotIn(forbidden, agent)

    def test_export_never_copies_credentials_or_links(self):
        exporter = load('prepare-runtime')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / 'source', root / 'destination'
            source.mkdir(); destination.mkdir()
            for name in ('.env', 'auth.json', 'unsafe.pth'):
                (source / name).write_text('synthetic secret')
            (source / 'module.py').write_text('value=1')
            exporter.copy_tree(source, destination)
            self.assertEqual([p.name for p in destination.iterdir()], ['module.py'])
            (source / 'escape').symlink_to(root)
            with self.assertRaises(RuntimeError):
                exporter.copy_tree(source, destination)

    def test_provider_contract_inspects_ast_without_executing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'hermes_cli').mkdir()
            constants = ('AUTH_STORE_VERSION=1\nCODEX_OAUTH_CLIENT_ID=' + repr(oauth.CLIENT_ID) +
                         '\nCODEX_OAUTH_TOKEN_URL=' + repr(oauth.TOKEN_URL) +
                         '\nDEFAULT_CODEX_BASE_URL=' + repr(oauth.BASE_URL) + '\n')
            (root / 'hermes_cli/auth.py').write_text(constants + 'raise RuntimeError("must not execute")\n' +
                'def _read_codex_tokens(): pass\ndef _save_codex_tokens(): pass\n' +
                'def _auth_store_lock(): return path.with_suffix(".lock")\n')
            self.assertIn('hermes_cli/auth.py', installer.provider_contract(root))
            (root / 'hermes_cli/auth.py').write_text(constants.replace('AUTH_STORE_VERSION=1', 'AUTH_STORE_VERSION=9'))
            with self.assertRaises(RuntimeError):
                installer.provider_contract(root)

    def test_existing_oauth_and_telegram_are_discovered_without_manual_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / 'ai-team/runtime/hermes-home'
            home.mkdir(parents=True)
            config = root / 'config'; config.mkdir()
            values = {home / '.env': 'TELEGRAM_BOT_TOKEN=123:synthetic\nTELEGRAM_ALLOWED_USERS=42\n',
                      home / 'auth.json': json.dumps(auth_store()),
                      home / 'config.yaml': 'model:\n  default: gpt-synthetic\n  provider: openai-codex\n  openai_runtime: codex_app_server\n',
                      config / 'telegram.env': 'CEO_TELEGRAM_TOKEN=123:synthetic\nCEO_TELEGRAM_ALLOWED_CHATS=42\n'}
            for path, value in values.items():
                path.write_text(value); path.chmod(0o600)
            with patch.object(installer, 'LEGACY', root), patch.object(installer, 'LEGACY_HOME', home):
                credentials, model = installer.discover(os.getuid())
            self.assertEqual(credentials, {'telegram_token': '123:synthetic', 'owner': '42'})
            self.assertEqual(model, 'gpt-synthetic')
            for path, value in values.items():
                self.assertEqual(path.read_text(), value)  # no runtime/token switch

    def test_probe_handles_permission_denied_as_inaccessible(self):
        probe = load('probe')
        for error in (PermissionError('synthetic denied'), FileNotFoundError('synthetic absent')):
            with patch.object(Path, 'stat', side_effect=error):
                self.assertFalse(probe.accessible('/run/credentials/synthetic'))
        with patch.object(Path, 'stat', return_value=object()):
            self.assertTrue(probe.accessible('/synthetic-visible'))

    def test_policy_symlinks_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            link = Path(directory) / 'link'
            link.symlink_to('/etc/passwd')
            with self.assertRaises(RuntimeError):
                installer.safe(link)

    def test_restore_stops_new_pollers_before_old_and_keeps_latest_auth(self):
        self.rollback_case(False)

    def test_unknown_refresh_outcome_never_restarts_old_or_replays_backup(self):
        self.rollback_case(True)

    def rollback_case(self, unknown):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            units = root / 'units'; units.mkdir()
            home = root / 'home'; home.mkdir()
            (home / 'auth.json').write_text('latest rotated canonical credentials')
            if unknown:
                (home / '.100print-refresh-pending').touch()
            snapshot = root / 'snapshot'
            previous = {'files': {}, 'services': {}, 'old': {'ActiveState': 'active', 'UnitFileState': 'enabled'}}
            for name in installer.NAMES:
                (units / name).write_text('new')
                previous['services'][name] = {'text': None, 'ActiveState': 'inactive', 'UnitFileState': 'disabled'}
            snapshot.write_text(json.dumps(previous))
            (root / 'telegram-enabled').write_text('active')
            events = []
            with patch.object(installer, 'BASE', root), patch.object(installer, 'UNITS', units), \
                 patch.object(installer, 'LEGACY_HOME', home), patch.object(installer, 'safe'), \
                 patch.object(installer.oauth, 'refresh_pending', return_value=unknown), \
                 patch.object(installer, 'service_state', return_value={'LoadState': 'loaded'}), \
                 patch.object(installer, 'stop_service', side_effect=lambda name: events.append(['stop', name])), \
                 patch.object(installer, 'stop_old', side_effect=lambda: events.append(['old', 'stop'])), \
                 patch.object(installer, 'write', side_effect=lambda path, data, *args: path.write_text(data)), \
                 patch.object(installer, 'run', side_effect=lambda cmd: events.append(cmd)), \
                 patch.object(installer, 'old_command', side_effect=lambda *args: ['old', *args]):
                if unknown:
                    with self.assertRaisesRegex(RuntimeError, 'outcome unknown'):
                        installer.restore(snapshot)
                else:
                    installer.restore(snapshot)
            self.assertEqual((home / 'auth.json').read_text(), 'latest rotated canonical credentials')
            self.assertFalse((root / 'telegram-enabled').exists())
            if unknown:
                self.assertTrue(snapshot.exists())
                self.assertNotIn(['old', 'start'], events)
            else:
                self.assertFalse(snapshot.exists())
                self.assertEqual(events[-1], ['old', 'start'])
                self.assertLess(events.index(['stop', installer.NAMES[1]]), events.index(['old', 'start']))
                self.assertFalse(any(units.iterdir()))

    def test_sources_compile(self):
        for path in (ROOT / 'ops/hermes').glob('*.py'):
            compile(path.read_text(), str(path), 'exec')


class InstallerTransactionTests(unittest.TestCase):
    """Fault injection only; these are not systemd/VPS acceptance tests."""
    def test_faults_at_each_stage_automatically_restore_previous_transport(self):
        for failure in ('verify', 'model-start', 'transport-start', 'probe', 'inference',
                        'file-check', 'telegram', 'enable'):
            with self.subTest(failure=failure):
                self.transaction(failure)

    def test_success_and_repeated_install_preserve_one_consumer_and_rollback(self):
        self.transaction(None, repeat=True)

    def transaction(self, failure, repeat=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / 'isolation'; base.mkdir()
            (base / 'rootfs').mkdir()
            (base / 'hermes-runtime').mkdir()
            units = root / 'units'; units.mkdir()
            home = root / 'legacy-home'; home.mkdir()
            auth_path = home / 'auth.json'
            auth_path.write_text(json.dumps(auth_store())); auth_path.chmod(0o600)
            (home / '.env').write_text('synthetic fixture')
            (home / 'config.yaml').write_text('synthetic fixture')
            state_dir = root / 'transport-state'; state_dir.mkdir()
            credentials = {'owner': '42', 'telegram_token': '123:synthetic'}
            account = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid())
            new_states = {name: {'LoadState': 'not-found', 'ActiveState': 'inactive', 'UnitFileState': '',
                                'MainPID': '0'} for name in installer.NAMES}
            old_state = {'LoadState': 'loaded', 'ActiveState': 'active', 'UnitFileState': 'enabled', 'MainPID': '900'}
            events = []
            faulted = False
            def fail(stage):
                nonlocal faulted
                if failure == stage and not faulted:
                    faulted = True
                    raise RuntimeError('injected ' + stage)
            def current(name=None, old=False):
                if old:
                    return dict(old_state)
                if name == installer.SYSTEM_OLD:
                    return {'LoadState': 'not-found', 'ActiveState': 'inactive', 'UnitFileState': ''}
                return dict(new_states[name])
            def command(argv, **kwargs):
                events.append(argv)
                if argv[0] == 'systemd-analyze':
                    fail('verify')
                if argv[0] == 'worker':
                    fail('file-check' if '-c' in argv else 'probe')
                if argv[0] == 'systemctl':
                    op = argv[1]
                    if op == 'start':
                        if argv[2] == installer.NAMES[0]: fail('model-start')
                        if argv[2] == installer.NAMES[1]: fail('transport-start')
                    if op == 'enable': fail('enable')
                    for name in argv[2:]:
                        if name in new_states:
                            if op == 'start':
                                new_states[name].update(LoadState='loaded', ActiveState='active', MainPID='123')
                                if name == installer.NAMES[1]: transport.initialize()
                            if op == 'stop': new_states[name].update(ActiveState='inactive', MainPID='0')
                            if op == 'enable': new_states[name]['UnitFileState'] = 'enabled'
                            if op == 'disable': new_states[name]['UnitFileState'] = 'disabled'
                if argv[0] == 'old':
                    if argv[1] == 'stop': old_state['ActiveState'] = 'inactive'
                    if argv[1] == 'start':
                        self.assertNotEqual(new_states[installer.NAMES[1]]['ActiveState'], 'active')
                        old_state['ActiveState'] = 'active'
                    if argv[1] == 'disable': old_state['UnitFileState'] = 'disabled'
                    if argv[1] == 'enable': old_state['UnitFileState'] = 'enabled'
                return SimpleNamespace(stdout='')
            def no_other():
                events.append(['no-other-pollers'])
                self.assertEqual(old_state['ActiveState'], 'inactive')
                self.assertFalse((base / 'telegram-enabled').exists())
            def inference(identifier):
                fail('inference')
                # Simulated durable canonical refresh; rollback must never restore backup.
                auth_path.write_text(json.dumps(auth_store(jwt(account='refreshed-fixture'))))
            def accept(*args):
                fail('telegram')
                self.assertEqual(old_state['ActiveState'], 'inactive')
                self.assertTrue((base / 'telegram-enabled').is_file())
            with ExitStack() as stack:
                for name, value in {'BASE': base, 'UNITS': units, 'CONFIG': base / 'hermes-config',
                                    'CONTROL': base / 'hermes-control', 'LEGACY_HOME': home,
                                    'TRANSPORT_STATE': state_dir}.items():
                    stack.enter_context(patch.object(installer, name, value))
                stack.enter_context(patch.object(transport, 'STATE', state_dir))
                stack.enter_context(patch.object(installer, 'safe'))
                stack.enter_context(patch.object(installer, 'identity', return_value=account))
                stack.enter_context(patch.object(installer.pwd, 'getpwnam', return_value=account))
                stack.enter_context(patch.object(installer.os, 'getgrouplist', return_value=[account.pw_gid]))
                stack.enter_context(patch.object(installer, 'discover', return_value=(credentials, 'fixed-model')))
                stack.enter_context(patch.object(installer, 'provider_contract', return_value={'synthetic': 'hash'}))
                stack.enter_context(patch.object(installer.shutil, 'which', return_value='/synthetic'))
                stack.enter_context(patch.object(installer, 'state', return_value={'Result': 'success', 'ExecMainStatus': '0'}))
                stack.enter_context(patch.object(installer, 'service_state', side_effect=current))
                stack.enter_context(patch.object(installer, 'old_command', side_effect=lambda *args: ['old', *args]))
                stack.enter_context(patch.object(installer, 'run', side_effect=command))
                stack.enter_context(patch.object(installer, 'wait_socket'))
                stack.enter_context(patch.object(installer, 'verify_bpf'))
                stack.enter_context(patch.object(installer, 'worker_command', side_effect=lambda args: ['worker', *args]))
                stack.enter_context(patch.object(installer, 'submit_probe', side_effect=lambda prompt: transport.submit(prompt)))
                stack.enter_context(patch.object(installer, 'await_job', side_effect=inference))
                stack.enter_context(patch.object(installer, 'assert_no_other_pollers', side_effect=no_other))
                stack.enter_context(patch.object(installer, 'await_telegram', side_effect=accept))
                stack.enter_context(patch('builtins.print'))
                arguments = SimpleNamespace(telegram_timeout=0)
                if failure:
                    with self.assertRaisesRegex(RuntimeError, 'injected'):
                        installer.install(arguments)
                    self.assertTrue(faulted)
                    self.assertEqual(old_state['ActiveState'], 'active')
                    self.assertEqual(old_state['UnitFileState'], 'enabled')
                    self.assertTrue(all(value['ActiveState'] != 'active' for value in new_states.values()))
                    self.assertFalse((base / 'telegram-enabled').exists())
                else:
                    installer.install(arguments)
                    self.assertEqual(old_state['ActiveState'], 'inactive')
                    self.assertEqual(old_state['UnitFileState'], 'disabled')
                    self.assertTrue((base / 'telegram-enabled').exists())
                    evidence = json.loads((base / 'hermes-evidence.json').read_text())
                    self.assertFalse(evidence['legacy_containment_removed'])
                    if repeat:
                        # Tests of an upgrade's reversible transaction, not local E2E proof.
                        installer.install(arguments)
                        rollback = base / 'hermes-last-rollback.json'
                        snapshot = base / 'hermes-rollback'
                        snapshot.write_bytes(rollback.read_bytes())
                        installer.restore(snapshot)
                        self.assertEqual(old_state['ActiveState'], 'inactive')
                        self.assertTrue(all(value['ActiveState'] == 'active' for value in new_states.values()))
                self.assertFalse((base / 'hermes-rollback').exists())
                if failure in (None, 'file-check', 'telegram', 'enable'):
                    self.assertEqual(oauth.claims(json.loads(auth_path.read_text())['providers']['openai-codex']['tokens']['access_token'])['https://api.openai.com/auth']['chatgpt_account_id'], 'refreshed-fixture')


if __name__ == '__main__':
    unittest.main()
