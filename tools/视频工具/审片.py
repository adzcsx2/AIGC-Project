"""Loopback-only review server. Media stays in place; records bind to content hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import mimetypes
import os
import re
import secrets
import threading
import time
import zlib
from contextlib import ExitStack, contextmanager
from datetime import UTC
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from video_tools import ROOT, decode_check, ffmpeg, probe, sha, write_json
from whitebox_core import validate_implementation

from autodl_video.paths import project_owner
from autodl_video.read_guard import guarded_read


def owned_path(project, path):
    """Resolve every read/write target, including children of existing junctions."""
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(project) or project_owner(resolved, root=ROOT) != project:
        raise ValueError("审片路径必须属于当前作品，不能经目录联接跨作品")
    return resolved


def write_owned_json(project, path, value):
    path = owned_path(project, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(owned_path(project, path), value)


@contextmanager
def record_lock(records, project=None, *, label="审片记录", timeout=10):
    """Lock a review artifact across services; process exit releases the OS lock."""
    project = project or project_owner(records, root=ROOT)
    if project is None:
        raise ValueError("审片记录必须属于已登记作品")
    records = owned_path(project, records)
    lock_path = owned_path(project, records.with_name(records.name + ".lock"))
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with owned_path(project, lock_path).open("a+b") as handle:
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise ValueError(f"{label}正被其他服务保存，请重试") from exc
                time.sleep(0.025)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def review_seconds(value):
    """Accept JSON numbers only, then persist the validated representation."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("记录时间码必须是有限数值，不能使用字符串或布尔值")
    try:
        seconds = float(value)
    except OverflowError as exc:
        raise ValueError("记录时间码必须是有限数值") from exc
    if not math.isfinite(seconds):
        raise ValueError("记录时间码必须是有限数值")
    return seconds


def read_png(path, binding=None):
    """Require a complete, checksum-valid and decodable PNG before serving it."""
    with guarded_read(path) as stream:
        data = stream.read()
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("检查帧缓存不是 PNG")
        offset, saw_header, saw_data = 8, False, False
        bindings = []
        while offset + 12 <= len(data):
            length = int.from_bytes(data[offset : offset + 4], "big")
            end = offset + 12 + length
            if end > len(data):
                break
            kind = data[offset + 4 : offset + 8]
            checksum = int.from_bytes(data[end - 4 : end], "big")
            if zlib.crc32(data[offset + 4 : end - 4]) != checksum:
                break
            if not saw_header:
                if kind != b"IHDR" or length != 13:
                    break
                saw_header = True
            if kind == b"IDAT":
                saw_data = True
            if kind == b"tEXt" and data[offset + 8 : end - 4].startswith(b"autodl-source\0"):
                bindings.append(data[offset + 8 : end - 4])
            if kind == b"IEND":
                if length or end != len(data) or not saw_data:
                    break
                if binding is not None and bindings != [binding]:
                    raise ValueError("检查帧缺少当前受保护源版本绑定，请重新提取")
                decode_check(path)
                return data
            offset = end
        raise ValueError("检查帧缓存不完整或损坏")


def frame_bytes(project, dest, source, frame, source_sha256):
    """Publish only complete frames; every service shares the same per-frame lock."""
    binding = b"autodl-source\0" + json.dumps(
        {"schema": 2, "sha256": source_sha256, "frame": frame}, sort_keys=True
    ).encode("ascii")
    with record_lock(dest, project, label="检查帧", timeout=120):
        dest = owned_path(project, dest)
        if dest.exists():
            try:
                return read_png(dest, binding)
            except ValueError:
                pass  # Old interrupted writes are repaired, never treated as cache hits.
        data = ffmpeg(
            [
                "-i",
                source,
                "-vf",
                f"select=eq(n\\,{frame})",
                "-frames:v",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "png",
                "-",
            ]
        )
        if not data:
            raise ValueError("帧不存在")
        # Bind the source identity inside the same atomic PNG, not a sidecar that
        # could disagree with its image after a crash. Legacy unbound frames miss.
        chunk = b"tEXt" + binding
        chunk = len(binding).to_bytes(4, "big") + chunk + zlib.crc32(chunk).to_bytes(4, "big")
        data = data[:-12] + chunk + data[-12:]
        temporary = owned_path(project, dest.with_name(f".{dest.stem}-{secrets.token_hex(8)}.tmp"))
        created = False
        try:
            with temporary.open("xb") as stream:
                created = True
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            data = read_png(owned_path(project, temporary), binding)
            owned_path(project, temporary).replace(owned_path(project, dest))
            return data
        finally:
            if created:
                owned_path(project, temporary).unlink(missing_ok=True)


def prepare(project, videos, edit_record=None, *, dependencies=(), implementation=()):
    project = Path(project).resolve()
    if not (project / "project.yaml").exists():
        raise ValueError("先建立作品 project.yaml")
    dependencies = list(dependencies)
    implementation = validate_implementation(list(implementation)) if implementation else []
    for item in dependencies:
        path = owned_path(project, item["path"])
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError("审片依据不属于当前作品或已变化")
    for item in implementation:
        if sha(item["path"]) != item["sha256"]:
            raise ValueError("白模工具实现已变化，请重新检查")
    media = []
    for i, file in enumerate(videos):
        path = owned_path(project, file)
        with guarded_read(path) as stream:
            if owned_path(project, file) != path or Path(stream.name) != path:
                raise ValueError("审片素材路径已变化，请重试")
            meta = probe(path)
            decode_check(path)
            media.append(
                {
                    "id": str(i),
                    "path": str(path),
                    "sha256": hashlib.file_digest(stream, "sha256").hexdigest(),
                    "name": path.name,
                    "duration": meta["duration"],
                    "fps": meta["video"]["avg_frame_rate"] if meta["video"] else None,
                    "technical": "decode_passed",
                }
            )
    seams = []
    if edit_record:
        edit_record = owned_path(project, edit_record)
        record = json.loads(edit_record.read_text("utf-8"))
        # Bind seam timeline to exactly one listed assembled movie.
        matching = [m for m in media if m["sha256"] == record.get("sha256")]
        if not matching:
            raise ValueError("剪辑记录不属于所选视频，不能复用接缝时间")
        seams = [{**s, "media_id": matching[0]["id"]} for s in record.get("seams", [])]
    directory = owned_path(project, project / "05-检查与验收/网页审片")
    config = owned_path(project, directory / "审片会话.json")
    record_name = "审片记录.json"
    if dependencies or implementation:
        signature = hashlib.sha256(
            json.dumps([dependencies, implementation], sort_keys=True).encode()
        ).hexdigest()[:16]
        record_name = f"白模审片记录-{signature}.json"
    records = owned_path(project, directory / record_name)
    directory.mkdir(parents=True, exist_ok=True)
    # Reuse a session only for the same sources; changed hash keeps prior review history.
    if config.exists():
        old = json.loads(config.read_text("utf-8"))
        if (
            old.get("implementation", []) != implementation
            or old.get("dependencies", []) != dependencies
            or [(m["id"], m["sha256"]) for m in old["media"]]
            != [(m["id"], m["sha256"]) for m in media]
        ):
            archive = owned_path(project, directory / "历史会话")
            archive.mkdir(exist_ok=True)
            target = owned_path(project, archive / f"审片会话-{secrets.token_hex(4)}.json")
            owned_path(project, config).rename(target)
    write_owned_json(
        project,
        config,
        {
            "schema_version": 1,
            "project": str(project),
            "media": media,
            "seams": seams,
            "records": str(records),
            "dependencies": dependencies,
            "implementation": implementation,
            "binding_kind": "whitebox" if implementation else "media",
        },
    )
    return config


def byte_range(header, size):
    if not header:
        return 0, size - 1, False
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header)
    if not match or not any(match.groups()) or size == 0:
        raise ValueError("invalid range")
    a, b = match.groups()
    if not a:
        length = int(b)
        if not length:
            raise ValueError("invalid suffix range")
        start, end = max(0, size - length), size - 1
    else:
        start, end = int(a), min(int(b) if b else size - 1, size - 1)
    if start >= size or start > end:
        raise ValueError("unsatisfiable range")
    return start, end, True


def file_stamp(info):
    """Track both file identity and changes, including same-sized replacements."""
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def server(config_path, port=8767):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text("utf-8"))
    project = Path(config["project"]).resolve()
    owned_path(project, config_path)
    implementation = config.get("implementation", [])
    if implementation or config.get("binding_kind") == "whitebox":
        implementation = validate_implementation(implementation)
    trusted_code = {Path(item["path"]) for item in implementation}
    media = {m["id"]: m for m in config["media"]}
    token = secrets.token_urlsafe(32)
    lock = threading.Lock()
    records = owned_path(project, config["records"])
    verified = {}
    verification_lock = threading.Lock()

    @contextmanager
    def verified_path(item, error, *, code=False):
        # A read lease spans validation AND use. Only hash cache misses serialize;
        # independent readers keep their own handles and can stream concurrently.
        original = Path(item["path"])
        path = original.resolve()
        if code:
            if path != original or path not in trusted_code:
                raise ValueError(error)
        else:
            path = owned_path(project, path)
        with guarded_read(path) as stream:
            with verification_lock:
                info = os.fstat(stream.fileno())
                stamp = file_stamp(info)
                key = (path, item["sha256"])
                if verified.get(key) != stamp:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                    if digest != item["sha256"]:
                        raise ValueError(error)
                if (
                    original.resolve() != path
                    or Path(stream.name) != path
                    or file_stamp(path.stat())[:4] != stamp[:4]
                    or file_stamp(os.fstat(stream.fileno())) != stamp
                ):
                    raise ValueError(error)
                verified[key] = stamp
            stream.seek(0)
            yield stream

    @contextmanager
    def current(item):
        with ExitStack() as readers:
            for dependency in config.get("dependencies", []):
                readers.enter_context(
                    verified_path(
                        dependency, "白模计划/来源已变化；审片会话失效，请重新检查并prepare"
                    )
                )
            for dependency in implementation:
                readers.enter_context(
                    verified_path(
                        dependency, "白模工具实现已变化；审片会话失效，请重新检查", code=True
                    )
                )
            yield readers.enter_context(
                verified_path(item, "视频已变化或素材路径越界；当前审片会话失效，请重新 prepare")
            )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Do not leak bearer token in access logs.

        def send_data(self, body, mime="application/json", status=200):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def authorized(self):
            host = self.headers.get("Host", "").split(":")[0]
            params = parse_qs(urlsplit(self.path).query)
            supplied = self.headers.get("X-Review-Token", params.get("token", [""])[0])
            return host in {"127.0.0.1", "localhost"} and secrets.compare_digest(supplied, token)

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            if not self.authorized():
                return self.send_data({"error": "未授权"}, status=403)
            url = urlsplit(self.path)
            params = parse_qs(url.query)
            try:
                with ExitStack() as readers:
                    if url.path == "/":
                        html = (Path(__file__).parent / "审片网页/index.html").read_bytes()
                        return self.send_data(html, "text/html; charset=utf-8")
                    if url.path == "/api/session":
                        for item in media.values():
                            readers.enter_context(current(item))
                        journal = owned_path(project, records)
                        saved = json.loads(journal.read_text("utf-8")) if journal.exists() else []
                        # Release read leases before publishing a complete response:
                        # the client may edit the plan as soon as it receives it.
                        readers.close()
                        return self.send_data({**config, "entries": saved})
                    key = params.get("id", [""])[0]
                    if key not in media:
                        return self.send_data({"error": "未知视频"}, status=404)
                    item = media[key]
                    stream = readers.enter_context(current(item))
                    path = Path(stream.name)
                    if url.path == "/api/frame":
                        frame = int(params.get("frame", ["0"])[0])
                        if not 0 <= frame <= 1000000:
                            raise ValueError("帧号越界")
                        cache = owned_path(project, config_path.parent / "检查帧" / item["sha256"])
                        cache.mkdir(parents=True, exist_ok=True)
                        dest = owned_path(project, cache / f"帧-{frame:08}.png")
                        data = frame_bytes(project, dest, path, frame, item["sha256"])
                        readers.close()
                        return self.send_data(data, "image/png")
                    if url.path != "/media":
                        readers.close()
                        return self.send_data({"error": "Not found"}, status=404)
                    size = os.fstat(stream.fileno()).st_size
                    try:
                        start, end, partial = byte_range(self.headers.get("Range"), size)
                    except ValueError:
                        readers.close()
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{size}")
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                    if self.command == "HEAD" or end < start:
                        readers.close()
                    self.send_response(206 if partial else 200)
                    self.send_header(
                        "Content-Type",
                        mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    )
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Length", str(end - start + 1))
                    self.send_header("Cache-Control", "no-store")
                    if partial:
                        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                    self.end_headers()
                    if self.command != "HEAD" and end >= start:
                        stream.seek(start)
                        remaining = end - start + 1
                        while remaining:
                            data = stream.read(min(1024 * 1024, remaining))
                            if not data:
                                break
                            remaining -= len(data)
                            if not remaining:
                                # All remaining source bytes are now immutable in
                                # memory. Release before the client can see EOF.
                                readers.close()
                            self.wfile.write(data)
            except (ValueError, OSError, KeyError) as exc:
                self.send_data({"error": str(exc)}, status=409)

        def do_POST(self):
            if not self.authorized():
                return self.send_data({"error": "未授权"}, status=403)
            if urlsplit(self.path).path != "/api/review":
                return self.send_data({"error": "Not found"}, status=404)
            try:
                with ExitStack() as readers:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 32768:
                        raise ValueError("记录大小无效")
                    data = json.loads(self.rfile.read(length))
                    item = media[data["media_id"]]
                    readers.enter_context(current(item))
                    if data.get("sha256") != item["sha256"]:
                        raise ValueError("记录不属于当前视频版本")
                    if data.get("dimension") not in {
                        "stills",
                        "dynamic",
                        "listening",
                        "user_acceptance",
                    }:
                        raise ValueError("验收维度无效")
                    if data.get("verdict") not in {"passed", "failed", "pending"}:
                        raise ValueError("验收状态无效")
                    if not isinstance(data.get("note"), str) or not data["note"].strip():
                        raise ValueError("请记录具体依据或问题")
                    start = review_seconds(data["start_seconds"])
                    end = review_seconds(data["end_seconds"])
                    if not 0 <= start <= end <= item["duration"]:
                        raise ValueError("记录时间范围越界")
                    data.update(start_seconds=start, end_seconds=end)
                    if not data.get("reviewer"):
                        raise ValueError("请填写实际审片者")
                    from datetime import datetime

                    data["recorded_at"] = datetime.now(UTC).isoformat()
                    data["id"] = secrets.token_hex(8)
                    with lock, record_lock(records, project):
                        journal = owned_path(project, records)
                        saved = json.loads(journal.read_text("utf-8")) if journal.exists() else []
                        if not isinstance(saved, list):
                            raise ValueError("历史审片记录格式无效，保留原文件")
                        saved.append(data)
                        write_owned_json(project, records, saved)
                    readers.close()
                    self.send_data(data)
            except (ValueError, KeyError, TypeError, OSError) as exc:
                self.send_data({"error": str(exc)}, status=400)

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.review_url = f"http://127.0.0.1:{httpd.server_port}/?token={token}"
    return httpd


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--project", required=True)
    p.add_argument("--video", action="append", required=True)
    p.add_argument("--edit-record")
    p = sub.add_parser("serve")
    p.add_argument("config")
    p.add_argument("--port", type=int, default=8767)
    p.add_argument("--url-file")
    args = ap.parse_args()
    if args.command == "prepare":
        print(prepare(args.project, args.video, args.edit_record))
    else:
        url_path = None
        if args.url_file:
            config = json.loads(Path(args.config).read_text("utf-8"))
            url_path = owned_path(Path(config["project"]).resolve(), args.url_file)
        httpd = server(args.config, args.port)
        try:
            if url_path:
                owned_path(Path(config["project"]).resolve(), url_path).write_text(
                    httpd.review_url, encoding="utf-8"
                )
            print(httpd.review_url, flush=True)
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.server_close()


if __name__ == "__main__":
    main()
