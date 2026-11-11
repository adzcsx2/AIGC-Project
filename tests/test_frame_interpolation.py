"""Source preservation and media invariants for the project-local 补帧 skill."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools/视频工具/补帧核心.py"
SPEC = importlib.util.spec_from_file_location("frame_interpolation", SCRIPT)
interpolation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(interpolation)


def test_file_search_requires_selection_and_ignores_previous_exports(tmp_path):
    for directory in (
        tmp_path / "第一版",
        tmp_path / "第二版",
        tmp_path / ".补帧-临时",
        tmp_path / ".媒体输入-临时",
    ):
        directory.mkdir()
        (directory / "双人对决.mp4").touch()
    (tmp_path / "双人对决-补帧60帧.mp4").touch()
    (tmp_path / "双人对决-花絮.mp4").touch()
    matches = interpolation.find_videos("双人对决", [tmp_path])
    assert set(matches) == {tmp_path / "第一版/双人对决.mp4", tmp_path / "第二版/双人对决.mp4"}


def test_explicit_path_is_not_replaced_by_a_fuzzy_match(tmp_path):
    (tmp_path / "双人对决.mp4").touch()
    assert interpolation.find_videos(str(tmp_path / "缺失/双人对决.mp4"), [tmp_path]) == []


def test_publish_keeps_existing_file_and_versions_the_new_output(tmp_path):
    partial = tmp_path / "待发布.mp4"
    partial.write_bytes(b"validated video")
    existing = tmp_path / "对决-补帧60帧.mp4"
    existing.write_bytes(b"previous version")
    output = interpolation.publish(partial, tmp_path, "对决-补帧60帧", ".mp4")
    assert output.name == "对决-补帧60帧-版本02.mp4"
    assert output.read_bytes() == b"validated video"
    assert existing.read_bytes() == b"previous version"


def test_packet_timeline_uses_presentation_order_and_detects_variable_timing():
    packets = [
        {"pts_time": "0", "duration_time": "0.04"},
        {"pts_time": "0.08", "duration_time": "0.04"},
        {"pts_time": "0.04", "duration_time": "0.04"},
    ]
    assert interpolation.timeline(packets, Fraction(25)) == {
        "start": 0.0,
        "duration": 0.12,
        "variable": False,
    }
    packets[-1]["pts_time"] = "0.02"
    assert interpolation.timeline(packets, Fraction(25))["variable"]


GPU_TEST = pytest.mark.skipif(
    os.environ.get("RUN_RIFE_TESTS") != "1", reason="Set RUN_RIFE_TESTS=1 for local GPU integration"
)


def ffmpeg(*arguments):
    return subprocess.run(
        [interpolation.tool("ffmpeg"), "-nostdin", "-v", "error", *map(str, arguments)],
        capture_output=True,
        check=True,
    ).stdout


def audio_hash(path):
    return ffmpeg("-i", path, "-map", "0:a:0", "-c", "copy", "-f", "hash", "-hash", "sha256", "-")


def interpolation_cli(source, *arguments):
    process = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(SCRIPT.with_name("补帧.py")),
            str(source),
            *map(str, arguments),
        ],
        capture_output=True,
        encoding="utf-8",
    )
    decoder = json.JSONDecoder()
    pending, messages = process.stdout.strip(), []
    while pending:
        message, end = decoder.raw_decode(pending)
        messages.append(message)
        pending = pending[end:].lstrip()
    return process, messages[-1]


def make_sample(path, fps, size="320x180", sar="1"):
    ffmpeg(
        "-n",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={size}:rate={fps}:duration=1",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000:duration=1",
        "-vf",
        f"setsar={sar}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        path,
    )


def replacement_sample(path, fps=120):
    ffmpeg(
        "-f",
        "lavfi",
        "-i",
        f"color=red:size=320x180:rate={fps}:duration=1",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=880:sample_rate=48000:duration=1",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        path,
    )


def test_plan_probes_one_snapshot_and_export_rejects_a_stale_plan(tmp_path, monkeypatch):
    source, replacement = tmp_path / "源片.mp4", tmp_path / "替换.mp4"
    make_sample(source, 120)
    replacement_sample(replacement, fps=60)
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    probe, snapshots = interpolation.probe, []

    def replace_between_probes(path, **kwargs):
        result = probe(path, **kwargs)
        snapshots.append(path)
        if not kwargs.get("packets"):
            source.write_bytes(replacement.read_bytes())
        return result

    monkeypatch.setattr(interpolation, "probe", replace_between_probes)
    plan = interpolation.make_plan(source, Fraction(60), interpolation.MPV_ROOT, None)
    assert plan["source_fps"] == "120" and plan["source_sha256"] == original
    assert len(snapshots) == 2 and snapshots[0] == snapshots[1] != source
    assert all(not path.parent.exists() for path in snapshots)
    with pytest.raises(interpolation.ExportError, match="计划绑定的版本不同"):
        interpolation.export(plan)
    assert not list(tmp_path.glob("*转帧率*"))


@pytest.mark.parametrize("restore", [False, True])
def test_conversion_uses_same_frozen_bytes_for_video_audio_and_record(
    tmp_path, monkeypatch, restore
):
    source, replacement = tmp_path / "源片.mp4", tmp_path / "替换.mp4"
    make_sample(source, 120)
    replacement_sample(replacement)
    original = source.read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    expected_audio = audio_hash(source)
    assert expected_audio != audio_hash(replacement)
    plan = interpolation.make_plan(source, Fraction(60), interpolation.MPV_ROOT, None)
    run_logged, snapshots = interpolation.run_logged, []
    monkeypatch.setattr(interpolation, "PROJECT", tmp_path)

    def replace_between_video_and_mux(args, *pargs, **kwargs):
        if "libx264" in args:
            snapshot = Path(args[args.index("-i") + 1])
            snapshots.append(snapshot)
            result = run_logged(args, *pargs, **kwargs)
            source.write_bytes(replacement.read_bytes())
            return result
        if "-copyts" in args:
            input_paths = [Path(args[i + 1]) for i, arg in enumerate(args) if arg == "-i"]
            assert input_paths[1] == snapshots[0] != source
            assert hashlib.sha256(input_paths[1].read_bytes()).hexdigest() == original_hash
            try:
                return run_logged(args, *pargs, **kwargs)
            finally:
                if restore:
                    source.write_bytes(original)
        return run_logged(args, *pargs, **kwargs)

    monkeypatch.setattr(interpolation, "run_logged", replace_between_video_and_mux)
    if restore:
        result = interpolation.export(plan)
        output = Path(result["output"])
        assert result["source_sha256"] == original_hash
        assert result["input_bindings"] == [{"path": str(source), "sha256": original_hash}]
        assert result["output_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
        assert result["checks"]["frames"] == 60
        assert audio_hash(output) == expected_audio
        assert source.read_bytes() == original
    else:
        with pytest.raises(ValueError, match="输入已变化"):
            interpolation.export(plan)
        assert not list(tmp_path.glob("*转帧率*"))
        record = next((tmp_path / ".autodl/interpolation").glob("*/result.json"))
        assert json.loads(record.read_text("utf-8"))["status"] == "failed"
    assert snapshots and all(not path.parent.exists() for path in snapshots)
    assert not list(tmp_path.glob(".补帧-*"))


def test_reuse_validates_snapshot_but_rejects_a_changed_original(tmp_path, monkeypatch):
    source, replacement = tmp_path / "源片.mp4", tmp_path / "替换.mp4"
    make_sample(source, 60)
    replacement_sample(replacement, fps=60)
    plan = interpolation.make_plan(source, Fraction(60), interpolation.MPV_ROOT, None)
    validate, snapshots = interpolation.validate, []
    monkeypatch.setattr(interpolation, "PROJECT", tmp_path)

    def replace_after_validation(path, *args):
        assert path != source
        snapshots.append(path)
        result = validate(path, *args)
        source.write_bytes(replacement.read_bytes())
        return result

    monkeypatch.setattr(interpolation, "validate", replace_after_validation)
    with pytest.raises(ValueError, match="输入已变化"):
        interpolation.export(plan)
    assert snapshots and all(not path.parent.exists() for path in snapshots)
    record = next((tmp_path / ".autodl/interpolation").glob("*/result.json"))
    assert json.loads(record.read_text("utf-8"))["status"] == "failed"


@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
def test_export_failure_cleans_input_snapshot_and_rendering_files(tmp_path, monkeypatch, failure):
    source = tmp_path / "源片.mp4"
    make_sample(source, 120)
    original = source.read_bytes()
    plan = interpolation.make_plan(source, Fraction(60), interpolation.MPV_ROOT, None)
    monkeypatch.setattr(interpolation, "PROJECT", tmp_path)
    snapshots = []

    def fail_encoding(args, *pargs, **kwargs):
        snapshots.append(Path(args[args.index("-i") + 1]))
        raise failure("interrupted encoder")

    monkeypatch.setattr(interpolation, "run_logged", fail_encoding)
    with pytest.raises(failure):
        interpolation.export(plan)
    assert snapshots and all(not path.parent.exists() for path in snapshots)
    assert not list(tmp_path.glob(".补帧-*")) and not list(tmp_path.glob("*转帧率*"))
    assert source.read_bytes() == original


@GPU_TEST
def test_real_rife_and_mux_use_one_snapshot_across_live_source_replacement(tmp_path, monkeypatch):
    source, replacement = tmp_path / "源片.mp4", tmp_path / "替换.mp4"
    make_sample(source, 24, "640x384")
    replacement_sample(replacement, fps=24)
    original = source.read_bytes()
    expected_audio = audio_hash(source)
    plan = interpolation.make_plan(source, Fraction(60), interpolation.MPV_ROOT, None)
    render, run_logged = interpolation.render_rife, interpolation.run_logged
    snapshots = []
    monkeypatch.setattr(interpolation, "PROJECT", tmp_path)

    def render_then_replace(plan, temp, log_path, job_dir, source_input):
        assert source_input != source
        snapshots.append(source_input)
        encoded = render(plan, temp, log_path, job_dir, source_input)
        source.write_bytes(replacement.read_bytes())
        return encoded

    def mux_then_restore(args, *pargs, **kwargs):
        if "-copyts" in args:
            paths = [Path(args[i + 1]) for i, arg in enumerate(args) if arg == "-i"]
            assert paths[1] == snapshots[0]
            try:
                return run_logged(args, *pargs, **kwargs)
            finally:
                source.write_bytes(original)
        return run_logged(args, *pargs, **kwargs)

    monkeypatch.setattr(interpolation, "render_rife", render_then_replace)
    monkeypatch.setattr(interpolation, "run_logged", mux_then_restore)
    result = interpolation.export(plan)
    assert result["checks"]["frames"] == 60 and result["checks"]["full_decode"] == "passed"
    assert result["source_sha256"] == hashlib.sha256(original).hexdigest()
    assert audio_hash(Path(result["output"])) == expected_audio
    assert source.read_bytes() == original
    assert snapshots and all(not path.parent.exists() for path in snapshots)


@pytest.mark.parametrize("fps", [60, 120])
def test_cli_reuses_or_converts_without_rife_and_preserves_audio(tmp_path, fps):
    source = tmp_path / f"源片{fps}fps.mp4"
    make_sample(source, fps)
    before = hashlib.sha256(source.read_bytes()).digest()
    process, result = interpolation_cli(source, "--mpv-root", tmp_path / "没有RIFE")
    assert process.returncode == 0, process.stdout + process.stderr
    output = Path(result["output"])
    assert result["status"] == "completed"
    assert result["operation"] == ("reuse" if fps == 60 else "convert_frame_rate")
    assert result["reused"] is (fps == 60)
    assert (output == source) is (fps == 60)
    assert result["checks"]["full_decode"] == "passed"
    assert result["checks"]["fps"] == "60"
    assert result["checks"]["frames"] == 60
    assert result["checks"]["duration"] == pytest.approx(1, abs=0.002)
    assert (result["checks"]["width"], result["checks"]["height"]) == (320, 180)
    assert audio_hash(source) == audio_hash(output)
    assert hashlib.sha256(source.read_bytes()).digest() == before
    if fps == 120:
        assert "转帧率60帧" in output.name
        # A second call must preserve the first published copy.
        published = hashlib.sha256(output.read_bytes()).digest()
        repeated, newer = interpolation_cli(source, "--mpv-root", tmp_path / "没有RIFE")
        assert repeated.returncode == 0
        assert Path(newer["output"]) != output
        assert hashlib.sha256(output.read_bytes()).digest() == published


def test_cli_rejects_corrupt_target_rate_instead_of_reusing_it(tmp_path):
    source = tmp_path / "损坏60fps.mp4"
    make_sample(source, 60)
    packets = json.loads(
        interpolation.capture(
            [
                interpolation.tool("ffprobe"),
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_packets",
                "-of",
                "json",
                str(source),
            ]
        )
    )["packets"]
    packet = packets[len(packets) // 2]
    data = bytearray(source.read_bytes())
    start = int(packet["pos"]) + 4
    length = min(120, int(packet["size"]) - 4)
    data[start : start + length] = b"\xff" * length
    source.write_bytes(data)
    before = hashlib.sha256(source.read_bytes()).digest()
    process, result = interpolation_cli(source)
    assert process.returncode != 0
    assert result["status"] == "failed"
    assert "output" not in result
    assert list(tmp_path.glob("*.mp4")) == [source]
    assert hashlib.sha256(source.read_bytes()).digest() == before


@pytest.mark.parametrize(("codec", "suffix"), [("mov_text", ".mp4"), ("srt", ".mkv")])
def test_cli_selects_subtitle_compatible_container_without_losing_streams(tmp_path, codec, suffix):
    base = tmp_path / "无字幕.mp4"
    make_sample(base, 120)
    subtitles = tmp_path / "字幕.srt"
    subtitles.write_text("1\n00:00:00,100 --> 00:00:00,800\n测试字幕\n", encoding="utf-8")
    source = tmp_path / ("字幕源片" + suffix)
    ffmpeg(
        "-i",
        base,
        "-i",
        subtitles,
        "-map",
        "0",
        "-map",
        "1:s:0",
        "-c",
        "copy",
        "-c:s",
        codec,
        "-metadata:s:s:0",
        "language=zho",
        source,
    )
    before = hashlib.sha256(source.read_bytes()).digest()
    process, result = interpolation_cli(source, "--mpv-root", tmp_path / "没有RIFE")
    assert process.returncode == 0, process.stdout + process.stderr
    output = Path(result["output"])
    assert output.suffix == suffix
    assert result["checks"]["frames"] == 60
    original_sub = [
        s for s in interpolation.probe(source)["streams"] if s["codec_type"] == "subtitle"
    ]
    exported_sub = [
        s for s in interpolation.probe(output)["streams"] if s["codec_type"] == "subtitle"
    ]
    assert len(original_sub) == len(exported_sub) == 1
    assert exported_sub[0]["codec_name"] == original_sub[0]["codec_name"]
    assert exported_sub[0]["tags"]["language"] == "zho"
    for path in (source, output):
        digest = ffmpeg("-i", path, "-map", "0:s:0", "-c", "copy", "-f", "hash", "-")
        if path == source:
            subtitle_digest = digest
        else:
            assert digest == subtitle_digest
    assert audio_hash(source) == audio_hash(output)
    assert hashlib.sha256(source.read_bytes()).digest() == before
    missing_subtitles = tmp_path / ("漏字幕候选" + suffix)
    ffmpeg("-i", output, "-map", "0:v:0", "-map", "0:a:0", "-c", "copy", missing_subtitles)
    plan = interpolation.make_plan(source, Fraction(60), interpolation.MPV_ROOT, None)
    with pytest.raises(interpolation.ExportError, match="subtitle"):
        interpolation.validate(missing_subtitles, plan, tmp_path / "检查.log")


@pytest.mark.parametrize("fps", [24, 60])
def test_incompatible_mov_text_audio_is_rejected_before_rife_but_can_be_reused(tmp_path, fps):
    base, source = tmp_path / "源画面.mp4", tmp_path / "PCM和字幕.mov"
    make_sample(base, fps, "640x384")
    subtitles = tmp_path / "字幕.srt"
    subtitles.write_text("1\n00:00:00,100 --> 00:00:00,800\n测试字幕\n", encoding="utf-8")
    ffmpeg(
        "-i",
        base,
        "-i",
        subtitles,
        "-map",
        "0",
        "-map",
        "1:s:0",
        "-c:v",
        "copy",
        "-c:a",
        "pcm_s16le",
        "-c:s",
        "mov_text",
        source,
    )
    before = hashlib.sha256(source.read_bytes()).digest()
    process, result = interpolation_cli(source, "--mpv-root", tmp_path / "没有RIFE")
    if fps == 60:
        assert process.returncode == 0, process.stdout + process.stderr
        assert result["reused"] and Path(result["output"]) == source
        assert result["suffix"] == ".mov"
    else:
        assert process.returncode == 1
        assert "mov_text" in result["error"] and "MKV" in result["error"]
        assert "运行环境缺少" not in result["error"]
        assert "running" not in process.stdout
        assert "output" not in result
    assert hashlib.sha256(source.read_bytes()).digest() == before
    assert list(tmp_path.glob("*补帧*")) == []


@GPU_TEST
def test_real_rife_cli_from_centralized_entry(tmp_path):
    source = tmp_path / "统一入口源片.mp4"
    make_sample(source, 24, "640x384", sar="2")
    before = hashlib.sha256(source.read_bytes()).digest()
    process, result = interpolation_cli(source)
    assert process.returncode == 0, process.stdout + process.stderr
    assert result["operation"] == "interpolate"
    assert result["checks"]["full_decode"] == "passed"
    assert result["checks"]["frames"] == 60
    assert result["checks"]["duration"] == pytest.approx(1, abs=0.002)
    assert result["display_sample_aspect_ratio"] == "2"
    assert result["checks"]["display_sample_aspect_ratio"] == "2"
    assert result["checks"]["display_aspect_ratio"] == "10/3"
    assert audio_hash(source) == audio_hash(Path(result["output"]))
    assert hashlib.sha256(source.read_bytes()).digest() == before


@pytest.mark.parametrize("rotation", [0, 90, 180])
def test_converted_display_sar_and_rotation_are_preserved_and_validated(tmp_path, rotation):
    base, source = tmp_path / "宽像素.mp4", tmp_path / "带方向源片.mp4"
    make_sample(base, 120, sar="2")
    ffmpeg("-display_rotation", str(rotation), "-i", base, "-c", "copy", source)
    before = hashlib.sha256(source.read_bytes()).digest()
    process, result = interpolation_cli(source, "--mpv-root", tmp_path / "无RIFE")
    assert process.returncode == 0, process.stdout + process.stderr
    expected_sar = "1/2" if rotation == 90 else "2"
    assert result["display_sample_aspect_ratio"] == expected_sar
    assert result["checks"]["display_sample_aspect_ratio"] == expected_sar
    assert result["checks"]["rotation"] == 0
    output = Path(result["output"])
    assert audio_hash(output) == audio_hash(source)
    assert hashlib.sha256(source.read_bytes()).digest() == before
    candidate = tmp_path / "错误像素比例.mp4"
    ffmpeg("-i", output, "-vf", "setsar=1", "-c:v", "libx264", "-c:a", "copy", candidate)
    plan = interpolation.make_plan(source, Fraction(60), interpolation.MPV_ROOT, None)
    with pytest.raises(interpolation.ExportError, match="像素比例"):
        interpolation.validate(candidate, plan, tmp_path / "检查.log")
    wrong_rotation = tmp_path / "错误旋转.mp4"
    ffmpeg("-display_rotation", "180", "-i", output, "-c", "copy", wrong_rotation)
    with pytest.raises(interpolation.ExportError, match="旋转"):
        interpolation.validate(wrong_rotation, plan, tmp_path / "旋转检查.log")


@GPU_TEST
@pytest.mark.parametrize("fps", ["24", "25", "30000/1001"])
def test_real_rife_export_preserves_source_audio_duration_and_resolution(tmp_path, fps):
    source = tmp_path / "中文 空格与$符号-源片.mp4"
    ffmpeg(
        "-n",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size=640x384:rate={fps}:duration=1",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000:duration=1",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        source,
    )
    before = hashlib.sha256(source.read_bytes()).digest()
    plan = interpolation.make_plan(source, Fraction(60), interpolation.MPV_ROOT, None)
    result = interpolation.export(plan)
    output = Path(result["output"])
    assert output.parent == source.parent
    assert output.name == source.stem + "-补帧60帧.mp4"
    assert result["checks"]["frames"] == 60
    assert result["checks"]["duration"] == pytest.approx(1, abs=0.002)
    assert audio_hash(source) == audio_hash(output)
    assert hashlib.sha256(source.read_bytes()).digest() == before
    first_frame = ffmpeg("-i", output, "-frames:v", "1", "-pix_fmt", "gray", "-f", "rawvideo", "-")
    assert sum(first_frame) / len(first_frame) > 20  # No initialization dummy/black frame.


@GPU_TEST
def test_subtitles_and_two_audio_tracks_are_kept_in_mkv(tmp_path):
    subtitles = tmp_path / "字幕.srt"
    subtitles.write_text("1\n00:00:00,100 --> 00:00:00,800\n测试字幕\n", encoding="utf-8")
    source = tmp_path / "双音轨带字幕.mkv"
    ffmpeg(
        "-n",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=640x384:rate=24:duration=1",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=1",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=880:duration=1",
        "-i",
        subtitles,
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-map",
        "2:a",
        "-map",
        "3:s",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-c:s",
        "srt",
        source,
    )
    plan = interpolation.make_plan(source, Fraction(60), interpolation.MPV_ROOT, None)
    result = interpolation.export(plan)
    output = Path(result["output"])
    assert output.suffix == ".mkv"
    streams = interpolation.probe(output)["streams"]
    assert [s["codec_type"] for s in streams].count("audio") == 2
    assert [s["codec_type"] for s in streams].count("subtitle") == 1
    assert audio_hash(source) == audio_hash(output)


@GPU_TEST
def test_variable_timestamps_are_normalized_without_changing_playback_length(tmp_path):
    source = tmp_path / "变帧率源片.mkv"
    ffmpeg(
        "-n",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=640x384:rate=24:duration=1",
        "-vf",
        r"select=not(eq(mod(n\,3)\,2))",
        "-fps_mode",
        "vfr",
        "-c:v",
        "ffv1",
        source,
    )
    plan = interpolation.make_plan(source, Fraction(60), interpolation.MPV_ROOT, None)
    assert plan["normalize"]
    result = interpolation.export(plan)
    assert result["checks"]["duration"] == pytest.approx(plan["duration"], abs=1 / 60 + 0.003)
    assert result["checks"]["audio_tracks"] == 0


def test_skill_metadata_exposes_the_requested_chinese_command():
    import yaml

    skill = Path(__file__).resolve().parents[1] / ".agents/skills/补帧"
    document = (skill / "SKILL.md").read_text(encoding="utf-8")
    metadata = yaml.safe_load(document.split("---", 2)[1])
    interface = yaml.safe_load((skill / "agents/openai.yaml").read_text(encoding="utf-8"))
    assert metadata["name"] == "补帧"
    assert "$补帧" in interface["interface"]["default_prompt"]
    assert interface["policy"]["allow_implicit_invocation"]
    json.dumps(metadata, ensure_ascii=False)  # Metadata is serializable for discovery.
