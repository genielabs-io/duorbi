import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from a2acode.backends.base import RunRequest, Result
from duorbi.agy_backend import AgyBackend
from duorbi.session_store import SessionStore
from test_agy_backend import Collector


def framed(text, conversation=None):
    return json.dumps({'version': 1, 'intent': 'resume' if conversation else 'new',
                       'conversation_id': conversation, 'text': text})


class PersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = SessionStore(self.root / 'state')
        script = self.root / 'fake.py'
        script.write_text('''import sys,json
a=sys.argv
resume=a[a.index('--conversation')+1] if '--conversation' in a else None
print(json.dumps({'status':'SUCCESS','conversation_id':resume or 'agy-first',
                  'response':resume or 'new'}))
''')
        self.command = [sys.executable, str(script)]

    def backend(self):
        return AgyBackend(self.root, command=self.command, store=SessionStore(self.root / 'state'))

    async def test_new_backend_restores_persisted_id_without_upstream_memory(self):
        first = Collector()
        await self.backend().drive(first, RunRequest(framed('hello'), context_id='ctx'))
        self.assertEqual(self.store.get(self.root, 'ctx')['conversation_id'], 'agy-first')
        second = Collector()
        await self.backend().drive(second, RunRequest(framed('again', 'agy-first'), context_id='ctx'))
        self.assertEqual(second.events[0].text, 'agy-first')

    async def test_unknown_or_mismatched_resume_never_launches_cli(self):
        self.store.save(self.root, 'ctx', 'real-id')
        for context, expected in [('missing', 'real-id'), ('ctx', 'wrong-id')]:
            with patch('duorbi.agy_backend.asyncio.create_subprocess_exec') as spawn:
                with self.assertRaises(ValueError):
                    await self.backend().drive(Collector(), RunRequest(framed('again', expected), context_id=context))
                spawn.assert_not_called()
        self.assertEqual(self.store.get(self.root, 'ctx')['conversation_id'], 'real-id')

    async def test_raw_prompt_and_new_intent_cannot_reset_existing_context(self):
        self.store.save(self.root, 'ctx', 'real-id')
        for prompt in ['raw text', framed('hello')]:
            with self.assertRaises(ValueError):
                await self.backend().drive(Collector(), RunRequest(prompt, context_id='ctx'))

    async def test_failed_durable_save_never_publishes_success(self):
        sink = Collector()
        backend = self.backend()
        with patch.object(backend.store, 'save', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                await backend.drive(sink, RunRequest(framed('hello'), context_id='ctx'))
        self.assertFalse(any(isinstance(e, Result) for e in sink.events))
        self.assertIsNone(self.store.get(self.root, 'ctx'))
        with self.store.claim(self.root, 'ctx'):
            pass

    async def test_resumed_cli_returning_other_id_preserves_saved_mapping(self):
        self.store.save(self.root, 'ctx', 'real-id')
        backend = self.backend()
        backend.command = [sys.executable, '-c', 'print(\'{"status":"SUCCESS","conversation_id":"wrong","response":"bad"}\')']
        with self.assertRaisesRegex(RuntimeError, 'different conversation'):
            await backend.drive(Collector(), RunRequest(framed('again', 'real-id'), context_id='ctx'))
        self.assertEqual(self.store.get(self.root, 'ctx')['conversation_id'], 'real-id')


if __name__ == '__main__':
    unittest.main()
