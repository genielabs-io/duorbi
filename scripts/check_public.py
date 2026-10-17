"""Check the public source boundary and built archives without extracting them.

This is a small release guard, not a complete credential or secret scanner.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PARTS = {'state', 'runtime', 'logs', 'backups', 'upstream', '.venv',
                 '__pycache__', '.git', '.aws'}
SOURCE_DIRS = ('src', 'tests', 'scripts', 'docs', 'examples', 'assets', 'licenses', '.github')
SOURCE_FILES = ('README.md', 'README.ko.md', 'INSTALL.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md',
                'CONTRIBUTING.md', 'SECURITY.md', 'CHANGELOG.md',
                'pyproject.toml', 'uv.lock', '.gitignore', 'licenses/a2a-sdk-LICENSE.txt')
LICENSE_PAYLOADS = ('LICENSE', 'THIRD_PARTY_NOTICES.md', 'licenses/a2a-sdk-LICENSE.txt')
PERSONAL_PATH = re.compile(r'/(?:Users|Volumes)/')
PRIVATE_KEY = re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')


def check_member(name, content, *, link=False):
    issues = []
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or link:
        issues.append(f'{name}: unsafe archive member or link')
    if (PRIVATE_PARTS.intersection(path.parts) or path.name.startswith('.env')
            or path.suffix in {'.db', '.log', '.pyc', '.pyo'}
            or '.sqlite' in path.name):
        issues.append(f'{name}: private runtime/state file')
    text = content.decode('utf-8', errors='replace')
    if PERSONAL_PATH.search(text):
        issues.append(f'{name}: personal path in content')
    if PRIVATE_KEY.search(content):
        issues.append(f'{name}: private key material')
    return issues


def check_archive(path):
    path = Path(path)
    issues = []
    payloads = set()
    if path.suffix == '.whl' or zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if not member.is_dir():
                    link = (member.external_attr >> 16) & 0o170000 == 0o120000
                    content = archive.read(member)
                    if content.strip():
                        payloads.add(member.filename)
                    issues.extend(check_member(member.filename, content, link=link))
    else:
        with tarfile.open(path) as archive:
            for member in archive:
                if member.isdir():
                    continue
                content = archive.extractfile(member).read() if member.isfile() else b''
                if content.strip():
                    payloads.add(member.name)
                issues.extend(check_member(member.name, content, link=not member.isfile()))
    if path.name.startswith('duorbi-'):
        if path.suffix == '.whl':
            version = path.name.split('-')[1]
            prefix = f'duorbi-{version}.dist-info/licenses/'
        else:
            prefix = path.name.removesuffix('.tar.gz') + '/'
        for name in LICENSE_PAYLOADS:
            if prefix + name not in payloads:
                issues.append(f'{path.name}: missing or empty license/notice payload {name}')
    return issues


def check_source(root):
    issues = []
    for name in SOURCE_FILES:
        path = root / name
        if not path.is_file():
            issues.append(f'{name}: required public file missing')
        else:
            issues.extend(check_member(name, path.read_bytes(), link=path.is_symlink()))
    for name in SOURCE_DIRS:
        directory = root / name
        if not directory.is_dir():
            issues.append(f'{name}: required public directory missing')
            continue
        for path in directory.rglob('*'):
            # Local interpreter caches are allowed on disk, never in archives.
            if '__pycache__' in path.parts:
                continue
            if path.is_symlink():
                issues.append(f'{path.relative_to(root)}: unsafe source link')
            elif path.is_file():
                issues.extend(check_member(path.relative_to(root).as_posix(), path.read_bytes()))
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archives', type=Path, help='Also inspect wheel/sdist files in this directory')
    args = parser.parse_args()
    issues = check_source(ROOT)
    inspected = []
    if args.archives:
        for path in sorted(args.archives.iterdir()):
            if path.name.endswith(('.whl', '.tar.gz')):
                inspected.append(path.name)
                issues.extend(check_archive(path))
        if not inspected:
            issues.append('No wheel or source distribution found')
    print(json.dumps({'ok': not issues, 'archives': inspected, 'issues': issues}, indent=2))
    return 1 if issues else 0


if __name__ == '__main__':
    raise SystemExit(main())
