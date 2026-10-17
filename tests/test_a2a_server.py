"""Duorbi owns execution lifetime independently of HTTP subscribers."""
import asyncio
import unittest
from unittest.mock import AsyncMock

from a2a.server.agent_execution import RequestContext
from a2a.server.context import ServerCallContext
from a2a.server.events import EventQueue
from a2a.types import Message, Part, Role, SendMessageRequest, TaskState
from duorbi.a2a_server import DuorbiExecutor, build_app


class Queue(EventQueue):
    def __init__(self):
        self.events = []

    async def enqueue_event(self, event):
        self.events.append(event)


def context(parts=None):
    return RequestContext(ServerCallContext(), SendMessageRequest(message=Message(
        message_id='message', role=Role.ROLE_USER, context_id='ctx',
        parts=parts if parts is not None else [Part(text='envelope')])))


def states(queue):
    return [e.status.state for e in queue.events if e.DESCRIPTOR.name == 'TaskStatusUpdateEvent']


class ExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_requested_model_is_forwarded_as_request_metadata_not_attestation(self):
        backend = AsyncMock()
        backend.run.return_value = {'response': 'review', 'conversation_id': 'agy-id',
                                    'requested_model': 'claude-sonnet-5-5-high'}
        queue = Queue()
        await DuorbiExecutor(backend).execute(context(), queue)
        metadata = queue.events[-1].status.message.metadata
        self.assertEqual(metadata['requested_model'], 'claude-sonnet-5-5-high')
        self.assertNotIn('actual_model', metadata)

    async def test_exact_text_and_provider_neutral_session_metadata(self):
        answer = '  exact\n한글 🙂\n'
        backend = AsyncMock()
        backend.run.return_value = {'response': answer, 'conversation_id': 'agy-id', 'num_turns': 2}
        queue = Queue()
        await DuorbiExecutor(backend).execute(context(), queue)
        complete = queue.events[-1]
        self.assertEqual(complete.status.state, TaskState.TASK_STATE_COMPLETED)
        self.assertEqual(complete.status.message.parts[0].text, answer)
        self.assertEqual(complete.status.message.metadata['agent_session_id'], 'agy-id')
        self.assertNotIn('claude_session_id', complete.status.message.metadata)
        artifacts = [e for e in queue.events if e.DESCRIPTOR.name == 'TaskArtifactUpdateEvent']
        self.assertEqual(artifacts[0].artifact.parts[0].text, answer)

    async def test_mixed_nontext_parts_fail_before_backend(self):
        backend = AsyncMock()
        queue = Queue()
        await DuorbiExecutor(backend).execute(context([Part(text='ok'), Part(raw=b'attachment', media_type='application/octet-stream')]), queue)
        backend.run.assert_not_called()
        self.assertEqual(states(queue)[-1], TaskState.TASK_STATE_FAILED)

    async def test_error_is_explicit_failed_without_artifact(self):
        backend = AsyncMock()
        backend.run.side_effect = PermissionError('cleanup failed')
        queue = Queue()
        await DuorbiExecutor(backend).execute(context(), queue)
        self.assertEqual(states(queue)[-1], TaskState.TASK_STATE_FAILED)
        self.assertFalse(any(e.DESCRIPTOR.name == 'TaskArtifactUpdateEvent' for e in queue.events))

    async def test_cancel_waits_for_cleanup_and_only_then_publishes_terminal(self):
        started, cleanup_started, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        backend = AsyncMock()

        async def run(*args, **kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleanup_started.set()
                await release.wait()
        backend.run.side_effect = run
        executor, queue, ctx = DuorbiExecutor(backend), Queue(), context()
        executing = asyncio.create_task(executor.execute(ctx, queue))
        await started.wait()
        canceling = asyncio.create_task(executor.cancel(ctx, queue))
        await cleanup_started.wait()
        self.assertFalse(canceling.done())
        self.assertNotIn(TaskState.TASK_STATE_CANCELED, states(queue))
        release.set()
        await asyncio.wait_for(canceling, 2)
        await asyncio.wait_for(executing, 2)
        self.assertEqual(states(queue).count(TaskState.TASK_STATE_CANCELED), 1)
        self.assertFalse(executor.running)

    async def test_shutdown_cancels_work_and_rejects_new_work(self):
        backend = AsyncMock()
        started, cleaned = asyncio.Event(), asyncio.Event()
        async def run(*args, **kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()
        backend.run.side_effect = run
        executor, queue = DuorbiExecutor(backend), Queue()
        executing = asyncio.create_task(executor.execute(context(), queue))
        await started.wait()
        await executor.shutdown()
        await executing
        self.assertTrue(cleaned.is_set())
        await executor.execute(context(), Queue())
        self.assertEqual(backend.run.await_count, 1)
        self.assertEqual(states(queue)[-1], TaskState.TASK_STATE_CANCELED)

    async def test_cancel_during_publication_has_one_terminal_outcome(self):
        entered, release = asyncio.Event(), asyncio.Event()
        class PausedQueue(Queue):
            async def enqueue_event(self, event):
                if event.DESCRIPTOR.name == 'TaskArtifactUpdateEvent':
                    entered.set()
                    await release.wait()
                await super().enqueue_event(event)
        backend = AsyncMock()
        backend.run.return_value = {'response': 'ok', 'conversation_id': 'agy'}
        executor, queue, ctx = DuorbiExecutor(backend), PausedQueue(), context()
        executing = asyncio.create_task(executor.execute(ctx, queue))
        await entered.wait()
        canceling = asyncio.create_task(executor.cancel(ctx, queue))
        await asyncio.sleep(0)
        release.set()
        await asyncio.wait_for(asyncio.gather(executing, canceling), 2)
        terminals = [s for s in states(queue) if s in {TaskState.TASK_STATE_COMPLETED,
                     TaskState.TASK_STATE_CANCELED, TaskState.TASK_STATE_FAILED}]
        self.assertEqual(terminals, [TaskState.TASK_STATE_COMPLETED])

    async def test_repeated_cancellation_of_cancel_hook_finishes_cleanup(self):
        started, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        backend = AsyncMock()
        async def run(*args, **kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await release.wait()
        backend.run.side_effect = run
        executor, queue, ctx = DuorbiExecutor(backend), Queue(), context()
        executing = asyncio.create_task(executor.execute(ctx, queue))
        await started.wait()
        canceling = asyncio.create_task(executor.cancel(ctx, queue))
        await cleaning.wait()
        canceling.cancel()
        await asyncio.sleep(0)
        canceling.cancel()
        await asyncio.sleep(0)
        self.assertFalse(canceling.done())
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await canceling
        await asyncio.wait_for(executing, 2)
        self.assertEqual(states(queue)[-1], TaskState.TASK_STATE_CANCELED)

    async def test_cancel_cleanup_failure_is_failed(self):
        backend = AsyncMock()
        started = asyncio.Event()
        async def run(*args, **kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                raise OSError('cleanup failure')
        backend.run.side_effect = run
        executor, queue, ctx = DuorbiExecutor(backend), Queue(), context()
        executing = asyncio.create_task(executor.execute(ctx, queue))
        await started.wait()
        await executor.cancel(ctx, queue)
        await executing
        self.assertEqual(states(queue)[-1], TaskState.TASK_STATE_FAILED)
        self.assertNotIn(TaskState.TASK_STATE_CANCELED, states(queue))


class ProcessLifespanTests(unittest.IsolatedAsyncioTestCase):
    async def test_asgi_lifespan_shutdown_cleans_real_cli_and_child_before_unlock(self):
        import json
        import os
        from pathlib import Path
        import sys
        import tempfile
        from duorbi.agy_backend import AgyBackend
        from duorbi.agy_request import encode_request
        from duorbi.session_store import SessionStore
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / 'pids.json'
            code = ('import os,json,pathlib,subprocess,sys,time; '
                    'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"],'
                    'stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); '
                    'pathlib.Path(sys.argv[1]).write_text(json.dumps([os.getpid(),p.pid]));time.sleep(60)')
            store = SessionStore(root / 'state')
            backend = AgyBackend(tmp, command=[sys.executable, '-c', code, str(marker)], store=store)
            app = build_app(backend, url='http://127.0.0.1:19100/', card_name='fixture', card_description='fixture')
            queue = Queue()
            async with app.router.lifespan_context(app):
                executing = asyncio.create_task(app.state.executor.execute(
                    context([Part(text=encode_request('hello'))]), queue))
                for _ in range(200):
                    if marker.exists():
                        break
                    await asyncio.sleep(.01)
                self.assertTrue(marker.exists())
            await asyncio.wait_for(executing, 2)
            self.assertEqual(states(queue)[-1], TaskState.TASK_STATE_CANCELED)
            for pid in json.loads(marker.read_text()):
                if os.name == 'nt':
                    from duorbi.win32_jobs import process_is_running
                    self.assertFalse(process_is_running(pid))
                else:
                    with self.assertRaises(ProcessLookupError):
                        os.kill(pid, 0)
            self.assertIsNone(store.get(tmp, 'ctx'))
            with store.claim(tmp, 'ctx'):
                pass

    async def test_real_backend_cleanup_failure_is_failed_without_save_or_artifact(self):
        import sys
        import tempfile
        from unittest.mock import patch
        from duorbi.agy_backend import AgyBackend, stop_process
        from duorbi.agy_request import encode_request
        from duorbi.session_store import SessionStore
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(tmp)
            code = 'print(\'{"status":"SUCCESS","conversation_id":"agy","response":"ok"}\')'
            backend = AgyBackend(tmp, command=[sys.executable, '-c', code], store=store)
            async def failing_cleanup(proc):
                await stop_process(proc)
                raise OSError('fixture cleanup failure')
            queue = Queue()
            with patch('duorbi.agy_backend.stop_process', side_effect=failing_cleanup):
                await DuorbiExecutor(backend).execute(context([Part(text=encode_request('hello'))]), queue)
            self.assertEqual(states(queue)[-1], TaskState.TASK_STATE_FAILED)
            self.assertFalse(any(e.DESCRIPTOR.name == 'TaskArtifactUpdateEvent' for e in queue.events))
            self.assertIsNone(store.get(tmp, 'ctx'))
            with store.claim(tmp, 'ctx'):
                pass
