"""Release guards reject private runtime files even inside built archives."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile


class PublicArchiveTests(unittest.TestCase):
    def audit(self):
        path = Path(__file__).resolve().parents[1] / 'scripts' / 'check_public.py'
        self.assertTrue(path.exists(), 'publication audit is not implemented')
        spec = importlib.util.spec_from_file_location('public_audit', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_archive_rejects_private_state_even_with_harmless_content(self):
        audit = self.audit()
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'example.whl'
            with zipfile.ZipFile(archive, 'w') as output:
                output.writestr('duorbi/state/conversations.sqlite3', 'placeholder')
            issues = audit.check_archive(archive)
            self.assertTrue(issues, 'private state was accepted')
            self.assertTrue(any('state' in item for item in issues))

    def test_archive_rejects_personal_paths_and_traversal(self):
        audit = self.audit()
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'example.whl'
            with zipfile.ZipFile(archive, 'w') as output:
                output.writestr('duorbi/example.py', 'target = ' + repr('/' + 'Users/example/work'))
                output.writestr('../outside.txt', 'bad member')
            issues = audit.check_archive(archive)
            self.assertTrue(any('personal path' in item for item in issues), issues)
            self.assertTrue(any('unsafe' in item for item in issues), issues)

    def test_public_python_package_is_accepted(self):
        audit = self.audit()
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'example.whl'
            with zipfile.ZipFile(archive, 'w') as output:
                output.writestr('duorbi/__init__.py', '__version__ = "0.1.0a1"')
                output.writestr('duorbi-0.1.0a1.dist-info/METADATA', 'Name: duorbi\n')
            self.assertEqual(audit.check_archive(archive), [])


if __name__ == '__main__':
    unittest.main()
