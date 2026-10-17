"""Per-turn model selection must survive A2A without changing resume identity."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from duorbi.agy_backend import AgyBackend
from duorbi.agy_request import decode_request, encode_request
from duorbi.bridge import parser
from duorbi.session_store import SessionStore


class EnvelopeModelTests(unittest.TestCase):
    def test_no_selection_keeps_v1_and_decodes_without_model(self):
        encoded = encode_request('한글 🙂', 'saved-id')
        self.assertEqual(json.loads(encoded), {
            'version': 1, 'intent': 'resume', 'conversation_id': 'saved-id', 'text': '한글 🙂'})
        self.assertEqual(decode_request(encoded), ('한글 🙂', 'saved-id', None))

    def test_explicit_model_uses_v2_so_old_server_cannot_ignore_it(self):
        for model in ['gemini-4-argon-high', 'claude-sonnet-5-5-high']:
            with self.subTest(model=model):
                encoded = encode_request('review', 'saved-id', model=model)
                self.assertEqual(json.loads(encoded)['version'], 2)
                self.assertEqual(json.loads(encoded)['model'], model)
                self.assertEqual(decode_request(encoded), ('review', 'saved-id', model))
                args = parser().parse_args(['call', 'review', '--model', model, '--context', 'ctx'])
                self.assertEqual(args.model, model)

    def test_invalid_selection_is_rejected_in_encoder_and_untrusted_envelope(self):
        for model in ['', '   ', '--auto', 'Claude Sonnet', 'x\n', 'x' * 129,
                      '$(touch marker)', ['claude'], 123, None]:
            with self.subTest(model=model):
                if model is not None:
                    with self.assertRaises(ValueError):
                        encode_request('review', model=model)
                raw = json.dumps({'version': 2, 'intent': 'new', 'conversation_id': None,
                                  'text': 'review', 'model': model})
                with self.assertRaises(ValueError):
                    decode_request(raw)
        for version, extra in [(1, {'model': 'claude-sonnet-5-5-high'}), (2, {}),
                               (3, {}), (True, {})]:
            with self.assertRaises(ValueError):
                decode_request(json.dumps({'version': version, 'intent': 'new',
                                           'conversation_id': None, 'text': 'review', **extra}))


class ModelBackendTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_switch_and_omission_preserve_saved_conversation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / 'fake.py'
            script.write_text('''import json,sys
from pathlib import Path
a=sys.argv
Path('argv.json').write_text(json.dumps(a))
resume=a[a.index('--conversation')+1] if '--conversation' in a else None
print(json.dumps({'status':'SUCCESS','conversation_id':resume or 'saved-agy',
                  'response':a[a.index('-p')+1]}))
''', encoding='utf-8')
            store = SessionStore(root / 'state')
            for model in ['gemini-4-argon-high', 'claude-sonnet-5-5-high', None]:
                saved = store.get(root, 'ctx')
                prompt = 'literal $(do-not-run) 한글 🙂'
                # New backend and store instances simulate a bridge restart.
                backend = AgyBackend(root, command=[sys.executable, str(script)],
                                     store=SessionStore(root / 'state'))
                value = await backend.run(encode_request(
                    prompt, saved['conversation_id'] if saved else None, model=model), context_id='ctx')
                self.assertEqual(value['conversation_id'], 'saved-agy')
                self.assertEqual(value['response'], prompt)
                argv = json.loads((root / 'argv.json').read_text())
                self.assertEqual(argv[argv.index('--mode') + 1], 'plan')
                self.assertNotIn('--continue', argv)
                if saved:
                    self.assertEqual(argv[argv.index('--conversation') + 1], 'saved-agy')
                if model:
                    self.assertIn('--model', argv)
                    self.assertEqual(argv[argv.index('--model') + 1], model)
                    self.assertEqual(value['requested_model'], model)
                else:
                    self.assertNotIn('--model', argv)
                    self.assertNotIn('requested_model', value)
            self.assertEqual(len(store.list(root)), 1)

    async def test_malformed_model_never_spawns_or_changes_saved_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp) / 'state')
            store.save(tmp, 'ctx', 'saved-agy')
            backend = AgyBackend(tmp, command=[sys.executable], store=store)
            raw = json.dumps({'version': 2, 'intent': 'resume', 'conversation_id': 'saved-agy',
                              'model': '--dangerously-skip-permissions', 'text': 'review'})
            with patch('duorbi.agy_backend.spawn_owned_process') as spawn:
                with self.assertRaises(ValueError):
                    await backend.run(raw, context_id='ctx')
                spawn.assert_not_called()
            self.assertEqual(store.get(tmp, 'ctx')['conversation_id'], 'saved-agy')
