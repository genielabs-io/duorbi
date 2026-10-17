"""Real OS lock guarantees, exercised on POSIX and native Windows."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


class FileLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'context.lock'

    def test_separate_threads_fail_immediately_and_different_files_are_independent(self):
        from duorbi.file_locks import exclusive_lock

        def contend():
            start = time.monotonic()
            with self.assertRaisesRegex(RuntimeError, 'already running'):
                with exclusive_lock(self.path):
                    self.fail('parallel claim was accepted')
            return time.monotonic() - start

        with ThreadPoolExecutor(max_workers=1) as pool:
            with exclusive_lock(self.path):
                self.assertLess(pool.submit(contend).result(timeout=3), 1)
                with exclusive_lock(self.root / 'other.lock'):
                    pass
        with exclusive_lock(self.path):
            pass
        self.assertTrue(self.path.is_file(), 'lock files must never be deleted')
        if os.name == 'nt':
            self.assertGreaterEqual(self.path.stat().st_size, 1)

    def test_os_lock_contends_across_processes_and_releases_on_crash(self):
        from duorbi.file_locks import exclusive_lock
        ready = self.root / 'ready'
        code = '''
from pathlib import Path
import sys
from duorbi.file_locks import exclusive_lock
with exclusive_lock(Path(sys.argv[1])):
    Path(sys.argv[2]).touch()
    sys.stdin.buffer.read()
'''
        child = subprocess.Popen([sys.executable, '-c', code, str(self.path), str(ready)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.stop_child, child)
        deadline = time.monotonic() + 5
        while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(ready.exists(), f'child did not acquire lock: exit={child.poll()}')
        with self.assertRaisesRegex(RuntimeError, 'already running'):
            with exclusive_lock(self.path):
                self.fail('parent acquired child lock')
        child.kill()
        child.wait(timeout=5)
        with exclusive_lock(self.path):
            pass
        self.assertTrue(self.path.exists())

    def test_parent_lock_blocks_child_without_waiting(self):
        from duorbi.file_locks import exclusive_lock
        code = '''
from pathlib import Path
import sys
from duorbi.file_locks import exclusive_lock
try:
    with exclusive_lock(Path(sys.argv[1])):
        raise AssertionError('child acquired parent lock')
except RuntimeError as exc:
    assert 'already running' in str(exc)
'''
        with exclusive_lock(self.path):
            child = subprocess.run([sys.executable, '-c', code, str(self.path)], capture_output=True, timeout=3)
        self.assertEqual(child.returncode, 0, child.stderr)

    @staticmethod
    def stop_child(child):
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
