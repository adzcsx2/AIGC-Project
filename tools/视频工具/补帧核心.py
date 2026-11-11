"""Local RIFE export using the user's installed mpv-lazy runtime."""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import uuid
from fractions import Fraction
from pathlib import Path

from autodl_video.errors import AutoDLError
from autodl_video.media_inputs import MediaInputs, file_digest
from autodl_video.paths import ensure_project_output, resolve_media_path

PROJECT = Path(__file__).resolve().parents[2]
MPV_ROOT = Path(r"D:\mpv_lazy2\mpv\mpv-lazy")
EXTENSIONS = {".mp4", ".mkv", ".mov", ".m4v", ".avi", ".webm", ".ts", ".m2ts", ".flv"}
EXCLUDED = {".git", ".venv", ".agents", ".autodl", "node_modules", "__pycache__"}


class ExportError(RuntimeError):
    pass


def emit(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2), flush=True)


def tool(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise ExportError(f"未找到 {name}，请检查本机已有 FFmpeg 安装及 PATH。")
    return executable


def capture(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, check=False)
    if result.returncode:
        message = result.stderr.decode("utf-8", errors="replace")[-4000:]
        raise ExportError(f"{Path(args[0]).name} 执行失败：{message}")
    return result.stdout.decode("utf-8", errors="replace")


def probe(path: Path, *, packets: bool = False, count: bool = False) -> dict:
    args = [tool("ffprobe"), "-v", "error", "-of", "json"]
    if packets:
        args += [
            "-select_streams",
            "V:0",
            "-show_packets",
            "-show_entries",
            "packet=pts_time,duration_time",
        ]
    else:
        args += ["-show_streams", "-show_format"]
        if count:
            args += ["-count_frames"]
    return json.loads(capture([*args, str(path)]))


def find_videos(query: str, roots: list[Path]) -> list[Path]:
    direct = resolve_media_path(Path(query).expanduser(), PROJECT)
    if direct.is_file():
        return [direct.resolve()] if direct.suffix.lower() in EXTENSIONS else []
    if Path(query).is_absolute() or len(Path(query).parts) > 1:
        return []
    matches: set[Path] = set()
    key = query.casefold()
    for root in dict.fromkeys(p.resolve() for p in roots if p.is_dir()):
        for directory, subdirs, files in os.walk(root):
            subdirs[:] = [
                d
                for d in subdirs
                if d not in EXCLUDED and not d.startswith((".补帧-", ".媒体输入-"))
            ]
            for name in files:
                path = Path(directory, name)
                if path.suffix.lower() in EXTENSIONS and key in name.casefold():
                    if "补帧" not in key and "补帧" in path.stem:
                        continue
                    matches.add(path.resolve())
    exact = {p for p in matches if key in {p.name.casefold(), p.stem.casefold()}}
    return sorted(exact or matches, key=lambda p: str(p).casefold())


def rate(value: str) -> Fraction:
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise ExportError(f"无法识别帧率：{value}") from error
    if result <= 0:
        raise ExportError(f"帧率必须为正数：{value}")
    return result


def timeline(packets: list[dict], fps: Fraction) -> dict:
    points = sorted(
        (float(p["pts_time"]), float(p.get("duration_time", 0))) for p in packets if "pts_time" in p
    )
    if len(points) < 2:
        raise ExportError("视频有效帧不足两帧，无法进行运动补帧。")
    deltas = [b[0] - a[0] for a, b in zip(points, points[1:], strict=False)]
    step = float(1 / fps)
    variable = any(abs(delta - step) > max(0.0021, step * 0.05) for delta in deltas)
    duration = points[-1][0] + (points[-1][1] or statistics.median(deltas)) - points[0][0]
    return {"start": points[0][0], "duration": duration, "variable": variable}


def display_geometry(video: dict) -> tuple[int, int, Fraction, float]:
    """Describe the displayed canvas, including SAR inversion on quarter turns."""
    rotation = float(video.get("tags", {}).get("rotate", 0))
    for side in video.get("side_data_list", []):
        rotation = float(side.get("rotation", rotation))
    if not math.isfinite(rotation) or rotation % 90:
        raise ExportError("视频带非90度旋转，需要先明确旋转后的画布。")
    ratio = video.get("sample_aspect_ratio", "1:1")
    sar = Fraction(ratio.replace(":", "/")) if ratio not in (None, "N/A", "0:1") else Fraction(1)
    if sar <= 0:
        raise ExportError("视频像素比例必须为正数。")
    width, height = video["width"], video["height"]
    if round(rotation) % 180:
        width, height, sar = height, width, 1 / sar
    return width, height, sar, rotation % 360


def make_plan(
    source: Path, target: Fraction, mpv_root: Path, output_stem: str | None, *, captured=None
) -> dict:
    if captured is None:
        with MediaInputs() as captured:
            return make_plan(source, target, mpv_root, output_stem, captured=captured)
    source = resolve_media_path(source, PROJECT)
    source_input = captured.capture(source)
    info = probe(source_input)
    videos = [
        s
        for s in info["streams"]
        if s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")
    ]
    if len(videos) != 1:
        raise ExportError("需要恰好一条实际视频轨；多视频轨文件请先指定并提取需要处理的轨道。")
    video = videos[0]
    try:
        fps = rate(video.get("avg_frame_rate", "0/0"))
    except ExportError:
        fps = rate(video.get("r_frame_rate", "0/0"))
    times = timeline(probe(source_input, packets=True)["packets"], fps)
    if fps == target and not times["variable"]:
        operation = "reuse"
    elif fps >= target:
        operation = "convert_frame_rate"
    else:
        operation = "interpolate"
    if times["variable"]:
        nominal = rate(video.get("r_frame_rate", str(fps)))
        fps = nominal if nominal < target and nominal <= 2 * fps else fps.limit_denominator(1001)
    if operation != "reuse" and video.get("color_transfer") in {"smpte2084", "arib-std-b67"}:
        raise ExportError("当前流程用于SDR；此视频为HDR，需要单独的保色补帧方案，未转换或提交。")
    width, height, sar, rotation = display_geometry(video)
    if operation != "reuse" and (width % 2 or height % 2):
        raise ExportError("此视频宽高为奇数，当前H.264导出需要偶数画布；请先明确补边方式。")
    if operation == "interpolate" and (
        width < 384 or height < 384 or width > 4096 or height > 2176
    ):
        raise ExportError("原分辨率超出当前RIFE引擎范围（宽384–4096、高384–2176）；未擅自缩放。")
    if output_stem and (
        Path(output_stem).name != output_stem
        or any(c in output_stem for c in '<>:"/\\|?*')
        or output_stem.endswith((".", " "))
    ):
        raise ExportError("--output-stem 只能填写不含扩展名的合法文件名，不能包含目录。")
    audio = [s for s in info["streams"] if s["codec_type"] == "audio"]
    subtitles = [s for s in info["streams"] if s["codec_type"] == "subtitle"]
    attachments = [s for s in info["streams"] if s["codec_type"] == "attachment"]
    mp4_audio = {"aac", "mp3", "ac3", "eac3", "alac"}
    needs_mkv = (
        bool(attachments)
        or any(a["codec_name"] not in mp4_audio for a in audio)
        or any(s["codec_name"] != "mov_text" for s in subtitles)
    )
    if operation == "reuse":
        suffix = source.suffix
    else:
        if needs_mkv and any(s["codec_name"] == "mov_text" for s in subtitles):
            raise ExportError(
                "mov_text 字幕不能无损复制到 MKV，但当前音轨、其他字幕或附件需要 MKV；"
                "请先明确兼容封装或字幕处理方案，未补帧、转码或删除任何轨道。"
            )
        suffix = ".mkv" if needs_mkv else ".mp4"
    label = str(target.numerator) if target.denominator == 1 else f"{float(target):.3f}"
    filename_label = "转帧率" if operation == "convert_frame_rate" else "补帧"
    algorithms = {
        "interpolate": "RIFE v4.6 / TensorRT FP16 / Turbo",
        "convert_frame_rate": "FFmpeg CFR frame-rate conversion (no interpolation)",
        "reuse": "Verified source reuse (no encoding)",
    }
    return {
        "source": str(source),
        "source_sha256": captured.digest(source),
        "input_binding_method": "private_file_snapshots",
        "input_bindings": captured.bindings(),
        "source_fps": str(fps),
        "target_fps": str(target),
        "factor": str(target / fps),
        "duration": times["duration"],
        "source_video_start": times["start"],
        "width": width,
        "height": height,
        "display_sample_aspect_ratio": str(sar),
        "display_aspect_ratio": str(Fraction(width, height) * sar),
        "source_rotation": rotation,
        "output_rotation": rotation if operation == "reuse" else 0,
        "frames": math.floor(times["duration"] * float(target) + 0.5),
        "normalize": times["variable"] or bool(rotation % 360),
        "source_video_index": video["index"],
        "audio_streams": audio,
        "subtitle_streams": subtitles,
        "attachment_streams": attachments,
        "output_stem": output_stem or f"{source.stem}-{filename_label}{label}帧",
        "suffix": suffix,
        "mpv_root": str(mpv_root),
        "operation": operation,
        "algorithm": algorithms[operation],
        "scene_detection": operation == "interpolate",
        "status": "planned",
        "container_reason": (
            "核验后复用源容器"
            if operation == "reuse"
            else (
                "MKV兼容音轨、字幕与附件，直接复制"
                if suffix == ".mkv"
                else "MP4兼容音轨与mov_text字幕，直接复制"
            )
        ),
    }


def write_vpy(path: Path, plan: dict) -> None:
    factor = rate(plan["factor"])
    target = rate(plan["target_fps"])
    path.write_text(
        "import vapoursynth as vs\nimport k7sfunc as k7f\n"
        "clip = k7f.FMT_CTRL(video_in, h_max=0)\n"
        f"clip = k7f.RIFE_NV(clip, model=46, int8_qnt=False, turbo=True, "
        f"fps_in={float(rate(plan['source_fps']))!r}, fps_num={factor.numerator}, "
        f"fps_den={factor.denominator}, sc_mode=1, gpu=0, gpu_t=2, ws_size=0)\n"
        f"clip = vs.core.std.AssumeFPS(clip, fpsnum={target.numerator}, "
        f"fpsden={target.denominator})\n"
        f"clip = vs.core.std.SetFrameProps(clip, _DurationNum={target.denominator}, "
        f"_DurationDen={target.numerator})\nclip.set_output()\n",
        encoding="utf-8",
    )


def run_logged(args: list[str], log_path: Path, cwd: Path | None = None) -> None:
    with log_path.open("ab") as log:
        log.write((json.dumps(args, ensure_ascii=False) + "\n").encode("utf-8"))
        log.flush()
        result = subprocess.run(args, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise ExportError(f"处理失败（退出码{result.returncode}），日志：{log_path}")


def validate(output: Path, plan: dict, log_path: Path) -> dict:
    result = probe(output, count=True)
    streams = result["streams"]
    video = next(
        s
        for s in streams
        if s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")
    )
    target = rate(plan["target_fps"])
    if abs(float(rate(video["avg_frame_rate"]) / target) - 1) > 0.001:
        raise ExportError("导出实际平均帧率不符，未发布结果。")
    width, height, sar, rotation = display_geometry(video)
    if (width, height) != (plan["width"], plan["height"]):
        raise ExportError("导出分辨率与原画幅不符，未发布结果。")
    if sar != Fraction(plan["display_sample_aspect_ratio"]):
        raise ExportError("导出显示像素比例与源片不符，未发布结果。")
    if rotation != plan["output_rotation"]:
        raise ExportError("导出旋转与计划不符，未发布结果。")
    if int(video["nb_read_frames"]) != plan["frames"]:
        raise ExportError("导出实际解码帧数不符，未发布结果。")
    times = timeline(probe(output, packets=True)["packets"], target)
    if times["variable"] or abs(times["duration"] - plan["duration"]) > float(1 / target) + 0.003:
        raise ExportError("导出时间戳或时长不符，未发布结果。")
    audios = [s for s in streams if s["codec_type"] == "audio"]
    if len(audios) != len(plan["audio_streams"]):
        raise ExportError("原音轨数量没有保留，未发布结果。")
    for original, exported in zip(plan["audio_streams"], audios, strict=True):
        for field in ("codec_name", "sample_rate", "channels"):
            if original.get(field) != exported.get(field):
                raise ExportError(f"音轨的{field}发生变化，未发布结果。")
        if "start_time" in original and "start_time" in exported:
            old_offset = float(original["start_time"]) - plan["source_video_start"]
            new_offset = float(exported["start_time"]) - times["start"]
            if abs(old_offset - new_offset) > 0.05:
                raise ExportError("音画相对起点发生变化，未发布结果。")
    for kind, key in (("subtitle", "subtitle_streams"), ("attachment", "attachment_streams")):
        expected = [s.get("codec_name") for s in plan[key]]
        actual = [s.get("codec_name") for s in streams if s["codec_type"] == kind]
        if actual != expected:
            raise ExportError(f"原{kind}轨数量或编码没有保留，未发布结果。")
    run_logged(
        [
            tool("ffmpeg"),
            "-nostdin",
            "-v",
            "error",
            "-xerror",
            "-i",
            str(output),
            "-map",
            "0:V:0",
            "-map",
            "0:a?",
            "-f",
            "null",
            "-",
        ],
        log_path,
    )
    return {
        "fps": str(target),
        "frames": int(video["nb_read_frames"]),
        "duration": times["duration"],
        "width": video["width"],
        "height": video["height"],
        "display_width": width,
        "display_height": height,
        "display_sample_aspect_ratio": str(sar),
        "display_aspect_ratio": str(Fraction(width, height) * sar),
        "rotation": rotation,
        "audio_tracks": len(audios),
        "full_decode": "passed",
    }


def publish(partial: Path, directory: Path, stem: str, suffix: str) -> Path:
    version = 1
    while True:
        tag = "" if version == 1 else f"-版本{version:02d}"
        output = ensure_project_output(directory / f"{stem}{tag}{suffix}", partial, root=PROJECT)
        try:
            os.link(partial, output)
        except FileExistsError:
            version += 1
            continue
        except OSError:
            try:
                destination = output.open("xb")
            except FileExistsError:
                version += 1
                continue
            try:
                with destination, partial.open("rb") as incoming:
                    shutil.copyfileobj(incoming, destination)
            except BaseException:
                output.unlink(missing_ok=True)
                raise
        return output


def render_rife(plan: dict, temp: Path, log_path: Path, job_dir: Path, source_input: Path) -> Path:
    mpv_root = Path(plan["mpv_root"])
    ffmpeg = tool("ffmpeg")
    input_path = source_input
    if plan["normalize"]:
        input_path = temp / "时间线规范化.mkv"
        run_logged(
            [
                ffmpeg,
                "-nostdin",
                "-v",
                "error",
                "-n",
                "-i",
                str(source_input),
                "-map",
                f"0:{plan['source_video_index']}",
                "-an",
                "-sn",
                "-dn",
                "-vf",
                "setpts=PTS-STARTPTS",
                "-r",
                plan["source_fps"],
                "-fps_mode",
                "cfr",
                "-c:v",
                "ffv1",
                "-pix_fmt",
                "yuv420p",
                "-t",
                str(plan["duration"]),
                str(input_path),
            ],
            log_path,
        )
    vpy = temp / "RIFE补帧.vpy"
    write_vpy(vpy, plan)
    shutil.copyfile(vpy, job_dir / "RIFE补帧.vpy")
    encoded = temp / "补帧画面.mp4"
    # Pad before the streaming wrapper to avoid losing final source frames.
    # Trim after RIFE to the measured frame count and restore exact CFR PTS.
    filters = (
        "lavfi=[setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=1],"
        f'vapoursynth=file="{vpy.as_posix()}",'
        f"lavfi=[fps=fps={plan['target_fps']}:start_time=0,"
        f"trim=end_frame={plan['frames']},"
        f"setpts=N/({plan['target_fps']}*TB),format=yuv420p]"
    )
    run_logged(
        [
            str(mpv_root / "mpv.com"),
            "--no-config",
            "--load-scripts=no",
            "--load-stats-overlay=no",
            "--no-audio",
            "--sid=no",
            "--hwdec=no",
            "--resume-playback=no",
            "--audio-file-auto=no",
            "--sub-auto=no",
            "--video-sync=audio",
            "--interpolation=no",
            "--vf=" + filters,
            "--ovc=h264_nvenc",
            "--ovcopts=preset=p4,rc=vbr,cq=18,b=0",
            "--of=mp4",
            "--o=" + str(encoded),
            str(input_path),
        ],
        log_path,
        mpv_root,
    )
    return encoded


def export(plan: dict, *, captured=None) -> dict:
    if captured is None:
        with MediaInputs() as captured:
            return export(plan, captured=captured)
    source = Path(plan["source"])
    source_input = captured.capture(source)
    if captured.digest(source) != plan.get("source_sha256"):
        raise ExportError("源文件与补帧计划绑定的版本不同，请重新探测；未发布结果。")
    mpv_root = Path(plan["mpv_root"])
    if plan["operation"] == "interpolate":
        for relative in (
            "mpv.com",
            "k7sfunc.py",
            "vs-plugins/vstrt.dll",
            "vs-plugins/models/rife_v2/rife_v4.6.onnx",
        ):
            if not (mpv_root / relative).is_file():
                raise ExportError(f"补帧运行环境缺少文件：{mpv_root / relative}")
    ffmpeg = tool("ffmpeg")
    job_dir = PROJECT / ".autodl" / "interpolation" / uuid.uuid4().hex
    job_dir.mkdir(parents=True)
    record = job_dir / "result.json"
    log_path = job_dir / "export.log"
    plan = dict(plan, status="running", log=str(log_path))
    record.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    emit(
        {
            "status": "running",
            "source": str(source),
            "log": str(log_path),
            "operation": plan["operation"],
            "message": {
                "interpolate": "本地RIFE补帧中；首次分辨率可能需要编译TensorRT缓存。",
                "convert_frame_rate": "另存目标帧率副本，原音轨直接复制。",
                "reuse": "完整检查已有目标帧率文件，不重复编码。",
            }[plan["operation"]],
        }
    )
    try:
        if plan["operation"] == "reuse":
            checks = validate(source_input, plan, log_path)
            captured.check_current()
            plan.update(
                status="completed",
                output=str(source),
                output_sha256=captured.digest(source),
                reused=True,
                checks=checks,
            )
            return plan
        # TemporaryDirectory only removes its own freshly created sibling directory.
        with tempfile.TemporaryDirectory(prefix=".补帧-", dir=source.parent) as temp_name:
            temp = Path(temp_name)
            if plan["operation"] == "interpolate":
                encoded = render_rife(plan, temp, log_path, job_dir, source_input)
            else:
                encoded = temp / "转帧率画面.mp4"
                effect = (
                    f"setpts=PTS-STARTPTS,fps={plan['target_fps']}:start_time=0,"
                    f"trim=end_frame={plan['frames']},"
                    f"setpts=N/({plan['target_fps']}*TB)"
                )
                run_logged(
                    [
                        ffmpeg,
                        "-nostdin",
                        "-v",
                        "error",
                        "-n",
                        "-i",
                        str(source_input),
                        "-map",
                        f"0:{plan['source_video_index']}",
                        "-an",
                        "-sn",
                        "-dn",
                        "-vf",
                        effect,
                        "-c:v",
                        "libx264",
                        "-crf",
                        "18",
                        "-preset",
                        "medium",
                        "-pix_fmt",
                        "yuv420p",
                        str(encoded),
                    ],
                    log_path,
                )
            partial = temp / ("合并原音轨" + plan["suffix"])
            args = [
                ffmpeg,
                "-nostdin",
                "-v",
                "error",
                "-n",
                "-copyts",
                "-i",
                str(encoded),
                "-itsoffset",
                str(-plan["source_video_start"]),
                "-i",
                str(source_input),
                "-map",
                "0:v:0",
                "-map",
                "1:a?",
                "-map",
                "1:s?",
                "-map_metadata",
                "1",
                "-map_chapters",
                "1",
            ]
            if plan["suffix"] == ".mkv":
                args += ["-map", "1:t?"]
            # With stream copy this fixes the last packet duration, not interpolation.
            args += ["-c", "copy", "-r:v", plan["target_fps"]]
            if plan["suffix"] == ".mp4":
                args += ["-movflags", "+faststart"]
            run_logged([*args, str(partial)], log_path)
            checks = validate(partial, plan, log_path)
            captured.check_current()
            output_sha256 = file_digest(partial)
            output = publish(partial, source.parent, plan["output_stem"], plan["suffix"])
        plan.update(
            status="completed",
            output=str(output),
            output_sha256=output_sha256,
            reused=False,
            checks=checks,
        )
        return plan
    except BaseException as error:
        plan.update(status="failed", error=str(error))
        raise
    finally:
        record.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RIFE本地补帧，在源视频目录生成新视频。")
    parser.add_argument("video", help="视频路径、完整文件名或文件名中的关键词")
    parser.add_argument("--fps", default="60", help="目标帧率，默认60")
    parser.add_argument("--find", action="store_true", help="仅列出匹配文件")
    parser.add_argument("--dry-run", action="store_true", help="仅探测并显示计划")
    parser.add_argument("--search-root", type=Path, action="append", default=[])
    parser.add_argument("--mpv-root", type=Path, default=MPV_ROOT)
    parser.add_argument("--output-stem", help="自定义新文件名，不含扩展名")
    args = parser.parse_args(argv)
    try:
        matches = find_videos(args.video, [Path.cwd(), PROJECT, *args.search_root])
        if args.find:
            emit({"matches": [str(p) for p in matches]})
            return 0 if matches else 1
        if len(matches) != 1:
            emit(
                {
                    "status": "needs_selection",
                    "matches": [str(p) for p in matches],
                    "message": "未找到视频或匹配不唯一，请明确具体文件。",
                }
            )
            return 2
        with MediaInputs() as captured:
            plan = make_plan(
                matches[0],
                rate(args.fps),
                args.mpv_root.resolve(),
                args.output_stem,
                captured=captured,
            )
            if args.dry_run:
                emit(plan)
            else:
                emit(export(plan, captured=captured))
        return 0
    except (ExportError, AutoDLError, OSError, ValueError, KeyError) as error:
        emit({"status": "failed", "error": str(error)})
        return 1
    except KeyboardInterrupt:
        emit({"status": "interrupted", "message": "补帧已中断，原片保留。"})
        return 130


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
