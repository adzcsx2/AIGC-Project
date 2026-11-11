"""Cross-process locks for local read-modify-publish transactions."""

from __future__ import annotations

import hashlib
import math
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .errors import AutoDLError


@contextmanager
def resource_lock(target: Path, *, root: Path, timeout: float = 120) -> Iterator[None]:
    """Lock a canonical resource; callers must reread it inside the context.

    All writers of a resource must use the same repository root. Lock files are
    retained: unlinking them could let a new writer bypass an existing waiter.
    The operating system releases the lock when its process exits.
    """
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout < 0
    ):
        raise AutoDLError("Lock timeout must be a finite nonnegative number")
    identity = os.path.normcase(str(target.resolve()))
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    path = root.resolve() / ".autodl" / "locks" / f"resource-{digest}.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if stream.seek(0, os.SEEK_END) == 0:
            stream.write(b"\0")
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            stream.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in {11, 13, 35}:
                    raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AutoDLError(f"Resource is in use; retry later: {target}") from None
                time.sleep(min(0.05, remaining))
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)
