"""Nonblocking process-lifetime locks for one complete context turn."""
from contextlib import contextmanager
import errno
import os

if os.name == 'nt':
    import msvcrt
else:
    import fcntl


@contextmanager
def exclusive_lock(path):
    """Claim a persistent lock file; closing the descriptor releases the lock.

    Never unlink the file: replacing its identity can let two callers own the
    same context. Each claim opens its own non-inheritable descriptor, so both
    independent store instances and independent threads contend normally.
    """
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_BINARY', 0), 0o600)
    try:
        try:
            if os.name == 'nt':
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            contention = isinstance(exc, BlockingIOError) or (
                os.name == 'nt' and exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK))
            if not contention:
                raise
            raise RuntimeError('A turn in this context is already running') from exc
        if os.name == 'nt' and os.fstat(fd).st_size == 0:
            # Windows permits locking beyond EOF. Initialize while holding the
            # lock, so simultaneous first claims cannot write a locked byte.
            os.write(fd, b'\0')
        yield
    finally:
        os.close(fd)
