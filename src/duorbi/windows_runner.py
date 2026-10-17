"""Private launch gate: no target code runs until the parent assigns our Job.

The Job handle belongs only to the parent. EOF (including parent death before
assignment) fails closed. Target stdout/stderr are inherited without decoding.
"""
import os
import subprocess
import sys

LAUNCH_TOKEN = b'duorbi-launch-v1\n'


def main():
    if sys.stdin.buffer.readline(len(LAUNCH_TOKEN) + 1) != LAUNCH_TOKEN:
        return 125
    command = sys.argv[1:]
    if (not command or command[0].lower().endswith(('.cmd', '.bat'))
            or (os.name == 'nt' and not command[0].lower().endswith('.exe'))):
        return 125
    try:
        return subprocess.call(command, stdin=subprocess.DEVNULL, shell=False)
    except OSError:
        # Avoid echoing argv, which can contain private prompts.
        print('Unable to launch native agy executable', file=sys.stderr)
        return 126


if __name__ == '__main__':
    raise SystemExit(main())
