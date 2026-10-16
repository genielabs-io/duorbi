import tempfile
import unittest
from pathlib import Path

from duorbi.session_store import SessionStore


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / 'project'
        self.project.mkdir()
        self.state = self.root / 'state'
        self.store = SessionStore(self.state)

    def test_reopen_and_symlink_restore_same_project(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.project, target_is_directory=True)
        self.store.save(self.project, 'ctx1', 'agy1')
        reopened = SessionStore(self.state)
        self.assertEqual(reopened.get(alias, 'ctx1')['conversation_id'], 'agy1')
        self.assertEqual(reopened.latest(alias)['context_id'], 'ctx1')

    def test_projects_are_isolated_and_empty_history_is_explicit(self):
        self.store.save(self.project, 'ctx1', 'agy1')
        other = self.root / 'other'
        other.mkdir()
        self.assertIsNone(self.store.get(other, 'ctx1'))
        self.assertIsNone(self.store.latest(other))
        self.assertEqual(self.store.list(other), [])
        self.store.save(other, 'ctx1', 'other-agy')
        self.assertEqual(self.store.get(self.project, 'ctx1')['conversation_id'], 'agy1')

    def test_latest_tracks_successful_use_and_retains_older_conversations(self):
        self.store.save(self.project, 'old', 'agy1')
        self.store.save(self.project, 'new', 'agy2')
        self.store.save(self.project, 'old', 'agy1')
        self.assertEqual([r['context_id'] for r in self.store.list(self.project)], ['old', 'new'])

    def test_mapping_cannot_be_replaced_or_shared_under_another_context(self):
        self.store.save(self.project, 'ctx1', 'agy1')
        with self.assertRaises(ValueError):
            self.store.save(self.project, 'ctx1', 'different')
        with self.assertRaises(ValueError):
            self.store.save(self.project, 'ctx2', 'agy1')
        with self.assertRaises(ValueError):
            self.store.save(self.root / 'other', 'ctx3', 'agy1')
        self.assertEqual(self.store.get(self.project, 'ctx1')['conversation_id'], 'agy1')

    def test_store_identity_persists_and_distinguishes_state_directories(self):
        self.assertEqual(self.store.identity, SessionStore(self.state).identity)
        self.assertNotEqual(self.store.identity, SessionStore(self.root / 'other-state').identity)

    def test_lock_shared_between_instances_and_released_after_error(self):
        other = SessionStore(self.state)
        with self.assertRaisesRegex(RuntimeError, 'test failure'):
            with self.store.claim(self.project, 'ctx1'):
                with self.assertRaisesRegex(RuntimeError, 'already running'):
                    with other.claim(self.project, 'ctx1'):
                        self.fail('parallel claim was accepted')
                with other.claim(self.project, 'different'):
                    pass
                raise RuntimeError('test failure')
        with other.claim(self.project, 'ctx1'):
            pass

    def test_database_permissions_and_no_prompt_columns(self):
        self.store.save(self.project, 'ctx1', 'agy1')
        self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)
        row = self.store.get(self.project, 'ctx1')
        self.assertEqual(set(row), {'project', 'context_id', 'conversation_id',
                                    'created_at', 'updated_at', 'last_used_ns'})


if __name__ == '__main__':
    unittest.main()
