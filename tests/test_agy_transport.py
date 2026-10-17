"""Real A2A HTTP with a deterministic local CLI fixture, including restart."""
from contextlib import closing
import hashlib
import json
import sqlite3
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

from fake_cli import install_fake_agy

class PersistentTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory(prefix='duorbi-fake-cli-')
        cls.addClassCleanup(cls.fixture.cleanup)
        cls.bindir = install_fake_agy(cls.fixture.name)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / 'project 한글 🙂 with spaces'
        self.project.mkdir()
        self.state = self.root / 'state'
        self.env = {**os.environ, 'PATH': str(self.bindir) + os.pathsep + os.environ['PATH']}
        resolved = Path(shutil.which('agy', path=self.env['PATH'])).resolve()
        self.assertEqual(resolved.parent, self.bindir.resolve(), 'refusing to use a real agy')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        self.server = None
        self.log = (self.root / 'server.log').open('w', encoding='utf-8')
        self.addCleanup(self.log.close)
        self.addCleanup(self.stop)

    def args(self, command):
        return [sys.executable, '-m', 'duorbi',
                command, '--project', str(self.project), '--port', str(self.port),
                '--state-dir', str(self.state)]

    def start(self):
        self.server = subprocess.Popen(self.args('serve'), env=self.env, cwd=self.root, stdout=self.log, stderr=self.log)
        for _ in range(100):
            if self.server.poll() is not None:
                raise AssertionError((self.root / 'server.log').read_text(encoding='utf-8'))
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{self.port}/.well-known/agent-card.json', timeout=1):
                    return
            except OSError:
                time.sleep(.05)
        self.fail('Server did not start')

    def stop(self):
        if self.server is not None:
            self.server.terminate()
            try:
                self.server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.server.kill()
                self.server.wait(timeout=5)
            self.server = None

    def run_cli(self, command, *extra, input_text=None):
        proc = subprocess.run(self.args(command) + list(extra), env=self.env, cwd=self.root,
                              text=True, encoding='utf-8', capture_output=True, timeout=30, input=input_text)
        rows = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertTrue(rows, proc.stderr)
        return proc.returncode, rows[-1]

    def test_continue_after_server_restart_and_explicit_new(self):
        self.start()
        code, first = self.run_cli('call', 'remember-FIRST', '--new')
        self.assertEqual(code, 0, first)
        self.stop()
        self.start()
        code, second = self.run_cli('call', 'recall', '--continue')
        self.assertEqual(code, 0, second)
        self.assertEqual(second['response'], 'remember-FIRST')
        self.assertEqual(second['context_id'], first['context_id'])
        self.assertEqual(second['agent_session_id'], first['agent_session_id'])
        code, third = self.run_cli('call', 'SECOND', '--new')
        self.assertEqual(code, 0, third)
        self.assertNotEqual(third['context_id'], first['context_id'])
        code, listed = self.run_cli('sessions')
        self.assertEqual(code, 0, listed)
        self.assertEqual(len(listed['sessions']), 2)
        code, resumed = self.run_cli('call', 'recall', '--context', first['context_id'])
        self.assertEqual(code, 0, resumed)
        self.assertEqual(resumed['response'], 'remember-FIRST')

    def test_unicode_stdin_and_literal_arguments_survive_restart(self):
        self.start()
        prompt = '기억해 줘 🙂 "quotes" & echo SHOULD_NOT_RUN | %PATH% $(pwd) ' + 'C:\\with spaces\\'
        code, first = self.run_cli('call', '-', '--new', input_text=prompt)
        self.assertEqual(code, 0, first)
        self.assertEqual(first['response'], prompt)
        self.stop()
        self.start()
        code, resumed = self.run_cli('call', 'recall', '--context', first['context_id'])
        self.assertEqual(code, 0, resumed)
        self.assertEqual(resumed['response'], prompt)
        self.assertFalse((self.project / 'SHOULD_NOT_RUN').exists())

    def test_missing_history_and_unknown_context_fail_without_model(self):
        for flags in [('--continue',), ('--context', 'unknown')]:
            code, result = self.run_cli('call', 'hello', *flags)
            self.assertEqual(code, 2, result)
            self.assertIn('saved', result['error'].lower())
        self.assertFalse((self.project / '.fake-agy.json').exists())

    def test_wrong_state_directory_is_rejected_before_starting_conversation(self):
        self.start()
        code, result = self.run_cli('call', 'hello', '--state-dir', str(self.root / 'wrong-state'))
        self.assertEqual(code, 2, result)
        self.assertIn('different', result['error'])
        self.assertFalse((self.project / '.fake-agy.json').exists())

    def test_import_then_restore_and_reject_cross_project_import(self):
        (self.project / '.fake-agy.json').write_text(json.dumps({'known-agy': 'imported memory'}), encoding='utf-8')
        code, result = self.run_cli('import-session', '--context', 'known-context', '--conversation', 'known-agy')
        self.assertEqual(code, 0, result)
        other = self.root / 'other-project'
        other.mkdir()
        code, rejected = self.run_cli('import-session', '--context', 'other-context', '--conversation', 'known-agy', '--project', str(other))
        self.assertEqual(code, 2, rejected)
        self.start()
        code, result = self.run_cli('call', 'recall', '--continue')
        self.assertEqual(code, 0, result)
        self.assertEqual(result['response'], 'imported memory')

    def test_constructed_legacy_database_preserves_identity_and_resume_after_restart(self):
        # Build the legacy v1 schema independently, without opening any user state.
        self.state.mkdir()
        project = str(self.project.resolve())
        with closing(sqlite3.connect(self.state / 'conversations.sqlite3')) as db, db:
            db.execute('CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            db.execute("INSERT INTO metadata VALUES ('identity', 'fixture-store-id')")
            db.execute('CREATE TABLE conversations (project TEXT NOT NULL, context_id TEXT NOT NULL, '
                       'conversation_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, '
                       'updated_at TEXT NOT NULL, last_used_ns INTEGER NOT NULL, '
                       'PRIMARY KEY (project, context_id))')
            db.execute('INSERT INTO conversations VALUES (?, ?, ?, ?, ?, ?)',
                       (project, 'legacy-context', 'legacy-agy', '2026-01-01', '2026-01-01', 1))
            db.execute('PRAGMA user_version=1')
        (self.project / '.fake-agy.json').write_text(json.dumps({'legacy-agy': 'legacy memory'}), encoding='utf-8')
        code, info = self.run_cli('info')
        self.assertEqual(code, 0, info)
        digest = hashlib.sha256(('antigravity:' + project).encode()).hexdigest()
        identity = hashlib.sha256(f'{self.state.resolve()}:fixture-store-id'.encode()).hexdigest()[:16]
        self.assertEqual(info['name'], f'Antigravity A2A {digest[:16]} store {identity}')
        default = subprocess.run([sys.executable, '-m', 'duorbi', 'info', '--project', project,
                                  '--state-dir', str(self.state)], env=self.env, cwd=self.root,
                                 text=True, encoding='utf-8', capture_output=True, timeout=30)
        self.assertEqual(default.returncode, 0, default.stderr)
        self.assertEqual(json.loads(default.stdout)['port'], 20000 + int(digest[:8], 16) % 20000)
        for selector in [('--continue',), ('--context', 'legacy-context')]:
            self.start()
            code, resumed = self.run_cli('call', 'recall', *selector)
            self.assertEqual(code, 0, resumed)
            self.assertEqual(resumed['context_id'], 'legacy-context')
            self.assertEqual(resumed['agent_session_id'], 'legacy-agy')
            self.assertEqual(resumed['response'], 'legacy memory')
            self.stop()

    def test_deleted_agent_history_fails_and_keeps_saved_mapping(self):
        self.start()
        code, first = self.run_cli('call', 'remember')
        self.assertEqual(code, 0, first)
        self.stop()
        (self.project / '.fake-agy.json').unlink()
        self.start()
        code, failed = self.run_cli('call', 'recall', '--continue')
        self.assertEqual(code, 2, failed)
        self.assertEqual(failed['state'], 'failed')
        code, listed = self.run_cli('sessions')
        self.assertEqual(code, 0, listed)
        self.assertEqual(listed['sessions'][0]['conversation_id'], first['agent_session_id'])

    def test_advertised_jsonrpc_route_executes_text_with_only_declared_capabilities(self):
        from duorbi.agy_request import encode_request
        self.start()
        with self.rest('/.well-known/agent-card.json') as response:
            card = json.load(response)
        self.assertEqual(card['capabilities'], {'streaming': True})
        self.assertEqual(card['defaultInputModes'], ['text/plain'])
        self.assertEqual(card['defaultOutputModes'], ['text/plain'])
        self.assertEqual([skill['id'] for skill in card['skills']], ['text-review'])
        self.assertEqual({interface['protocolBinding'] for interface in card['supportedInterfaces']},
                         {'HTTP+JSON', 'JSONRPC'})
        with self.rest('/', {'jsonrpc': '2.0', 'id': 'fixture', 'method': 'SendMessage',
                             'params': {'message': {'messageId': 'fixture', 'role': 'ROLE_USER',
                                                    'parts': [{'text': encode_request('exact')}]} }}) as response:
            result = json.load(response)
        task = result['result']['task']
        self.assertEqual(task['status']['state'], 'TASK_STATE_COMPLETED')
        self.assertEqual(task['status']['message']['parts'][0]['text'], 'exact')
        self.assertIn('agent_session_id', task['status']['message']['metadata'])

    def rest(self, path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(f'http://127.0.0.1:{self.port}' + path,
                                         data=data, headers={'Content-Type': 'application/json', 'A2A-Version': '1.0'})
        return urllib.request.urlopen(request, timeout=10)

    def stream(self, context='ctx', parts=None):
        from duorbi.agy_request import encode_request
        return self.rest('/message:stream', {'message': {
            'messageId': 'fixture-message', 'role': 'ROLE_USER', 'contextId': context,
            'parts': parts or [{'text': encode_request('hello')}]}})

    def next_event(self, stream):
        while True:
            line = stream.readline().decode()
            if not line:
                self.fail('SSE stream ended without expected event')
            if line.startswith('data: '):
                return json.loads(line[6:])

    def wait_for_cli(self):
        marker = self.project / '.fake-pids.json'
        for _ in range(200):
            if marker.exists():
                return json.loads(marker.read_text())
            time.sleep(.02)
        self.fail('fake CLI did not start')

    def assert_processes_stopped(self, pids):
        def alive(pid):
            if os.name == 'nt':
                from duorbi.win32_jobs import process_is_running
                return process_is_running(pid)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return False
            return True
        for _ in range(200):
            if not any(alive(pid) for pid in pids.values() if pid):
                return
            time.sleep(.02)
        self.fail(f'fake CLI process survived: {pids}')

    def test_http_cancel_waits_for_owned_tree_and_releases_context_lock(self):
        (self.project / '.fake-control.json').write_text(json.dumps({'wait': True, 'child': True}))
        self.start()
        with self.stream() as stream:
            first = self.next_event(stream)
            task_id = first['task']['id']
            pids = self.wait_for_cli()
            with self.rest(f'/tasks/{task_id}:cancel', {}) as response:
                canceled = json.load(response)
            self.assertEqual(canceled['status']['state'], 'TASK_STATE_CANCELED')
            self.assert_processes_stopped(pids)
            self.assertFalse((self.project / '.fake-agy.json').exists())
            code, listed = self.run_cli('sessions')
            self.assertEqual(listed['sessions'], [])
            from duorbi.session_store import SessionStore
            with SessionStore(self.state).claim(self.project, 'ctx'):
                pass
            with self.rest(f'/tasks/{task_id}') as response:
                self.assertEqual(json.load(response)['status']['state'], 'TASK_STATE_CANCELED')
        (self.project / '.fake-control.json').unlink()
        code, resumed = self.run_cli('call', 'after canceled')
        self.assertEqual(code, 0, resumed)

    @unittest.skipIf(os.name == 'nt', 'Windows terminate is owner death; ASGI lifespan is covered separately')
    def test_sigterm_with_open_stream_bounds_drain_and_cleans_running_tree(self):
        (self.project / '.fake-control.json').write_text(json.dumps({'wait': True, 'child': True}))
        self.start()
        with self.stream() as stream:
            self.next_event(stream)
            pids = self.wait_for_cli()
            started = time.monotonic()
            self.stop()
            self.assertLess(time.monotonic() - started, 8)
            self.assert_processes_stopped(pids)
        from duorbi.session_store import SessionStore
        store = SessionStore(self.state)
        self.assertEqual(store.list(self.project), [])
        with store.claim(self.project, 'ctx'):
            pass

    def test_http_concurrent_turn_in_same_context_fails_before_another_cli_launch(self):
        (self.project / '.fake-control.json').write_text(json.dumps({'wait': True, 'child': True}))
        self.start()
        with self.stream(context='shared-context') as first_stream:
            first_id = self.next_event(first_stream)['task']['id']
            pids = self.wait_for_cli()
            with self.stream(context='shared-context') as second_stream:
                second_id = self.next_event(second_stream)['task']['id']
                self.assertNotEqual(first_id, second_id)
                while True:
                    event = self.next_event(second_stream)
                    if 'statusUpdate' in event:
                        state = event['statusUpdate']['status']['state']
                        if state in {'TASK_STATE_COMPLETED', 'TASK_STATE_FAILED'}:
                            self.assertEqual(state, 'TASK_STATE_FAILED')
                            break
            self.assertEqual((self.project / '.fake-invocations').read_text().splitlines(),
                             [str(pids['owner'])])
            code, listed = self.run_cli('sessions')
            self.assertEqual(listed['sessions'], [])
            (self.project / '.fake-release').touch()
            while True:
                event = self.next_event(first_stream)
                if 'statusUpdate' in event and event['statusUpdate']['status']['state'] == 'TASK_STATE_COMPLETED':
                    break
        self.assert_processes_stopped(pids)
        from duorbi.session_store import SessionStore
        store = SessionStore(self.state)
        self.assertEqual(len(store.list(self.project)), 1)
        with store.claim(self.project, 'shared-context'):
            pass

    def test_stream_disconnect_continues_and_saves_after_cleanup(self):
        answer = '  exact 한글 🙂\nfinal\n'
        (self.project / '.fake-control.json').write_text(json.dumps({'wait': True, 'child': True, 'response': answer}))
        self.start()
        with self.stream() as stream:
            task_id = self.next_event(stream)['task']['id']
            pids = self.wait_for_cli()
        # Closing the response detaches the subscriber; the SDK producer persists.
        (self.project / '.fake-release').touch()
        for _ in range(200):
            with self.rest(f'/tasks/{task_id}') as response:
                task = json.load(response)
            if task['status']['state'] == 'TASK_STATE_COMPLETED':
                break
            time.sleep(.02)
        else:
            self.fail(task)
        self.assertEqual(task['status']['message']['parts'][0]['text'], answer)
        self.assertEqual(task['status']['message']['metadata']['agent_session_id'],
                         json.loads((self.project / '.fake-agy.json').read_text()).popitem()[0])
        self.assert_processes_stopped(pids)
        code, listed = self.run_cli('sessions')
        self.assertEqual(len(listed['sessions']), 1)

    def test_server_shutdown_cleans_disconnected_running_cli_tree(self):
        (self.project / '.fake-control.json').write_text(json.dumps({'wait': True, 'child': True}))
        self.start()
        with self.stream() as stream:
            self.next_event(stream)
            pids = self.wait_for_cli()
        self.stop()
        self.assert_processes_stopped(pids)
        from duorbi.session_store import SessionStore
        store = SessionStore(self.state)
        self.assertEqual(store.list(self.project), [])
        with store.claim(self.project, 'ctx'):
            pass

    def test_mixed_parts_fail_over_http_without_launching_cli(self):
        from duorbi.agy_request import encode_request
        self.start()
        with self.stream(parts=[{'text': encode_request('hello')},
                                {'raw': 'YXR0YWNobWVudA==', 'mediaType': 'application/octet-stream'}]) as stream:
            while True:
                event = self.next_event(stream)
                if 'statusUpdate' in event and event['statusUpdate']['status']['state'] == 'TASK_STATE_FAILED':
                    break
        self.assertFalse((self.project / '.fake-agy.json').exists())
        code, listed = self.run_cli('sessions')
        self.assertEqual(listed['sessions'], [])

    def test_cli_failure_returns_failed_without_saved_mapping_or_artifact(self):
        (self.project / '.fake-control.json').write_text(json.dumps({'status': 'WAITING'}))
        self.start()
        code, failed = self.run_cli('call', 'hello')
        self.assertEqual(code, 2, failed)
        self.assertEqual(failed['state'], 'failed')
        self.assertEqual(failed['response'], '')
        self.assertNotIn('agent_session_id', failed)
        code, listed = self.run_cli('sessions')
        self.assertEqual(listed['sessions'], [])


if __name__ == '__main__':
    unittest.main()
