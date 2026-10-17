"""Project-scoped Antigravity text collaboration over a2acode HTTP."""

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from uuid import uuid4

from . import __version__


def emit(data):
    text = json.dumps(data, ensure_ascii=False) + '\n'
    stream = getattr(sys.stdout, 'buffer', None)
    if stream is None:  # StringIO and other text-only embedding/test streams.
        sys.stdout.write(text)
        sys.stdout.flush()
    else:
        stream.write(text.encode('utf-8'))
        stream.flush()


def read_stdin():
    """The piped prompt is UTF-8, independently of the console code page."""
    stream = getattr(sys.stdin, 'buffer', None)
    return stream.read().decode('utf-8') if stream is not None else sys.stdin.read()


def project_settings(project, port):
    project = Path(project).expanduser().resolve()
    if not project.is_dir():
        raise ValueError(f'Project directory does not exist: {project}')
    identity = 'antigravity:' + str(project)
    digest = hashlib.sha256(identity.encode()).hexdigest()
    if port is None:
        port = 20000 + int(digest[:8], 16) % 20000
    if not 1 <= port <= 65535:
        raise ValueError('Port must be between 1 and 65535')
    return {'project': str(project), 'port': port,
            'url': f'http://127.0.0.1:{port}/',
            'name': f'Antigravity A2A {digest[:16]}'}


def validate_card(card, settings):
    if card.get('name') != settings['name']:
        raise ValueError('Server belongs to a different project/state store or is not this '
                         'launcher. Choose a different --port for serve and call.')


def status_code(state):
    return 0 if state == 'completed' else 3 if state == 'input_required' else 2


def serve(args, settings):
    import uvicorn
    from a2acode.server import build_app
    from .agy_backend import AgyBackend

    backend = AgyBackend(settings['project'], store=args.store)
    app = build_app(backend, url=settings['url'], card_name=settings['name'],
                    card_description='Project-scoped Antigravity headless JSON agent via a2acode. '
                    'Text collaboration in plan mode; no A2A tool-approval relay.')
    emit({'type': 'server', 'backend': backend.name, **settings})
    uvicorn.run(app, host='127.0.0.1', port=settings['port'], log_level='info')


async def inspect_card(settings):
    import httpx
    async with httpx.AsyncClient(timeout=10, trust_env=False) as http:
        response = await http.get(settings['url'] + '.well-known/agent-card.json')
        response.raise_for_status()
        card = response.json()
        validate_card(card, settings)
        return card


async def call(args, settings):
    import httpx
    from a2a.client import create_client
    from a2a.client.client import ClientConfig
    from a2a.types import Message, Part, Role, SendMessageRequest, TaskState
    from google.protobuf.json_format import MessageToDict

    prompt = read_stdin() if args.text == '-' else args.text
    if not prompt.strip():
        raise ValueError('Message is empty')
    from .agy_request import encode_request
    saved = None
    if args.continue_latest:
        saved = args.store.latest(settings['project'])
        if saved is None:
            raise ValueError('No saved conversation for this project; use --new')
    elif args.context:
        saved = args.store.get(settings['project'], args.context)
        if saved is None:
            raise ValueError('No saved conversation for this context/project; inspect sessions or import-session')
    if saved:
        args.context = saved['context_id']
    prompt = encode_request(prompt, saved['conversation_id'] if saved else None)
    await inspect_card(settings)
    message = Message(message_id=uuid4().hex, role=Role.ROLE_USER,
                      parts=[Part(text=prompt)])
    if args.context:
        message.context_id = args.context
    result = {'type': 'result', 'project': settings['project'],
              'url': settings['url'], 'context_id': args.context,
              'task_id': None, 'state': 'unknown', 'response': ''}

    def status(value):
        result['state'] = TaskState.Name(value.state).removeprefix('TASK_STATE_').lower()
        detail = ''.join(p.text for p in value.message.parts if p.text)
        metadata = MessageToDict(value.message).get('metadata', {})
        # Upstream uses this historical field name for every backend.
        if metadata.get('claude_session_id'):
            result['agent_session_id'] = metadata['claude_session_id']
        if 'num_turns' in metadata:
            result['num_turns'] = metadata['num_turns']
        result['detail'] = detail
        result['permission'] = metadata.get('a2acode_permission')
        if result['state'] == 'completed':
            # a2acode carries the entire answer here, including text streamed
            # before an earlier permission pause in a separate client call.
            result['response'] = detail
        emit({'type': 'status', 'state': result['state'], 'detail': detail,
              'permission': result['permission']})

    async with httpx.AsyncClient(timeout=httpx.Timeout(args.timeout, connect=10),
                                 trust_env=False) as http:
        client = await create_client(settings['url'],
                                     ClientConfig(streaming=True, httpx_client=http))
        try:
            async with asyncio.timeout(args.timeout):
                async for event in client.send_message(SendMessageRequest(message=message)):
                    kind = event.WhichOneof('payload')
                    if kind == 'task':
                        task = event.task
                        result.update(task_id=task.id, context_id=task.context_id)
                        emit({'type': 'task', 'task_id': task.id,
                              'context_id': task.context_id})
                        status(task.status)
                    elif kind == 'status_update':
                        status(event.status_update.status)
                    elif kind == 'artifact_update':
                        artifact = event.artifact_update.artifact
                        if artifact.name == 'response':
                            text = ''.join(p.text for p in artifact.parts if p.text)
                            result['response'] += text
                            emit({'type': 'response_delta', 'text': text})
                    elif kind == 'message':
                        result['response'] += ''.join(p.text for p in event.message.parts if p.text)
        finally:
            closer = client.close()
            if closer is not None:
                await closer
    emit(result)
    return status_code(result['state'])


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument('--version', action='version', version=f'duorbi {__version__}')
    sub = root.add_subparsers(dest='command', required=True)
    for name in ['info', 'status', 'serve', 'call', 'sessions', 'import-session']:
        cmd = sub.add_parser(name)
        cmd.add_argument('--project', default='.', help='Workspace (default: current directory)')
        cmd.add_argument('--port', type=int, help='Override project-derived port on both server and client')
        cmd.add_argument('--state-dir', help='Antigravity state directory; use the same directory for server and client')
        if name == 'sessions':
            cmd.add_argument('--limit', type=int, default=20)
        if name == 'import-session':
            cmd.add_argument('--context', required=True, help='Known A2A context ID from an earlier verified result')
            cmd.add_argument('--conversation', required=True, help='Actual agy conversation ID from that result')
        if name == 'call':
            cmd.add_argument('text', help='Message; use - to read stdin')
            selector = cmd.add_mutually_exclusive_group()
            selector.add_argument('--context', help='Context ID returned by a previous call')
            selector.add_argument('--continue', dest='continue_latest', action='store_true',
                                  help='Resume the latest saved Antigravity conversation for this project')
            selector.add_argument('--new', action='store_true', help='Start a new conversation (the default)')
            cmd.add_argument('--timeout', type=float,
                             help='Seconds to wait (default: 210); does not cancel server work')
    return root


def main():
    args = parser().parse_args()
    try:
        settings = project_settings(args.project, args.port)
        from .session_store import SessionStore
        args.store = SessionStore(args.state_dir)
        settings.update(state_dir=str(args.store.directory), store_identity=args.store.identity)
        settings['name'] += f' store {args.store.identity}'
        if args.command == 'info':
            emit(settings)
        elif args.command == 'status':
            asyncio.run(inspect_card(settings))
            emit({'type': 'status', 'state': 'ready', **settings})
        elif args.command == 'serve':
            serve(args, settings)
        elif args.command == 'sessions':
            emit({'type': 'sessions', 'project': settings['project'],
                  'sessions': args.store.list(settings['project'], args.limit)})
        elif args.command == 'import-session':
            with args.store.claim(settings['project'], args.context):
                args.store.save(settings['project'], args.context, args.conversation)
            emit({'type': 'imported', 'session': args.store.get(settings['project'], args.context),
                  'note': 'Registered known IDs; actual agy availability is checked on the next resume.'})
        else:
            if args.timeout is None:
                args.timeout = 210
            if args.timeout <= 0:
                raise ValueError('--timeout must be positive')
            return asyncio.run(call(args, settings))
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        emit({'type': 'error', 'error': str(exc), 'error_class': type(exc).__name__})
        return 2


if __name__ == '__main__':
    sys.exit(main())
