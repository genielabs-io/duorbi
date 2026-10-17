"""Antigravity headless JSON adapter for a2acode's A2A server.

The CLI conversation ID is resumed explicitly; this is not an ACP backend.
Tool approval round trips are not supported by this adapter.
"""
import asyncio
import json
import os
import signal
import shutil
from dataclasses import replace

from a2acode.backends.base import Result, TextDelta

from .processes import (OwnedWindowsProcess, finish_cleanup, spawn_owned_process,
                        stop_windows_process)


def diagnostic_hint(*messages):
    """Classify diagnostics without copying arbitrary CLI output into logs."""
    text = '\n'.join(m.decode('utf-8', errors='replace') if isinstance(m, bytes)
                     else m for m in messages if isinstance(m, (str, bytes))).lower()
    categories = [
        ('authentication required', ('authentication', 'unauthenticated', 'sign in', 'login', 'invalid api key', 'expired token')),
        ('permission or approval required', ('permission denied', 'approval required', 'consent')),
        ('rate limit or quota exceeded', ('rate limit', 'quota', 'resource_exhausted')),
        ('deadline exceeded', ('deadline', 'timed out', 'timeout')),
        ('connection failure', ('connection refused', 'connection reset', 'network error', 'dns')),
        ('invalid CLI arguments', ('unknown option', 'unknown flag', 'unrecognized argument', 'invalid argument')),
    ]
    for label, markers in categories:
        if any(marker in text for marker in markers):
            return label
    return 'unclassified CLI error; raw diagnostics omitted'


def parse_result(output, returncode, resume, stderr=b''):
    try:
        value = json.loads(output)
    except (ValueError, UnicodeError) as exc:
        detail = diagnostic_hint(stderr)
        raise RuntimeError(f'agy did not return a JSON result (exit {returncode}); {detail}') from exc
    detail = diagnostic_hint(stderr, value.get('error') if isinstance(value, dict) else None)
    if returncode:
        raise RuntimeError(f'agy exited with code {returncode}; {detail}')
    if not isinstance(value, dict):
        raise RuntimeError('agy returned a non-object result')
    state = value.get('status')
    if state != 'SUCCESS':
        # Do not turn WAITING or partial output into a completed A2A task.
        known = state if isinstance(state, str) and state in {
            'ERROR', 'WAITING', 'RUNNING', 'CANCELED', 'INTERRUPTED', 'INVALID'} else 'UNKNOWN'
        raise RuntimeError(f'agy status {known}; {detail}. '
                           'This adapter cannot relay tool approvals.')
    conversation = value.get('conversation_id')
    if not isinstance(conversation, str) or not conversation:
        raise RuntimeError('agy omitted conversation_id')
    if resume and conversation != resume:
        raise RuntimeError('agy resumed a different conversation')
    if not isinstance(value.get('response'), str):
        raise RuntimeError('agy omitted response text')
    return value


async def signal_group(pid, sig):
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        return False
    except PermissionError:
        # macOS may report EPERM as the last group member is reaped. Only
        # suppress it if an OS process listing confirms the group is gone;
        # a real permission denial for a live group must still surface.
        check = await asyncio.create_subprocess_exec(
            '/bin/ps', '-axo', 'pgid=', stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL)
        groups, _ = await check.communicate()
        if check.returncode or str(pid).encode() in groups.split():
            raise
        return False
    return True


async def stop_process(proc, grace=5):
    if isinstance(proc, OwnedWindowsProcess):
        return await finish_cleanup(stop_windows_process(proc))
    return await finish_cleanup(_stop_posix_process(proc, grace))


async def _stop_posix_process(proc, grace=5):
    # A finished leader can leave descendants holding its stdout pipe open.
    # The process group belongs exclusively to this invocation.
    try:
        if await signal_group(proc.pid, signal.SIGTERM):
            # Wait on the whole group, not just a leader that may already be dead.
            deadline = asyncio.get_running_loop().time() + grace
            while await signal_group(proc.pid, 0):
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    break
                await asyncio.sleep(min(.05, remaining))
    finally:
        # A cancellation can arrive during the grace period, not only during
        # communicate(). Always finish termination before releasing the context.
        if await signal_group(proc.pid, 0):
            await signal_group(proc.pid, signal.SIGKILL)
        await asyncio.wait_for(proc.wait(), 5)


class AgyBackend:
    name = 'antigravity'

    def __init__(self, cwd, command=None, timeout=180, exit_grace=10, store=None):
        executable = shutil.which('agy.exe' if os.name == 'nt' else 'agy') if command is None else None
        if command is None and not executable:
            raise ValueError('agy executable is not on PATH')
        self.command = command or [executable]
        if os.name == 'nt' and not str(self.command[0]).lower().endswith('.exe'):
            raise ValueError('Windows requires a native .exe executable; .cmd/.bat wrappers are unsupported')
        self.cwd = cwd
        self.timeout = timeout
        self.exit_grace = exit_grace
        self.active = set()
        self.store = store

    async def drive(self, session, request):
        if self.store is None:
            return await self._drive(session, request)
        from .agy_request import decode_request
        if not request.context_id:
            raise ValueError('A2A context ID is required')
        text, expected = decode_request(request.prompt)
        with self.store.claim(self.cwd, request.context_id):
            saved = self.store.get(self.cwd, request.context_id)
            if expected is not None:
                if saved is None or saved['conversation_id'] != expected:
                    raise ValueError('Saved conversation missing or changed; refusing to start a new one')
                if request.resume and request.resume != expected:
                    raise ValueError('In-memory and saved conversation IDs disagree')
            elif saved is not None or request.resume:
                raise ValueError('New conversation requested with an existing context')
            await self._drive(session, replace(request, prompt=text, resume=expected))

    async def _drive(self, session, request):
        context = request.context_id
        if context in self.active:
            raise RuntimeError('A turn in this context is already running')
        if request.attachments:
            raise ValueError('Antigravity adapter accepts text only; include relevant excerpts')
        self.active.add(context)
        proc = None
        try:
            command = [*self.command, '-p', request.prompt, '--output-format', 'json',
                       '--mode', 'plan', '--print-timeout', f'{self.timeout}s']
            if request.resume:
                command.extend(['--conversation', request.resume])
            proc = await spawn_owned_process(command, cwd=self.cwd)
            async with asyncio.timeout(self.timeout + self.exit_grace):
                stdout, stderr = await proc.communicate()
            value = parse_result(stdout, proc.returncode, request.resume, stderr)
        finally:
            try:
                if proc is not None:
                    await finish_cleanup(stop_process(proc))
            finally:
                self.active.discard(context)
        # Publish success only after cleanup succeeds. In particular, do not
        # update the executor's conversation mapping for a failed cleanup.
        if self.store is not None:
            self.store.save(self.cwd, context, value['conversation_id'])
        await session.emit(TextDelta(value['response']))
        await session.emit(Result(session_id=value['conversation_id'],
                                  num_turns=value.get('num_turns'),
                                  usage=value.get('usage'), stop_reason='completed'))
