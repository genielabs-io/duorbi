"""Duorbi text execution, using the official A2A SDK's protocol surface."""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (create_agent_card_routes, create_jsonrpc_routes,
                               create_rest_routes)
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (AgentCapabilities, AgentCard, AgentInterface, AgentSkill,
                       Part, Task, TaskState, TaskStatus)
from starlette.applications import Starlette

from . import __version__
from .processes import finish_cleanup


@dataclass
class _Execution:
    work: asyncio.Task
    updater: TaskUpdater
    canceled: bool = False
    terminal_ready: asyncio.Event = field(default_factory=asyncio.Event)
    cancel_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class DuorbiExecutor(AgentExecutor):
    """Own backend jobs until cleanup, even when a streaming reader leaves."""

    def __init__(self, backend):
        self.backend = backend
        self.running = {}
        self.closing = False

    async def execute(self, context, event_queue):
        task_id, context_id = context.task_id, context.context_id
        updater = TaskUpdater(event_queue, task_id, context_id)
        if context.current_task is None:
            await event_queue.enqueue_event(Task(
                id=task_id, context_id=context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED)))
        if self.closing:
            await updater.failed(updater.new_agent_message([Part(text='Server is shutting down')]))
            return
        message = context.message
        if (message is None or not message.parts or
                any(part.WhichOneof('content') != 'text' for part in message.parts)):
            await updater.failed(updater.new_agent_message([
                Part(text='Antigravity adapter accepts text only; include relevant excerpts')]))
            return
        await updater.start_work()
        if self.closing:
            await updater.failed(updater.new_agent_message([Part(text='Server is shutting down')]))
            return
        work = asyncio.create_task(self.backend.run(
            context.get_user_input(), context_id=context_id))
        execution = _Execution(work, updater)
        self.running[task_id] = execution
        try:
            try:
                value = await asyncio.shield(work)
            except asyncio.CancelledError:
                if execution.canceled:
                    # cancel() owns the terminal event and waits for cleanup.
                    await execution.terminal_ready.wait()
                else:
                    await self._cancel(execution)
                return
            except Exception as exc:
                async with execution.cancel_lock:
                    if not execution.canceled:
                        await updater.failed(updater.new_agent_message([Part(text=str(exc))]))
                        execution.terminal_ready.set()
                return
            # Completion publication and cancellation have one owner. Once
            # publication starts, its completed outcome wins a concurrent cancel.
            async with execution.cancel_lock:
                if not execution.canceled:
                    metadata = {'agent_session_id': value['conversation_id']}
                    if value.get('num_turns') is not None:
                        metadata['num_turns'] = value['num_turns']
                    if value.get('requested_model') is not None:
                        metadata['requested_model'] = value['requested_model']
                    answer = value['response']
                    await updater.add_artifact([Part(text=answer)], name='response', last_chunk=True)
                    await updater.complete(updater.new_agent_message([Part(text=answer)], metadata=metadata))
                    execution.terminal_ready.set()
        finally:
            self.running.pop(task_id, None)

    async def _cancel(self, execution):
        await finish_cleanup(self._cancel_owned(execution))

    async def _cancel_owned(self, execution):
        async with execution.cancel_lock:
            if execution.terminal_ready.is_set():
                return
            execution.canceled = True
            execution.work.cancel()
            try:
                await execution.work
            except asyncio.CancelledError:
                await execution.updater.cancel()
            except Exception as exc:
                # A failed cleanup is a failure, never a successful cancellation.
                await execution.updater.failed(execution.updater.new_agent_message([Part(text=str(exc))]))
            else:
                await execution.updater.cancel()
            finally:
                execution.terminal_ready.set()

    async def cancel(self, context, event_queue):
        execution = self.running.get(context.task_id)
        if execution is not None:
            await self._cancel(execution)

    async def shutdown(self):
        self.closing = True
        await finish_cleanup(asyncio.gather(*(self._cancel(execution)
                                              for execution in list(self.running.values()))))


def build_app(backend, *, url, card_name, card_description):
    """Build official card/REST/JSON-RPC routes with ephemeral task history."""
    executor = DuorbiExecutor(backend)
    card = AgentCard(
        name=card_name, description=card_description, version=__version__,
        supported_interfaces=[
            AgentInterface(url=url, protocol_binding='HTTP+JSON', protocol_version='1.0'),
            AgentInterface(url=url, protocol_binding='JSONRPC', protocol_version='1.0')],
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=['text/plain'], default_output_modes=['text/plain'],
        skills=[AgentSkill(id='text-review', name='Text collaboration',
                           description='Project-scoped text review and design discussion in plan mode',
                           tags=['text', 'review'])])
    store = InMemoryTaskStore()
    handler = DefaultRequestHandler(executor, store, agent_card=card)

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            await executor.shutdown()

    routes = [*create_agent_card_routes(card),
              *create_jsonrpc_routes(handler, rpc_url='/'),
              *create_rest_routes(handler)]
    app = Starlette(routes=routes, lifespan=lifespan)
    app.state.executor = executor
    app.state.handler = handler
    app.state.task_store = store
    return app
