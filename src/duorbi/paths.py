"""Portable state selection without creating directories or reading credentials."""
import os
from pathlib import Path
import sys


def state_directory(directory=None, *, environ=None, home=None, platform=None):
    """Return a canonical state path; explicit arguments override environment."""
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    platform = sys.platform if platform is None else platform
    selected = directory if directory is not None else environ.get('DUORBI_STATE_DIR')
    if not selected:
        if platform == 'darwin':
            selected = home / 'Library' / 'Application Support' / 'Duorbi'
        else:
            selected = Path(environ.get('XDG_STATE_HOME') or home / '.local' / 'state') / 'duorbi'
    path = Path(selected)
    if str(path) == '~' or str(path).startswith('~/'):
        path = home / str(path)[2:] if str(path) != '~' else home
    else:
        path = path.expanduser()
    return path.resolve()
