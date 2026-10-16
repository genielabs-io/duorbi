import asyncio
import json
import os
import signal
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from a2acode.backends.base import Result, RunRequest, TextDelta
from duorbi.agy_backend import AgyBackend, parse_result, stop_process


class Collector:
    def __init__(self):
        self.events = []

    async def emit(self, event):
        self.events.append(event)


class AgyTests(unittest.IsolatedAsyncioTestCase):
    def test_only_success_with_matching_conversation_is_accepted(self):
        result = {'status': 'SUCCESS', 'conversation_id': 'session1', 'response': 'ok'}
        self.assertEqual(parse_result(json.dumps(result), 0, 'session1'), result)
        for state in ['ERROR', 'WAITING', 'RUNNING', 'CANCELED', 'INTERRUPTED', 'INVALID']:
            with self.assertRaises(RuntimeError):
                parse_result(json.dumps({**result, 'status': state}), 0, None)
        for output, code, resume in [('noise', 0, None), (json.dumps(result), 1, None),
                                     (json.dumps(result), 0, 'different'), ('{}', 0, None)]:
            with self.assertRaises(RuntimeError):
                parse_result(output, code, resume)

    async def test_resume_is_explicit_and_prompt_is_not_shell_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / 'fake.py'
            script.write_text('''import json, sys
a=sys.argv
assert '--continue' not in a
assert '--dangerously-skip-permissions' not in a
assert a[a.index('--conversation')+1] == 'session1'
assert a[a.index('--mode')+1] == 'plan'
print(json.dumps({'status':'SUCCESS','conversation_id':'session1',
                  'response':a[a.index('-p')+1]}))
''')
            backend = AgyBackend(tmp, command=[sys.executable, str(script)])
            sink = Collector()
            prompt = 'literal $(touch SHOULD_NOT_EXIST) `pwd`'
            await backend.drive(sink, RunRequest(prompt, context_id='ctx', resume='session1'))
            self.assertEqual([e.text for e in sink.events if isinstance(e, TextDelta)], [prompt])
            self.assertEqual([e.session_id for e in sink.events if isinstance(e, Result)], ['session1'])
            self.assertFalse((Path(tmp) / 'SHOULD_NOT_EXIST').exists())

    async def test_timeout_terminates_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = AgyBackend(tmp, command=[sys.executable, '-c', 'import time; time.sleep(60)'], timeout=.1, exit_grace=.05)
            with self.assertRaises(TimeoutError):
                await backend.drive(Collector(), RunRequest('test', context_id='ctx'))
            self.assertFalse(backend.active)

    async def test_cleanup_failure_releases_context_and_does_not_publish_success(self):
        code = 'import json; print(json.dumps({"status":"SUCCESS","conversation_id":"session1","response":"ok"}))'
        backend = AgyBackend('.', command=[sys.executable, '-c', code])
        sink = Collector()

        async def failing_cleanup(proc):
            await stop_process(proc)
            raise PermissionError('simulated cleanup failure')

        with patch('duorbi.agy_backend.stop_process', side_effect=failing_cleanup):
            with self.assertRaisesRegex(PermissionError, 'simulated cleanup'):
                await backend.drive(sink, RunRequest('hello', context_id='ctx'))
        self.assertFalse(backend.active)
        self.assertFalse(any(isinstance(e, Result) for e in sink.events))
        await backend.drive(sink, RunRequest('again', context_id='ctx'))
        self.assertEqual([e.text for e in sink.events if isinstance(e, TextDelta)], ['ok'])

    async def test_cli_gets_time_to_flush_its_own_timeout_result(self):
        code = ('import json,time; time.sleep(.2); '
                'print(json.dumps({"status":"ERROR","error":"deadline exceeded"}))')
        backend = AgyBackend('.', command=[sys.executable, '-c', code], timeout=.1, exit_grace=1)
        with self.assertRaisesRegex(RuntimeError, 'deadline exceeded'):
            await backend.drive(Collector(), RunRequest('hello', context_id='ctx'))
        self.assertFalse(backend.active)

    async def test_failed_cli_reports_category_without_exposing_raw_secrets(self):
        code = ('import sys; '
                'print("authentication required Bearer PRIVATE_TOKEN api_key=PRIVATE_KEY",file=sys.stderr); '
                'sys.exit(1)')
        backend = AgyBackend('.', command=[sys.executable, '-c', code])
        with self.assertRaises(RuntimeError) as caught:
            await backend.drive(Collector(), RunRequest('hello', context_id='ctx'))
        detail = str(caught.exception)
        self.assertIn('authentication required', detail)
        self.assertNotIn('PRIVATE_TOKEN', detail)
        self.assertNotIn('PRIVATE_KEY', detail)

    def test_json_errors_are_classified_without_echoing_unknown_payloads(self):
        for error, expected in [('rate limit exceeded PRIVATE_TOKEN', 'rate limit'),
                                ('unknown option PRIVATE_KEY', 'invalid CLI arguments'),
                                ('PRIVATE_UNCLASSIFIED', 'unclassified CLI error')]:
            with self.assertRaises(RuntimeError) as caught:
                parse_result(json.dumps({'status':'ERROR', 'error':error}), 0, None)
            self.assertIn(expected, str(caught.exception))
            self.assertNotIn('PRIVATE', str(caught.exception))

    async def test_same_context_parallel_turn_is_rejected(self):
        backend = AgyBackend('.', command=['unused'])
        backend.active.add('ctx')
        with self.assertRaisesRegex(RuntimeError, 'already running'):
            await backend.drive(Collector(), RunRequest('test', context_id='ctx'))

    async def test_cleanup_removes_descendant_after_leader_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / 'child.pid'
            code = ('import subprocess,sys,pathlib; '
                    'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
                    'pathlib.Path(sys.argv[1]).write_text(str(p.pid))')
            proc = await asyncio.create_subprocess_exec(
                sys.executable, '-c', code, str(pidfile),
                stdout=asyncio.subprocess.PIPE, start_new_session=True)
            try:
                for _ in range(100):
                    if proc.returncode is not None and pidfile.exists():
                        break
                    await asyncio.sleep(.01)
                self.assertEqual(proc.returncode, 0)
                child = int(pidfile.read_text())
                os.kill(child, 0)
                await stop_process(proc)
                for _ in range(100):
                    try:
                        os.kill(child, 0)
                    except ProcessLookupError:
                        break
                    await asyncio.sleep(.01)
                else:
                    self.fail('descendant survived cleanup')
            finally:
                await stop_process(proc)

    async def test_orphaned_descendant_can_finish_sigterm_handler(self):
        with tempfile.TemporaryDirectory() as tmp:
            ready, done = Path(tmp) / 'ready', Path(tmp) / 'done'
            child = Path(tmp) / 'child.py'
            child.write_text('''import signal,time,sys
from pathlib import Path
def finish(*args):
    time.sleep(.2)
    Path(sys.argv[2]).write_text('clean shutdown')
    raise SystemExit(0)
signal.signal(signal.SIGTERM, finish)
Path(sys.argv[1]).write_text('ready')
while True: time.sleep(.05)
''')
            parent = ('import subprocess,sys; '
                      'subprocess.Popen([sys.executable,*sys.argv[1:]])')
            proc = await asyncio.create_subprocess_exec(
                sys.executable, '-c', parent, str(child), str(ready), str(done),
                stdout=asyncio.subprocess.PIPE, start_new_session=True)
            try:
                for _ in range(200):
                    if ready.exists() and proc.returncode is not None:
                        break
                    await asyncio.sleep(.01)
                self.assertTrue(ready.exists())
                self.assertEqual(proc.returncode, 0)
                await stop_process(proc)
                self.assertTrue(done.exists(), 'child was killed before graceful cleanup finished')
            finally:
                await stop_process(proc)

    async def test_uncooperative_process_is_killed_after_grace(self):
        with tempfile.TemporaryDirectory() as tmp:
            ready = Path(tmp) / 'ready'
            code = ('import signal,sys,time,pathlib; '
                    'signal.signal(signal.SIGTERM,signal.SIG_IGN); '
                    'pathlib.Path(sys.argv[1]).write_text("ready"); time.sleep(60)')
            proc = await asyncio.create_subprocess_exec(
                sys.executable, '-c', code, str(ready), start_new_session=True)
            try:
                for _ in range(200):
                    if ready.exists():
                        break
                    await asyncio.sleep(.01)
                self.assertTrue(ready.exists())
                await asyncio.wait_for(stop_process(proc, grace=.1), 2)
                self.assertEqual(proc.returncode, -signal.SIGKILL)
            finally:
                await stop_process(proc, grace=.1)

    async def test_cancellation_terminates_process_and_releases_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            ready = Path(tmp) / 'ready'
            code = ('import os,time,pathlib; '
                    f'pathlib.Path({str(ready)!r}).write_text(str(os.getpid())); time.sleep(60)')
            backend = AgyBackend(tmp, command=[sys.executable, '-c', code])
            task = asyncio.create_task(backend.drive(Collector(), RunRequest('hello', context_id='ctx')))
            try:
                for _ in range(200):
                    if ready.exists():
                        break
                    await asyncio.sleep(.01)
                self.assertTrue(ready.exists())
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                self.assertFalse(backend.active)
                with self.assertRaises(ProcessLookupError):
                    os.kill(int(ready.read_text()), 0)
            finally:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

    async def test_cancellation_during_cleanup_still_kills_and_reaps_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            ready = Path(tmp) / 'ready'
            code = ('import signal,sys,time,pathlib; '
                    'signal.signal(signal.SIGTERM,signal.SIG_IGN); '
                    'pathlib.Path(sys.argv[1]).write_text("ready"); time.sleep(60)')
            proc = await asyncio.create_subprocess_exec(
                sys.executable, '-c', code, str(ready), start_new_session=True)
            try:
                for _ in range(200):
                    if ready.exists():
                        break
                    await asyncio.sleep(.01)
                self.assertTrue(ready.exists())
                cleanup = asyncio.create_task(stop_process(proc))
                await asyncio.sleep(.1)
                cleanup.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await cleanup
                self.assertEqual(proc.returncode, -signal.SIGKILL)
            finally:
                await stop_process(proc, grace=.1)


if __name__ == '__main__':
    unittest.main()
