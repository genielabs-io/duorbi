"""Public CLI and pure portable state-path contract."""
import hashlib
import io
import json
import os
from pathlib import Path, PureWindowsPath
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


class StatePathTests(unittest.TestCase):
    def test_windows_tilde_accepts_both_separators_and_path_objects(self):
        from duorbi.paths import state_directory
        home = Path(tempfile.gettempdir(), 'duorbi-injected-home').resolve()
        for selected in ('~/saved/상태', '~\\saved\\상태', '~//saved/상태', '~\\\\saved\\상태', PureWindowsPath('~/saved/상태')):
            with self.subTest(selected=selected):
                self.assertEqual(state_directory(selected, environ={}, home=home, platform='win32'), home / 'saved' / '상태')
        self.assertEqual(state_directory(environ={'DUORBI_STATE_DIR': '~\\environment'}, home=home, platform='win32'), home / 'environment')

    def test_repeated_tilde_separators_still_resolve_under_injected_home(self):
        from duorbi.paths import state_directory
        home = Path(tempfile.gettempdir(), 'duorbi-injected-home').resolve()
        self.assertEqual(state_directory('~//saved', environ={}, home=home, platform='linux'), home / 'saved')

    @unittest.skipUnless(os.name == 'posix', 'POSIX backslash is a literal filename character')
    def test_posix_backslash_tilde_keeps_existing_user_expansion_semantics(self):
        from duorbi.paths import state_directory
        selected = '~\\literal'
        with self.assertRaises(RuntimeError):
            state_directory(selected, environ={}, home=Path('/unused'), platform='linux')

    def test_windows_uses_local_app_data_or_home_fallback(self):
        from duorbi.paths import state_directory
        home = Path(tempfile.gettempdir(), 'duorbi-test-home').resolve()
        local = home / '로컬 상태'
        self.assertEqual(state_directory(environ={'LOCALAPPDATA': str(local), 'XDG_STATE_HOME': str(home / 'ignored')}, home=home, platform='win32'), local / 'Duorbi')
        self.assertEqual(state_directory(environ={}, home=home, platform='win32'), home / 'AppData/Local/Duorbi')
        self.assertEqual(state_directory('~/explicit', environ={'LOCALAPPDATA': str(local), 'DUORBI_STATE_DIR': '~/environment'}, home=home, platform='win32'), home / 'explicit')
        self.assertEqual(state_directory(environ={'LOCALAPPDATA': str(local), 'DUORBI_STATE_DIR': '~/environment'}, home=home, platform='win32'), home / 'environment')

    def test_platform_defaults_and_xdg(self):
        from duorbi.paths import state_directory
        home = Path('/tmp/duorbi-test-home').resolve()
        self.assertEqual(state_directory(environ={}, home=home, platform='darwin'), home / 'Library/Application Support/Duorbi')
        self.assertEqual(state_directory(environ={}, home=home, platform='linux'), home / '.local/state/duorbi')
        self.assertEqual(state_directory(environ={'XDG_STATE_HOME':'~/saved'}, home=home, platform='linux'), home / 'saved/duorbi')
        self.assertEqual(state_directory(environ={'XDG_STATE_HOME':'/tmp/xdg'}, home=home, platform='darwin'), home / 'Library/Application Support/Duorbi')

    def test_explicit_then_environment_then_default_and_expand_home(self):
        from duorbi.paths import state_directory
        home = Path('/tmp/duorbi-test-home').resolve()
        env = {'DUORBI_STATE_DIR':'~/environment', 'XDG_STATE_HOME':'/tmp/xdg'}
        self.assertEqual(state_directory('~/explicit', environ=env, home=home, platform='darwin'), home / 'explicit')
        self.assertEqual(state_directory(environ=env, home=home, platform='linux'), home / 'environment')
        self.assertEqual(state_directory(environ={'DUORBI_STATE_DIR':''}, home=home, platform='linux'), home / '.local/state/duorbi')


class PublicCLITests(unittest.TestCase):
    def test_info_pipe_is_utf8_even_when_python_stream_encoding_is_ascii(self):
        with tempfile.TemporaryDirectory(prefix='duorbi-한글-') as tmp:
            root = Path(tmp)
            env = {**os.environ, 'PYTHONIOENCODING': 'ascii', 'PYTHONUTF8': '0'}
            proc = subprocess.run([sys.executable, '-m', 'duorbi.bridge', 'info', '--project', str(root), '--state-dir', str(root / '상태-😀')], env=env, capture_output=True, timeout=10)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            info = json.loads(proc.stdout.decode('utf-8'))
            self.assertEqual(info['project'], str(root.resolve()))
            self.assertEqual(info['state_dir'], str((root / '상태-😀').resolve()))

    def test_stdin_protocol_decodes_utf8_independent_of_text_stream_encoding(self):
        from duorbi import bridge
        value = '한국어 질문 😀\n두 번째 줄'
        stream = io.TextIOWrapper(io.BytesIO(value.encode('utf-8')), encoding='cp1252')
        with patch('sys.stdin', stream):
            self.assertEqual(bridge.read_stdin(), value)
        with patch('sys.stdin', io.StringIO(value)):
            self.assertEqual(bridge.read_stdin(), value)

    def test_stdin_protocol_rejects_invalid_utf8(self):
        from duorbi import bridge
        stream = io.TextIOWrapper(io.BytesIO(b'\xff'), encoding='cp1252')
        with patch('sys.stdin', stream), self.assertRaises(UnicodeDecodeError):
            bridge.read_stdin()

    def test_cli_reports_invalid_utf8_stdin_before_any_network_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, 'PYTHONIOENCODING': 'cp1252', 'PYTHONUTF8': '0'}
            proc = subprocess.run([sys.executable, '-m', 'duorbi.bridge', 'call', '-', '--project', tmp, '--state-dir', str(Path(tmp) / 'state'), '--context', 'missing'], input=b'\xff', env=env, capture_output=True, timeout=10)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            result = json.loads(proc.stdout.decode('utf-8'))
            self.assertEqual(result['error_class'], 'UnicodeDecodeError')

    def test_public_parser_has_only_antigravity_commands(self):
        from duorbi.bridge import parser
        args = parser().parse_args(['call', 'hello', '--new'])
        self.assertFalse(hasattr(args, 'agent'))
        self.assertFalse(hasattr(args, 'task'))
        for argv in [['--agent','gemini','info'], ['serve','--backend','echo'], ['call','hi','--task','id'], ['serve','--agent-command','cmd']]:
            with redirect_stdout(io.StringIO()), patch('sys.stderr', new=io.StringIO()):
                with self.assertRaises(SystemExit) as exc:
                    parser().parse_args(argv)
                self.assertEqual(exc.exception.code, 2)

    def test_version_and_console_entrypoint(self):
        from duorbi import __version__
        from duorbi.bridge import parser
        with redirect_stdout(io.StringIO()) as output, self.assertRaises(SystemExit) as exc:
            parser().parse_args(['--version'])
        self.assertEqual(exc.exception.code, 0)
        self.assertEqual(output.getvalue().strip(), f'duorbi {__version__}')

    def test_info_uses_cli_state_over_environment_and_legacy_identity(self):
        from duorbi.bridge import main
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / 'selected'
            with patch.dict('os.environ', {'DUORBI_STATE_DIR':str(root / 'unused')}), patch('sys.argv', ['duorbi','info','--project',tmp,'--state-dir',str(state)]), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(), 0)
            info = json.loads(output.getvalue())
            digest = hashlib.sha256(('antigravity:' + str(root.resolve())).encode()).hexdigest()
            self.assertEqual(info['port'], 20000 + int(digest[:8],16) % 20000)
            self.assertEqual(info['name'], f'Antigravity A2A {digest[:16]} store {info["store_identity"]}')
            self.assertEqual(info['state_dir'], str(state.resolve()))
            self.assertFalse((root / 'unused').exists())
