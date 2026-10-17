import os
import tempfile
import unittest
from pathlib import Path


class BridgeTests(unittest.TestCase):
    def setUp(self):
        from duorbi import bridge
        self.bridge = bridge

    def test_symlink_and_real_path_use_same_project_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project with spaces'
            root.mkdir()
            alias = Path(tmp) / 'alias'
            try:
                alias.symlink_to(root, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                if os.name == 'nt' and (isinstance(exc, NotImplementedError)
                                       or getattr(exc, 'winerror', None) in (1, 50, 1314)):
                    self.skipTest(f'directory symlink unavailable: {exc}')
                raise
            a = self.bridge.project_settings(root, None)
            b = self.bridge.project_settings(alias, None)
            self.assertEqual(a, b)
            self.assertTrue(20000 <= a['port'] < 40000)

    def test_explicit_port_and_missing_project_are_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.bridge.project_settings(tmp, 19100)['port'], 19100)
            for port in [0, -1, 65536]:
                with self.assertRaises(ValueError):
                    self.bridge.project_settings(tmp, port)
            with self.assertRaises(ValueError):
                self.bridge.project_settings(Path(tmp) / 'missing', None)

    def test_a_port_collision_cannot_route_to_another_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = self.bridge.project_settings(tmp, 19100)
            self.bridge.validate_card({'name': settings['name']}, settings)
            with self.assertRaises(ValueError):
                self.bridge.validate_card({'name': 'another project'}, settings)

    def test_only_completed_tasks_have_success_exit_code(self):
        self.assertEqual(self.bridge.status_code('completed'), 0)
        self.assertEqual(self.bridge.status_code('input_required'), 3)
        for state in ['failed', 'canceled', 'rejected', 'working', 'unknown']:
            self.assertEqual(self.bridge.status_code(state), 2)


if __name__ == '__main__':
    unittest.main()


class ClientCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_sends_selection_over_a2a_and_reads_requested_model(self):
        import json
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch
        from a2a.types import (Message, Part, Role, StreamResponse, Task,
                              TaskState, TaskStatus)
        from duorbi.bridge import call
        requests = []
        model = 'claude-sonnet-5-5-high'

        class Client:
            async def send_message(self, request):
                requests.append(request)
                yield StreamResponse(task=Task(id='task', context_id='context',
                    status=TaskStatus(state=TaskState.TASK_STATE_COMPLETED,
                        message=Message(role=Role.ROLE_AGENT, parts=[Part(text='review')],
                            metadata={'agent_session_id': 'agy-id', 'requested_model': model}))))

            async def close(self):
                pass

        args = SimpleNamespace(text='hello', continue_latest=False, context=None,
                               timeout=2, model=model)
        settings = {'project': 'fixture', 'url': 'http://127.0.0.1:19100/'}
        with patch('duorbi.bridge.inspect_card', new=AsyncMock()), \
             patch('a2a.client.create_client', new=AsyncMock(return_value=Client())), \
             patch('duorbi.bridge.emit') as emit:
            self.assertEqual(await call(args, settings), 0)
        envelope = json.loads(requests[0].message.parts[0].text)
        self.assertEqual(envelope['version'], 2)
        self.assertEqual(envelope['model'], model)
        self.assertEqual(envelope['text'], 'hello')
        self.assertEqual(emit.call_args.args[0]['requested_model'], model)

    async def test_legacy_session_metadata_and_empty_completion_keep_artifact(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch
        from a2a.types import (Artifact, Message, Part, Role, StreamResponse, Task,
                               TaskArtifactUpdateEvent, TaskState, TaskStatus,
                               TaskStatusUpdateEvent)
        from duorbi.bridge import call
        events = [
            StreamResponse(task=Task(id='task', context_id='context',
                                     status=TaskStatus(state=TaskState.TASK_STATE_WORKING))),
            StreamResponse(artifact_update=TaskArtifactUpdateEvent(
                task_id='task', context_id='context',
                artifact=Artifact(artifact_id='response', name='response', parts=[Part(text='exact\n')]))),
            StreamResponse(status_update=TaskStatusUpdateEvent(
                task_id='task', context_id='context', status=TaskStatus(
                    state=TaskState.TASK_STATE_COMPLETED,
                    message=Message(role=Role.ROLE_AGENT, metadata={'claude_session_id': 'legacy-id'}))))]
        class Client:
            async def send_message(self, request):
                for event in events:
                    yield event
            async def close(self):
                pass
        args = SimpleNamespace(text='hello', continue_latest=False, context=None, timeout=2)
        settings = {'project': 'fixture', 'url': 'http://127.0.0.1:19100/'}
        with patch('duorbi.bridge.inspect_card', new=AsyncMock()), \
             patch('a2a.client.create_client', new=AsyncMock(return_value=Client())), \
             patch('duorbi.bridge.emit') as emit:
            self.assertEqual(await call(args, settings), 0)
        final = emit.call_args.args[0]
        self.assertEqual(final['response'], 'exact\n')
        self.assertEqual(final['agent_session_id'], 'legacy-id')
