"""Durable task records and streaming downloads. Never reuse the authenticated HTTP client."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .catalog import utc_now
from .client import safe_id
from .config import atomic_json
from .errors import AutoDLError
from .paths import project_owner, resolve_media_path

EXTENSIONS = {
    "mp4",
    "webm",
    "mov",
    "mkv",
    "wav",
    "mp3",
    "flac",
    "ogg",
    "png",
    "jpg",
    "jpeg",
    "webp",
    "gif",
}


class TaskStore:
    def __init__(self, root: Path):
        self.root = root
        self.directory = root / ".autodl" / "tasks"

    def save(self, task_id: str, **updates: object) -> dict:
        path = self.directory / f"{safe_id(task_id)}.json"
        with self.lock(task_id):
            data = self.read(task_id) if path.exists() else {"task_id": task_id}
            data.update(updates)
            data["updated_at"] = utc_now()
            atomic_json(path, data)
        return data

    @contextmanager
    def lock(self, task_id: str, *, download: bool = False) -> Iterator[None]:
        """Serialize task updates/downloads across processes; OS releases locks on exit."""
        name = f"{safe_id(task_id)}.{'download' if download else 'record'}.lock"
        path = self.directory.parent / "locks" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+b") as stream:
            if stream.seek(0, os.SEEK_END) == 0:
                stream.write(b"\0")
                stream.flush()
            deadline = time.monotonic() + 120
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
                    if time.monotonic() >= deadline:
                        raise AutoDLError(
                            f"Task {task_id} is in use by another process; retry later"
                        ) from None
                    time.sleep(0.05)
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream, fcntl.LOCK_UN)

    def read(self, task_id: str) -> dict:
        path = self.directory / f"{safe_id(task_id)}.json"
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            raise AutoDLError(f"No readable local record for task {task_id}") from None
        if not isinstance(data, dict) or data.get("task_id") != task_id:
            raise AutoDLError(f"Invalid local record for task {task_id}")
        for key in ("config_path", "output_dir", "download_scope"):
            if isinstance(data.get(key), str):
                data[key] = str(resolve_media_path(self.root / data[key], self.root))
        if "files" in data:
            if not isinstance(data["files"], list) or any(
                not isinstance(p, str) or not p.strip() for p in data["files"]
            ):
                raise AutoDLError(f"Invalid result file list for task {task_id}")
            data["files"] = [str(resolve_media_path(self.root / p, self.root))
                             for p in data["files"]]
        journal = data.get("download_journal", [])
        if not isinstance(journal, list):
            raise AutoDLError(f"Invalid download journal for task {task_id}")
        for entry in journal:
            if (
                not isinstance(entry, dict)
                or not isinstance(entry.get("path"), str)
                or not entry["path"].strip()
                or type(entry.get("size")) is not int
                or entry["size"] <= 0
                or not isinstance(entry.get("sha256"), str)
                or len(entry["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in entry["sha256"])
                or not isinstance(entry.get("state"), str)
                or entry.get("state") not in {"pending", "published"}
            ):
                raise AutoDLError(f"Invalid download journal for task {task_id}")
            entry["path"] = str(resolve_media_path(self.root / entry["path"], self.root))
        return data

    @staticmethod
    def recovery_files(record: dict) -> list[Path]:
        """Only a complete hash-matching file can recover a pre-publication intent."""
        paths = [Path(value) for value in record.get("files", [])]
        for entry in record.get("download_journal", []):
            path = Path(entry["path"])
            if path not in paths and _same_content(
                path, entry["size"], bytes.fromhex(entry["sha256"])
            ):
                paths.append(path)
        return paths

    def list(self) -> list[dict]:
        if not self.directory.exists():
            return []
        return [self.read(path.stem) for path in sorted(self.directory.glob("*.json"))]


def download_results(
    data: dict,
    destination: Path,
    *,
    transport: httpx.BaseTransport | None = None,
    max_bytes: int = 2 * 1024**3,
    existing_files: list[Path] | None = None,
    root: Path | None = None,
    on_publish: Callable[[Path, int, str], None] | None = None,
    on_result: Callable[[Path, int, str], None] | None = None,
) -> list[Path]:
    """Verify every remote result; reuse equal archives and never overwrite local files.

    ``existing_files`` must come from this task's record. Their order/count is not
    assumed to match a refreshed response: only downloaded content can identify
    a reusable file. Missing or changed archives produce separate recovery files.
    Callers limit this list to the requested directory for explicit downloads.
    ``on_publish`` records a hash-bound intent before atomic publication; ``on_result``
    records completion. Together they let the caller recover publication interruptions.
    """
    task_id = safe_id(data.get("task_id", "unknown"))
    results = data.get("results")
    if not isinstance(results, list) or not results:
        raise AutoDLError(f"Task {task_id} returned no downloadable results")
    destination = resolve_media_path(destination, root)
    destination.mkdir(parents=True, exist_ok=True)
    owner = project_owner(destination, root=root)
    candidates = []
    for path in existing_files or []:
        path = resolve_media_path(path, root)
        if (
            project_owner(path, root=root) == owner
            and (owner is not None or path.is_relative_to(destination))
        ):
            candidates.append(path)
    saved = []
    # This client has no Token, including when a result URL redirects to a CDN.
    with httpx.Client(timeout=120, follow_redirects=True, transport=transport) as client:
        for index, result in enumerate(results, 1):
            item = {"url": result} if isinstance(result, str) else result
            if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                raise AutoDLError("Result has no downloadable URL")
            parsed = urlsplit(item["url"])
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
            ):
                raise AutoDLError("Result URL must be HTTPS without embedded credentials")
            extension = str(item.get("file_type") or Path(parsed.path).suffix.lstrip(".")).lower()
            if extension not in EXTENSIONS:
                extension = {"video": "mp4", "audio": "wav", "image": "png"}.get(
                    item.get("type"), "bin"
                )
            target = destination / f"{task_id}_{index:02d}.{extension}"
            try:
                # A unique directory avoids touching any pre-existing .part file,
                # including a hard link to source media or another in-flight run.
                with tempfile.TemporaryDirectory(prefix=f".{task_id}-", dir=destination) as folder:
                    temporary = Path(folder) / "download.part"
                    with client.stream("GET", item["url"]) as response:
                        response.raise_for_status()
                        content_type = response.headers.get("content-type", "").lower()
                        if "text/html" in content_type or "application/json" in content_type:
                            raise AutoDLError(
                                "Download returned an error document instead of media"
                            )
                        length = response.headers.get("content-length")
                        if length and int(length) > max_bytes:
                            raise AutoDLError("Download exceeds the configured size limit")
                        total = 0
                        digest = hashlib.sha256()
                        with temporary.open("wb") as output:
                            for chunk in response.iter_bytes():
                                total += len(chunk)
                                if total > max_bytes:
                                    raise AutoDLError("Download exceeds the configured size limit")
                                digest.update(chunk)
                                output.write(chunk)
                        if total == 0:
                            raise AutoDLError("Download returned an empty file")
                    target = _publish_result(
                        temporary, target, candidates, total, digest.digest(), on_publish
                    )
                    if on_result is not None:
                        on_result(target, total, digest.hexdigest())
            except (httpx.HTTPError, OSError, ValueError) as exc:
                raise AutoDLError(
                    f"Download failed ({type(exc).__name__}); query the task for a fresh URL"
                ) from None
            saved.append(target)
            candidates.append(target)
    return saved


def _same_content(path: Path, size: int, digest: bytes) -> bool:
    try:
        if not path.is_file() or path.stat().st_size != size:
            return False
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            actual = hashlib.file_digest(stream, "sha256").digest()
            after = path.stat()
        return actual == digest and (
            before.st_ino, before.st_size, before.st_mtime_ns
        ) == (after.st_ino, after.st_size, after.st_mtime_ns)
    except OSError:
        return False


def _publish_result(
    temporary: Path, target: Path, candidates: list[Path], size: int, digest: bytes,
    on_publish: Callable[[Path, int, str], None] | None = None,
) -> Path:
    for candidate in candidates:
        if _same_content(candidate, size, digest):
            return candidate
    original = target
    version = 1
    while True:
        # Do not follow a link outside the requested output location for reuse.
        if not target.is_symlink() and _same_content(target, size, digest):
            return target
        if target.exists() or target.is_symlink():
            version += 1
            target = original.with_name(
                f"{original.stem}-下载恢复-版本{version:02}{original.suffix}"
            )
            continue
        if on_publish is not None:
            on_publish(target, size, digest.hex())
        try:
            # Same-filesystem publication is atomic and fails if anything exists.
            os.link(temporary, target)
            return target
        except FileExistsError:
            # Recheck the winner's bytes before selecting a new version.
            continue
