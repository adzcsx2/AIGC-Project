"""Local reference-video inspection, accurate trimming and audio removal."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .errors import AutoDLError
from .paths import ensure_project_output, resolve_media_path


def _tool(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise AutoDLError(f"{name} is required on PATH")
    return executable


def probe_video(path: str | Path, *, root: Path | None = None) -> dict:
    source = resolve_media_path(Path(path), root)
    if not source.is_file():
        raise AutoDLError(f"Reference video not found: {source}")
    try:
        result = subprocess.run(
            [
                _tool("ffprobe"),
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(source),
            ],
            capture_output=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        raise AutoDLError("ffprobe timed out while inspecting the local video") from None
    try:
        data = json.loads(result.stdout)
        video = next(
            s
            for s in data["streams"]
            if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
        )
        duration = float(video.get("duration") or data["format"]["duration"])
        if result.returncode or not math.isfinite(duration) or duration <= 0:
            raise ValueError
        return {
            "path": str(source),
            "duration": duration,
            "width": video["width"],
            "height": video["height"],
            "fps": video.get("avg_frame_rate"),
            "codec": video.get("codec_name"),
            "video_stream_index": video["index"],
            "has_audio": any(s.get("codec_type") == "audio" for s in data["streams"]),
        }
    except (ValueError, KeyError, TypeError, StopIteration):
        raise AutoDLError("ffprobe could not read a video stream with a valid duration") from None


def prepare_reference(
    source: str | Path,
    destination: str | Path,
    *,
    start: float = 0,
    duration: float | None = None,
    root: Path | None = None,
) -> dict:
    for name, value in (("start", start), ("duration", duration)):
        if name == "duration" and value is None:
            continue
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or (value <= 0 if name == "duration" else value < 0)
        ):
            sign = "positive" if name == "duration" else "nonnegative"
            raise AutoDLError(f"{name} must be a finite {sign} number")
    source = resolve_media_path(Path(source), root)
    destination = ensure_project_output(Path(destination), source, root=root)
    if destination.suffix.lower() != ".mp4":
        raise AutoDLError("Prepared reference output must have an .mp4 extension")
    if destination.exists() or source == destination:
        raise AutoDLError("Output already exists; choose a new file to preserve the original")
    info = probe_video(source, root=root)
    if start >= info["duration"] or (
        duration is not None and start + duration > info["duration"] + 0.001
    ):
        raise AutoDLError(
            "Requested clip exceeds source duration; no padding or extension is applied"
        )
    executable = _tool("ffmpeg")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".reference-", dir=destination.parent) as folder:
        output = Path(folder) / "silent.mp4"
        command = [executable, "-nostdin", "-v", "error", "-n"]
        if start:
            command += ["-ss", str(start)]
        command += ["-i", str(source)]
        if duration is not None:
            command += ["-t", str(duration)]
        command += [
            "-map",
            f"0:{info['video_stream_index']}",
            "-an",
            "-sn",
            "-dn",
            "-map_metadata",
            "-1",
        ]
        # Trimming decodes to the requested frame; full-length H.264/HEVC keeps video packets.
        copy = start == 0 and duration is None and info["codec"] in {"h264", "hevc"}
        command += (
            ["-c:v", "copy"]
            if copy
            else ["-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p"]
        )
        command += ["-movflags", "+faststart", str(output)]
        result = subprocess.run(command, capture_output=True)
        if result.returncode:
            raise AutoDLError(
                "ffmpeg reference preparation failed: "
                + result.stderr.decode("utf-8", errors="replace")[-500:]
            )
        prepared = probe_video(output, root=root)
        if prepared["has_audio"]:
            raise AutoDLError("Prepared reference unexpectedly contains audio")
        # Same-filesystem hard link publishes atomically and refuses an existing target.
        os.link(output, destination)
    prepared["path"] = str(destination)
    return {"source": str(source), "start": start, "video_stream_copied": copy, **prepared}
