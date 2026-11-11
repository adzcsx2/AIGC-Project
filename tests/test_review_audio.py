"""Regression coverage for audio coverage, review persistence, and versioned UI requests."""

import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
import zlib
from array import array
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest

from autodl_video.errors import AutoDLError

TOOL_DIR = Path(__file__).resolve().parents[1] / "tools/视频工具"
sys.path.insert(0, str(TOOL_DIR))


def load_tool(name, filename):
    spec = importlib.util.spec_from_file_location(name, TOOL_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = load_tool("audio_regression_core", "video_tools.py")
music = load_tool("audio_regression_music", "音乐.py")
review = load_tool("audio_regression_review", "审片.py")


def make_movie(path, audio_duration=None, offset=0, audio_filter=None):
    args = ["-f", "lavfi", "-i", "color=black:s=64x64:r=24:d=3"]
    if audio_duration is not None:
        args += [
            "-itsoffset",
            str(offset),
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=777:sample_rate=48000:duration={audio_duration}",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:a",
            "aac",
        ]
        if audio_filter:
            args += ["-af", audio_filter]
    core.ffmpeg([*args, "-c:v", "libx264", path])
    return path


def make_plan(folder, video, asset=None, start=0, end=3, source_in=0):
    manifest = folder / "materials.yaml"
    assets, cues = {}, []
    if asset:
        assets["MUSIC"] = {
            "kind": "audio",
            "state": "ready",
            "path": str(asset),
            "sha256": core.sha(asset),
        }
        cues.append(
            {
                "cue_id": "C1",
                "start_seconds": start,
                "end_seconds": end,
                "purpose": "验证",
                "entry_trigger": "开始",
                "exit_trigger": "结束",
                "instrumentation": "sine",
                "source_asset_id": "MUSIC",
                "source_in_seconds": source_in,
            }
        )
    regions = []
    if not cues:
        regions = [{"start_seconds": 0, "end_seconds": 3, "reason": "全片留白"}]
    else:
        if start:
            regions.append({"start_seconds": 0, "end_seconds": start, "reason": "开场留白"})
        if end < 3:
            regions.append({"start_seconds": end, "end_seconds": 3, "reason": "结尾留白"})
    plan = {
        "timeline": {
            "video_path": str(video),
            "video_sha256": core.sha(video),
            "duration_seconds": 3,
            "time_unit": "seconds",
            "time_origin": "edited_timeline_start",
            "verified": True,
        },
        "materials_manifest": str(manifest),
        "dialogue": {"source_has_embedded_music": False},
        "music": {"cues": cues, "no_music_regions": regions},
    }
    core.write_yaml(manifest, {"assets": assets})
    path = folder / "配乐方案.yaml"
    core.write_yaml(path, plan)
    return path, plan


def test_music_requires_actual_audio_samples_not_container_duration(tmp_path):
    video = make_movie(tmp_path / "静音.mp4")
    asset = make_movie(tmp_path / "短音轨.mp4", audio_duration=1)
    assert core.probe(asset)["duration"] == 3
    assert float(core.probe(asset)["audio"][0]["duration"]) == 1
    plan, _ = make_plan(tmp_path, video, asset)
    with pytest.raises(ValueError, match="音乐不足以覆盖"):
        music.mix(plan, tmp_path / "不应导出.mp4")
    assert not (tmp_path / "不应导出.mp4").exists()


def test_music_checks_late_start_and_renders_valid_source_in(tmp_path):
    video = make_movie(tmp_path / "静音.mp4")
    asset = make_movie(tmp_path / "延后音轨.mp4", audio_duration=1, offset=1)
    assert float(core.probe(asset)["audio"][0]["start_time"]) > 0.9
    path, plan = make_plan(tmp_path, video, asset, end=1)
    with pytest.raises(ValueError, match="音乐不足以覆盖"):
        music.validate(path)
    plan["music"]["cues"][0]["source_in_seconds"] = 1
    core.write_yaml(path, plan)
    output = music.mix(path, tmp_path / "有效入点.mp4")
    samples = core.ffmpeg(
        [
            "-ss",
            "0.2",
            "-t",
            "0.6",
            "-i",
            output,
            "-map",
            "0:a:0",
            "-c:a",
            "pcm_s16le",
            "-f",
            "s16le",
            "-",
        ]
    )
    assert any(samples)


def test_music_rejects_internal_audio_timestamp_gap(tmp_path):
    video = make_movie(tmp_path / "静音.mp4")
    asset = make_movie(
        tmp_path / "音轨含空洞.mp4",
        audio_duration=2,
        audio_filter="asetpts=PTS+gte(T\\,1)/TB",
    )
    assert core.probe(asset)["duration"] >= 3
    path, _ = make_plan(tmp_path, video, asset)
    with pytest.raises(ValueError, match="音乐不足以覆盖"):
        music.validate(path)


@pytest.mark.parametrize("embedded", [True, "unknown"])
def test_removing_all_cues_does_not_make_embedded_music_clean(tmp_path, embedded):
    video = make_movie(tmp_path / "带音乐.mp4", audio_duration=3)
    path, plan = make_plan(tmp_path, video)
    plan["dialogue"]["source_has_embedded_music"] = embedded
    core.write_yaml(path, plan)
    with pytest.raises(ValueError, match="干净对白底轨"):
        music.validate(path)


def test_no_audio_stream_can_remain_unscored_without_a_dialogue_stem(tmp_path):
    video = make_movie(tmp_path / "静音.mp4")
    path, plan = make_plan(tmp_path, video)
    plan["dialogue"] = {}
    core.write_yaml(path, plan)
    music.validate(path)


def test_music_project_boundary_checks_inputs_and_output(tmp_path):
    a, b = tmp_path / "作品甲", tmp_path / "作品乙"
    for folder in (a, b):
        core.write_yaml(folder / "project.yaml", {"name": folder.name})
    video = make_movie(a / "源片.mp4")
    path, plan = make_plan(a, video)
    with pytest.raises(AutoDLError, match="作品"):
        music.mix(path, b / "混音.mp4")
    assert not (b / "混音.mp4").exists()
    core.write_yaml(b / "materials.yaml", {"assets": {}})
    plan["materials_manifest"] = str(b / "materials.yaml")
    core.write_yaml(path, plan)
    with pytest.raises(AutoDLError, match="作品"):
        music.validate(path)


def music_cli(*arguments):
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(TOOL_DIR / "音乐.py"), *map(str, arguments)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


def make_multitrack(path, *, video=False):
    args = ["-f", "lavfi", "-i", "testsrc2=s=64x64:r=24:d=3"] if video else []
    for hz in (440, 880):
        args += ["-f", "lavfi", "-i", f"sine=frequency={hz}:sample_rate=48000:duration=3"]
    if video:
        args += ["-map", "0:v:0", "-c:v", "libx264"]
    args += [
        "-map",
        f"{int(video)}:a:0",
        "-map",
        f"{int(video) + 1}:a:0",
        "-c:a",
        "pcm_s16le",
        "-disposition:a:0",
        "0",
        "-disposition:a:1",
        "default",
    ]
    core.ffmpeg([*args, path])
    return path


@pytest.mark.parametrize("input_kind", ["video", "cue", "stem"])
def test_music_cli_requires_track_for_each_used_multitrack_input(tmp_path, input_kind):
    video = (
        make_multitrack(tmp_path / "多轨视频.mkv", video=True)
        if input_kind == "video"
        else make_movie(tmp_path / "静音视频.mp4")
    )
    asset = make_multitrack(tmp_path / "多轨音频.mka") if input_kind != "video" else None
    path, plan = make_plan(tmp_path, video, asset if input_kind == "cue" else None)
    if input_kind == "stem":
        core.write_yaml(
            tmp_path / "materials.yaml",
            {
                "assets": {
                    "STEM": {
                        "kind": "audio",
                        "state": "ready",
                        "path": str(asset),
                        "sha256": core.sha(asset),
                    }
                }
            },
        )
        plan["dialogue"]["stem_asset_id"] = "STEM"
        core.write_yaml(path, plan)
    output = tmp_path / "指定音轨混音.mkv"
    rejected = music_cli("mix", path, "--output", output)
    assert rejected.returncode != 0 and "audio_track" in rejected.stderr
    assert not output.exists()
    if input_kind == "cue":
        plan["music"]["cues"][0]["audio_track"] = 1
    else:
        plan["dialogue"]["stem_audio_track" if input_kind == "stem" else "audio_track"] = 1
    core.write_yaml(path, plan)
    before = {p: core.sha(p) for p in (video, asset) if p}
    accepted = music_cli("mix", path, "--output", output)
    assert accepted.returncode == 0, accepted.stderr
    samples = array(
        "f",
        core.ffmpeg(
            [
                "-ss",
                "0.5",
                "-t",
                "1",
                "-i",
                output,
                "-map",
                "0:a:0",
                "-ac",
                "1",
                "-ar",
                "48000",
                "-f",
                "f32le",
                "-",
            ]
        ),
    )
    amplitudes = {
        hz: abs(
            sum(
                value
                * complex(
                    math.cos(2 * math.pi * hz * i / 48000), math.sin(2 * math.pi * hz * i / 48000)
                )
                for i, value in enumerate(samples)
            )
        )
        for hz in (440, 880)
    }
    assert amplitudes[880] > amplitudes[440] * 20
    record = json.loads(core.media_record_path(output, "混音").read_text("utf-8"))
    selected = (
        record["audio_inputs"]["music"][0]
        if input_kind == "cue"
        else record["audio_inputs"]["dialogue"]
    )
    assert selected["audio_track"] == 1
    assert selected["sha256"] == core.sha(asset or video)
    assert record["actual_listening"] == "pending"
    assert all(core.sha(p) == digest for p, digest in before.items())


def signal_window(path):
    """Measure the signal at absolute stream PTS, including AAC decoder priming."""
    samples = array(
        "f",
        core.ffmpeg(
            [
                "-copyts",
                "-i",
                path,
                "-map",
                "0:a:0",
                "-ac",
                "1",
                "-ar",
                "48000",
                "-f",
                "f32le",
                "-",
            ]
        ),
    )
    active = [i for i, value in enumerate(samples) if abs(value) > 0.05]
    start = float(core.probe(path)["audio"][0].get("start_time", 0))
    return start + active[0] / 48000, start + active[-1] / 48000


@pytest.mark.parametrize("video_start,audio_start", [(1, 0), (0, 1), (5, 5), (5, 6)])
def test_music_cli_preserves_video_pts_and_absolute_dialogue_events(
    tmp_path, video_start, audio_start
):
    video = tmp_path / "延后时间戳.mkv"
    core.ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=64x64:r=24:d=3",
            "-f",
            "lavfi",
            "-i",
            r"aevalsrc=if(between(t\,1\,1.5)\,0.2*sin(2*PI*777*t)\,0):s=48000:d=3",
            "-vf",
            f"setpts=PTS+{video_start}/TB",
            "-af",
            f"asetpts=PTS+{audio_start}/TB",
            "-fps_mode",
            "passthrough",
            "-c:v",
            "libx264",
            "-c:a",
            "pcm_s16le",
            video,
        ]
    )
    path, plan = make_plan(tmp_path, video)
    duration = core.probe(video)["duration"]
    plan["timeline"]["duration_seconds"] = duration
    plan["music"]["no_music_regions"][0]["end_seconds"] = duration
    core.write_yaml(path, plan)
    output = tmp_path / "保留时间线混音.mkv"
    result = music_cli("mix", path, "--output", output)
    assert result.returncode == 0, result.stderr
    assert float(core.probe(output)["video"]["start_time"]) == video_start
    for before, after in zip(signal_window(video), signal_window(output), strict=True):
        assert abs(before - after) < 0.01
    assert core.ffmpeg(["-i", video, "-map", "0:v:0", "-c", "copy", "-f", "md5", "-"]) == (
        core.ffmpeg(["-i", output, "-map", "0:v:0", "-c", "copy", "-f", "md5", "-"])
    )


def make_gapped_dialogue(path, offset=0, gap_seconds=1):
    core.ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=64x64:r=24:d=3",
            "-f",
            "lavfi",
            "-i",
            r"aevalsrc=if(between(t\,1.1\,1.4)\,0.2*sin(2*PI*777*t)\,0):s=48000:d=2",
            "-vf",
            f"setpts=PTS+{offset}/TB",
            "-af",
            rf"asetpts=PTS+({offset}+{gap_seconds}*gte(T\,1))/TB",
            "-fps_mode",
            "passthrough",
            "-c:v",
            "libx264",
            "-c:a",
            "pcm_s16le",
            path,
        ]
    )
    return path


def audio_interval(path, start, end):
    return array(
        "f",
        core.ffmpeg(
            [
                "-copyts",
                "-i",
                path,
                "-map",
                "0:a:0",
                "-af",
                f"atrim=start={start}:end={end},asetpts=PTS-STARTPTS",
                "-ac",
                "1",
                "-ar",
                "48000",
                "-f",
                "f32le",
                "-",
            ]
        ),
    )


@pytest.mark.parametrize("offset", [0, 5])
@pytest.mark.parametrize("scored", [False, True])
@pytest.mark.parametrize("gap_seconds", [0.04, 1])
def test_music_cli_fills_dialogue_pts_gaps_without_interrupting_cues(
    tmp_path, offset, scored, gap_seconds
):
    video = make_gapped_dialogue(tmp_path / "对白内部缺样.mkv", offset, gap_seconds)
    gap_start, gap_end = offset + 1.01, offset + 1 + gap_seconds - 0.01
    assert not audio_interval(video, gap_start, gap_end)
    duration = core.probe(video)["duration"]
    asset = tmp_path / "连续音乐.wav" if scored else None
    if asset:
        core.ffmpeg(
            [
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=440:sample_rate=48000:duration={duration}",
                asset,
            ]
        )
    path, plan = make_plan(tmp_path, video, asset)
    plan["timeline"]["duration_seconds"] = duration
    if scored:
        plan["music"]["cues"][0].update(end_seconds=duration, gain_db=-18)
    else:
        plan["music"]["no_music_regions"][0]["end_seconds"] = duration
    core.write_yaml(path, plan)
    output = tmp_path / "对白保时且音乐连续.mkv"
    result = music_cli("mix", path, "--output", output)
    assert result.returncode == 0, result.stderr
    gap = audio_interval(output, gap_start, gap_end)
    # Require real decoded samples throughout the gap, not container-duration metadata.
    assert len(gap) >= round((gap_end - gap_start) * 48000) - 2
    if scored:
        amplitude = abs(
            sum(
                value
                * complex(
                    math.cos(2 * math.pi * 440 * i / 48000),
                    math.sin(2 * math.pi * 440 * i / 48000),
                )
                for i, value in enumerate(gap)
            )
        ) / len(gap)
        assert amplitude > 0.005  # The actual music frequency remains inside the dialogue gap.
    else:
        assert max(map(abs, gap)) < 0.0001
    # Music stays below this helper's threshold. The dialogue event must remain
    # at its known source PTS, including the gap and any initial offset.
    onset, ending = signal_window(output)
    assert abs(onset - (offset + gap_seconds + 1.1)) < 0.015
    assert abs(ending - (offset + gap_seconds + 1.4)) < 0.015
    assert core.ffmpeg(["-i", video, "-map", "0:v:0", "-c", "copy", "-f", "md5", "-"]) == (
        core.ffmpeg(["-i", output, "-map", "0:v:0", "-c", "copy", "-f", "md5", "-"])
    )
    record = json.loads(core.media_record_path(output, "混音").read_text("utf-8"))
    assert record["audio_timeline_coverage"] == "passed"
    assert record["actual_listening"] == "pending"


def test_mix_rejects_decodable_export_with_audio_pts_hole_before_publishing(tmp_path, monkeypatch):
    video = make_gapped_dialogue(tmp_path / "可解码但缺音轨区间.mkv")
    path, _ = make_plan(tmp_path, video)
    core.decode_check(video)

    def export_with_gap(arguments):
        # Inject a real, decodable but broken export at the encoder boundary.
        return core.ffmpeg(["-i", video, "-c", "copy", arguments[-1]])

    monkeypatch.setattr(music, "ffmpeg", export_with_gap)
    output = tmp_path / "不能发布.mkv"
    with pytest.raises(ValueError, match="导出音频时间线缺口"):
        music.mix(path, output)
    assert not output.exists()
    assert not core.media_record_path(output, "混音").exists()
    assert not list(tmp_path.glob(".混音-*"))


def test_music_source_in_uses_positive_source_pts(tmp_path):
    video = make_movie(tmp_path / "静音视频.mp4")
    asset = tmp_path / "晚起点音乐.mka"
    core.ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=777:sample_rate=48000:duration=3",
            "-af",
            "asetpts=PTS+5/TB",
            "-c:a",
            "pcm_s16le",
            asset,
        ]
    )
    path, _ = make_plan(tmp_path, video, asset, end=1, source_in=5)
    result = music_cli("mix", path, "--output", tmp_path / "源时间轴入点.mp4")
    assert result.returncode == 0, result.stderr


def test_music_cli_overlapping_dialogue_uses_one_gain_and_keeps_cue_fades(tmp_path):
    video = make_movie(tmp_path / "静音视频.mp4")
    asset = tmp_path / "连续音乐.wav"
    core.ffmpeg(["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=3", asset])
    path, plan = make_plan(tmp_path, video, asset)
    cue = plan["music"]["cues"][0]
    cue.update(gain_db=0, fade_in_seconds=0.2, fade_out_seconds=0.2)
    core.write_yaml(path, plan)
    control = tmp_path / "无避让.mp4"
    result = music_cli("mix", path, "--output", control)
    assert result.returncode == 0, result.stderr
    cue["dialogue_ducking"] = {
        "method": "regions",
        "gain_db": -12,
        # Unsorted, nested, duplicate, overlapping and touching dialogue regions.
        "regions": [
            {"start_seconds": a, "end_seconds": b}
            for a, b in [(1.2, 1.8), (0.5, 1.3), (0.5, 1.3), (0.7, 1), (1.8, 2.2), (2.28, 2.5)]
        ],
    }
    core.write_yaml(path, plan)
    output = tmp_path / "重叠对白避让.mp4"
    result = music_cli("mix", path, "--output", output)
    assert result.returncode == 0, result.stderr

    def rms(path, start, end):
        samples = audio_interval(path, start, end)
        return math.sqrt(sum(value * value for value in samples) / len(samples))

    for start, end in [(0.8, 0.95), (1.2, 1.3), (1.5, 1.6), (1.75, 1.85), (2.05, 2.15)]:
        gain = 20 * math.log10(rms(output, start, end) / rms(control, start, end))
        assert gain == pytest.approx(-12, abs=0.3)
    # Nearby disjoint regions have overlapping ramps: use their maximum envelope,
    # not two multiplied gains (which would reduce this window by about 9 dB).
    ramp_gain = 20 * math.log10(rms(output, 2.23, 2.25) / rms(control, 2.23, 2.25))
    # eval=frame quantizes the ramp to decoded audio block boundaries.
    assert -8 < ramp_gain < -3
    # The independent cue fades remain effective outside the dialogue regions.
    plateau = rms(output, 0.25, 0.35)
    assert rms(output, 0.02, 0.06) < plateau * 0.3
    assert rms(output, 2.94, 2.98) < plateau * 0.3


@pytest.mark.parametrize("input_kind", ["cue", "stem"])
@pytest.mark.parametrize("registered_audio_project", [True, False])
def test_music_rejects_foreign_project_audio_assets(tmp_path, input_kind, registered_audio_project):
    first, other = tmp_path / "作品甲", tmp_path / "作品乙"
    core.write_yaml(first / "project.yaml", {"name": first.name})
    other.mkdir()
    if registered_audio_project:
        core.write_yaml(other / "project.yaml", {"name": other.name})
    video = make_movie(first / "源片.mp4")
    asset = other / "配乐.wav"
    core.ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=777:sample_rate=48000:duration=3",
            asset,
        ]
    )
    path, plan = make_plan(first, video, asset if input_kind == "cue" else None)
    if input_kind == "stem":
        core.write_yaml(
            first / "materials.yaml",
            {
                "assets": {
                    "STEM": {
                        "kind": "audio",
                        "state": "ready",
                        "path": str(asset),
                        "sha256": core.sha(asset),
                    }
                }
            },
        )
        plan["dialogue"]["stem_asset_id"] = "STEM"
        core.write_yaml(path, plan)
    output = first / "不应导出.mp4"
    with pytest.raises(AutoDLError, match="作品"):
        music.mix(path, output)
    assert not output.exists()


@pytest.mark.parametrize("input_kind", ["cue", "stem"])
def test_music_standalone_temporary_mix_can_reference_unowned_audio(tmp_path, input_kind):
    work, external = tmp_path / "临时混音", tmp_path / "临时输入"
    work.mkdir()
    external.mkdir()
    video = make_movie(work / "视频.mp4")
    asset = external / "音频.wav"
    core.ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=777:sample_rate=48000:duration=3",
            asset,
        ]
    )
    path, plan = make_plan(work, video, asset)
    if input_kind == "stem":
        plan["dialogue"]["stem_asset_id"] = "MUSIC"
        plan["music"] = {
            "cues": [],
            "no_music_regions": [{"start_seconds": 0, "end_seconds": 3, "reason": "留白"}],
        }
        core.write_yaml(path, plan)
    output = work / "临时混音.mp4"
    assert music.mix(path, output) == output
    assert output.is_file()


@contextmanager
def running_service(config, tool_dir=TOOL_DIR):
    # Slow only the atomic write to make a lost read/modify/write deterministic
    # without a cross-process lock; all requests still run the real HTTP handler.
    script = """
import sys, time, importlib.util
from pathlib import Path
sys.path.insert(0, sys.argv[1])
spec = importlib.util.spec_from_file_location('review_child', Path(sys.argv[1]) / '审片.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)
original = review.write_json
def slow_write(path, data):
    time.sleep(0.08)
    original(path, data)
review.write_json = slow_write
server = review.server(sys.argv[2], 0)
print(server.review_url, flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
"""
    process = subprocess.Popen(
        [sys.executable, "-X", "utf8", "-c", script, str(tool_dir), str(config)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        url = process.stdout.readline().strip()
        assert url.startswith("http://127.0.0.1:"), process.stderr.read()
        yield url
    finally:
        process.terminate()
        process.communicate(timeout=10)


def test_http_records_survive_concurrent_services_and_abrupt_lock_owner_exit(tmp_path):
    core.write_yaml(tmp_path / "project.yaml", {"name": "隔离验证"})
    video = make_movie(tmp_path / "源片.mp4")
    config = review.prepare(tmp_path, [video])
    records = config.parent / "审片记录.json"
    history = {"id": "historical", "note": "旧审片依据"}
    core.write_json(records, [history])
    payload = {
        "media_id": "0",
        "sha256": core.sha(video),
        "dimension": "dynamic",
        "verdict": "pending",
        "reviewer": "regression",
        "start_seconds": 0,
        "end_seconds": 1,
    }
    with running_service(config) as first, running_service(config) as second:
        urls = [u.replace("/?", "/api/review?") for u in (first, second)]

        def save(index):
            with httpx.Client(trust_env=False) as client:
                return client.post(
                    urls[index % 2], json={**payload, "note": f"保存记录{index}"}
                ).status_code

        with ThreadPoolExecutor(max_workers=8) as pool:
            assert list(pool.map(save, range(12))) == [200] * 12
        saved = json.loads(records.read_text("utf-8"))
        assert len(saved) == 13
        assert saved[0] == history
        assert {x["note"] for x in saved[1:]} == {f"保存记录{i}" for i in range(12)}
        with httpx.Client(trust_env=False) as client:
            bad = client.post(urls[0], json={**payload, "note": "过期", "sha256": "bad"})
            assert bad.status_code == 400
        assert len(json.loads(records.read_text("utf-8"))) == 13

    script = """
import sys, time, importlib.util
from pathlib import Path
sys.path.insert(0, sys.argv[1])
spec = importlib.util.spec_from_file_location('review_lock_child', Path(sys.argv[1]) / '审片.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)
with review.record_lock(Path(sys.argv[2])):
    print('locked', flush=True)
    time.sleep(60)
"""
    owner = subprocess.Popen(
        [sys.executable, "-c", script, str(TOOL_DIR), str(records)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        assert owner.stdout.readline().strip() == "locked"
    finally:
        owner.terminate()
        owner.communicate(timeout=10)
    with running_service(config) as restarted:
        with httpx.Client(trust_env=False) as client:
            reply = client.post(
                restarted.replace("/?", "/api/review?"), json={**payload, "note": "异常退出后保存"}
            )
            assert reply.status_code == 200
    assert len(json.loads(records.read_text("utf-8"))) == 14


@contextmanager
def threaded_service(config):
    httpd = review.server(config, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.review_url.split("?", 1)
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_review_requires_finite_numeric_times_and_preserves_legacy_history(tmp_path):
    core.write_yaml(tmp_path / "project.yaml", {"name": "时间码验证"})
    video = make_movie(tmp_path / "源片.mp4")
    config = review.prepare(tmp_path, [video])
    records = config.parent / "审片记录.json"
    payload = {
        "media_id": "0", "sha256": core.sha(video), "dimension": "dynamic",
        "verdict": "pending", "reviewer": "regression", "note": "isolated timecode test",
        "start_seconds": 0, "end_seconds": 1,
    }
    history = {**payload, "start_seconds": "0", "end_seconds": "1", "id": "legacy"}
    core.write_json(records, [history])
    before = records.read_bytes()
    with threaded_service(config) as (base, query), httpx.Client(trust_env=False) as client:
        assert client.get(base + "api/session?" + query).json()["entries"] == [history]
        assert records.read_bytes() == before
        for field in ("start_seconds", "end_seconds"):
            for value in ("0", "1", True, False, None, [], {}, math.nan, math.inf, -math.inf,
                          10**400):
                response = client.post(
                    base + "api/review?" + query,
                    content=json.dumps({**payload, field: value}),
                    headers={"Content-Type": "application/json"},
                )
                assert response.status_code == 400, (field, value, response.text)
                assert records.read_bytes() == before
        for start, end in ((0, 1), (0.25, 1.5)):
            response = client.post(
                base + "api/review?" + query,
                json={**payload, "start_seconds": start, "end_seconds": end},
            )
            assert response.status_code == 200
            assert type(response.json()["start_seconds"]) is float
            assert type(response.json()["end_seconds"]) is float
        saved = client.get(base + "api/session?" + query).json()["entries"]
        assert saved[0] == history
        assert saved == json.loads(records.read_text("utf-8"))
        assert [(x["start_seconds"], x["end_seconds"]) for x in saved[1:]] == [
            (0.0, 1.0), (0.25, 1.5)
        ]


def test_review_frame_partial_write_is_not_published_and_retry_recovers(tmp_path, monkeypatch):
    core.write_yaml(tmp_path / "project.yaml", {"name": "缓存失败验证"})
    video = make_movie(tmp_path / "源片.mp4")
    config = review.prepare(tmp_path, [video])
    cache = config.parent / "检查帧" / core.sha(video)
    dest = cache / "帧-00000000.png"
    original_open = Path.open
    failed = False

    @contextmanager
    def failing_open(path, mode="r", *args, **kwargs):
        nonlocal failed
        with original_open(path, mode, *args, **kwargs) as stream:
            if mode == "xb" and path.parent == cache and not failed:
                class PartialWriter:
                    def write(self, data):
                        nonlocal failed
                        failed = True
                        stream.write(data[:8])
                        stream.flush()
                        raise OSError("injected partial frame write")

                yield PartialWriter()
            else:
                yield stream

    # Patch only the cache's exclusive temporary open, leaving all other I/O untouched.
    def patched_open(path, mode="r", *args, **kwargs):
        if mode == "xb" and path.parent == cache:
            return failing_open(path, mode, *args, **kwargs)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", patched_open)
    with threaded_service(config) as (base, query), httpx.Client(trust_env=False) as client:
        endpoint = base + "api/frame?id=0&frame=0&" + query
        first = client.get(endpoint)
        assert first.status_code == 409 and "partial frame write" in first.json()["error"]
        assert failed and not dest.exists() and not list(cache.glob("*.tmp"))
        second = client.get(endpoint)
        assert second.status_code == 200
        assert second.content == review.read_png(dest)
        assert client.get(endpoint).content == second.content


@pytest.mark.parametrize("damage", ["signature_only", "missing_end", "bad_checksum"])
def test_review_frame_repairs_old_corrupt_cache(tmp_path, damage):
    core.write_yaml(tmp_path / "project.yaml", {"name": "历史缓存修复验证"})
    video = make_movie(tmp_path / "源片.mp4")
    config = review.prepare(tmp_path, [video])
    dest = config.parent / "检查帧" / core.sha(video) / "帧-00000000.png"
    with threaded_service(config) as (base, query), httpx.Client(trust_env=False) as client:
        endpoint = base + "api/frame?id=0&frame=0&" + query
        original = client.get(endpoint)
        assert original.status_code == 200
        data = original.content
        if damage == "signature_only":
            data = data[:8]
        elif damage == "missing_end":
            data = data[:-12]
        else:
            data = data[:29] + bytes([data[29] ^ 1]) + data[30:]
        dest.write_bytes(data)
        recovered = client.get(endpoint)
        assert recovered.status_code == 200
        assert recovered.content == original.content == review.read_png(dest)


def test_review_frame_cache_is_atomic_across_service_processes(tmp_path):
    core.write_yaml(tmp_path / "project.yaml", {"name": "缓存并发验证"})
    video = make_movie(tmp_path / "源片.mp4")
    config = review.prepare(tmp_path, [video])
    dest = config.parent / "检查帧" / core.sha(video) / "帧-00000000.png"
    ready, release = tmp_path / "partial-ready", tmp_path / "release"
    script = r"""
import importlib.util, sys, time
from contextlib import contextmanager
from pathlib import Path
sys.path.insert(0, sys.argv[1])
spec = importlib.util.spec_from_file_location('cache_child', Path(sys.argv[1]) / '审片.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)
original = Path.open
ready, release = Path(sys.argv[3]), Path(sys.argv[4])
@contextmanager
def staged_open(path, mode, *args, **kwargs):
    with original(path, mode, *args, **kwargs) as stream:
        class StagedWriter:
            def write(self, data):
                stream.write(data[:8]); stream.flush(); ready.touch()
                deadline = time.monotonic() + 15
                while not release.exists():
                    if time.monotonic() >= deadline: raise RuntimeError('release timeout')
                    time.sleep(0.02)
                return 8 + stream.write(data[8:])
            def flush(self): return stream.flush()
            def fileno(self): return stream.fileno()
        yield StagedWriter()
def patched_open(path, mode='r', *args, **kwargs):
    if mode == 'xb' and path.suffix == '.tmp':
        return staged_open(path, mode, *args, **kwargs)
    return original(path, mode, *args, **kwargs)
Path.open = patched_open
server = review.server(sys.argv[2], 0)
print(server.review_url, flush=True)
server.serve_forever()
"""
    child = subprocess.Popen(
        [sys.executable, "-X", "utf8", "-c", script, str(TOOL_DIR), str(config),
         str(ready), str(release)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
    )
    try:
        first = child.stdout.readline().strip()
        assert first.startswith("http://127.0.0.1:"), child.stderr.read()
        with running_service(config) as second, ThreadPoolExecutor(max_workers=2) as pool:
            def fetch(url):
                with httpx.Client(trust_env=False, timeout=15) as client:
                    return client.get(url.replace("/?", "/api/frame?id=0&frame=0&"))

            first_request = pool.submit(fetch, first)
            deadline = time.monotonic() + 10
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            assert ready.exists() and not dest.exists()
            second_request = pool.submit(fetch, second)
            with pytest.raises(TimeoutError):
                second_request.result(timeout=0.3)
            assert not dest.exists()
            release.touch()
            a, b = first_request.result(timeout=15), second_request.result(timeout=15)
            assert a.status_code == b.status_code == 200
            assert a.content == b.content == review.read_png(dest)
            assert not list(dest.parent.glob("*.tmp"))
    finally:
        release.touch()
        child.terminate()
        child.communicate(timeout=10)


def review_dependency_fixture(tmp_path):
    core.write_yaml(tmp_path / "project.yaml", {"name": "隔离依赖验证"})
    video = make_movie(tmp_path / "源片.mp4")
    second = tmp_path / "第二版.mp4"
    shutil.copyfile(video, second)
    dependency = tmp_path / "工程.blend"
    dependency.write_bytes(b"a" * (4 * 1024 * 1024))
    config = review.prepare(
        tmp_path,
        [video, second],
        dependencies=[{"path": str(dependency), "sha256": core.sha(dependency)}],
    )
    return config, video, dependency


def test_review_hashes_unchanged_dependencies_once_across_concurrent_ranges(tmp_path, monkeypatch):
    config, video, dependency = review_dependency_fixture(tmp_path)
    original = review.hashlib.file_digest
    counts = {}
    count_lock = threading.Lock()

    def counted(stream, algorithm):
        path = Path(stream.name).resolve()
        with count_lock:
            counts[path] = counts.get(path, 0) + 1
        if path == dependency:
            time.sleep(0.1)  # Keep the initial miss open while other requests arrive.
        return original(stream, algorithm)

    monkeypatch.setattr(review.hashlib, "file_digest", counted)
    with threaded_service(config) as (base, query):
        barrier = threading.Barrier(8)

        def fetch(index):
            with httpx.Client(trust_env=False) as client:
                barrier.wait(timeout=10)
                return client.get(
                    base + "media?id=0&" + query,
                    headers={"Range": f"bytes={index * 10}-{index * 10 + 9}"},
                )

        with ThreadPoolExecutor(max_workers=8) as pool:
            replies = list(pool.map(fetch, range(8)))
        assert all(reply.status_code == 206 and len(reply.content) == 10 for reply in replies)
        with httpx.Client(trust_env=False) as client:
            assert client.get(base + "api/session?" + query).status_code == 200
            assert client.get(base + "api/frame?id=0&frame=0&" + query).status_code == 200
            assert counts[dependency] == counts[video] == 1
            # Metadata-only changes revalidate the bytes instead of invalidating
            # valid evidence or blindly keeping the previous cached fingerprint.
            info = dependency.stat()
            os.utime(dependency, ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000_000))
            assert client.get(base + "api/session?" + query).status_code == 200
            assert counts[dependency] == 2
            assert client.get(base + "api/session?" + query).status_code == 200
            assert counts[dependency] == 2


@pytest.mark.parametrize("changed", ["dependency", "media"])
def test_review_rejects_same_size_same_mtime_replacement(tmp_path, changed):
    config, video, dependency = review_dependency_fixture(tmp_path)
    target = dependency if changed == "dependency" else video
    with threaded_service(config) as (base, query), httpx.Client(trust_env=False) as client:
        endpoint = base + "api/session?" + query
        assert client.get(endpoint).status_code == 200
        info = target.stat()
        replacement = target.with_name("替换临时文件")
        replacement.write_bytes(b"x" * info.st_size)
        os.utime(replacement, ns=(info.st_atime_ns, info.st_mtime_ns))
        replacement.replace(target)
        assert target.stat().st_ino != info.st_ino
        assert client.get(endpoint).status_code == 409
        assert client.get(base + "media?id=0&" + query).status_code == 409


@pytest.mark.parametrize("changed", ["dependency", "media"])
def test_review_rejects_same_size_in_place_change_with_restored_mtime(tmp_path, changed):
    config, video, dependency = review_dependency_fixture(tmp_path)
    target = dependency if changed == "dependency" else video
    with threaded_service(config) as (base, query), httpx.Client(trust_env=False) as client:
        endpoint = base + "api/session?" + query
        assert client.get(endpoint).status_code == 200
        info = target.stat()
        with target.open("r+b") as writer:
            writer.write(b"changed")
        os.utime(target, ns=(info.st_atime_ns, info.st_mtime_ns))
        assert target.stat().st_ino == info.st_ino
        assert client.get(endpoint).status_code == 409


def test_review_blocks_dependency_changes_during_hash_read(tmp_path, monkeypatch):
    config, _, dependency = review_dependency_fixture(tmp_path)
    original = review.hashlib.file_digest
    modified = False

    def mutate_after_read(stream, algorithm):
        nonlocal modified
        digest = original(stream, algorithm)
        if Path(stream.name).resolve() == dependency and not modified:
            modified = True
            with pytest.raises(OSError):
                with dependency.open("ab") as writer:
                    writer.write(b"changed while checking")
        return digest

    monkeypatch.setattr(review.hashlib, "file_digest", mutate_after_read)
    with threaded_service(config) as (base, query), httpx.Client(trust_env=False) as client:
        endpoint = base + "api/session?" + query
        assert client.get(endpoint).status_code == 200
        assert modified
        # Once the reader releases the lease, a real modification still invalidates
        # the cache even if it happens to retain the same pathname and size.
        with dependency.open("r+b") as writer:
            writer.write(b"changed after reading")
        assert client.get(endpoint).status_code == 409


def assert_external_changes_blocked(source, replacement):
    script = r"""
import json, sys
from pathlib import Path
source, replacement = map(Path, sys.argv[1:])
results = {}
for action in ('write', 'replace', 'rename', 'parent_rename'):
    try:
        if action == 'write':
            with source.open('r+b') as stream: stream.write(b'corrupted by external writer')
        elif action == 'replace': replacement.replace(source)
        elif action == 'rename': source.rename(source.with_name('renamed-source.bin'))
        else: source.parent.rename(source.parent.with_name(source.parent.name + '-moved'))
        results[action] = 'changed'
    except OSError as exc:
        results[action] = {'winerror': exc.winerror, 'errno': exc.errno}
print(json.dumps(results))
"""
    child = subprocess.run(
        [sys.executable, "-c", script, str(source), str(replacement)],
        capture_output=True, text=True, encoding="utf-8", timeout=10,
    )
    assert child.returncode == 0, child.stderr
    results = json.loads(child.stdout)
    assert all(
        isinstance(value, dict)
        and (value["winerror"] in (5, 32, 33) or value["errno"] == 13)
        for value in results.values()
    ), results


def guarded_review_fixture(tmp_path, *, audio=False):
    core.write_yaml(tmp_path / "project.yaml", {"name": "受保护版本验证"})
    media = tmp_path / "媒体"
    media.mkdir()
    source = media / ("原音频.wav" if audio else "原视频.mp4")
    if audio:
        core.ffmpeg(["-f", "lavfi", "-i", "sine=frequency=777:duration=1", source])
    else:
        make_movie(source, audio_duration=3)
    replacement = tmp_path / "替换.bin"
    replacement.write_bytes(b"wrong replacement version")
    return source, replacement


def test_windows_read_guard_allows_process_readers_and_releases_on_error(tmp_path):
    source, replacement = guarded_review_fixture(tmp_path)
    ready, release = tmp_path / "reader-ready", tmp_path / "reader-release"
    script = r"""
import sys, time
from pathlib import Path
from autodl_video.read_guard import guarded_read
with guarded_read(sys.argv[1]) as stream:
    Path(sys.argv[2]).write_bytes(stream.read(32))
    while not Path(sys.argv[3]).exists(): time.sleep(0.02)
"""
    with review.guarded_read(source) as stream:
        assert not os.get_inheritable(stream.fileno())
        child = subprocess.Popen(
            [sys.executable, "-c", script, str(source), str(ready), str(release)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        try:
            deadline = time.monotonic() + 10
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            assert ready.exists()
            assert ready.read_bytes() == stream.read(32)
            assert_external_changes_blocked(source, replacement)
        finally:
            release.touch()
            _, stderr = child.communicate(timeout=10)
            assert child.returncode == 0, stderr
    with pytest.raises(RuntimeError), review.guarded_read(source):
        raise RuntimeError("consumer failed")
    with source.open("r+b"):
        pass
    source.rename(source.with_name("解除保护后可移动.mp4"))


@pytest.mark.parametrize("stage", ["probe", "decode_check", "file_digest"])
def test_prepare_holds_one_read_version_through_probe_decode_and_hash(tmp_path, monkeypatch, stage):
    source, replacement = guarded_review_fixture(tmp_path)
    digest = core.sha(source)
    owner = review.hashlib if stage == "file_digest" else review
    original = getattr(owner, stage)
    attacked = False

    def attack_after_stage(*args, **kwargs):
        nonlocal attacked
        result = original(*args, **kwargs)
        if not attacked:
            attacked = True
            assert_external_changes_blocked(source, replacement)
        return result

    monkeypatch.setattr(owner, stage, attack_after_stage)
    config = review.prepare(tmp_path, [source])
    data = json.loads(config.read_text("utf-8"))
    assert attacked and data["media"][0]["sha256"] == digest
    assert data["media"][0]["technical"] == "decode_passed"
    assert core.sha(source) == digest
    with source.open("r+b"):
        pass


def test_review_existing_writer_fails_closed_then_retries_without_copying_media(tmp_path):
    source, _ = guarded_review_fixture(tmp_path)
    config = review.prepare(tmp_path, [source])
    before = config.read_bytes()
    with threaded_service(config) as (base, query), httpx.Client(trust_env=False) as client:
        with source.open("r+b"):
            with pytest.raises(ValueError, match="正被写入或替换"):
                review.prepare(tmp_path, [source])
            assert config.read_bytes() == before
            for endpoint in ("api/session?", "media?id=0&", "api/frame?id=0&frame=0&"):
                response = client.get(base + endpoint + query)
                assert response.status_code == 409
                assert "正被写入或替换" in response.json()["error"]
        assert client.get(base + "media?id=0&" + query).content == source.read_bytes()
        assert client.get(base + "api/frame?id=0&frame=0&" + query).status_code == 200
    assert list(tmp_path.rglob("*.mp4")) == [source]


@pytest.mark.parametrize("audio", [False, True])
def test_http_range_streams_guarded_handle_and_rejects_external_replacement(
    tmp_path, monkeypatch, audio
):
    source, replacement = guarded_review_fixture(tmp_path, audio=audio)
    config = review.prepare(tmp_path, [source])
    expected = source.read_bytes()[:128]
    original = review.byte_range
    attacked = False

    def attack_after_validation(header, size):
        nonlocal attacked
        attacked = True
        assert_external_changes_blocked(source, replacement)
        return original(header, size)

    monkeypatch.setattr(review, "byte_range", attack_after_validation)
    with threaded_service(config) as (base, query), httpx.Client(trust_env=False) as client:
        response = client.get(base + "media?id=0&" + query, headers={"Range": "bytes=0-127"})
        assert response.status_code == 206 and response.content == expected
        assert attacked
    with source.open("r+b"):
        pass


def test_http_frame_holds_source_through_real_ffmpeg_and_releases_failure(tmp_path, monkeypatch):
    source, replacement = guarded_review_fixture(tmp_path)
    config = review.prepare(tmp_path, [source])
    original = review.ffmpeg
    calls = 0

    def attack_before_decode(arguments):
        nonlocal calls
        calls += 1
        assert_external_changes_blocked(source, replacement)
        if calls == 1:
            raise ValueError("injected encoder failure")
        return original(arguments)

    monkeypatch.setattr(review, "ffmpeg", attack_before_decode)
    with threaded_service(config) as (base, query), httpx.Client(trust_env=False) as client:
        endpoint = base + "api/frame?id=0&frame=0&" + query
        assert client.get(endpoint).status_code == 409
        with source.open("r+b"):
            pass
        response = client.get(endpoint)
        assert response.status_code == 200
        assert client.get(endpoint).content == response.content
        assert calls == 2
    cache = config.parent / "检查帧" / core.sha(source) / "帧-00000000.png"
    assert b'autodl-source\0' in cache.read_bytes()
    expected = core.ffmpeg([
        "-i", source, "-an", "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "md5", "-",
    ])
    actual = core.ffmpeg(["-i", cache, "-pix_fmt", "rgb24", "-f", "md5", "-"])
    assert actual == expected


def test_review_save_retains_source_lease_until_record_publication(tmp_path, monkeypatch):
    source, replacement = guarded_review_fixture(tmp_path)
    config = review.prepare(tmp_path, [source])
    original = review.write_owned_json
    attacked = False

    def attack_at_record_publication(project, path, value):
        nonlocal attacked
        attacked = True
        assert_external_changes_blocked(source, replacement)
        return original(project, path, value)

    monkeypatch.setattr(review, "write_owned_json", attack_at_record_publication)
    with threaded_service(config) as (base, query), httpx.Client(trust_env=False) as client:
        response = client.post(base + "api/review?" + query, json={
            "media_id": "0", "sha256": core.sha(source), "dimension": "stills",
            "verdict": "pending", "reviewer": "regression", "note": "isolated lease test",
            "start_seconds": 0, "end_seconds": 1,
        })
        assert response.status_code == 200 and attacked
    with source.open("r+b"):
        pass


@pytest.mark.parametrize("endpoint", ["session", "frame", "review", "range", "head", "416"])
def test_review_releases_source_before_client_observes_complete_response(
    tmp_path, monkeypatch, endpoint
):
    source, _ = guarded_review_fixture(tmp_path)
    dependency = tmp_path / "plan.yaml"
    dependency.write_text("notes: original\n", encoding="utf-8")
    digest = core.sha(source)
    config = review.prepare(
        tmp_path, [source],
        dependencies=[{"path": str(dependency), "sha256": core.sha(dependency)}],
    )
    httpd = review.server(config, port=0)
    sent, resume = threading.Event(), threading.Event()
    original_setup = httpd.RequestHandlerClass.setup

    def pause_after_complete_write(handler):
        original_setup(handler)
        writer = handler.wfile

        class PausedWriter:
            remaining = None

            def __getattr__(self, name):
                return getattr(writer, name)

            def write(self, data):
                result = writer.write(data)
                if self.remaining is None:
                    headers = bytes(data).decode("latin-1")
                    self.remaining = int(next(
                        line.split(":", 1)[1] for line in headers.split("\r\n")
                        if line.lower().startswith("content-length:")
                    ))
                    if handler.command == "HEAD":
                        self.remaining = 0
                else:
                    self.remaining -= len(data)
                if self.remaining == 0:
                    # All advertised bytes are already in the socket. Keep the
                    # handler inside write(), so a misplaced ExitStack is visible.
                    sent.set()
                    assert resume.wait(timeout=10), "client did not finish assertions"
                return result

        handler.wfile = PausedWriter()

    monkeypatch.setattr(httpd.RequestHandlerClass, "setup", pause_after_complete_write)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base, query = httpd.review_url.split("?", 1)
    try:
        with httpx.Client(trust_env=False) as client:
            if endpoint == "review":
                response = client.post(base + "api/review?" + query, json={
                    "media_id": "0", "sha256": digest, "dimension": "stills",
                    "verdict": "pending", "reviewer": "regression", "note": "response lease test",
                    "start_seconds": 0, "end_seconds": 1,
                })
            elif endpoint in {"session", "frame"}:
                suffix = "session?" if endpoint == "session" else "frame?id=0&frame=0&"
                response = client.get(base + "api/" + suffix + query)
            elif endpoint == "head":
                response = client.head(base + "media?id=0&" + query)
            else:
                requested = "bytes=0-127" if endpoint == "range" else "bytes=999999999-"
                response = client.get(base + "media?id=0&" + query, headers={"Range": requested})
            assert response.status_code == {"range": 206, "416": 416}.get(endpoint, 200)
            assert sent.wait(timeout=5)
            # A completed response must not require scheduling luck before a user
            # can save the plan or reopen the source for editing. No retries/sleeps.
            dependency.write_text("notes: immediately updated\n", encoding="utf-8")
            with source.open("r+b"):
                pass
    finally:
        resume.set()
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_media_stream_keeps_lease_until_last_chunk_is_frozen(tmp_path, monkeypatch):
    core.write_yaml(tmp_path / "project.yaml", {"name": "分块读取保护验证"})
    source = tmp_path / "合成多块音频.wav"
    core.ffmpeg([
        "-f", "lavfi", "-i", "sine=sample_rate=48000:duration=15", "-ac", "2", source,
    ])
    expected = source.read_bytes()
    assert len(expected) > 2 * 1024 * 1024
    replacement = tmp_path / "替换音频.wav"
    replacement.write_bytes(b"different source")
    config = review.prepare(tmp_path, [source])
    httpd = review.server(config, port=0)
    original_setup = httpd.RequestHandlerClass.setup
    checked, released = False, False

    def intercept_chunk_write(handler):
        original_setup(handler)
        writer = handler.wfile

        class CheckedWriter:
            headers_written = False
            remaining = len(expected)

            def __getattr__(self, name):
                return getattr(writer, name)

            def write(self, data):
                nonlocal checked, released
                if not self.headers_written:
                    self.headers_written = True
                elif handler.path.startswith("/media?"):
                    self.remaining -= len(data)
                    if not checked:
                        assert self.remaining > 0
                        assert_external_changes_blocked(source, replacement)
                        checked = True
                    elif not self.remaining:
                        # The final bytes are already detached from the source.
                        # A new edit must succeed even before sendall returns.
                        with source.open("r+b") as editor:
                            editor.write(b"new source version")
                        released = True
                return writer.write(data)

        handler.wfile = CheckedWriter()

    monkeypatch.setattr(httpd.RequestHandlerClass, "setup", intercept_chunk_write)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base, query = httpd.review_url.split("?", 1)
    try:
        with httpx.Client(trust_env=False) as client:
            response = client.get(base + "media?id=0&" + query)
            assert response.status_code == 200 and response.content == expected
            assert checked and released
            assert client.get(base + "api/session?" + query).status_code == 409
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("mismatch", ["unbound", "hash", "frame", "schema"])
def test_review_does_not_reuse_valid_png_from_wrong_source_snapshot(tmp_path, mismatch):
    source, _ = guarded_review_fixture(tmp_path)
    config = review.prepare(tmp_path, [source])
    digest = core.sha(source)
    cache = config.parent / "检查帧" / digest / "帧-00000000.png"
    cache.parent.mkdir(parents=True)
    png = core.ffmpeg([
        "-f", "lavfi", "-i", "color=red:s=64x64", "-frames:v", "1",
        "-f", "image2pipe", "-vcodec", "png", "-",
    ])
    binding = {"schema": 2, "sha256": digest, "frame": 0}
    if mismatch != "unbound":
        binding[{"hash": "sha256", "frame": "frame", "schema": "schema"}[mismatch]] = "wrong"
        text = b"autodl-source\0" + json.dumps(binding, sort_keys=True).encode("ascii")
        chunk = b"tEXt" + text
        chunk = len(text).to_bytes(4, "big") + chunk + zlib.crc32(chunk).to_bytes(4, "big")
        png = png[:-12] + chunk + png[-12:]
    cache.write_bytes(png)
    review.read_png(cache)  # The poisoned frame is valid PNG, not merely truncated bytes.
    with threaded_service(config) as (base, query), httpx.Client(trust_env=False) as client:
        response = client.get(base + "api/frame?id=0&frame=0&" + query)
        assert response.status_code == 200 and response.content != png
    expected = core.ffmpeg([
        "-i", source, "-an", "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "md5", "-",
    ])
    assert core.ffmpeg(["-i", cache, "-pix_fmt", "rgb24", "-f", "md5", "-"]) == expected


def test_page_preserves_version_speed_and_handles_range_playback_and_stale_frames():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is needed to execute the page's actual JavaScript")
    script = r"""
const fs=require('fs'), vm=require('vm'), assert=require('assert/strict');
const html=fs.readFileSync(process.argv[1],'utf8');
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const nodes={};
for(const id of ['media','player','end','start','technical','exact','seams','entries',
  'play','back','next','speed','setStart','setEnd','range','loop','time','getFrame','frame',
  'status','save','dimension','verdict','reviewer','note']){
  nodes[id]={value:'',hidden:true,src:'',checked:false,children:[],
    replaceChildren(){this.children=[]},
    removeAttribute(key){this[key]=''},
    add(option){if(!this.value)this.value=option.value},append(child){this.children.push(child)},
    play(){this.paused=false;this.ended=false;this.playCount=(this.playCount||0)+1;
      return Promise.resolve()},pause(){this.paused=true}};
}
nodes.speed.value='1';
Object.defineProperty(nodes.player,'src',{
  get(){return this.mediaSrc||''},
  set(value){this.mediaSrc=value;this.playbackRate=this.defaultPlaybackRate||1;
    this.currentTime=0;this.paused=true;this.ended=false}
});
const session={media:[{id:'A',sha256:'a',duration:3},{id:'B',sha256:'b',duration:3}],
  entries:[null,{sha256:'a',start_seconds:'0',end_seconds:'1',note:'legacy strings'},
    {sha256:'a',start_seconds:false,end_seconds:true,note:'legacy booleans'},
    {sha256:'a',start_seconds:null,end_seconds:1,note:'legacy missing value'},
    {sha256:'a',start_seconds:'',end_seconds:1,note:'legacy empty string'},
    {sha256:'a',start_seconds:'Infinity',end_seconds:1,note:'legacy nonfinite'},
    {sha256:'a',start_seconds:2,end_seconds:1,note:'legacy reversed range'}],seams:[]};
const pending=[], urls=[];
const context=vm.createContext({document:{getElementById:id=>nodes[id],createElement:()=>({})},
  location:{search:'?token=test'},URLSearchParams,AbortController,
  URL:{createObjectURL:blob=>{urls.push(blob);return 'blob:'+blob.name},revokeObjectURL(){}},
  Option:function(text,value){this.text=text;this.value=value},
  fetch:(path,options)=>path==='/api/session'
    ?Promise.resolve({ok:true,json:async()=>session})
    :new Promise(resolve=>pending.push({resolve,options})),console});
vm.runInContext(code,context);
setImmediate(()=>{(async()=>{
  assert.equal(nodes.entries.children.length,6);
  assert(nodes.entries.children[5].textContent.startsWith('0.000–1.000s'));
  assert(nodes.entries.children.slice(0,5).every(x=>x.textContent.startsWith('时间码无效')));
  assert.equal(nodes.status.textContent,undefined);
  nodes.frame.value='0';
  const a=nodes.getFrame.onclick();
  nodes.speed.value='2';nodes.speed.onchange();
  assert.equal(nodes.player.playbackRate,2);
  nodes.media.value='B';nodes.media.onchange();
  nodes.player.onloadedmetadata();
  assert.equal(nodes.speed.value,'2');assert.equal(nodes.player.playbackRate,2);
  assert.equal(pending[0].options.signal.aborted,true);
  pending[0].resolve({ok:true,blob:async()=>({name:'A'})});await a;
  assert.equal(nodes.exact.hidden,true);assert.equal(urls.length,0);
  const old=nodes.getFrame.onclick();
  nodes.frame.value='1';const latest=nodes.getFrame.onclick();
  pending[2].resolve({ok:true,blob:async()=>({name:'B-latest'})});await latest;
  pending[1].resolve({ok:true,blob:async()=>({name:'B-old'})});await old;
  assert.equal(nodes.exact.src,'blob:B-latest');assert.equal(urls.length,1);
  nodes.start.value='0.5';nodes.end.value='1';await nodes.range.onclick();
  nodes.player.currentTime=1.05;nodes.player.ontimeupdate();
  assert.equal(nodes.player.currentTime,1);assert.equal(nodes.player.paused,true);
  await nodes.play.onclick();nodes.player.currentTime=1.5;nodes.player.ontimeupdate();
  assert.equal(nodes.player.currentTime,1.5);assert.equal(nodes.player.paused,false);
  nodes.loop.checked=true;await nodes.range.onclick();
  nodes.player.currentTime=1.05;nodes.player.ontimeupdate();
  assert.equal(nodes.player.currentTime,0.5);assert.equal(nodes.player.paused,false);
  await nodes.play.onclick();await nodes.play.onclick();
  nodes.player.currentTime=1.5;nodes.player.ontimeupdate();
  assert.equal(nodes.loop.checked,false);assert.equal(nodes.player.currentTime,1.5);
  nodes.loop.checked=true;nodes.start.value='0';nodes.end.value='3';
  await nodes.range.onclick();
  nodes.player.currentTime=3;nodes.player.paused=true;nodes.player.ended=true;
  nodes.player.ontimeupdate();await nodes.player.onended();
  assert.equal(nodes.player.currentTime,0);assert.equal(nodes.player.paused,false);
  nodes.loop.checked=false;nodes.player.paused=true;
  const count=nodes.player.playCount;await nodes.player.onended();
  assert.equal(nodes.player.playCount,count);
  nodes.start.value='4';await nodes.range.onclick();
  assert.equal(nodes.player.playCount,count);
  nodes.start.value='0';nodes.end.value='1';nodes.loop.checked=true;
  await nodes.range.onclick();nodes.media.value='A';nodes.media.onchange();
  assert.equal(nodes.loop.checked,false);assert.equal(nodes.player.paused,true);
  assert.equal(nodes.exact.hidden,true);assert.equal(nodes.player.playbackRate,2);
  await nodes.player.play();nodes.player.currentTime=2;nodes.player.ontimeupdate();
  assert.equal(nodes.player.currentTime,2);assert.equal(nodes.player.paused,false);
  console.log('version speed, range playback and stale frames passed');
})().catch(error=>{console.error(error);process.exitCode=1})});
"""
    result = subprocess.run(
        [node, "-e", script, str(TOOL_DIR / "审片网页/index.html")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "version speed, range playback and stale frames passed" in result.stdout


def directory_link(path, target):
    """Use real NTFS junctions on Windows, not mocked resolve/ownership checks."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(path), str(target)],
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr.decode(errors="replace")
    else:
        path.symlink_to(target, target_is_directory=True)


def two_works(tmp_path):
    first, other = tmp_path / "作品甲", tmp_path / "作品乙"
    for folder in (first, other):
        core.write_yaml(folder / "project.yaml", {"name": folder.name})
    (other / "保留原件.txt").write_text("do not modify", encoding="utf-8")
    return first, other


@pytest.mark.parametrize("relative", ["02-素材", "02-素材/音频", "02-素材/音频/配乐"])
def test_music_import_rejects_foreign_junction_before_copy_or_manifest_change(tmp_path, relative):
    first, other = two_works(tmp_path)
    manifest = first / "materials.yaml"
    core.write_yaml(manifest, {"assets": {}})
    source = tmp_path / "外部音频.wav"
    core.ffmpeg(["-f", "lavfi", "-i", "sine=duration=0.2", source])
    directory_link(first / relative, other)
    before = manifest.read_bytes()
    result = music_cli(
        "import",
        source,
        "--manifest",
        manifest,
        "--asset-id",
        "MUSIC",
        "--name",
        "导入配乐.wav",
        "--provenance",
        "isolated regression",
    )
    assert result.returncode != 0 and "作品" in result.stderr
    assert manifest.read_bytes() == before
    assert sorted(p.name for p in other.iterdir()) == ["project.yaml", "保留原件.txt"]


@pytest.mark.parametrize(
    "relative", ["05-检查与验收", "05-检查与验收/网页审片", "05-检查与验收/网页审片/审片会话.json"]
)
def test_review_prepare_rejects_junctions_at_each_destination_level(tmp_path, relative):
    first, other = two_works(tmp_path)
    video = make_movie(first / "样片.mp4")
    directory_link(first / relative, other)
    with pytest.raises(ValueError, match="当前作品"):
        review.prepare(first, [video])
    assert sorted(p.name for p in other.iterdir()) == ["project.yaml", "保留原件.txt"]


def test_review_prepare_preserves_current_session_when_history_is_a_foreign_junction(tmp_path):
    first, other = two_works(tmp_path)
    video = make_movie(first / "样片.mp4")
    config = review.prepare(first, [video])
    before = config.read_bytes()
    directory_link(config.parent / "历史会话", other)
    video.write_bytes(video.read_bytes() + b"updated version")
    with pytest.raises(ValueError, match="当前作品"):
        review.prepare(first, [video])
    assert config.read_bytes() == before
    assert sorted(p.name for p in other.iterdir()) == ["project.yaml", "保留原件.txt"]


@pytest.mark.parametrize("target", ["records", "lock", "cache", "hash_folder", "frame"])
def test_review_rechecks_child_write_paths_after_service_start(tmp_path, target):
    first, other = two_works(tmp_path)
    video = make_movie(first / "样片.mp4")
    config = review.prepare(first, [video])
    data = json.loads(config.read_text("utf-8"))
    if target == "records":
        data["records"] = str(first / "独立记录" / "记录.json")
        core.write_json(config, data)
        link = first / "独立记录"
    elif target == "lock":
        link = Path(data["records"] + ".lock")
    else:
        link = config.parent / "检查帧"
        if target in {"hash_folder", "frame"}:
            link = link / core.sha(video)
        if target == "frame":
            link = link / "帧-00000000.png"
    with threaded_service(config) as (base, query), httpx.Client(trust_env=False) as client:
        assert client.get(base + "api/session?" + query).status_code == 200
        directory_link(link, other)
        if target in {"records", "lock"}:
            response = client.post(
                base + "api/review?" + query,
                json={
                    "media_id": "0",
                    "sha256": core.sha(video),
                    "start_seconds": 0,
                    "end_seconds": 1,
                    "dimension": "dynamic",
                    "verdict": "pending",
                    "reviewer": "test",
                    "note": "reject redirected record",
                },
            )
            assert response.status_code == 400
        else:
            response = client.get(base + "api/frame?id=0&frame=0&" + query)
            assert response.status_code == 409
        assert "当前作品" in response.json()["error"]
    assert sorted(p.name for p in other.iterdir()) == ["project.yaml", "保留原件.txt"]


def whitebox_http_fixture(tmp_path):
    """Clone the real entry points so implementation changes never touch shared code."""
    import whitebox_core

    tool_dir = tmp_path / "独立工具" / "视频工具"
    tool_dir.mkdir(parents=True)
    names = [
        "whitebox_blender.py",
        "whitebox_core.py",
        "白模.py",
        "video_tools.py",
        "whitebox_saved.py",
    ]
    for name in [*names, "审片.py"]:
        shutil.copyfile(TOOL_DIR / name, tool_dir / name)
    work = tmp_path / "作品"
    core.write_yaml(work / "project.yaml", {"name": "隔离白模"})
    blend = work / "工程.blend"
    blend.write_bytes(b"isolated saved-input fingerprint; no Blender run")
    plan_path = work / "白模计划.yaml"
    core.write_yaml(
        plan_path,
        {
            "schema_version": 1,
            "fps": {"num": 24, "den": 1},
            "frame_count": 72,
            "source": {"blend": blend.name, "sha256": core.sha(blend)},
            "subjects": {"A": {"objects": ["Subject"]}},
            "shots": [
                {
                    "id": "S1",
                    "start_frame": 0,
                    "end_frame": 72,
                    "camera": "Camera",
                    "subjects": ["A"],
                }
            ],
        },
    )
    context = whitebox_core.load_plan(plan_path)
    job, report = work / "执行输入.json", work / "场景检查.json"
    core.write_json(job, {"isolated": True})
    core.write_json(report, {"failures": [], "isolated": True})
    movie = make_movie(work / "审片版.mp4")
    bundle = {
        "schema_version": 1,
        "dependencies": context["dependencies"],
        "implementation": [whitebox_core.descriptor(tool_dir / name) for name in names],
        "job": whitebox_core.descriptor(job),
        "artifacts": [whitebox_core.descriptor(report), whitebox_core.descriptor(movie)],
        "status": "checks_passed",
    }
    bundle_path = work / "白模检查包.json"
    core.write_json(bundle_path, bundle)
    return tool_dir, plan_path, bundle_path, bundle, job, report, movie


def whitebox_cli(tool_dir, command, plan, bundle):
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(tool_dir / "白模.py"), command, str(plan), str(bundle)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


@pytest.mark.parametrize("changed", ["job", "report", "implementation"])
def test_whitebox_review_http_invalidates_every_bundle_dependency(tmp_path, changed):
    tool_dir, plan, bundle_path, _, job, report, movie = whitebox_http_fixture(tmp_path)
    prepared = whitebox_cli(tool_dir, "review", plan, bundle_path)
    assert prepared.returncode == 0, prepared.stderr
    config = Path(json.loads(prepared.stdout)["session"])
    with running_service(config, tool_dir) as url, httpx.Client(trust_env=False) as client:
        endpoint = url.replace("/?", "/api/session?")
        assert client.get(endpoint).status_code == 200
        assert client.get(endpoint).status_code == 200  # Warm the normal hash cache.
        target = {"job": job, "report": report, "implementation": tool_dir / "whitebox_blender.py"}[
            changed
        ]
        target.write_bytes(target.read_bytes() + b"\nchanged")
        assert client.get(endpoint).status_code == 409
        saved = client.post(
            url.replace("/?", "/api/review?"),
            json={
                "media_id": "0",
                "sha256": core.sha(movie),
                "start_seconds": 0,
                "end_seconds": 1,
                "dimension": "dynamic",
                "verdict": "pending",
                "reviewer": "test",
                "note": "stale dependency must fail",
            },
        )
        assert saved.status_code == 400
    check = whitebox_cli(tool_dir, "check-bundle", plan, bundle_path)
    assert check.returncode != 0 and "已变化" in check.stderr
    records = Path(json.loads(config.read_text("utf-8"))["records"])
    assert not records.exists()


@pytest.mark.parametrize("invalid", ["empty", "missing", "duplicate", "external"])
def test_whitebox_bundle_and_server_require_exact_tool_implementation_whitelist(tmp_path, invalid):
    tool_dir, plan, bundle_path, bundle, _, _, _ = whitebox_http_fixture(tmp_path)
    prepared = whitebox_cli(tool_dir, "review", plan, bundle_path)
    assert prepared.returncode == 0, prepared.stderr
    config = Path(json.loads(prepared.stdout)["session"])
    implementation = list(bundle["implementation"])
    if invalid == "empty":
        implementation = []
    elif invalid == "missing":
        implementation.pop()
    elif invalid == "duplicate":
        implementation[0] = implementation[1]
    else:
        external = tmp_path / "任意外部脚本.py"
        external.write_text("# unrelated file", encoding="utf-8")
        implementation[0] = {"path": str(external), "sha256": core.sha(external)}
    bundle["implementation"] = implementation
    core.write_json(bundle_path, bundle)
    checked = whitebox_cli(tool_dir, "check-bundle", plan, bundle_path)
    assert checked.returncode != 0 and "白名单" in checked.stderr
    session = json.loads(config.read_text("utf-8"))
    session["implementation"] = implementation
    core.write_json(config, session)
    served = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(tool_dir / "审片.py"),
            "serve",
            str(config),
            "--port",
            "0",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    assert served.returncode != 0 and "白名单" in served.stderr


def test_mix_two_containers_have_independent_immutable_records(tmp_path):
    movie = make_movie(tmp_path / "源片.mp4")
    plan, _ = make_plan(tmp_path, movie)
    first = music.mix(plan, tmp_path / "同名.mp4")
    first_record = core.media_record_path(first, "混音")
    saved = first_record.read_bytes()
    second = music.mix(plan, tmp_path / "同名.mkv")
    second_record = core.media_record_path(second, "混音")
    assert first_record != second_record and first_record.read_bytes() == saved
    for output, record in ((first, first_record), (second, second_record)):
        data = json.loads(record.read_text("utf-8"))
        assert data["output"] == str(output) and data["sha256"] == core.sha(output)
        assert data["actual_listening"] == "pending"


@pytest.mark.parametrize(
    "action,kind,suffix", [("mix", "混音", ".mp4"), ("create", "制作", ".wav")]
)
def test_music_preserves_orphan_record_before_creating_media(tmp_path, action, kind, suffix):
    if action == "mix":
        movie = make_movie(tmp_path / "源片.mp4")
        config, _ = make_plan(tmp_path, movie)
    else:
        config = tmp_path / "音符.yaml"
        core.write_yaml(
            config,
            {
                "duration_seconds": 0.2,
                "notes": [
                    {"start_seconds": 0, "duration_seconds": 0.2, "midi_note": 60},
                ],
            },
        )
    output = tmp_path / ("保留记录" + suffix)
    record = core.media_record_path(output, kind)
    record.write_bytes(b"earlier evidence")
    rejected = music_cli(action, config, "--output", output)
    assert rejected.returncode != 0 and "记录已存在" in rejected.stderr
    assert record.read_bytes() == b"earlier evidence" and not output.exists()


def test_music_cli_create_import_review_gate_and_mix_complete_chain(tmp_path):
    work = tmp_path / "作品"
    core.write_yaml(work / "project.yaml", {"name": "音乐流程"})
    movie = make_movie(work / "无配乐母版.mp4")
    plan_path, plan = make_plan(work, movie)
    notes, sketch = tmp_path / "音符.yaml", tmp_path / "器乐草稿.wav"
    core.write_yaml(
        notes,
        {
            "duration_seconds": 3,
            "notes": [
                {"start_seconds": 0, "duration_seconds": 3, "midi_note": 60},
            ],
        },
    )
    created = music_cli("create", notes, "--output", sketch)
    assert created.returncode == 0, created.stderr
    creation = json.loads(core.media_record_path(sketch, "制作").read_text("utf-8"))
    assert creation["ai_model"] is None and creation["status"] == "draft_requires_listening"
    imported = music_cli(
        "import",
        sketch,
        "--manifest",
        work / "materials.yaml",
        "--asset-id",
        "MUSIC",
        "--name",
        "正式配乐.wav",
        "--provenance",
        "本地器乐验证",
    )
    assert imported.returncode == 0, imported.stderr
    asset_path = Path(json.loads(imported.stdout))
    assert asset_path.is_relative_to(work / "02-素材/音频/配乐")
    assert core.sha(asset_path) == core.sha(sketch)
    manifest = core.read_yaml(work / "materials.yaml")
    assert manifest["assets"]["MUSIC"]["state"] == "needs_review"
    plan["music"] = {
        "no_music_regions": [],
        "cues": [
            {
                "cue_id": "C1",
                "start_seconds": 0,
                "end_seconds": 3,
                "purpose": "验证",
                "entry_trigger": "开始",
                "exit_trigger": "结束",
                "instrumentation": "器乐",
                "source_asset_id": "MUSIC",
            }
        ],
    }
    core.write_yaml(plan_path, plan)
    pending = music_cli("validate", plan_path)
    assert pending.returncode != 0 and "尚未检查" in pending.stderr
    manifest["assets"]["MUSIC"]["state"] = "ready"
    core.write_yaml(work / "materials.yaml", manifest)
    output = work / "配乐版.mp4"
    original = core.sha(movie)
    mixed = music_cli("mix", plan_path, "--output", output)
    assert mixed.returncode == 0, mixed.stderr
    assert core.sha(movie) == original
    record = json.loads(core.media_record_path(output, "混音").read_text("utf-8"))
    assert record["sha256"] == core.sha(output) and record["actual_listening"] == "pending"


@pytest.mark.parametrize("entry", ["import", "prepare"])
def test_write_boundaries_reject_nested_registered_work_without_a_link(tmp_path, entry):
    work, _ = two_works(tmp_path)
    nested = work / ("02-素材/音频/配乐" if entry == "import" else "05-检查与验收/网页审片")
    core.write_yaml(nested / "project.yaml", {"name": "嵌套的另一作品"})
    if entry == "import":
        manifest = work / "materials.yaml"
        core.write_yaml(manifest, {"assets": {}})
        source = tmp_path / "输入.wav"
        core.ffmpeg(["-f", "lavfi", "-i", "sine=duration=0.2", source])
        with pytest.raises(AutoDLError, match="作品"):
            music.import_asset(source, manifest, "M", "配乐.wav", "test")
        assert core.read_yaml(manifest) == {"assets": {}}
    else:
        movie = make_movie(work / "样片.mp4")
        with pytest.raises(ValueError, match="当前作品"):
            review.prepare(work, [movie])
    assert [p.name for p in nested.iterdir()] == ["project.yaml"]


@pytest.mark.parametrize("same_id", [False, True])
def test_music_cli_concurrent_imports_preserve_registrations_and_recheck_ids(tmp_path, same_id):
    work = tmp_path / "作品"
    core.write_yaml(work / "project.yaml", {"name": "并发音乐导入"})
    manifest = work / "materials.yaml"
    original = {"assets": {"KEEP": {"provenance": "既有登记"}}, "schema_version": 2}
    core.write_yaml(manifest, original)
    sources = [tmp_path / f"源音频{i}.wav" for i in (1, 2)]
    for index, source in enumerate(sources, 1):
        core.ffmpeg(["-f", "lavfi", "-i", f"sine=frequency={440 * index}:duration=0.2", source])
    hashes = [core.sha(source) for source in sources]
    staged, release = tmp_path / "登记前就绪", tmp_path / "允许登记"
    # Hold the first real CLI at the final manifest-write boundary. The second
    # CLI must wait, then reload; atomic replacement alone loses its registration.
    script = """
import importlib.util, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
spec = importlib.util.spec_from_file_location('music_child', Path(sys.argv[1]) / '音乐.py')
music = importlib.util.module_from_spec(spec)
spec.loader.exec_module(music)
staged, release = Path(sys.argv[2]), Path(sys.argv[3])
original = music.write_yaml
def delayed_write(path, data):
    staged.write_text('media published; manifest not committed', encoding='utf-8')
    deadline = time.monotonic() + 20
    while not release.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError('test release was not received')
        time.sleep(0.01)
    original(path, data)
music.write_yaml = delayed_write
sys.argv = ['音乐.py', *sys.argv[4:]]
music.main()
"""

    def arguments(index, asset_id):
        return [
            "import",
            str(sources[index - 1]),
            "--manifest",
            str(manifest),
            "--asset-id",
            asset_id,
            "--name",
            f"配乐{index}.wav",
            "--provenance",
            "isolated concurrent import",
        ]

    first = subprocess.Popen(
        [
            sys.executable,
            "-X",
            "utf8",
            "-c",
            script,
            str(TOOL_DIR),
            str(staged),
            str(release),
            *arguments(1, "M1"),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    second = None
    try:
        deadline = time.monotonic() + 10
        while not staged.exists() and first.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert staged.exists(), "first CLI did not reach the manifest publication boundary"
        second = subprocess.Popen(
            [
                sys.executable,
                "-X",
                "utf8",
                str(TOOL_DIR / "音乐.py"),
                *arguments(2, "M1" if same_id else "M2"),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        try:
            second.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            pass  # It is correctly waiting for the first manifest transaction.
        finally:
            release.write_text("continue", encoding="utf-8")
        _, first_error = first.communicate(timeout=15)
        _, second_error = second.communicate(timeout=15)
        assert first.returncode == 0, first_error
        if same_id:
            assert second.returncode != 0 and "资产 ID 已存在" in second_error
        else:
            assert second.returncode == 0, second_error
    finally:
        release.touch()
        for process in (first, second):
            if process is not None and process.poll() is None:
                process.terminate()
                process.communicate(timeout=5)
    saved = core.read_yaml(manifest)
    assert saved["schema_version"] == 2
    assert saved["assets"]["KEEP"] == original["assets"]["KEEP"]
    assert set(saved["assets"]) == ({"KEEP", "M1"} if same_id else {"KEEP", "M1", "M2"})
    expected_assets = [(1, "M1")] if same_id else [(1, "M1"), (2, "M2")]
    for index, asset_id in expected_assets:
        asset = saved["assets"][asset_id]
        path = (manifest.parent / asset["path"]).resolve()
        assert path.name == f"配乐{index}.wav" and core.sha(path) == hashes[index - 1]
        assert asset["sha256"] == hashes[index - 1] and asset["state"] == "needs_review"
    assert (work / "02-素材/音频/配乐/配乐2.wav").exists() is (not same_id)
    assert [core.sha(source) for source in sources] == hashes


@pytest.mark.parametrize("deduplicated", [False, True])
def test_music_import_manifest_failure_preserves_inputs_and_allows_retry(
    tmp_path, monkeypatch, deduplicated
):
    work = tmp_path / "作品"
    core.write_yaml(work / "project.yaml", {"name": "导入恢复"})
    manifest = work / "materials.yaml"
    core.write_yaml(manifest, {"assets": {"KEEP": {"provenance": "原记录"}}})
    source = tmp_path / "源音乐.wav"
    core.ffmpeg(["-f", "lavfi", "-i", "sine=duration=0.2", source])
    existing = work / "原有配乐.wav"
    if deduplicated:
        shutil.copyfile(source, existing)
    output = existing if deduplicated else work / "02-素材/音频/配乐/导入配乐.wav"
    before, source_hash = manifest.read_bytes(), core.sha(source)

    def fail_registration(path, data):
        assert Path(path) == manifest and output.is_file()
        assert core.sha(output) == source_hash
        raise OSError("synthetic manifest write failure after media publication")

    monkeypatch.setattr(music, "write_yaml", fail_registration)
    with pytest.raises(OSError, match="synthetic manifest"):
        music.import_asset(source, manifest, "MUSIC", "导入配乐.wav", "isolated retry")
    assert manifest.read_bytes() == before and core.sha(source) == source_hash
    assert output.exists() is deduplicated
    retried = music_cli(
        "import",
        source,
        "--manifest",
        manifest,
        "--asset-id",
        "MUSIC",
        "--name",
        "导入配乐.wav",
        "--provenance",
        "isolated retry",
    )
    assert retried.returncode == 0, retried.stderr
    assert Path(json.loads(retried.stdout)) == output
    assert core.sha(output) == source_hash
    assert set(core.read_yaml(manifest)["assets"]) == {"KEEP", "MUSIC"}


def test_music_import_failure_does_not_remove_replacement_file(tmp_path, monkeypatch):
    work = tmp_path / "作品"
    core.write_yaml(work / "project.yaml", {"name": "回滚所有权"})
    manifest = work / "materials.yaml"
    core.write_yaml(manifest, {"assets": {}})
    source = tmp_path / "源音乐.wav"
    core.ffmpeg(["-f", "lavfi", "-i", "sine=duration=0.2", source])
    output = work / "02-素材/音频/配乐/导入配乐.wav"
    replacement = tmp_path / "替换文件"
    replacement.write_bytes(b"another writer's file")

    def replace_then_fail(path, data):
        replacement.replace(output)
        raise OSError("synthetic manifest failure")

    monkeypatch.setattr(music, "write_yaml", replace_then_fail)
    with pytest.raises(OSError, match="synthetic manifest"):
        music.import_asset(source, manifest, "MUSIC", "导入配乐.wav", "isolated identity")
    assert output.read_bytes() == b"another writer's file"
    assert core.read_yaml(manifest) == {"assets": {}}


@pytest.fixture
def captured_score(tmp_path):
    work = tmp_path / "快照混音"
    core.write_yaml(work / "project.yaml", {"name": "隔离快照验证"})
    video = make_movie(work / "源片.mp4")
    paths = {"video": video}
    replacements = {}
    for key, hz in (("cue_a", 440), ("cue_b", 660), ("stem", 220)):
        path, alternative = work / f"{key}.wav", work / f"替换-{key}.wav"
        for target, frequency in ((path, hz), (alternative, hz + 1100)):
            core.ffmpeg(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"sine=frequency={frequency}:sample_rate=48000:duration=3",
                    target,
                ]
            )
        paths[key], replacements[key] = path, alternative.read_bytes()
    alternative_video = work / "替换画面.mp4"
    core.ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "color=red:s=64x64:r=24:d=3",
            "-c:v",
            "libx264",
            alternative_video,
        ]
    )
    replacements["video"] = alternative_video.read_bytes()
    plan_path, plan = make_plan(work, video, paths["cue_a"])
    manifest = work / "materials.yaml"
    materials = core.read_yaml(manifest)
    for asset_id, key in (("SECOND", "cue_b"), ("STEM", "stem")):
        materials["assets"][asset_id] = {
            "kind": "audio",
            "state": "ready",
            "path": str(paths[key]),
            "sha256": core.sha(paths[key]),
        }
    core.write_yaml(manifest, materials)
    plan["dialogue"]["stem_asset_id"] = "STEM"
    cue = plan["music"]["cues"][0]
    # The first and last cue share a source; capturing must deduplicate that path.
    plan["music"]["cues"] = [
        {
            **cue,
            "cue_id": f"C{i}",
            "start_seconds": i,
            "end_seconds": i + 1,
            "source_asset_id": asset_id,
        }
        for i, asset_id in enumerate(("MUSIC", "SECOND", "MUSIC"))
    ]
    core.write_yaml(plan_path, plan)
    paths.update(plan=plan_path, manifest=manifest)
    alternative_plan = work / "变更方案.yaml"
    plan["music"]["cues"][0]["gain_db"] = -50
    core.write_yaml(alternative_plan, plan)
    replacements["plan"] = alternative_plan.read_bytes()
    alternative_manifest = work / "变更清单.yaml"
    materials["assets"]["MUSIC"]["state"] = "needs_review"
    core.write_yaml(alternative_manifest, materials)
    replacements["manifest"] = alternative_manifest.read_bytes()
    return work, plan_path, paths, replacements


def test_mix_encodes_frozen_inputs_when_all_originals_change_then_revert(
    captured_score, monkeypatch
):
    work, plan, paths, replacements = captured_score
    originals = {key: path.read_bytes() for key, path in paths.items()}
    expected = {str(path): core.sha(path) for path in paths.values()}
    control = music.mix(plan, work / "对照.mp4")
    encode = music.ffmpeg
    encoder_inputs = []

    def change_originals_during_real_encode(arguments):
        encoder_inputs.extend(
            Path(arguments[i + 1]) for i, arg in enumerate(arguments) if arg == "-i"
        )
        assert len(encoder_inputs) == 5 and len(set(encoder_inputs)) == 4
        assert not set(encoder_inputs) & set(paths.values())
        assert all(path.is_file() and not path.is_relative_to(work) for path in encoder_inputs)
        for key, path in paths.items():
            path.write_bytes(replacements[key])
        try:
            return encode(arguments)
        finally:
            for key, path in paths.items():
                path.write_bytes(originals[key])

    monkeypatch.setattr(music, "ffmpeg", change_originals_during_real_encode)
    output = music.mix(plan, work / "替换后恢复.mp4")
    for stream, codec in (("v:0", "copy"), ("a:0", "pcm_s16le")):
        assert core.ffmpeg(
            ["-i", output, "-map", f"0:{stream}", "-c", codec, "-f", "md5", "-"]
        ) == core.ffmpeg(
            [
                "-i",
                control,
                "-map",
                f"0:{stream}",
                "-c",
                codec,
                "-f",
                "md5",
                "-",
            ]
        )
    record = json.loads(core.media_record_path(output, "混音").read_text("utf-8"))
    assert {item["path"]: item["sha256"] for item in record["input_bindings"]} == expected
    assert record["source"] == str(paths["video"])
    assert record["source_sha256"] == expected[str(paths["video"])]
    assert record["plan_sha256"] == expected[str(plan)]
    assert record["materials_manifest_sha256"] == expected[str(paths["manifest"])]
    assert record["audio_inputs"]["dialogue"]["sha256"] == expected[str(paths["stem"])]
    assert all(item["sha256"] == expected[item["path"]] for item in record["audio_inputs"]["music"])
    assert record["actual_listening"] == "pending"
    assert all(path.read_bytes() == originals[key] for key, path in paths.items())
    assert all(not path.exists() for path in encoder_inputs)


@pytest.mark.parametrize("changed", ["plan", "manifest", "video", "stem", "cue_a", "cue_b"])
def test_mix_rejects_changed_dependencies_after_real_encoding(captured_score, monkeypatch, changed):
    work, plan, paths, replacements = captured_score
    encode = music.ffmpeg
    encoder_inputs = []

    def mutate_and_encode(arguments):
        encoder_inputs.extend(
            Path(arguments[i + 1]) for i, arg in enumerate(arguments) if arg == "-i"
        )
        paths[changed].write_bytes(replacements[changed])
        return encode(arguments)

    monkeypatch.setattr(music, "ffmpeg", mutate_and_encode)
    output = work / "不应发布.mp4"
    with pytest.raises(ValueError, match="混音依据已变化"):
        music.mix(plan, output)
    assert encoder_inputs  # The real encoder ran, using the captured inputs.
    assert not output.exists() and not core.media_record_path(output, "混音").exists()
    assert all(not path.exists() for path in encoder_inputs)
    assert not list(work.glob(".混音-*"))


@contextmanager
def import_paused_before_registration(folder, source, manifest, *, fail=False):
    """Run the actual import transaction in a process held after media publication."""
    staged, release = folder / "已发布音频", folder / "继续登记"
    script = """
import importlib.util, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
spec = importlib.util.spec_from_file_location('music_child', Path(sys.argv[1]) / '音乐.py')
music = importlib.util.module_from_spec(spec)
spec.loader.exec_module(music)
original = music.write_yaml
staged, release, fail = Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4] == 'fail'
def delayed_write(path, data):
    staged.write_text('media published', encoding='utf-8')
    deadline = time.monotonic() + 20
    while not release.exists():
        if time.monotonic() > deadline:
            raise TimeoutError('isolated import release timed out')
        time.sleep(0.01)
    if fail:
        raise OSError('synthetic registration failure')
    original(path, data)
music.write_yaml = delayed_write
sys.argv = ['音乐.py', *sys.argv[5:]]
music.main()
"""
    arguments = [
        "import",
        str(source),
        "--manifest",
        str(manifest),
        "--asset-id",
        "A",
        "--name",
        "配乐甲.wav",
        "--provenance",
        "isolated process test",
    ]
    process = subprocess.Popen(
        [
            sys.executable,
            "-X",
            "utf8",
            "-c",
            script,
            str(TOOL_DIR),
            str(staged),
            str(release),
            "fail" if fail else "pass",
            *arguments,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        deadline = time.monotonic() + 10
        while not staged.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert staged.exists(), "import did not reach its manifest boundary"
        yield process, release, arguments
    finally:
        release.touch()
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=5)


def test_music_import_recovers_identical_target_after_real_process_termination(tmp_path):
    work = tmp_path / "作品"
    core.write_yaml(work / "project.yaml", {"name": "强停恢复"})
    manifest = work / "materials.yaml"
    core.write_yaml(manifest, {"assets": {}})
    source = tmp_path / "原始音乐.wav"
    core.ffmpeg(["-f", "lavfi", "-i", "sine=duration=0.2", source])
    expected = core.sha(source)
    with import_paused_before_registration(tmp_path, source, manifest) as (child, _, arguments):
        child.terminate()
        child.communicate(timeout=5)
    output = work / "02-素材/音频/配乐/配乐甲.wav"
    assert output.is_file() and core.read_yaml(manifest) == {"assets": {}}
    identity = output.stat()
    retried = music_cli(*arguments)
    assert retried.returncode == 0, retried.stderr
    assert Path(json.loads(retried.stdout)) == output
    assert os.path.samestat(output.stat(), identity)
    assert core.sha(output) == core.sha(source) == expected
    assert core.read_yaml(manifest)["assets"]["A"]["sha256"] == expected
    duplicate = music_cli(*arguments)
    assert duplicate.returncode != 0 and "资产 ID 已存在" in duplicate.stderr
    assert core.sha(output) == expected


def test_music_import_recovery_never_overwrites_different_existing_content(tmp_path):
    work = tmp_path / "作品"
    core.write_yaml(work / "project.yaml", {"name": "恢复碰撞"})
    manifest = work / "materials.yaml"
    core.write_yaml(manifest, {"assets": {}})
    output = work / "02-素材/音频/配乐/配乐甲.wav"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"another owner's existing file")
    source = tmp_path / "原始音乐.wav"
    core.ffmpeg(["-f", "lavfi", "-i", "sine=duration=0.2", source])
    result = music_cli(
        "import",
        source,
        "--manifest",
        manifest,
        "--asset-id",
        "A",
        "--name",
        "配乐甲.wav",
        "--provenance",
        "isolated collision",
    )
    assert result.returncode != 0 and "内容不同" in result.stderr
    assert output.read_bytes() == b"another owner's existing file"
    assert core.read_yaml(manifest) == {"assets": {}}


def test_music_import_keeps_media_when_interrupted_after_manifest_commit(tmp_path, monkeypatch):
    work = tmp_path / "作品"
    core.write_yaml(work / "project.yaml", {"name": "提交后中断"})
    manifest = work / "materials.yaml"
    core.write_yaml(manifest, {"assets": {}})
    source = tmp_path / "原始音乐.wav"
    core.ffmpeg(["-f", "lavfi", "-i", "sine=duration=0.2", source])
    write = music.write_yaml

    def commit_then_interrupt(path, data):
        write(path, data)
        raise KeyboardInterrupt("isolated interruption after atomic manifest commit")

    monkeypatch.setattr(music, "write_yaml", commit_then_interrupt)
    with pytest.raises(KeyboardInterrupt, match="after atomic manifest commit"):
        music.import_asset(source, manifest, "M", "已登记音乐.wav", "isolated cancellation")
    asset = core.read_yaml(manifest)["assets"]["M"]
    output = (manifest.parent / asset["path"]).resolve()
    assert output.is_file() and core.sha(output) == asset["sha256"] == core.sha(source)


@pytest.mark.parametrize("first_fails", [False, True])
def test_music_import_serializes_shared_assets_across_different_manifests(tmp_path, first_fails):
    work = tmp_path / "作品"
    core.write_yaml(work / "project.yaml", {"name": "跨清单事务"})
    first, second = work / "版本甲.yaml", work / "版本乙.yaml"
    for manifest in (first, second):
        core.write_yaml(manifest, {"assets": {}})
    source = tmp_path / "原始音乐.wav"
    core.ffmpeg(["-f", "lavfi", "-i", "sine=duration=0.2", source])
    expected = core.sha(source)
    other = None
    with import_paused_before_registration(tmp_path, source, first, fail=first_fails) as (
        child,
        release,
        _,
    ):
        try:
            other = subprocess.Popen(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    str(TOOL_DIR / "音乐.py"),
                    "import",
                    str(source),
                    "--manifest",
                    str(second),
                    "--asset-id",
                    "B",
                    "--name",
                    "配乐乙.wav",
                    "--provenance",
                    "isolated second manifest",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            with pytest.raises(subprocess.TimeoutExpired):
                other.communicate(timeout=1)
            assert core.read_yaml(second) == {"assets": {}}
            release.touch()
            _, first_error = child.communicate(timeout=15)
            second_output, second_error = other.communicate(timeout=15)
            if first_fails:
                assert child.returncode != 0 and "synthetic registration failure" in first_error
                assert core.read_yaml(first) == {"assets": {}}
            else:
                assert child.returncode == 0, first_error
            assert other.returncode == 0, second_error
        finally:
            if other is not None and other.poll() is None:
                other.terminate()
                other.communicate(timeout=5)
    asset = core.read_yaml(second)["assets"]["B"]
    output = (second.parent / asset["path"]).resolve()
    assert output == Path(json.loads(second_output))
    assert output.name == ("配乐乙.wav" if first_fails else "配乐甲.wav")
    assert core.sha(output) == asset["sha256"] == core.sha(source) == expected
    first_output = work / "02-素材/音频/配乐/配乐甲.wav"
    assert first_output.exists() is (not first_fails)
