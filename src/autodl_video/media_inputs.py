"""Short-lived private input copies for multi-stage local media operations."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
from pathlib import Path


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class MediaInputs:
    """Bind every read to captured bytes, never to a mutable source pathname.

    The context owns all copies, including incomplete captures. Copies live in
    system temporary storage rather than an asset tree and are removed on normal
    or exceptional exit. A hard process kill cannot run this cleanup.
    """

    def __init__(self):
        self.files: dict[Path, dict] = {}
        self._temporary = None

    def __enter__(self):
        self._temporary = tempfile.TemporaryDirectory(prefix=".媒体输入-")
        self.directory = Path(self._temporary.name)
        return self

    def __exit__(self, *exc):
        self._temporary.cleanup()

    def capture(self, source: Path) -> Path:
        source = Path(source)
        if source in self.files:
            return self.files[source]["snapshot"]
        source = source.resolve()
        if source in self.files:
            return self.files[source]["snapshot"]
        if self._temporary is None:
            raise RuntimeError("媒体快照必须在上下文中使用")
        snapshot = self.directory / f"input-{len(self.files):04}{source.suffix}"
        try:
            with source.open("rb") as reader, snapshot.open("xb") as writer:
                before = os.fstat(reader.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise ValueError("媒体输入必须是普通文件")
                shutil.copyfileobj(reader, writer, length=1024 * 1024)
                after = os.fstat(reader.fileno())

            def stamp(info):
                return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

            digest = file_digest(snapshot)
            if (
                stamp(before) != stamp(after)
                or not os.path.samestat(before, source.stat())
                or file_digest(source) != digest
            ):
                raise ValueError(f"媒体输入在捕获时变化：{source}")
            # Repeated paths are captured once; byte-identical aliases/files also
            # share one private copy, never a hard link to the live original.
            existing = next(
                (item["snapshot"] for item in self.files.values() if item["sha256"] == digest),
                None,
            )
            if existing is not None:
                snapshot.unlink()
                snapshot = existing
            self.files[source] = {"snapshot": snapshot, "sha256": digest}
            return snapshot
        except BaseException:
            snapshot.unlink(missing_ok=True)
            raise

    def digest(self, source: Path) -> str:
        return self.files[Path(source)]["sha256"]

    def bindings(self) -> list[dict]:
        return [{"path": str(path), "sha256": item["sha256"]} for path, item in self.files.items()]

    def check_current(self) -> None:
        for path, item in self.files.items():
            if path.resolve() != path or not path.is_file() or file_digest(path) != item["sha256"]:
                raise ValueError(f"媒体输入已变化，未发布结果：{path}")
