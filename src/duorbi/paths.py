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
        elif platform == 'win32':
            selected = Path(environ.get('LOCALAPPDATA') or home / 'AppData' / 'Local') / 'Duorbi'
        else:
            selected = Path(environ.get('XDG_STATE_HOME') or home / '.local' / 'state') / 'duorbi'
    # Expand before Path normalizes separators on native Windows. In particular,
    # honor the supplied home rather than Path.expanduser()'s process environment.
    selected = os.fspath(selected)
    windows_separators = platform == 'win32' or os.name == 'nt'
    if selected == '~':
        path = home
    elif selected.startswith('~/') or (windows_separators and selected.startswith('~\\')):
        suffix = selected[2:]
        if windows_separators:
            suffix = suffix.replace('\\', '/')
        path = home / suffix.lstrip('/')
    else:
        path = Path(selected).expanduser()
    return path.resolve()
