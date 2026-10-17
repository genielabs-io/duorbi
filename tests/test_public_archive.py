"""Release guards reject private runtime files even inside built archives."""
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile


class PublicArchiveTests(unittest.TestCase):
    def write_duorbi_archive(self, directory, kind, omitted=None):
        files = {'LICENSE': b'Duorbi MIT license fixture',
                 'THIRD_PARTY_NOTICES.md': b'a2acode attribution fixture',
                 'licenses/a2acode-LICENSE.txt': b'Apache-2.0 license fixture'}
        files.pop(omitted, None)
        if kind == 'wheel':
            path = Path(directory) / 'duorbi-9.9.9-py3-none-any.whl'
            with zipfile.ZipFile(path, 'w') as archive:
                for name, content in files.items():
                    archive.writestr('duorbi-9.9.9.dist-info/licenses/' + name, content)
        else:
            path = Path(directory) / 'duorbi-9.9.9.tar.gz'
            with tarfile.open(path, 'w:gz') as archive:
                for name, content in files.items():
                    member = tarfile.TarInfo('duorbi-9.9.9/' + name)
                    member.size = len(content)
                    archive.addfile(member, io.BytesIO(content))
        return path

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

    def test_duorbi_archives_reject_missing_license_or_notice_payloads(self):
        audit = self.audit()
        with tempfile.TemporaryDirectory() as tmp:
            for kind in ('wheel', 'sdist'):
                for omitted in ('LICENSE', 'THIRD_PARTY_NOTICES.md',
                                'licenses/a2acode-LICENSE.txt'):
                    with self.subTest(kind=kind, omitted=omitted):
                        path = self.write_duorbi_archive(tmp, kind, omitted)
                        issues = audit.check_archive(path)
                        self.assertTrue(any(omitted in item and 'missing' in item
                                            for item in issues), issues)

    def test_duorbi_archives_accept_required_license_and_notice_payloads(self):
        audit = self.audit()
        with tempfile.TemporaryDirectory() as tmp:
            for kind in ('wheel', 'sdist'):
                with self.subTest(kind=kind):
                    path = self.write_duorbi_archive(tmp, kind)
                    self.assertEqual(audit.check_archive(path), [])


if __name__ == '__main__':
    unittest.main()
