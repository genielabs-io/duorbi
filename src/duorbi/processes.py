"""Contain subprocess trees before launching CLI code on either platform."""
import asyncio
import os
import sys


async def finish_cleanup(awaitable):
    """Finish ownership cleanup even when a caller cancels more than once."""
    task = asyncio.ensure_future(awaitable)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    result = task.result()  # A cleanup failure must prevent publishing success.
    if cancelled:
        raise asyncio.CancelledError
    return result


class OwnedWindowsProcess:
    def __init__(self, process, job):
        self.process, self.job = process, job

    def __getattr__(self, name):
        return getattr(self.process, name)


async def stop_windows_process(proc):
    if proc.job.closed:
        return
    try:
        proc.job.terminate()
        deadline = asyncio.get_running_loop().time() + 5
        while proc.job.active_count():
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError('Windows process tree did not terminate')
            await asyncio.sleep(.01)
    finally:
        # Even a failed termination/query must release the last owner handle.
        proc.job.close()
        await asyncio.wait_for(proc.wait(), 5)


async def spawn_owned_process(command, *, cwd):
    windows = os.name == 'nt'
    job = None
    if windows:
        from .win32_jobs import Job
        if not str(command[0]).lower().endswith('.exe'):
            raise ValueError('Windows requires a native .exe executable; .cmd/.bat wrappers are unsupported')
        job = Job()
        # Isolated mode excludes the target project's cwd/PYTHONPATH, so it
        # cannot shadow the trusted launch gate before Job assignment.
        argv = [sys.executable, '-I', '-m', 'duorbi.windows_runner', *command]
        options = {'stdin': asyncio.subprocess.PIPE}
    else:
        argv = command
        options = {'stdin': asyncio.subprocess.DEVNULL, 'start_new_session': True}
    creation = asyncio.create_task(asyncio.create_subprocess_exec(
        *argv, cwd=cwd, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, **options))
    proc = None
    try:
        # asyncio may create the OS process before delivering the Process object.
        # Keep creation alive until ownership can be recovered on cancellation.
        try:
            proc = await asyncio.shield(creation)
        except asyncio.CancelledError:
            async def recover():
                nonlocal proc
                proc = await creation
            await finish_cleanup(recover())
            raise
        if windows:
            owned = OwnedWindowsProcess(proc, job)
            job.assign(proc.pid)
            from .windows_runner import LAUNCH_TOKEN
            proc.stdin.write(LAUNCH_TOKEN)
            await proc.stdin.drain()
            proc.stdin.close()
            return owned
        return proc
    except BaseException:
        async def abandon():
            try:
                if proc is not None:
                    if windows:
                        # No token is sent on failed assignment or cancelled spawn.
                        if proc.stdin is not None:
                            proc.stdin.close()
                        if proc.returncode is None:
                            proc.kill()
                        # Close before waiting: an assigned descendant can keep
                        # runner pipes open even after the runner is dead.
                        job.close()
                        await asyncio.wait_for(proc.wait(), 5)
                    else:
                        from .agy_backend import stop_process
                        await stop_process(proc)
            finally:
                if job is not None:
                    job.close()
        await finish_cleanup(abandon())
        raise
