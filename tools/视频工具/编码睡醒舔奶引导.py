"""Encode a complete 24fps guide and two overlapping replacement inputs."""

import argparse
import json
import math
import struct
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

from project_tool_safety import json_staging, publish_bundle
from whitebox_saved import checked_destination, project_path, sha

from autodl_video.media_inputs import MediaInputs

FPS = 24
FRAME_COUNT = 768
SEGMENT_RANGES = ((0, 504), (456, 768))


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True).stdout


def probe(path):
    return json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-count_frames",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ]
        )
    )


def validate_output(path, count, dimensions, audio):
    meta = probe(path)
    streams = meta["streams"]
    video = [s for s in streams if s["codec_type"] == "video"]
    sound = [s for s in streams if s["codec_type"] == "audio"]
    if len(streams) != 2 or len(video) != 1 or len(sound) != 1:
        raise ValueError("输出须恰好含一条视频轨和一条音轨")
    v, a = video[0], sound[0]
    if (
        int(v["nb_read_frames"]) != count
        or Fraction(v["avg_frame_rate"]) != FPS
        or [v["width"], v["height"]] != dimensions
    ):
        raise ValueError("输出帧数、帧率或尺寸不符合绑定")
    if int(a["sample_rate"]) != int(audio["sample_rate"]) or a["channels"] != audio["channels"]:
        raise ValueError("输出音轨规格改变")
    duration = count / FPS
    if (
        abs(float(v.get("start_time", 0))) > 0.0001
        or abs(float(a.get("start_time", 0))) > 0.001
        or abs(float(v["duration"]) - duration) > 0.001
        or abs(float(a["duration"]) - duration) > 0.03
    ):
        raise ValueError("输出音画时间范围不匹配")
    timing = json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_frames",
                "-show_entries",
                "frame=best_effort_timestamp_time",
                "-of",
                "json",
                str(path),
            ]
        )
    )["frames"]
    if len(timing) != count or any(
        abs(float(frame["best_effort_timestamp_time"]) - index / FPS) > 0.0001
        for index, frame in enumerate(timing)
    ):
        raise ValueError("输出实际逐帧时间戳不符合24fps")
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-v",
            "error",
            "-nostdin",
            "-xerror",
            "-i",
            str(path),
            "-map",
            "0:v",
            "-map",
            "0:a",
            "-f",
            "null",
            "-",
        ]
    )
    return meta


def encode(project, frame_dir, version, *, frame_count=FRAME_COUNT, segment_ranges=SEGMENT_RANGES):
    project = Path(project).resolve()
    frames = project_path(project, frame_dir)
    names = [f"帧{i:04d}.png" for i in range(1, frame_count + 1)]
    if {f.name for f in frames.glob("帧*.png")} != set(names):
        raise ValueError(f"Expected {frame_count} consecutive images")
    if len(segment_ranges) != 2 or any(
        not 0 <= start < end <= frame_count for start, end in segment_ranges
    ):
        raise ValueError("Invalid segment frame ranges")
    source_frames = [project_path(project, frames / name, exists=True) for name in names]
    audio = project_path(project, "02-素材/音频/睡醒舔奶-32秒声音引导04.wav", exists=True)
    binding_path = project_path(project, frames / "序列绑定.json", exists=True)
    outputs = [
        project_path(project, value)
        for value in [
            f"04-输出/处理过程/龙宝宝-睡醒舔奶-森林引导{version}.mp4",
            f"04-输出/处理过程/睡醒舔奶-替换引导-段一{version}.mp4",
            f"04-输出/处理过程/睡醒舔奶-替换引导-段二{version}.mp4",
        ]
    ]
    record = project_path(project, f"05-检查与验收/睡醒舔奶-引导编码检查{version}.json")
    for output in [*outputs, record]:
        checked_destination(output, project)
    with (
        MediaInputs() as captured,
        tempfile.TemporaryDirectory(prefix=".引导编码-", dir=project) as folder,
    ):
        folder = Path(folder)
        binding = json.loads(captured.capture(binding_path).read_text("utf-8"))
        if (
            binding.get("schema") != 1
            or binding.get("frames") != str(frames.relative_to(project))
            or binding.get("fps") != FPS
            or binding.get("fps_base") != 1
            or binding.get("frame_start") != 1
            or binding.get("frame_end") != frame_count
        ):
            raise ValueError("帧序列未绑定本作品的24fps时间轴")
        blend = project_path(project, binding["blend"], exists=True)
        captured.capture(blend)
        if captured.digest(blend) != binding.get("blend_sha256"):
            raise ValueError("帧序列绑定的工程已变化")
        dimensions = [
            math.floor(n * binding["resolution_percentage"] / 100) for n in binding["resolution"]
        ]
        # Sequence aliases stay on the snapshot volume (projects may be on E:,
        # while the private input cache is on C:). These link private copies only.
        sequence = captured.directory / "frames"
        sequence.mkdir()
        for source, name in zip(source_frames, names, strict=True):
            private = captured.capture(source)
            with private.open("rb") as stream:
                header = stream.read(24)
            if (
                header[:8] != b"\x89PNG\r\n\x1a\n"
                or header[12:16] != b"IHDR"
                or list(struct.unpack(">II", header[16:24])) != dimensions
            ):
                raise ValueError(f"帧尺寸或PNG格式不符合绑定：{source}")
            (sequence / name).hardlink_to(private)
        private_audio = captured.capture(audio)
        audio_meta = probe(private_audio)
        if len(audio_meta["streams"]) != 1 or audio_meta["streams"][0]["codec_type"] != "audio":
            raise ValueError("声音引导必须恰好包含一条音轨")
        audio_stream = audio_meta["streams"][0]
        if abs(float(audio_stream["duration"]) - frame_count / FPS) > 1 / int(
            audio_stream["sample_rate"]
        ):
            raise ValueError("声音引导时长与帧序列不匹配")
        staged = [folder / f"output-{index}.mp4" for index in range(3)]
        video_options = [
            "-c:v",
            "libx264",
            "-crf",
            "17",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
        ]
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-xerror",
                "-n",
                "-framerate",
                str(FPS),
                "-start_number",
                "1",
                "-i",
                str(sequence / "帧%04d.png"),
                "-i",
                str(private_audio),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                *video_options,
                "-t",
                str(frame_count / FPS),
                str(staged[0]),
            ]
        )
        for destination, (start, end) in zip(staged[1:], segment_ranges, strict=True):
            filters = (
                f"[0:v]trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS[v];"
                f"[0:a]atrim=start={start / FPS}:end={end / FPS},asetpts=PTS-STARTPTS[a]"
            )
            run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-nostdin",
                    "-xerror",
                    "-n",
                    "-i",
                    str(staged[0]),
                    "-filter_complex",
                    filters,
                    "-map",
                    "[v]",
                    "-map",
                    "[a]",
                    *video_options,
                    str(destination),
                ]
            )
        counts = [frame_count, *(end - start for start, end in segment_ranges)]
        data = []
        for private, output, count in zip(staged, outputs, counts, strict=True):
            meta = validate_output(private, count, dimensions, audio_stream)
            data.append(
                dict(
                    path=str(output.relative_to(project)),
                    sha256=sha(private),
                    probe=meta,
                    full_decode="passed",
                )
            )
        input_bindings = [
            {"path": str(Path(item["path"]).relative_to(project)), "sha256": item["sha256"]}
            for item in captured.bindings()
        ]
        value = dict(
            frames=frame_count,
            fps=FPS,
            source_frame_ranges=segment_ranges,
            overlap_seconds=[segment_ranges[1][0] / FPS, segment_ranges[0][1] / FPS],
            source_inputs=input_bindings,
            sequence_binding=binding,
            outputs=data,
            dynamic_review="pending",
            actual_listening="pending",
        )
        staged_record = json_staging(folder, record.name, value)
        publish_bundle(
            [*zip(staged, outputs, strict=True), (staged_record, record)],
            project,
            validate=captured.check_current,
        )
    return outputs, record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--frames", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    outputs, record = encode(args.project, args.frames, args.version)
    print(
        json.dumps({"videos": [str(f) for f in outputs], "record": str(record)}, ensure_ascii=False)
    )


if __name__ == "__main__":
    main()
