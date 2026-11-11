"""Small local video operations; all media commands use argv, never a shell."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from bisect import bisect_left
from fractions import Fraction
from pathlib import Path

import yaml

from autodl_video.errors import AutoDLError
from autodl_video.media_inputs import MediaInputs
from autodl_video.paths import ensure_project_output, project_owner, resolve_media_path

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(args, cwd=None):
    result = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", errors="replace")[-5000:])
    return result.stdout


def executable(name):
    value = shutil.which(name)
    if not value:
        raise ValueError(f"未找到本机 {name}")
    return value


def ffmpeg(args, cwd=None):
    return run([executable("ffmpeg"), "-hide_banner", "-v", "error", "-nostdin", *args], cwd)


def probe(path):
    data = json.loads(
        run(
            [
                executable("ffprobe"),
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                Path(path).resolve(),
            ]
        )
    )
    data["duration"] = float(data["format"].get("duration", 0))
    data["video"] = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    data["audio"] = [s for s in data["streams"] if s["codec_type"] == "audio"]
    return data


def read_yaml(path):
    data = yaml.safe_load(Path(path).read_text("utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("需要 YAML 对象")
    return data


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, suffix=".tmp", encoding="utf-8", delete=False
    ) as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        temporary = Path(stream.name)
    temporary.replace(path)


def media_record_path(output, kind):
    """Keep the complete media filename so different containers have distinct records."""
    if kind not in {"剪辑", "水印", "混音", "制作"}:
        raise ValueError("未知媒体记录类型")
    output = Path(output)
    return output.with_name(f"{output.name}.{kind}记录.json")


def prepare_media_record(output, kind):
    """Check immutable-record ownership and collisions before rendering any output."""
    output = Path(output)
    candidate = media_record_path(output, kind)
    path = ensure_project_output(candidate, output, root=ROOT)
    if os.path.lexists(candidate) or os.path.lexists(path):
        raise ValueError(f"媒体记录已存在，保留原记录并另存版本：{candidate}")
    return path


def write_media_record(output, kind, value):
    """Atomically publish a complete record without replacing another writer's file."""
    path = prepare_media_record(output, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", dir=path.parent, suffix=".tmp", encoding="utf-8", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2)
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            raise ValueError(f"媒体记录被其他任务占用，未覆盖：{path}") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def write_yaml(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, suffix=".tmp", encoding="utf-8", delete=False
    ) as stream:
        yaml.safe_dump(value, stream, allow_unicode=True, sort_keys=False)
        temporary = Path(stream.name)
    temporary.replace(path)


def resolve(base, value):
    return resolve_media_path(Path(base) / value, ROOT)


def output_path(source, output, label, *, sources=()):
    source = resolve_media_path(Path(source), ROOT)
    sources = tuple(Path(item) for item in sources)
    owners = [project_owner(path, root=ROOT) for path in (source, *sources)]
    if any(owner is not None for owner in owners) and any(owner is None for owner in owners):
        raise AutoDLError("已登记作品的配置和全部输入须先归档到同一作品；不能混入未归档文件")
    if output:
        dest = ensure_project_output(Path(output), source, *sources, root=ROOT)
        if dest.exists() or dest == source:
            raise ValueError(f"输出已存在，保留原文件：{dest}")
    else:
        dest = source.with_name(f"{source.stem}-{label}{source.suffix}")
        count = 2
        while dest.exists():
            dest = source.with_name(f"{source.stem}-{label}-版本{count:02}{source.suffix}")
            count += 1
        dest = ensure_project_output(dest, source, *sources, root=ROOT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    return dest


def number(value, name, minimum=0, maximum=float("inf")):
    if isinstance(value, bool):
        raise ValueError(f"{name} 必须为数字")
    n = float(value)
    if not math.isfinite(n) or not minimum <= n <= maximum:
        raise ValueError(f"{name} 超出范围")
    return n


def decode_check(path):
    ffmpeg(["-xerror", "-i", path, "-map", "0:v?", "-map", "0:a?", "-f", "null", "-"])


def display_geometry(video):
    """Return the decoded display canvas and SAR after FFmpeg's autorotation."""
    rotation = float(video.get("tags", {}).get("rotate", 0))
    for side in video.get("side_data_list", []):
        rotation = float(side.get("rotation", rotation))
    if not math.isfinite(rotation) or rotation % 90:
        raise ValueError("非90度旋转需要先明确输出画布")
    width, height = video["width"], video["height"]
    ratio = video.get("sample_aspect_ratio", "1:1")
    sar = Fraction(ratio.replace(":", "/")) if ratio not in (None, "N/A", "0:1") else Fraction(1)
    if round(rotation) % 180:
        width, height, sar = height, width, 1 / sar
    return width, height, sar


def frame_timeline(path, video):
    """Read presentation timestamps from decoded frames, in the stream's time base."""
    data = json.loads(
        run(
            [
                executable("ffprobe"),
                "-v",
                "error",
                "-select_streams",
                str(video["index"]),
                "-show_frames",
                "-show_entries",
                "frame=best_effort_timestamp,duration,pkt_duration",
                "-of",
                "json",
                path,
            ]
        )
    )
    base = Fraction(video["time_base"])
    frames = data.get("frames", [])
    if not frames or any("best_effort_timestamp" not in frame for frame in frames):
        raise ValueError("无法取得完整解码帧时间戳")
    points = [int(frame["best_effort_timestamp"]) * base for frame in frames]
    if any(b <= a for a, b in zip(points, points[1:], strict=False)):
        raise ValueError("视频帧时间戳不是严格递增")
    duration = int(frames[-1].get("duration", frames[-1].get("pkt_duration", 0))) * base
    return [point - points[0] for point in points], duration, base


def validate_video_timeline(reference, output, before, after):
    old, old_duration, old_base = frame_timeline(reference, before)
    new, new_duration, new_base = frame_timeline(output, after)
    if len(old) != len(new):
        raise ValueError("输出解码帧数与输入不一致")
    # Each relative timestamp includes two container-quantized endpoints. Cap
    # the allowance below a quarter frame so coarse time bases cannot hide edits.
    tolerance = 2 * (old_base + new_base)
    steps = [b - a for points in (old, new) for a, b in zip(points, points[1:], strict=False)]
    if steps:
        tolerance = min(tolerance, min(steps) / 4)
    if any(abs(a - b) > tolerance for a, b in zip(old, new, strict=True)):
        raise ValueError("输出逐帧时间戳与输入不一致")
    if old_duration > 0 and new_duration > 0 and abs(old_duration - new_duration) > tolerance:
        raise ValueError("输出尾帧时长与输入不一致")


def publish(temp, dest, *, reference=None, copy_audio=False, record=None):
    decode_check(temp)
    after = probe(temp)
    if reference:
        before = probe(reference)
        if abs(after["duration"] - before["duration"]) > 0.12:
            raise ValueError("输出时长与输入不一致")
        if bool(before["video"]) != bool(after["video"]):
            raise ValueError("视频轨未完整保留")
        if before["video"]:
            if display_geometry(after["video"]) != display_geometry(before["video"]):
                raise ValueError("输出显示画布或像素比例与输入不一致")
            validate_video_timeline(reference, temp, before["video"], after["video"])
        if copy_audio and [(s["codec_name"], s["channels"]) for s in after["audio"]] != [
            (s["codec_name"], s["channels"]) for s in before["audio"]
        ]:
            raise ValueError("音轨未完整保留")
        if copy_audio:
            for source_track, output_track in zip(before["audio"], after["audio"], strict=True):
                old_offset = float(source_track.get("start_time", 0)) - float(
                    before["video"].get("start_time", 0)
                )
                new_offset = float(output_track.get("start_time", 0)) - float(
                    after["video"].get("start_time", 0)
                )
                if abs(new_offset - old_offset) > 0.025:
                    raise ValueError("音画相对起点改变")
    if Path(dest).exists():
        raise ValueError("输出路径被其他任务占用")
    record_path = None
    if record is not None:
        kind, build_record = record
        record_path = write_media_record(dest, kind, build_record(after))
    # Windows rename fails if the destination exists; never replace source media.
    try:
        Path(temp).rename(dest)
    except BaseException:
        if record_path is not None:
            record_path.unlink(missing_ok=True)
        raise
    return after


def drawtext_size(layout, folder, width, height):
    """Measure using the exact font, shaping and textfile used by the export."""
    process = subprocess.run(
        [
            executable("ffmpeg"),
            "-hide_banner",
            "-nostdin",
            "-nostats",
            "-loglevel",
            "repeat+info",
            "-f",
            "lavfi",
            "-i",
            f"color=s={width}x{height}:r=1:d=1",
            "-frames:v",
            "1",
            "-vf",
            layout + ":x='print(text_w);print(text_h);0':y=0",
            "-f",
            "null",
            "-",
        ],
        cwd=folder,
        capture_output=True,
    )
    log = process.stderr.decode("utf-8", errors="replace")
    if process.returncode:
        raise ValueError(log[-5000:])
    try:
        values = [
            float(value) for value in re.findall(r"^\[Eval @ [^\]]+\][ \t]+([^\r\n]+)", log, re.M)
        ]
    except ValueError as error:
        raise ValueError("无法解析水印实际排版尺寸，未导出") from error
    if (
        len(values) < 2
        or len(values) % 2
        or any(not math.isfinite(value) or value <= 0 for value in values)
        or any(values[i : i + 2] != values[:2] for i in range(0, len(values), 2))
    ):
        raise ValueError("无法取得水印实际排版尺寸或没有可绘制文字，未导出")
    return math.ceil(values[0]), math.ceil(values[1])


def watermark(
    source,
    output=None,
    *,
    text="@CallMeQueenAI",
    opacity=0.45,
    period=40,
    margin=24,
    font_size=None,
    font="C:/Windows/Fonts/arial.ttf",
):
    with MediaInputs() as captured:
        return _watermark(
            source,
            output,
            captured=captured,
            text=text,
            opacity=opacity,
            period=period,
            margin=margin,
            font_size=font_size,
            font=font,
        )


def _watermark(source, output, *, captured, text, opacity, period, margin, font_size, font):
    source = resolve_media_path(Path(source), ROOT)
    source_input = captured.capture(source)
    meta = probe(source_input)
    if not meta["video"]:
        raise ValueError("输入没有视频")
    if meta["video"].get("color_transfer") in {"smpte2084", "arib-std-b67"}:
        raise ValueError("HDR 输入需要专用色彩流程，不能按 SDR 导出")
    if not text or len(text) > 128 or "\n" in text:
        raise ValueError("水印应为 1–128 字的单行文本")
    opacity = number(opacity, "opacity", 0, 1)
    period = number(period, "period", 1, 36000)
    w, h, _ = display_geometry(meta["video"])
    margin = number(margin, "margin", 0, min(w, h) / 4)
    size = int(number(font_size or max(12, round(h * 0.028)), "font_size", 6, h / 4))
    dest = output_path(source, output, "移动水印")
    prepare_media_record(dest, "水印")
    with tempfile.TemporaryDirectory(prefix=".水印-", dir=dest.parent) as folder:
        folder = Path(folder)
        (folder / "text.txt").write_text(text, encoding="utf-8")
        shutil.copyfile(font, folder / "font.ttf")
        layout = f"drawtext=fontfile=font.ttf:textfile=text.txt:expansion=none:fontsize={size}"
        text_width, text_height = drawtext_size(layout, folder, w, h)
        border = 1
        # drawtext's raster clipping region extends by borderw + 1 on each side
        # for glyph bearings/subpixel rounding (vf_drawtext.c, draw_text). Reserve
        # that actual renderer bound, including the outline, inside the margin.
        raster_padding = border + 1
        inset = margin + raster_padding
        if text_width + 2 * inset > w or text_height + 2 * inset > h:
            raise ValueError("水印实际排版与轮廓超出画布边距，请减小字号、边距或缩短文字")
        if text_width + text_height + 4 * inset >= w + h:
            raise ValueError("水印与边距占满画布，无法沿边移动")
        lx, ly = f"(w-tw-2*{inset})", f"(h-th-2*{inset})"
        p = f"mod(t*2*({lx}+{ly})/{period},2*({lx}+{ly}))"
        x = f"{inset}+if(lt({p},{lx}),{p},if(lt({p},{lx}+{ly}),{lx},max(0,2*{lx}+{ly}-{p})))"
        y = (
            f"{inset}+if(lt({p},{lx}),0,if(lt({p},{lx}+{ly}),{p}-{lx},"
            f"if(lt({p},2*{lx}+{ly}),{ly},2*({lx}+{ly})-{p})))"
        )
        effect = (
            f"{layout}:fontcolor=white@{opacity}:borderw={border}:"
            f"bordercolor=black@0.4:x='{x}':y='{y}'"
        )
        temp = folder / f"export{dest.suffix}"
        ffmpeg(
            [
                "-i",
                source_input,
                "-map",
                "0",
                "-c",
                "copy",
                "-c:v:0",
                "libx264",
                "-crf",
                "18",
                "-preset",
                "medium",
                "-vf",
                effect,
                "-fps_mode",
                "passthrough",
                temp,
            ],
            cwd=folder,
        )

        def build_record(after):
            # publish() has now completed every decode and timeline check.
            captured.check_current()
            return {
                "source": str(source),
                "source_sha256": captured.digest(source),
                "input_binding_method": "private_file_snapshots",
                "input_bindings": captured.bindings(),
                "output": str(dest),
                "output_sha256": sha(temp),
                "text": text,
                "text_width_pixels": text_width,
                "text_height_pixels": text_height,
                "raster_padding_pixels": raster_padding,
                "margin_pixels": margin,
                "font_size": size,
                "period_seconds": period,
                "opacity": opacity,
                "video_reencoded": True,
                "audio_stream_copy": True,
                "duration": after["duration"],
                "dynamic_review": "pending",
                "listening": "pending",
            }

        publish(temp, dest, reference=source_input, copy_audio=True, record=("水印", build_record))
    return dest


def extract_frames(source, output, *, interval=1, frame=None):
    with MediaInputs() as captured:
        return _extract_frames(source, output, interval=interval, frame=frame, captured=captured)


def _extract_frames(source, output, *, interval, frame, captured):
    source = resolve_media_path(Path(source), ROOT)
    source_input = captured.capture(source)
    output = ensure_project_output(Path(output), source, root=ROOT)
    if output.exists():
        raise ValueError("抽帧目录已存在，请另存版本")
    interval = number(interval, "interval", 0.01, 3600)
    if frame is not None:
        if isinstance(frame, bool) or not isinstance(frame, int) or frame < 0:
            raise ValueError("帧号必须是非负整数")
        effect = f"select=eq(n\\,{frame})"
        args = ["-frames:v", "1"]
    else:
        effect = f"fps=1/{interval}"
        args = []
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".抽帧-", dir=output.parent) as folder:
        staging = Path(folder) / "frames"
        staging.mkdir()
        ffmpeg(
            [
                "-i",
                source_input,
                "-vf",
                effect,
                "-fps_mode",
                "vfr",
                *args,
                staging / "检查帧-%06d.png",
            ]
        )
        files = list(staging.glob("*.png"))
        if not files:
            raise ValueError("指定帧不存在")
        captured.check_current()
        write_json(
            staging / "抽帧记录.json",
            {
                "source": str(source),
                "sha256": captured.digest(source),
                "input_binding_method": "private_file_snapshots",
                "input_bindings": captured.bindings(),
                "frame_zero_based": frame,
                "interval_seconds": interval,
                "count": len(files),
                "visual_review": "pending",
            },
        )
        if output.exists():
            raise ValueError("抽帧输出路径被其他任务占用")
        staging.rename(output)
    return output


def audio_speed_filter(speed, sample_rate):
    """Change sample timing, then restore pitch without discarding high frequencies."""
    if speed == 1:
        return "", sample_rate, 1.0
    filters = ffmpeg(["-filters"]).decode("utf-8", errors="replace")
    if not any(
        len(row.split()) > 1 and row.split()[1] == "rubberband" for row in filters.splitlines()
    ):
        raise ValueError("变速保持音高需要本机 FFmpeg 的 rubberband 滤镜；未降级或变调导出")
    retimed_rate = round(sample_rate * speed)
    working_rate = max(sample_rate, retimed_rate)
    # High-speed material must retain its raised Nyquist limit until pitch has
    # been restored; downsampling to 48k first would irreversibly remove treble.
    return (
        f"asetrate={retimed_rate},aresample={working_rate},"
        f"rubberband=tempo=1:pitch={sample_rate / retimed_rate}:"
        "window=short:transients=crisp:detector=percussive:channels=together,"
        "aresample=48000,",
        working_rate,
        retimed_rate / sample_rate,
    )


def edit_interval(source, video, start, end):
    """Resolve requested seconds to decoded frames and their shared AV boundaries."""
    points, tail, base = frame_timeline(source, video)
    first = bisect_left(points, Fraction(str(start)))
    stop = bisect_left(points, Fraction(str(end)))
    if first == stop:
        raise ValueError("裁切区间内没有实际视频帧")
    if stop == len(points) and tail <= 0:
        raise ValueError("无法确定源视频尾帧时长，不能同步裁切音画")
    return {
        "requested_in": start,
        "requested_out": end,
        "in": float(points[first]),
        "out": float(points[stop] if stop < len(points) else points[-1] + tail),
        "source_frame_start": first,
        "source_frame_end_exclusive": stop,
        "source_time_base": str(base),
    }


def validate_edit_audio(path, expected_frames):
    """Reject missing audio coverage before publishing a decoded edit preview."""
    meta = probe(path)
    if not meta["video"] or len(meta["audio"]) != 1:
        raise ValueError("剪辑结果须包含视频和一条完整音轨")
    points, tail, _ = frame_timeline(path, meta["video"])
    if len(points) != expected_frames or tail <= 0:
        raise ValueError("剪辑视频实际帧数或尾帧时长与计划不符")
    expected_end = points[-1] + tail
    track = meta["audio"][0]
    base, sample_rate = Fraction(track["time_base"]), int(track["sample_rate"])
    tolerance = max(2 * base, Fraction(1, sample_rate))
    frames = json.loads(
        run(
            [
                executable("ffprobe"),
                "-v",
                "error",
                "-select_streams",
                str(track["index"]),
                "-show_frames",
                "-show_entries",
                "frame=pts,nb_samples",
                "-of",
                "json",
                path,
            ]
        )
    ).get("frames", [])
    cursor, previous = Fraction(0), None
    for frame in frames:
        if "pts" not in frame or int(frame.get("nb_samples", 0)) <= 0:
            raise ValueError("剪辑音轨缺少实际时间戳或样本数")
        start = int(frame["pts"]) * base
        if previous is not None and start <= previous:
            raise ValueError("剪辑音轨时间戳不是严格递增")
        if start > cursor + tolerance:
            raise ValueError("剪辑音轨内部有未填充的时间戳缺口")
        previous = start
        cursor = max(cursor, start + Fraction(int(frame["nb_samples"]), sample_rate))
    if not frames or cursor < expected_end - tolerance:
        raise ValueError("剪辑音轨未覆盖完整视频时间线")


def edit(config, output):
    with MediaInputs() as captured:
        return _edit(config, output, captured=captured)


def _edit(config, output, *, captured):
    config = resolve_media_path(Path(config), ROOT)
    data = read_yaml(captured.capture(config))
    clips = data.get("clips", [])
    if not clips:
        raise ValueError("clips 不能为空")
    fps = Fraction(str(data.get("fps", 24)))
    if not 1 <= fps <= 240:
        raise ValueError("fps 超出范围")
    args, filters, concat, records = [], [], [], []
    total, dims, aspect_ratio = 0, None, None
    for index, clip in enumerate(clips):
        source = resolve(config.parent, clip["path"])
        source_input = captured.capture(source)
        meta = probe(source_input)
        v = meta["video"]
        if not v:
            raise ValueError("片段没有视频")
        if v.get("color_transfer") in {"smpte2084", "arib-std-b67"}:
            raise ValueError("HDR 片段需要专用色彩流程")
        size = (v["width"], v["height"])
        if dims is not None and size != dims:
            raise ValueError("片段尺寸不同，先明确缩放/裁切方案")
        dims = size
        ratio = Fraction(str(v.get("sample_aspect_ratio", "1:1")).replace(":", "/"))
        if not ratio:
            ratio = Fraction(1)
        if aspect_ratio is not None and ratio != aspect_ratio:
            raise ValueError("片段像素比例不同，先明确缩放/裁切方案")
        aspect_ratio = ratio
        audio_track = clip.get("audio_track")
        if audio_track is None and len(meta["audio"]) > 1:
            raise ValueError(
                "片段有多条音轨，请用 audio_track 明确选择零起算音轨；不自动丢弃默认对白"
            )
        if audio_track is not None and (
            isinstance(audio_track, bool)
            or not isinstance(audio_track, int)
            or not 0 <= audio_track < len(meta["audio"])
        ):
            raise ValueError("audio_track 必须指定存在的零起算音轨")
        if meta["audio"] and audio_track is None:
            audio_track = 0
        start = number(clip.get("in_seconds", 0), "in", 0, meta["duration"])
        end = number(clip.get("out_seconds", meta["duration"]), "out", start, meta["duration"])
        speed = number(clip.get("speed", 1), "speed", 0.125, 8)
        if end <= start:
            raise ValueError("片段出点必须晚于入点")
        selected = edit_interval(source_input, v, start, end)
        requested_duration = (end - start) / speed
        start, end = selected["in"], selected["out"]
        mapped_duration = (end - start) / speed
        output_frames = math.floor(mapped_duration * fps + Fraction(1, 2))
        if output_frames < 1:
            raise ValueError("变速后的区间不足一个输出帧，请调整区间、速度或帧率")
        # Both streams end on the same delivery-frame boundary. The fractional
        # tail is CFR quantization, not a change to the requested playback speed.
        duration = float(output_frames / fps)
        args += ["-i", source_input]
        filters.append(
            f"[{index}:v:0]trim=start_frame={selected['source_frame_start']}:"
            f"end_frame={selected['source_frame_end_exclusive']},"
            f"setpts=(PTS-STARTPTS)/{speed},fps={fps}:start_time=0,"
            f"trim=end_frame={output_frames}[v{index}]"
        )
        if meta["audio"]:
            offset = float(meta["audio"][audio_track].get("start_time", 0)) - float(
                v.get("start_time", 0)
            )
            # Keep internal PTS gaps and the relative AV origin until the resampler
            # has materialized them as silence (or trimmed negative leading audio).
            audio_rate = max(48000, int(meta["audio"][audio_track]["sample_rate"]))
            jitter = max(
                2 * float(Fraction(meta["audio"][audio_track]["time_base"])), 1 / audio_rate
            )
            tempo, working_rate, actual_audio_speed = audio_speed_filter(speed, audio_rate)
            # Retain the source prefix and a short lookahead for the pitch
            # processor, then remove that analysis context from the final output.
            audio_end = end + (0.5 if speed != 1 else 0)
            output_start = start / speed
            filters.append(
                f"[{index}:a:{audio_track}]asetpts=PTS-STARTPTS+({offset})/TB,"
                f"aresample={audio_rate}:async=1:first_pts=0:min_hard_comp={jitter},"
                f"apad,atrim=end={audio_end},asetpts=N/SR/TB,"
                f"{tempo}asetpts=N/SR/TB,apad,"
                f"atrim=start={output_start}:end={output_start + duration},asetpts=N/SR/TB,"
                f"aresample=48000,aformat=channel_layouts=stereo[a{index}]"
            )
        else:
            working_rate, actual_audio_speed = 48000, speed
            filters.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={duration}[a{index}]")
        concat.append(f"[v{index}][a{index}]")
        records.append(
            {
                "source": str(source),
                "sha256": captured.digest(source),
                **selected,
                "speed": speed,
                "audio_track": audio_track,
                "audio_speed": actual_audio_speed,
                "audio_working_sample_rate": working_rate,
                "audio_tempo_method": (
                    "rubberband_pitch_compensated_resampling"
                    if audio_track is not None and speed != 1
                    else "original_pitch"
                ),
                "timeline_start": total,
                "duration": duration,
                "mapped_duration": mapped_duration,
                "output_frames": output_frames,
                "requested_duration": requested_duration,
            }
        )
        total += duration
    filters.append("".join(concat) + f"concat=n={len(clips)}:v=1:a=1[v][a]")
    dest = output_path(config, output, "剪辑预览", sources=[r["source"] for r in records])
    prepare_media_record(dest, "剪辑")
    with tempfile.TemporaryDirectory(prefix=".剪辑-", dir=dest.parent) as folder:
        temp = Path(folder) / f"edit{dest.suffix}"
        process = subprocess.run(
            [
                executable("ffmpeg"),
                "-hide_banner",
                "-nostdin",
                "-v",
                "verbose",
                *args,
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-c:v",
                "libx264",
                "-crf",
                "18",
                "-preset",
                "medium",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(temp),
            ],
            capture_output=True,
        )
        log = process.stderr.decode("utf-8", errors="replace")
        if process.returncode:
            raise ValueError(log[-5000:])
        ends = [int(n) / 1000000 for n in re.findall(r"Segment finished at pts=(\d+)", log)]
        if len(ends) != len(records):
            raise ValueError("未取得真实合成接缝时间，暂不发布剪辑结果")
        for i, item in enumerate(records):
            item["timeline_start"] = ends[i - 1] if i else 0
            item["duration"] = ends[i] - item["timeline_start"]
        validate_edit_audio(temp, sum(item["output_frames"] for item in records))

        def build_record(after):
            # Recheck the config and all clips after publish() finishes validation.
            captured.check_current()
            return {
                "config": str(config),
                "config_sha256": captured.digest(config),
                "input_binding_method": "private_file_snapshots",
                "input_bindings": captured.bindings(),
                "output": str(dest),
                "sha256": sha(temp),
                "clips": records,
                "seams": [
                    {
                        "at_seconds": r["timeline_start"],
                        "source": "pending",
                        "assembled": "pending",
                        "final": "pending",
                    }
                    for r in records[1:]
                ],
                "duration": after["duration"],
                "fps": str(fps),
                "seam_time_basis": "ffmpeg_concat_pts_seconds_before_encoder_frame_rounding",
                "status": "edit_preview",
                "final_interpolation": "pending",
                "dynamic_review": "pending",
                "audio_timeline_coverage": "passed",
                "listening": "pending",
            }

        publish(temp, dest, record=("剪辑", build_record))
    return dest


def main(kind=None):
    defaults = read_yaml(Path(__file__).parent / "默认配置.yaml")["watermark"]
    ap = argparse.ArgumentParser(description="本地视频工具，所有输出保留原片")
    sub = ap.add_subparsers(dest="command", required=True)
    wm = sub.add_parser("watermark")
    wm.add_argument("source")
    wm.add_argument("--output")
    wm.add_argument("--text", default=defaults["text"])
    wm.add_argument("--opacity", type=float, default=defaults["opacity"])
    wm.add_argument("--period", type=float, default=defaults["period_seconds"])
    wm.add_argument("--margin", type=float, default=defaults["margin_pixels"])
    wm.add_argument("--font-size", type=int)
    wm.add_argument("--font", default=defaults["font"])
    frames = sub.add_parser("frames")
    frames.add_argument("source")
    frames.add_argument("--output", required=True)
    frames.add_argument("--interval", type=float, default=1)
    frames.add_argument("--frame", type=int)
    editing = sub.add_parser("edit")
    editing.add_argument("config")
    editing.add_argument("--output", required=True)
    check = sub.add_parser("check")
    check.add_argument("source")
    import sys

    args = vars(ap.parse_args(([kind] + sys.argv[1:]) if kind else None))
    action = args.pop("command")
    if action == "watermark":
        result = watermark(**args)
    elif action == "frames":
        result = extract_frames(**args)
    elif action == "edit":
        result = edit(**args)
    else:
        decode_check(args["source"])
        result = probe(args["source"])
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
