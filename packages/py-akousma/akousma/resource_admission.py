"""One heavy managed operation per host. OS locks survive no process death.

This bounds active compute, not persistent model residency or physical RAM.
Never hold this lease across an HTTP request to another lease-owning service.
"""

from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
import fcntl
import json
import math
import os
from pathlib import Path
import threading
import time

_local = threading.local()


def resource_directory():
    return Path(
        os.environ.get(
            "LISTENINGSTACK_RESOURCE_DIR",
            str(Path.home() / ".local/share/listening-stack/resources"),
        )
    )


def _open_lock():
    directory = resource_directory()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(directory / "heavy.lock", os.O_RDWR | os.O_CREAT, 0o600)
    return os.fdopen(fd, "r+")


@contextmanager
def heavy_lease(owner, capability, *, timeout=900, checkpoint=None):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("lease timeout must be positive")
    identity = (os.getpid(), str(resource_directory().resolve()))
    if getattr(_local, "identity", None) == identity:
        if checkpoint:
            checkpoint()
        yield
        return
    waiting = time.monotonic()
    deadline = waiting + timeout
    with _open_lock() as stream:
        while True:
            if checkpoint:
                checkpoint()
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("heavy worker admission timed out")
                time.sleep(0.05)
        # How long this thread waited for another holder: a generation that waited
        # behind a listening is otherwise indistinguishable from a slow generation.
        _local.last_wait_seconds = time.monotonic() - waiting
        try:
            if checkpoint:
                checkpoint()
            stream.seek(0)
            stream.truncate()
            json.dump(
                {
                    "owner": owner,
                    "capability": capability,
                    "pid": os.getpid(),
                    "started_at": time.time(),
                },
                stream,
            )
            stream.flush()
            _local.identity = identity
            yield
        finally:
            _local.identity = None
            stream.seek(0)
            stream.truncate()
            stream.flush()
            fcntl.flock(stream, fcntl.LOCK_UN)


def last_wait_seconds():
    """Seconds this thread last waited to acquire the lease, or None if it never did."""
    return getattr(_local, "last_wait_seconds", None)


def admission_status():
    with _open_lock() as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            try:
                holder = json.loads(stream.read(4096))
            except (ValueError, OSError):
                holder = None
            return {
                "capacity": 1,
                "busy": True,
                "holder": holder,
                "scope": "managed heavy operations",
            }
        fcntl.flock(stream, fcntl.LOCK_UN)
        return {
            "capacity": 1,
            "busy": False,
            "holder": None,
            "scope": "managed heavy operations",
        }


def admitted(owner, *, checkpoint=None):
    """Wrap the owner boundary, including direct API calls; nested calls reuse it."""

    def decorate(fn):
        @wraps(fn)
        def run(*args, **kwargs):
            check = (lambda: checkpoint(*args, **kwargs)) if checkpoint else None
            with heavy_lease(owner, fn.__name__, checkpoint=check):
                return fn(*args, **kwargs)

        return run

    return decorate
