"""Install a local-only fake agy console executable, including Windows .exe."""
import csv
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


FAKE_SOURCE = '''import json,sys,uuid,os,subprocess,time
from pathlib import Path

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    a=sys.argv
    with Path('.fake-invocations').open('a') as calls: calls.write(str(os.getpid()) + chr(10))
    p=Path('.fake-agy.json')
    history=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    resume=a[a.index('--conversation')+1] if '--conversation' in a else None
    prompt=a[a.index('-p')+1]
    if resume and resume not in history:
        print(json.dumps({'status':'ERROR','error':'conversation unavailable'}))
        return
    control_path=Path('.fake-control.json')
    control=json.loads(control_path.read_text(encoding='utf-8')) if control_path.exists() else {}
    if control.get('wait'):
        child=None
        if control.get('child'):
            child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],
                                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        Path('.fake-pids.json').write_text(json.dumps({'owner':os.getpid(),'child':child.pid if child else None}))
        while not Path('.fake-release').exists(): time.sleep(.02)
    if control.get('status', 'SUCCESS') != 'SUCCESS':
        print(json.dumps({'status':control['status'],'error':'fixture failure'}))
        return
    key=resume or str(uuid.uuid4())
    if not resume: history[key]=prompt
    p.write_text(json.dumps(history,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'SUCCESS','conversation_id':key,'response':control.get('response',history[key])},ensure_ascii=False))
'''


def install_fake_agy(root):
    """No network or real provider: uv generates the platform's console launcher."""
    uv = shutil.which('uv')
    if not uv:
        raise RuntimeError('uv is required for portable HTTP test fixtures')
    root = Path(root).resolve()
    wheel = root / 'duorbi_fake_agy-0.0.0-py3-none-any.whl'
    metadata = 'duorbi_fake_agy-0.0.0.dist-info/'
    files = {
        'duorbi_fake_agy.py': FAKE_SOURCE,
        metadata + 'METADATA': 'Metadata-Version: 2.3\nName: duorbi-fake-agy\nVersion: 0.0.0\n',
        metadata + 'WHEEL': 'Wheel-Version: 1.0\nGenerator: duorbi-test-fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
        metadata + 'entry_points.txt': '[console_scripts]\nagy = duorbi_fake_agy:main\n',
    }
    record = io.StringIO()
    csv.writer(record, lineterminator='\n').writerows((name, '', '') for name in [*files, metadata+'RECORD'])
    files[metadata+'RECORD'] = record.getvalue()
    with zipfile.ZipFile(wheel, 'w') as archive:
        for name, content in files.items():
            archive.writestr(name, content.encode('utf-8'))
    env = {k:v for k,v in os.environ.items() if k not in {'VIRTUAL_ENV','PYTHONPATH','PYTHONHOME'}}
    venv = root / 'fake-venv'
    bindir = venv / ('Scripts' if os.name == 'nt' else 'bin')
    python = bindir / ('python.exe' if os.name == 'nt' else 'python')
    for command in ([uv,'venv','--python',sys.executable,str(venv)],
                    [uv,'pip','install','--python',str(python),'--no-index','--no-deps',str(wheel)]):
        subprocess.run(command,env=env,check=True,capture_output=True,text=True,encoding='utf-8',timeout=60)
    executable = bindir / ('agy.exe' if os.name == 'nt' else 'agy')
    if not executable.is_file():
        raise RuntimeError('fixture console executable was not generated')
    return bindir
