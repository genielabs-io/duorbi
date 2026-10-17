from concurrent.futures import ThreadPoolExecutor
import os
import re
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
        try:
            alias.symlink_to(self.project, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            if os.name == 'nt' and (isinstance(exc, NotImplementedError) or
                                    getattr(exc, 'winerror', None) in (1, 50, 1314)):
                self.skipTest(f'Windows directory symlink unavailable: {exc}')
            raise
        self.store.save(self.project, 'ctx1', 'agy1')
        reopened = SessionStore(self.state)
        self.assertEqual(reopened.get(alias, 'ctx1')['conversation_id'], 'agy1')
        self.assertEqual(reopened.latest(alias)['context_id'], 'ctx1')

    def test_reopen_restores_unicode_project_and_identifiers(self):
        project = self.root / '프로젝트 😀'
        project.mkdir()
        self.store.save(project, '문맥 😀', '대화 😀')
        reopened = SessionStore(self.state)
        self.assertEqual(reopened.get(project, '문맥 😀')['conversation_id'], '대화 😀')

    def test_concurrent_connections_persist_independent_contexts(self):
        def save(index):
            other = SessionStore(self.state)
            with other.claim(self.project, f'ctx{index}'):
                other.save(self.project, f'ctx{index}', f'agy{index}')
                return other.get(self.project, f'ctx{index}')['conversation_id']

        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(list(pool.map(save, range(12))), [f'agy{i}' for i in range(12)])
        self.assertEqual(len(self.store.list(self.project)), 12)

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
        if os.name == 'posix':
            self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
            self.assertEqual(self.store.locks.stat().st_mode & 0o777, 0o700)
        row = self.store.get(self.project, 'ctx1')
        self.assertEqual(set(row), {'project', 'context_id', 'conversation_id',
                                    'created_at', 'updated_at', 'last_used_ns'})

    @unittest.skipUnless(os.name == 'nt', 'Windows directory ACL contract')
    def test_new_windows_state_directories_have_private_protected_acls(self):
        import ctypes
        from ctypes import wintypes
        security = ctypes.WinDLL('advapi32', use_last_error=True)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        pointer = ctypes.c_void_p
        security.GetNamedSecurityInfoW.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(pointer), pointer, ctypes.POINTER(pointer), pointer, ctypes.POINTER(pointer)]
        security.GetNamedSecurityInfoW.restype = wintypes.DWORD
        security.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [pointer, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(wintypes.DWORD)]
        security.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = wintypes.BOOL
        kernel.LocalFree.argtypes = [pointer]
        kernel.LocalFree.restype = pointer
        for path in (self.state, self.store.locks):
            owner, dacl, descriptor = pointer(), pointer(), pointer()
            result = security.GetNamedSecurityInfoW(str(path), 1, 5, ctypes.byref(owner), None, ctypes.byref(dacl), None, ctypes.byref(descriptor))
            self.assertEqual(result, 0)
            try:
                self.assertTrue(owner.value, 'directory must have an owner')
                self.assertTrue(dacl.value, 'a NULL DACL would allow everyone')
                sddl = wintypes.LPWSTR()
                self.assertTrue(security.ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor, 1, 5, ctypes.byref(sddl), None))
                try:
                    self.assertIn('D:P', sddl.value, 'new directory must exclude inherited broad access')
                    trustees = [ace.split(';')[-1] for ace in re.findall(r'\(([^()]*)\)', sddl.value)]
                    self.assertTrue(trustees)
                    self.assertTrue(set(trustees).isdisjoint({'WD', 'AU', 'BU', 'S-1-1-0', 'S-1-5-11', 'S-1-5-32-545'}), sddl.value)
                finally:
                    kernel.LocalFree(ctypes.cast(sddl, pointer))
            finally:
                kernel.LocalFree(descriptor)


if __name__ == '__main__':
    unittest.main()
