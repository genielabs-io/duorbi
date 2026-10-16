"""Public CLI and pure portable state-path contract."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


class StatePathTests(unittest.TestCase):
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
