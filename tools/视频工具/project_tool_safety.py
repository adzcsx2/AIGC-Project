"""Version and publication checks for the project-specific production tools."""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
from pathlib import Path

from whitebox_saved import checked_destination, project_path, publish_new, save_new, sha


def read_json_bound(path):
    """Hash the very bytes parsed, rather than a second independent read."""
    payload = Path(path).read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    value = json.loads(payload.decode("utf-8-sig"))
    require_hash(path, digest)
    return value, digest


def require_hash(path, digest):
    if not Path(path).is_file() or sha(path) != digest:
        raise ValueError(f"来源在处理期间变化：{path}")


def save_checked(bpy, destination, project, validate):
    """Keep Blender's save private until its input versions have been rechecked."""
    destination = checked_destination(destination, project)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".工程保存-", dir=destination.parent) as folder:
        staging = Path(folder) / destination.name
        validate()
        save_new(bpy, staging, project)
        digest = sha(staging)
        validate()
        publish_new(staging, destination, project)
    return digest


def publish_bundle(items, project, *, validate=lambda: None):
    """Publish exclusively; caught failures remove only links created by this call.

    Each item is (private file, public file). No public target is used for encoding
    or serialization. Abrupt process termination cannot guarantee rollback.
    """
    items = [(Path(source), checked_destination(target, project)) for source, target in items]
    if len({target for _, target in items}) != len(items):
        raise ValueError("重复发布目标")
    for _, target in items:
        target.parent.mkdir(parents=True, exist_ok=True)
    published = []
    try:
        for source, target in items:
            validate()
            publish_new(source, target, project)
            published.append((source, target))
        validate()
    except BaseException:
        for source, target in reversed(published):
            if not target.is_symlink() and target.exists() and target.samefile(source):
                target.unlink()
        raise


def json_staging(folder, name, value):
    path = Path(folder) / name
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return path


def write_json_checked(destination, value, project, validate):
    destination = checked_destination(destination, project)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".工程证据-", dir=destination.parent) as folder:
        staging = json_staging(folder, destination.name, value)
        publish_bundle([(staging, destination)], project, validate=validate)


def sequence_binding(scene, blend, digest, frames, project):
    render = scene.render
    if not math.isfinite(render.fps_base) or render.fps_base <= 0 or render.fps <= 0:
        raise ValueError("无效的工程帧率")
    if scene.frame_start > scene.frame_end:
        raise ValueError("无效的工程帧范围")
    return {
        "schema": 1,
        "blend": str(project_path(project, blend).relative_to(project)),
        "blend_sha256": digest,
        "frames": str(project_path(project, frames).relative_to(project)),
        "engine": render.engine,
        "resolution": [render.resolution_x, render.resolution_y],
        "resolution_percentage": render.resolution_percentage,
        "fps": render.fps,
        "fps_base": render.fps_base,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
    }


def require_sequence_binding(record, binding):
    if record.get("sequence") != binding:
        raise ValueError("序列未绑定当前工程版本及渲染规格；请另存新版本")


def validate_sample_timeline(scene, samples):
    """This authored performance uses exact frame numbers on its 24fps timeline."""
    if (
        scene.render.fps != 24
        or scene.render.fps_base != 1
        or scene.frame_start != 1
        or scene.frame_end != 768
    ):
        raise ValueError("本作品几何核查仅支持1–768帧、24fps、fps_base=1的时间轴")
    if any(frame < scene.frame_start or frame > scene.frame_end for frame in samples):
        raise ValueError("采样帧超出工程时间轴")
