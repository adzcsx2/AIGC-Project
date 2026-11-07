"""Durable task records and streaming downloads. Never reuse the authenticated HTTP client."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .catalog import utc_now
from .client import safe_id
from .config import atomic_json
from .errors import AutoDLError

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
        self.directory = root / ".autodl" / "tasks"

    def save(self, task_id: str, **updates: object) -> dict:
        path = self.directory / f"{safe_id(task_id)}.json"
        data = self.read(task_id) if path.exists() else {"task_id": task_id}
        data.update(updates)
        data["updated_at"] = utc_now()
        atomic_json(path, data)
        return data

    def read(self, task_id: str) -> dict:
        path = self.directory / f"{safe_id(task_id)}.json"
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            raise AutoDLError(f"No readable local record for task {task_id}") from None
        if not isinstance(data, dict):
            raise AutoDLError(f"Invalid local record for task {task_id}")
        return data

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
) -> list[Path]:
    task_id = safe_id(data.get("task_id", "unknown"))
    results = data.get("results")
    if not isinstance(results, list) or not results:
        raise AutoDLError(f"Task {task_id} returned no downloadable results")
    destination.mkdir(parents=True, exist_ok=True)
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
            temporary = target.with_suffix(target.suffix + ".part")
            try:
                with client.stream("GET", item["url"]) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").lower()
                    if "text/html" in content_type or "application/json" in content_type:
                        raise AutoDLError("Download returned an error document instead of media")
                    length = response.headers.get("content-length")
                    if length and int(length) > max_bytes:
                        raise AutoDLError("Download exceeds the configured size limit")
                    total = 0
                    with temporary.open("wb") as output:
                        for chunk in response.iter_bytes():
                            total += len(chunk)
                            if total > max_bytes:
                                raise AutoDLError("Download exceeds the configured size limit")
                            output.write(chunk)
                    if total == 0:
                        raise AutoDLError("Download returned an empty file")
                temporary.replace(target)
            except (httpx.HTTPError, OSError, ValueError) as exc:
                raise AutoDLError(
                    f"Download failed ({type(exc).__name__}); query the task for a fresh URL"
                ) from None
            finally:
                temporary.unlink(missing_ok=True)
            saved.append(target)
    return saved
