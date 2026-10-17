"""Durable project-scoped A2A -> agy conversation mappings, never transcripts."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import sqlite3
import time
from uuid import uuid4


from .paths import state_directory
from .file_locks import exclusive_lock


class SessionStore:
    def __init__(self, directory=None):
        self.directory = state_directory(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.directory / 'conversations.sqlite3'
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        with closing(self._connect()) as db, db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise ValueError('Unsupported conversation database version')
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO metadata VALUES (?, ?)', ('identity', uuid4().hex))
            db.execute('''CREATE TABLE IF NOT EXISTS conversations (
                project TEXT NOT NULL, context_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                last_used_ns INTEGER NOT NULL,
                PRIMARY KEY (project, context_id))''')
            db.execute('PRAGMA user_version=1')
            identity = db.execute('SELECT value FROM metadata WHERE key=?', ('identity',)).fetchone()[0]
        self.identity = hashlib.sha256(f'{self.directory}:{identity}'.encode()).hexdigest()[:16]
        self.locks = self.directory / 'locks'
        self.locks.mkdir(exist_ok=True, mode=0o700)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        return db

    @staticmethod
    def project(path):
        return str(Path(path).expanduser().resolve())

    def get(self, project, context):
        with closing(self._connect()) as db:
            row = db.execute('SELECT * FROM conversations WHERE project=? AND context_id=?',
                             (self.project(project), context)).fetchone()
        return dict(row) if row else None

    def list(self, project, limit=20):
        if not 1 <= limit <= 1000:
            raise ValueError('Session list limit must be between 1 and 1000')
        with closing(self._connect()) as db:
            rows = db.execute('SELECT * FROM conversations WHERE project=? '
                              'ORDER BY last_used_ns DESC LIMIT ?',
                              (self.project(project), limit)).fetchall()
        return [dict(row) for row in rows]

    def latest(self, project):
        rows = self.list(project, 1)
        return rows[0] if rows else None

    def save(self, project, context, conversation):
        if not context or not conversation:
            raise ValueError('Both context and conversation IDs are required')
        now = datetime.now(timezone.utc).isoformat()
        try:
            with closing(self._connect()) as db, db:
                result = db.execute('''INSERT INTO conversations VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project, context_id) DO UPDATE SET
                    updated_at=excluded.updated_at, last_used_ns=excluded.last_used_ns
                    WHERE conversations.conversation_id=excluded.conversation_id''',
                    (self.project(project), context, conversation, now, now, time.time_ns()))
                if result.rowcount != 1:
                    raise ValueError('Refusing to replace a saved conversation ID')
        except sqlite3.IntegrityError as exc:
            raise ValueError('Conversation ID already belongs to another project/context') from exc

    def claim(self, project, context):
        digest = hashlib.sha256(f'{self.project(project)}\0{context}'.encode()).hexdigest()
        return exclusive_lock(self.locks / digest)
