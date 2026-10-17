import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


class ProcessTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancellation_while_spawn_returns_reaps_child(self):
        from duorbi.agy_backend import AgyBackend
        from a2acode.backends.base import RunRequest
        created = asyncio.Event()
        release = asyncio.Event()
        real_create = asyncio.create_subprocess_exec
        children = []

        async def delayed_create(*args, **kwargs):
            proc = await real_create(*args, **kwargs)
            children.append(proc)
            created.set()
            await release.wait()
            return proc

        backend = AgyBackend('.', command=[sys.executable, '-c', 'import time; time.sleep(60)'])
        class Sink:
            async def emit(self, event):
                raise AssertionError('cancelled turn published output')
        task = asyncio.create_task(backend.drive(Sink(), RunRequest('hello', context_id='ctx')))
        try:
            with patch('asyncio.create_subprocess_exec', side_effect=delayed_create):
                await created.wait()
                task.cancel()
                await asyncio.sleep(.01)
                task.cancel()
                release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            self.assertIsNotNone(children[0].returncode, 'spawn cancellation leaked the child')
            self.assertFalse(backend.active)
        finally:
            release.set()
            for proc in children:
                if proc.returncode is None:
                    proc.kill()
                    await proc.wait()

    async def test_runner_passes_literal_argv_after_launch_token(self):
        literal = '한글 😀 $(touch X) & echo "quote"'
        proc = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'duorbi.windows_runner', sys.executable, '-c',
            'import json,sys;print(json.dumps(sys.argv[1:]))', literal,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate(b'duorbi-launch-v1\n')
        self.assertEqual(proc.returncode, 0, stderr)
        self.assertEqual(json.loads(stdout), [literal])

    async def test_runner_does_not_execute_target_without_launch_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'launched'
            code = f'from pathlib import Path; Path({str(marker)!r}).touch()'
            proc = await asyncio.create_subprocess_exec(
                sys.executable, '-m', 'duorbi.windows_runner', sys.executable, '-c', code,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE)
            await proc.communicate(b'')
            self.assertFalse(marker.exists())
            self.assertNotEqual(proc.returncode, 0)


@unittest.skipUnless(os.name == 'nt', 'native Windows Job Object tests')
class WindowsProcessTests(unittest.IsolatedAsyncioTestCase):
    async def test_job_handle_is_non_inheritable_and_close_kills_descendants(self):
        from duorbi.processes import spawn_owned_process, stop_windows_process
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'pid'
            code = ('import pathlib,subprocess,sys; '
                    'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]); '
                    'pathlib.Path(sys.argv[1]).write_text(str(p.pid))')
            proc = await spawn_owned_process([sys.executable, '-c', code, str(marker)], cwd=tmp)
            try:
                self.assertFalse(os.get_handle_inheritable(proc.job.handle))
                for _ in range(300):
                    if marker.exists():
                        break
                    await asyncio.sleep(.01)
                self.assertTrue(marker.exists())
                # Wait for both direct target and Python runner to exit. The
                # orphan still holds stdout open; cleanup must use the Job.
                for _ in range(500):
                    if proc.returncode is not None:
                        break
                    await asyncio.sleep(.01)
                self.assertEqual(proc.returncode, 0)
                await stop_windows_process(proc)
                self.assertTrue(proc.job.closed)
                from duorbi.win32_jobs import process_is_running
                self.assertFalse(process_is_running(int(marker.read_text())))
            finally:
                await stop_windows_process(proc)

    async def test_project_module_cannot_replace_launch_gate(self):
        from duorbi.processes import spawn_owned_process, stop_windows_process
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / 'duorbi'
            package.mkdir()
            (package / '__init__.py').write_text('')
            marker = Path(tmp) / 'hijacked'
            (package / 'windows_runner.py').write_text(
                f'from pathlib import Path; Path({str(marker)!r}).touch()')
            proc = await spawn_owned_process(
                [sys.executable, '-c', 'print("native gate")'], cwd=tmp)
            try:
                stdout, stderr = await proc.communicate()
                self.assertEqual(proc.returncode, 0, stderr)
                self.assertEqual(stdout.strip(), b'native gate')
                self.assertFalse(marker.exists())
            finally:
                await stop_windows_process(proc)

    async def test_job_assignment_failure_never_launches_target(self):
        from duorbi.processes import spawn_owned_process
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'launched'
            code = f'from pathlib import Path; Path({str(marker)!r}).touch()'
            with patch('duorbi.win32_jobs.Job.assign', side_effect=OSError('assignment failed')):
                with self.assertRaisesRegex(OSError, 'assignment failed'):
                    await spawn_owned_process([sys.executable, '-c', code], cwd=tmp)
            self.assertFalse(marker.exists())

    async def test_cancellation_before_spawn_returns_never_launches_cli(self):
        from duorbi.processes import spawn_owned_process
        from duorbi.win32_jobs import Job
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'launched'
            code = f'from pathlib import Path; Path({str(marker)!r}).touch()'
            created, release = asyncio.Event(), asyncio.Event()
            real_create = asyncio.create_subprocess_exec
            jobs = []
            real_job = Job
            def record_job():
                job = real_job()
                jobs.append(job)
                return job
            async def delayed_create(*args, **kwargs):
                proc = await real_create(*args, **kwargs)
                created.set()
                await release.wait()
                return proc
            with patch('asyncio.create_subprocess_exec', side_effect=delayed_create), \
                    patch('duorbi.win32_jobs.Job', side_effect=record_job):
                task = asyncio.create_task(spawn_owned_process([sys.executable, '-c', code], cwd=tmp))
                await created.wait()
                task.cancel()
                await asyncio.sleep(.01)
                task.cancel()
                release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            self.assertFalse(marker.exists())
            self.assertTrue(jobs[0].closed)

    async def test_cancellation_during_handshake_closes_job_before_wait(self):
        from duorbi.processes import spawn_owned_process
        from duorbi.win32_jobs import Job
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'pid'
            code = ('import os,pathlib,time; '
                    'pathlib.Path(__import__("sys").argv[1]).write_text(str(os.getpid())); '
                    'time.sleep(60)')
            created = []
            drain_started = asyncio.Event()
            real_create = asyncio.create_subprocess_exec
            async def delayed_create(*args, **kwargs):
                proc = await real_create(*args, **kwargs)
                async def drain():
                    # The token is already written: wait until the target exists
                    # before suspending the handshake and cancelling its owner.
                    for _ in range(500):
                        if marker.exists():
                            break
                        await asyncio.sleep(.01)
                    drain_started.set()
                    await asyncio.Future()
                proc.stdin.drain = drain
                created.append(proc)
                return proc
            jobs = []
            def record_job():
                job = Job()
                jobs.append(job)
                return job
            with patch('asyncio.create_subprocess_exec', side_effect=delayed_create), \
                    patch('duorbi.win32_jobs.Job', side_effect=record_job):
                task = asyncio.create_task(spawn_owned_process(
                    [sys.executable, '-c', code, str(marker)], cwd=tmp))
                await asyncio.wait_for(drain_started.wait(), 10)
                self.assertTrue(marker.exists())
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, 3)
            self.assertTrue(jobs[0].closed)
            self.assertIsNotNone(created[0].returncode)
            from duorbi.win32_jobs import process_is_running
            self.assertFalse(process_is_running(int(marker.read_text())))

    async def test_repeated_cancellation_cannot_interrupt_job_cleanup(self):
        from duorbi.agy_backend import stop_process
        from duorbi.processes import spawn_owned_process
        proc = await spawn_owned_process(
            [sys.executable, '-c', 'import time;time.sleep(60)'], cwd='.')
        release = asyncio.Event()
        entered = asyncio.Event()
        actual_count = proc.job.active_count
        def slow_count():
            entered.set()
            return actual_count() if release.is_set() else 1
        try:
            with patch.object(proc.job, 'active_count', side_effect=slow_count):
                task = asyncio.create_task(stop_process(proc))
                await entered.wait()
                task.cancel()
                await asyncio.sleep(.02)
                task.cancel()
                await asyncio.sleep(.02)
                self.assertFalse(task.done())
                release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            self.assertTrue(proc.job.closed)
            self.assertIsNotNone(proc.returncode)
        finally:
            release.set()
            await stop_process(proc)

    async def test_success_kills_descendant_before_publishing_result(self):
        from a2acode.backends.base import Result, RunRequest
        from duorbi.agy_backend import AgyBackend
        from duorbi.win32_jobs import process_is_running
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'child.pid'
            code = ('import json,pathlib,subprocess,sys; '
                    'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"],'
                    'stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); '
                    'pathlib.Path(sys.argv[1]).write_text(str(p.pid)); '
                    'print(json.dumps({"status":"SUCCESS","conversation_id":"s1","response":"ok"}))')
            events = []
            test = self
            class Sink:
                async def emit(self, event):
                    test.assertFalse(process_is_running(int(marker.read_text())))
                    events.append(event)
            await AgyBackend(tmp, command=[sys.executable, '-c', code, str(marker)]).drive(
                Sink(), RunRequest('hello', context_id='ctx'))
            self.assertTrue(any(isinstance(event, Result) for event in events))

    async def test_job_cleanup_failure_closes_handle_and_publishes_no_result(self):
        from a2acode.backends.base import RunRequest
        from duorbi.agy_backend import AgyBackend
        from duorbi.win32_jobs import Job
        jobs, events = [], []
        def failing_job():
            job = Job()
            jobs.append(job)
            job.terminate = lambda: (_ for _ in ()).throw(OSError('termination failed'))
            return job
        class Sink:
            async def emit(self, event):
                events.append(event)
        code = 'import json;print(json.dumps({"status":"SUCCESS","conversation_id":"s1","response":"ok"}))'
        backend = AgyBackend('.', command=[sys.executable, '-c', code])
        with patch('duorbi.win32_jobs.Job', side_effect=failing_job):
            with self.assertRaisesRegex(OSError, 'termination failed'):
                await backend.drive(Sink(), RunRequest('hello', context_id='ctx'))
        self.assertFalse(events)
        self.assertTrue(jobs[0].closed)
        self.assertFalse(backend.active)

    async def test_parent_death_closes_only_job_handle_and_kills_runner_and_child(self):
        from duorbi.win32_jobs import process_is_running
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / 'pids.json'
            # This independent owner is forcibly terminated, bypassing finally.
            # A child-inherited Job handle would keep both processes alive.
            code = r'''import asyncio,json,pathlib,sys
from duorbi.processes import spawn_owned_process
async def main():
    child = "import os,pathlib,time;pathlib.Path(__import__('sys').argv[1]).write_text(str(os.getpid()));time.sleep(60)"
    target = str(pathlib.Path(sys.argv[1]).with_suffix('.target'))
    proc = await spawn_owned_process([sys.executable,'-c',child,target],cwd='.')
    while not pathlib.Path(target).exists():
        await asyncio.sleep(.01)
    pathlib.Path(sys.argv[1]).write_text(json.dumps([proc.pid,int(pathlib.Path(target).read_text())]))
    await asyncio.sleep(60)
asyncio.run(main())
'''
            owner = await asyncio.create_subprocess_exec(
                sys.executable, '-c', code, str(pidfile),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
            try:
                for _ in range(500):
                    if pidfile.exists() or owner.returncode is not None:
                        break
                    await asyncio.sleep(.01)
                if not pidfile.exists():
                    owner.kill()
                    _, error = await owner.communicate()
                    self.fail(f'owner failed to launch fixture: {error!r}')
                pids = json.loads(pidfile.read_text())
                self.assertTrue(all(process_is_running(pid) for pid in pids))
                owner.kill()
                await owner.wait()
                for _ in range(500):
                    if not any(process_is_running(pid) for pid in pids):
                        break
                    await asyncio.sleep(.01)
                self.assertFalse(any(process_is_running(pid) for pid in pids))
            finally:
                if owner.returncode is None:
                    owner.kill()
                    await owner.wait()

    def test_default_is_native_executable_and_wrappers_are_rejected(self):
        from duorbi.agy_backend import AgyBackend
        with patch('duorbi.agy_backend.shutil.which', return_value='C:/agy.exe') as which:
            self.assertEqual(AgyBackend('.').command, ['C:/agy.exe'])
            which.assert_called_once_with('agy.exe')
        for name in ['agy.cmd', 'AGY.BAT', 'agy.cmd ', 'agy', 'agy.bat.']:
            with self.assertRaisesRegex(ValueError, 'native.*executable'):
                AgyBackend('.', command=[name])


if __name__ == '__main__':
    unittest.main()
