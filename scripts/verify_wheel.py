"""Install the built wheel in a temporary venv and test outside the checkout."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    wheels = sorted((root / 'dist').glob('duorbi-*.whl'))
    if len(wheels) != 1:
        raise SystemExit('Build first; dist must contain exactly one Duorbi wheel.')
    uv = shutil.which('uv')
    if not uv:
        raise SystemExit('uv is required for the clean-wheel check.')
    env = {key: value for key, value in os.environ.items()
           if key not in {'PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'DUORBI_STATE_DIR'}}
    with tempfile.TemporaryDirectory(prefix='duorbi-wheel-') as temporary:
        # macOS exposes the same temporary directory through /var and /private/var.
        workspace = Path(temporary).resolve()
        python = workspace / 'venv' / 'bin' / 'python'
        subprocess.run([uv, 'venv', '--python', sys.executable, str(workspace / 'venv')],
                       env=env, check=True)
        constraints = workspace / 'constraints.txt'
        subprocess.run([uv, 'export', '--frozen', '--no-dev', '--no-emit-project',
                        '--output-file', str(constraints)], cwd=root, env=env,
                       check=True, stdout=subprocess.DEVNULL)
        subprocess.run([uv, 'pip', 'install', '--python', str(python),
                        '--constraint', str(constraints), str(wheels[0])],
                       env=env, check=True)
        for directory in ('tests', 'scripts'):
            shutil.copytree(root / directory, workspace / directory,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        env['DUORBI_STATE_DIR'] = str(workspace / 'state')
        probe = subprocess.run([str(python), '-c',
            'import json,duorbi; print(json.dumps({"module":duorbi.__file__}))'],
            cwd=workspace, env=env, check=True, text=True, capture_output=True)
        module_path = Path(json.loads(probe.stdout)['module']).resolve()
        if not module_path.is_relative_to(workspace / 'venv'):
            raise SystemExit('Import did not come from the installed wheel.')
        subprocess.run([str(workspace / 'venv' / 'bin' / 'duorbi'), '--version'],
                       cwd=workspace, env=env, check=True)
        subprocess.run([str(python), '-m', 'duorbi', 'info', '--project', str(workspace)],
                       cwd=workspace, env=env, check=True, stdout=subprocess.DEVNULL)
        subprocess.run([str(python), '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                       cwd=workspace, env=env, check=True)
        print(json.dumps({'ok': True, 'installed_wheel': wheels[0].name,
                          'import_from_installed_venv': True,
                          'tests_outside_checkout': True,
                          'pythonpath_removed': True,
                          'real_model_calls': 0}))


if __name__ == '__main__':
    main()
