"""Observable media, timeline, source preservation and review-version invariants."""

import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys
import threading
from array import array
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

from autodl_video.errors import AutoDLError
from autodl_video.media_inputs import MediaInputs

TOOL_DIR = Path(__file__).resolve().parents[1] / "tools/视频工具"
sys.path.insert(0, str(TOOL_DIR))


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, TOOL_DIR / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


core = module("video_tools", "video_tools.py")
music = module("music_tools", "音乐.py")
review = module("review_tools", "审片.py")


def test_media_input_snapshots_deduplicate_aliases_and_keep_private_bytes(tmp_path):
    source, alias = tmp_path / "源片.mp4", tmp_path / "同源.mp4"
    source.write_bytes(b"original media")
    alias.hardlink_to(source)
    with MediaInputs() as captured:
        snapshot = captured.capture(source)
        assert captured.capture(source) == captured.capture(alias) == snapshot
        assert len(list(captured.directory.iterdir())) == 1
        assert not snapshot.samefile(source)
        source.write_bytes(b"changed media")
        assert snapshot.read_bytes() == b"original media"
        assert captured.capture(source) == snapshot  # No late recapture.
        with pytest.raises(ValueError, match="输入已变化"):
            captured.check_current()
        directory = captured.directory
    assert not directory.exists()


@pytest.mark.parametrize("failure", ["copy_error", "interrupt", "changed"])
def test_media_input_capture_failure_cleans_partial_copy(tmp_path, monkeypatch, failure):
    import autodl_video.media_inputs as inputs

    source = tmp_path / "输入.mp4"
    source.write_bytes(b"old bytes")
    copy = inputs.shutil.copyfileobj

    def fail_during_copy(reader, writer, **kwargs):
        copy(reader, writer, **kwargs)
        if failure == "changed":
            source.write_bytes(b"different bytes")
        elif failure == "interrupt":
            raise KeyboardInterrupt
        else:
            raise OSError("copy failed")

    monkeypatch.setattr(inputs.shutil, "copyfileobj", fail_during_copy)
    error = {"copy_error": OSError, "interrupt": KeyboardInterrupt, "changed": ValueError}
    with MediaInputs() as captured:
        with pytest.raises(error[failure]):
            captured.capture(source)
        assert not captured.files and not list(captured.directory.iterdir())
        directory = captured.directory
    assert not directory.exists()


def snapshot_sample(path, color, frequency=880):
    core.ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"color={color}:s=320x180:r=24:d=3",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:sample_rate=48000:duration=3",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            path,
        ]
    )


def first_pixel(path, seconds=0):
    return tuple(
        core.ffmpeg(
            [
                "-ss",
                str(seconds),
                "-i",
                path,
                "-frames:v",
                "1",
                "-vf",
                "crop=2:2:0:0",
                "-pix_fmt",
                "rgb24",
                "-f",
                "rawvideo",
                "-",
            ]
        )[:3]
    )


@pytest.mark.parametrize("kind", ["watermark", "frames"])
def test_media_uses_snapshot_when_source_is_replaced_then_restored(
    movie, tmp_path, monkeypatch, kind
):
    replacement = tmp_path / "替换源片.mp4"
    snapshot_sample(replacement, "red")
    original, original_hash = movie.read_bytes(), core.sha(movie)
    expected_audio = stream_hash(movie, "0:a:0")
    ffmpeg, snapshots = core.ffmpeg, []

    def replace_during_encode(args, *pargs, **kwargs):
        if "-vf" in args and ("drawtext=" in str(args) or "%06d.png" in str(args[-1])):
            snapshot = Path(args[args.index("-i") + 1])
            snapshots.append(snapshot)
            assert snapshot != movie and core.sha(snapshot) == original_hash
            movie.write_bytes(replacement.read_bytes())
            try:
                return ffmpeg(args, *pargs, **kwargs)
            finally:
                movie.write_bytes(original)
        return ffmpeg(args, *pargs, **kwargs)

    monkeypatch.setattr(core, "ffmpeg", replace_during_encode)
    if kind == "watermark":
        output = core.watermark(movie, tmp_path / "水印.mp4", text="@test")
        record = json.loads(core.media_record_path(output, "水印").read_text("utf-8"))
        assert record["source_sha256"] == original_hash
        assert stream_hash(output, "0:a:0") == expected_audio
    else:
        folder = core.extract_frames(movie, tmp_path / "检查帧", frame=1)
        output = next(folder.glob("*.png"))
        record = json.loads((folder / "抽帧记录.json").read_text("utf-8"))
        assert record["sha256"] == original_hash
    assert max(first_pixel(output)) < 10  # Original black frame, never replacement red.
    assert record["input_binding_method"] == "private_file_snapshots"
    assert record["input_bindings"] == [{"path": str(movie), "sha256": original_hash}]
    assert core.sha(movie) == original_hash
    assert snapshots and all(not path.parent.exists() for path in snapshots)


def test_edit_freezes_config_and_multiple_repeated_inputs(movie, tmp_path, monkeypatch):
    second, replacement = tmp_path / "第二片.mp4", tmp_path / "替换.mp4"
    snapshot_sample(second, "blue", frequency=440)
    snapshot_sample(replacement, "red")
    config = tmp_path / "剪辑.yaml"
    core.write_yaml(
        config,
        {
            "clips": [
                {"path": movie.name, "out_seconds": 1},
                {"path": second.name, "out_seconds": 1},
                {"path": movie.name, "out_seconds": 1},
            ]
        },
    )
    originals = {path: path.read_bytes() for path in (config, movie, second)}
    hashes = {path: core.sha(path) for path in originals}
    run, captured_paths = core.subprocess.run, []

    def replace_during_encode(args, *pargs, **kwargs):
        if "-filter_complex" in args:
            captured_paths.extend(Path(args[i + 1]) for i, arg in enumerate(args) if arg == "-i")
            assert len(captured_paths) == 3 and captured_paths[0] == captured_paths[2]
            assert captured_paths[0] != captured_paths[1]
            assert [core.sha(path) for path in captured_paths] == [
                hashes[movie],
                hashes[second],
                hashes[movie],
            ]
            movie.write_bytes(replacement.read_bytes())
            second.write_bytes(replacement.read_bytes())
            core.write_yaml(config, {"fps": 60, "clips": [{"path": replacement.name}]})
            try:
                return run(args, *pargs, **kwargs)
            finally:
                for path, content in originals.items():
                    path.write_bytes(content)
        return run(args, *pargs, **kwargs)

    monkeypatch.setattr(core.subprocess, "run", replace_during_encode)
    output = core.edit(config, tmp_path / "剪辑.mp4")
    record = json.loads(core.media_record_path(output, "剪辑").read_text("utf-8"))
    assert record["fps"] == "24" and record["duration"] == pytest.approx(3, abs=0.01)
    assert record["config_sha256"] == hashes[config]
    assert [item["sha256"] for item in record["clips"]] == [
        hashes[movie],
        hashes[second],
        hashes[movie],
    ]
    assert len(record["input_bindings"]) == 3
    assert max(first_pixel(output)) < 10 and max(first_pixel(output, 2)) < 10
    red, green, blue = first_pixel(output, 1)
    assert blue > 200 and red < 10 and green < 10
    assert all(not path.parent.exists() for path in captured_paths)


@pytest.mark.parametrize("kind", ["watermark", "frames", "edit"])
def test_changed_media_is_not_published_and_private_inputs_are_cleaned(
    movie, tmp_path, monkeypatch, kind
):
    run, captured_paths = core.subprocess.run, []
    config = tmp_path / "剪辑.yaml"
    core.write_yaml(config, {"clips": [{"path": movie.name}]})
    output = tmp_path / ("帧目录" if kind == "frames" else "结果.mp4")

    def change_after_encode(args, *pargs, **kwargs):
        result = run(args, *pargs, **kwargs)
        if (
            "-filter_complex" in args
            or ("drawtext=" in str(args) and "libx264" in args)
            or "检查帧-" in str(args)
        ):
            captured_paths.extend(Path(args[i + 1]) for i, arg in enumerate(args) if arg == "-i")
            movie.write_bytes(b"source changed after encoding")
        return result

    monkeypatch.setattr(core.subprocess, "run", change_after_encode)
    with pytest.raises(ValueError, match="输入已变化"):
        if kind == "watermark":
            core.watermark(movie, output, text="@test")
        elif kind == "frames":
            core.extract_frames(movie, output, frame=1)
        else:
            core.edit(config, output)
    assert not output.exists() and not list(tmp_path.glob("*记录.json"))
    assert captured_paths and all(not path.parent.exists() for path in captured_paths)


@pytest.mark.parametrize(
    ("kind", "changed_input"),
    [("watermark", "source"), ("edit", "source"), ("edit", "config")],
)
def test_final_publish_validation_rechecks_live_inputs_before_record_or_media_publication(
    movie, tmp_path, monkeypatch, kind, changed_input
):
    replacement = tmp_path / "替换源片.mp4"
    snapshot_sample(replacement, "red")
    config = tmp_path / "剪辑.yaml"
    core.write_yaml(config, {"clips": [{"path": movie.name, "out_seconds": 1}]})
    originals = {movie: movie.read_bytes(), config: config.read_bytes()}
    target = movie if changed_input == "source" else config
    changed_bytes = replacement.read_bytes() if changed_input == "source" else b"clips: []\n"
    output = tmp_path / "未发布.mp4"
    snapshots, validation_changes = [], []
    publish, probe, timeline = core.publish, core.probe, core.validate_video_timeline
    in_publish = False

    class TrackedInputs(core.MediaInputs):
        def capture(self, source):
            snapshot = super().capture(source)
            snapshots.append(snapshot)
            return snapshot

    def during_publish(*args, **kwargs):
        nonlocal in_publish
        in_publish = True
        try:
            return publish(*args, **kwargs)
        finally:
            in_publish = False

    def replace_input():
        target.write_bytes(changed_bytes)
        validation_changes.append(target)

    def change_after_probe(path):
        result = probe(path)
        if kind == "edit" and in_publish:
            replace_input()
        return result

    def change_after_timeline(*args):
        result = timeline(*args)
        assert kind == "watermark" and in_publish
        replace_input()
        return result

    monkeypatch.setattr(core, "MediaInputs", TrackedInputs)
    monkeypatch.setattr(core, "publish", during_publish)
    monkeypatch.setattr(core, "probe", change_after_probe)
    monkeypatch.setattr(core, "validate_video_timeline", change_after_timeline)
    with pytest.raises(ValueError, match="输入已变化"):
        if kind == "watermark":
            core.watermark(movie, output, text="@test")
        else:
            core.edit(config, output)
    assert validation_changes == [target]
    assert not output.exists() and not list(tmp_path.glob("*记录.json"))
    assert snapshots and all(not path.parent.exists() for path in snapshots)
    assert not list(tmp_path.glob(".水印-*")) and not list(tmp_path.glob(".剪辑-*"))
    assert target.read_bytes() == changed_bytes  # Failure never rolls back an external change.
    for path, content in originals.items():
        if path != target:
            assert path.read_bytes() == content


@pytest.fixture
def movie(tmp_path):
    source = tmp_path / "测试源片.mp4"
    core.ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "color=black:s=320x180:r=24:d=3",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=500:sample_rate=48000:duration=3",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            source,
        ]
    )
    return source


def stream_hash(path, stream):
    return core.ffmpeg(["-i", path, "-map", stream, "-c", "copy", "-f", "md5", "-"])


def tool_cli(filename, *arguments):
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(TOOL_DIR / filename), *map(str, arguments)],
        capture_output=True,
        encoding="utf-8",
    )


def test_extract_cli_failure_leaves_destination_available_for_retry(movie, tmp_path):
    output = tmp_path / "抽帧重试"
    failed = tool_cli("抽帧.py", movie, "--output", output, "--frame", "999999")
    assert failed.returncode != 0
    assert not output.exists()
    assert not list(tmp_path.glob(".抽帧-*"))
    retried = tool_cli("抽帧.py", movie, "--output", output, "--frame", "2")
    assert retried.returncode == 0, retried.stderr
    assert len(list(output.glob("*.png"))) == 1


def test_edit_cli_requires_explicit_track_and_uses_the_selected_dialogue(tmp_path):
    source = tmp_path / "双音轨.mkv"
    core.ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=320x180:r=24:d=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:sample_rate=48000:duration=1",
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-map",
            "2:a",
            "-c:v",
            "libx264",
            "-c:a",
            "pcm_s16le",
            "-disposition:a:0",
            "0",
            "-disposition:a:1",
            "default",
            "-metadata:s:a:0",
            "language=eng",
            "-metadata:s:a:1",
            "language=zho",
            source,
        ]
    )
    config, output = tmp_path / "剪辑.yaml", tmp_path / "剪辑.mp4"
    data = {"clips": [{"path": source.name}]}
    core.write_yaml(config, data)
    before = core.sha(source)
    rejected = tool_cli("剪辑.py", config, "--output", output)
    assert rejected.returncode != 0 and "audio_track" in rejected.stderr
    assert not output.exists()
    data["clips"][0]["audio_track"] = 1
    core.write_yaml(config, data)
    selected = tool_cli("剪辑.py", config, "--output", output)
    assert selected.returncode == 0, selected.stderr
    samples = array(
        "f",
        core.ffmpeg(
            [
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
    )[5000:29000]
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
    record = json.loads(core.media_record_path(output, "剪辑").read_text("utf-8"))
    assert record["clips"][0]["audio_track"] == 1
    assert core.sha(source) == before


def test_edit_cli_keeps_non_square_pixel_display_aspect_ratio(tmp_path):
    source = tmp_path / "宽像素源片.mp4"
    core.ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=320x180:r=24:d=1",
            "-vf",
            "setsar=2",
            "-c:v",
            "libx264",
            source,
        ]
    )
    config, output = tmp_path / "剪辑.yaml", tmp_path / "结果.mp4"
    core.write_yaml(config, {"clips": [{"path": source.name}]})
    process = tool_cli("剪辑.py", config, "--output", output)
    assert process.returncode == 0, process.stderr
    original, edited = core.probe(source)["video"], core.probe(output)["video"]
    assert edited["sample_aspect_ratio"] == original["sample_aspect_ratio"] == "2:1"
    assert edited["display_aspect_ratio"] == original["display_aspect_ratio"] == "32:9"


def test_media_outputs_and_edit_inputs_stay_in_the_same_known_project(movie, tmp_path):
    first, other = tmp_path / "作品甲", tmp_path / "作品乙"
    for project in (first, other):
        project.mkdir()
        core.write_yaml(project / "project.yaml", {"name": project.name})
        shutil.copyfile(movie, project / movie.name)
    source = first / movie.name
    destination = other / "越界.mp4"
    with pytest.raises(AutoDLError, match="当前作品"):
        core.watermark(source, destination)
    with pytest.raises(AutoDLError, match="当前作品"):
        core.extract_frames(source, other / "越界帧")
    assert not destination.exists() and not (other / "越界帧").exists()
    config = first / "剪辑.yaml"
    core.write_yaml(config, {"clips": [{"path": str(other / movie.name)}]})
    with pytest.raises(AutoDLError, match="不同作品"):
        core.edit(config, first / "混用作品.mp4")
    core.write_yaml(config, {"clips": [{"path": movie.name}]})
    with pytest.raises(AutoDLError, match="当前作品"):
        core.edit(config, destination)
    assert not (first / "混用作品.mp4").exists() and not destination.exists()


def test_edit_cli_rejects_unarchived_inputs_but_keeps_standalone_workflows(movie, tmp_path):
    project = tmp_path / "作品甲"
    project.mkdir()
    core.write_yaml(project / "project.yaml", {"name": "作品甲"})
    archived = project / "已归档片段.mp4"
    shutil.copyfile(movie, archived)
    original = core.sha(movie)
    bound_config = project / "剪辑.yaml"
    unowned_config = tmp_path / "未归档配置.yaml"
    destination = project / "剪辑结果.mp4"
    for config, sources in (
        (bound_config, [archived, movie]),
        (unowned_config, [archived]),
    ):
        core.write_yaml(config, {"clips": [{"path": str(source)} for source in sources]})
        result = tool_cli("剪辑.py", config, "--output", destination)
        assert result.returncode != 0 and "未归档" in result.stderr
        assert not destination.exists()
        assert not list(project.glob(".剪辑-*"))

    # A complete standalone config/media/output set still works without a project.
    core.write_yaml(unowned_config, {"clips": [{"path": str(movie)}]})
    standalone = tool_cli("剪辑.py", unowned_config, "--output", tmp_path / "独立剪辑.mp4")
    assert standalone.returncode == 0, standalone.stderr

    # After archiving all inputs, the originally rejected destination is reusable.
    core.write_yaml(bound_config, {"clips": [{"path": str(archived)}]})
    retried = tool_cli("剪辑.py", bound_config, "--output", destination)
    assert retried.returncode == 0, retried.stderr
    assert core.sha(movie) == core.sha(archived) == original


def test_watermark_moves_and_preserves_source_audio(movie):
    original = core.sha(movie)
    output = core.watermark(movie, period=4, margin=12)
    assert core.sha(movie) == original
    assert core.probe(output)["video"]["avg_frame_rate"] == "24/1"
    assert stream_hash(movie, "0:a:0") == stream_hash(output, "0:a:0")
    frames = core.ffmpeg(
        [
            "-i",
            output,
            "-vf",
            "select=eq(n\\,0)+eq(n\\,24)",
            "-fps_mode",
            "vfr",
            "-an",
            "-f",
            "framemd5",
            "-",
        ]
    )
    rows = [r for r in frames.decode().splitlines() if not r.startswith("#")]
    assert len(rows) == 2 and rows[0].split(",")[-1] != rows[1].split(",")[-1]
    with pytest.raises(ValueError, match="输出已存在"):
        core.watermark(movie, output=movie)


@pytest.mark.parametrize(
    ("text", "margin", "font_size", "font_name"),
    [
        ("W" * 29, 0, 12, "arial.ttf"),
        ("W" * 25, 24, 12, "arial.ttf"),
        ("W" * 14, 24, 24, "arial.ttf"),
        ("W" * 25, 24, 12, "arialbi.ttf"),
    ],
)
def test_watermark_rejects_actual_font_layout_overflow_before_encoding(
    movie, tmp_path, monkeypatch, text, margin, font_size, font_name
):
    original = movie.read_bytes()
    output = tmp_path / "不能发布.mp4"
    ffmpeg, snapshots, layouts = core.ffmpeg, [], []

    class TrackedInputs(core.MediaInputs):
        def capture(self, source):
            snapshot = super().capture(source)
            snapshots.append(snapshot)
            return snapshot

    measure = core.drawtext_size

    def observe_layout(*args):
        dimensions = measure(*args)
        layouts.append(dimensions)
        return dimensions

    def forbid_video_encode(args, *pargs, **kwargs):
        assert "libx264" not in args, "oversized text must be rejected before media encoding"
        return ffmpeg(args, *pargs, **kwargs)

    monkeypatch.setattr(core, "MediaInputs", TrackedInputs)
    monkeypatch.setattr(core, "drawtext_size", observe_layout)
    monkeypatch.setattr(core, "ffmpeg", forbid_video_encode)
    with pytest.raises(ValueError, match="实际排版与轮廓超出"):
        core.watermark(
            movie,
            output,
            text=text,
            margin=margin,
            font_size=font_size,
            font=str(Path("C:/Windows/Fonts") / font_name),
        )
    assert layouts and layouts[0][0] + 2 * margin > 320
    assert not output.exists() and not list(tmp_path.glob("*记录.json"))
    assert snapshots and all(not path.parent.exists() for path in snapshots)
    assert not list(tmp_path.glob(".水印-*")) and movie.read_bytes() == original


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"text": "W" * 27, "margin": 0, "font_size": 12, "period": 1},
        {"text": "W" * 23, "margin": 24, "font_size": 12, "period": 1},
        {"text": "i" * 90, "margin": 24, "font_size": 12, "period": 1},
        {
            "text": "jjjjjj",
            "margin": 0,
            "font_size": 20,
            "period": 1,
            "font": "C:/Windows/Fonts/ariali.ttf",
        },
    ],
)
def test_moving_watermark_outline_fits_margin_against_unclipped_pixel_reference(
    tmp_path, monkeypatch, options
):
    source = tmp_path / "灰底有声源片.mp4"
    snapshot_sample(source, "gray")
    source_hash, audio = core.sha(source), stream_hash(source, "0:a:0")
    ffmpeg, observed = core.ffmpeg, []
    width, height, count = 320, 180, 24
    margin = options.get("margin", 24)
    baseline = ffmpeg(
        [
            "-i",
            source,
            "-frames:v",
            "1",
            "-pix_fmt",
            "gray",
            "-f",
            "rawvideo",
            "-",
        ]
    )[0]

    def inspect_real_render(args, *pargs, **kwargs):
        if "-c:v:0" in args:
            source_input = args[args.index("-i") + 1]
            effect = args[args.index("-vf") + 1]
            match = re.search(r":x='([^']*)':y='([^']*)'$", effect)
            assert match is not None
            positions = [
                re.sub(r"\bw\b", str(width), re.sub(r"\bh\b", str(height), value))
                for value in match.groups()
            ]
            padded_effect = (
                f"pad={3 * width}:{3 * height}:{width}:{height}:color=gray,"
                + effect[: match.start()]
                # drawtext rasterizes 26.6 coordinates. Quantize before translating
                # so adding the padding cannot change a subpixel rounding phase.
                + f":x='{width}+trunc(64*({positions[0]}))/64'"
                + f":y='{height}+(trunc(64*({positions[1]})+64*top_a)-64*top_a)/64'"
            )

            def pixels(filter_expression):
                return ffmpeg(
                    [
                        "-i",
                        source_input,
                        "-frames:v",
                        str(count),
                        "-an",
                        "-vf",
                        filter_expression,
                        "-pix_fmt",
                        "gray",
                        "-f",
                        "rawvideo",
                        "-",
                    ],
                    *pargs,
                    **kwargs,
                )

            regular, padded = pixels(effect), pixels(padded_effect)
            bounds = []
            for frame in range(count):
                tile = padded[frame * 9 * width * height : (frame + 1) * 9 * width * height]
                changed = [i for i, value in enumerate(tile) if value != baseline]
                assert changed  # Includes the dark outline on the neutral background.
                xs, ys = [i % (3 * width) for i in changed], [i // (3 * width) for i in changed]
                box = min(xs), min(ys), max(xs), max(ys)
                assert box[0] >= width + margin and box[2] < 2 * width - margin
                assert box[1] >= height + margin and box[3] < 2 * height - margin
                # The real-canvas raster equals the center of an unclipped canvas:
                # no glyph or outline pixels disappeared at any sampled position.
                central = b"".join(
                    tile[y * 3 * width + width : y * 3 * width + 2 * width]
                    for y in range(height, 2 * height)
                )
                assert central == regular[frame * width * height : (frame + 1) * width * height]
                bounds.append(box)
            assert len(set(bounds)) > 1
            observed.append(bounds)
        return ffmpeg(args, *pargs, **kwargs)

    monkeypatch.setattr(core, "ffmpeg", inspect_real_render)
    output = core.watermark(source, tmp_path / "移动水印.mp4", **options)
    assert observed and core.sha(source) == source_hash
    assert stream_hash(output, "0:a:0") == audio
    record = json.loads(core.media_record_path(output, "水印").read_text("utf-8"))
    assert record["text_width_pixels"] + 2 * (record["raster_padding_pixels"] + margin) <= width
    assert record["text_height_pixels"] + 2 * (record["raster_padding_pixels"] + margin) <= height


def test_watermark_cli_preserves_rotated_display_and_audio(tmp_path):
    base, source = tmp_path / "宽像素.mp4", tmp_path / "旋转源片.mp4"
    core.ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=640x360:r=24:d=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=500:sample_rate=48000:duration=1",
            "-vf",
            "setsar=2",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            base,
        ]
    )
    core.ffmpeg(["-display_rotation", "90", "-i", base, "-c", "copy", source])
    before = core.sha(source)
    output = tmp_path / "旋转水印.mp4"
    process = tool_cli("移动水印.py", source, "--output", output)
    assert process.returncode == 0, process.stderr
    video = core.probe(output)["video"]
    assert (video["width"], video["height"], video["sample_aspect_ratio"]) == (360, 640, "1:2")
    assert core.display_geometry(video) == core.display_geometry(core.probe(source)["video"])
    assert stream_hash(source, "0:a:0") == stream_hash(output, "0:a:0")
    assert core.sha(source) == before


def test_publish_accepts_container_quantization_with_identical_video(movie, tmp_path):
    source, partial, output = (tmp_path / n for n in ("源片.mkv", "待发布.mp4", "完成.mp4"))
    core.ffmpeg(["-i", movie, "-c:v", "copy", "-c:a", "pcm_s16le", source])
    core.ffmpeg(["-i", source, "-c:v", "copy", "-c:a", "aac", partial])
    original, remuxed = core.probe(source), core.probe(partial)
    assert original["video"]["avg_frame_rate"] != remuxed["video"]["avg_frame_rate"]
    assert stream_hash(source, "0:v:0") == stream_hash(partial, "0:v:0")
    core.publish(partial, output, reference=source)
    assert output.exists() and not partial.exists()


@pytest.mark.parametrize(
    ("effect", "error"),
    [
        ("setsar=2", "显示画布或像素比例"),
        ("scale=160:90", "显示画布或像素比例"),
        (r"select=not(eq(n\,24))", "解码帧数"),
        ("setpts=1.02*PTS", "逐帧时间戳"),
        (r"setpts=PTS+if(eq(N\,24)\,0.01/TB\,0)", "逐帧时间戳"),
    ],
)
def test_publish_rejects_geometry_frame_loss_and_retiming(movie, tmp_path, effect, error):
    partial, output = tmp_path / "错误候选.mp4", tmp_path / "不应发布.mp4"
    original = core.sha(movie)
    core.ffmpeg(
        [
            "-i",
            movie,
            "-vf",
            effect,
            "-fps_mode",
            "passthrough",
            "-enc_time_base",
            "1:24000",
            "-c:v",
            "libx264",
            "-c:a",
            "copy",
            partial,
        ]
    )
    with pytest.raises(ValueError, match=error):
        core.publish(partial, output, reference=movie)
    assert not output.exists()
    assert partial.exists() and core.sha(movie) == original


def test_edit_mapping_audio_speed_and_exact_frame(movie, tmp_path):
    config = tmp_path / "剪辑.yaml"
    core.write_yaml(
        config,
        {
            "clips": [
                {"path": movie.name, "in_seconds": 0.5, "out_seconds": 2.5, "speed": 2},
                {"path": movie.name, "in_seconds": 1, "out_seconds": 2, "speed": 1},
            ]
        },
    )
    result = core.edit(config, tmp_path / "剪辑结果.mp4")
    record = json.loads(core.media_record_path(result, "剪辑").read_text("utf-8"))
    assert abs(core.probe(result)["duration"] - 2) < 0.1
    assert record["seams"][0]["at_seconds"] == 1
    extracted = core.extract_frames(result, tmp_path / "精确帧", frame=10)
    assert len(list(extracted.glob("*.png"))) == 1
    assert core.sha(movie) == record["clips"][0]["sha256"]


def test_same_stem_containers_keep_independent_seams_and_review_binding(movie, tmp_path):
    core.write_yaml(tmp_path / "project.yaml", {"name": "记录版本验证"})
    config = tmp_path / "剪辑.yaml"
    first, second = tmp_path / "成片.mp4", tmp_path / "成片.mkv"
    legacy = first.with_suffix(".剪辑记录.json")
    legacy.write_text('{"historical": true}', encoding="utf-8")
    original = core.sha(movie)
    core.write_yaml(config, {"clips": [{"path": movie.name, "out_seconds": 0.5}] * 2})
    core.edit(config, first)
    first_record = core.media_record_path(first, "剪辑")
    first_bytes = first_record.read_bytes()
    core.write_yaml(config, {"clips": [{"path": movie.name, "out_seconds": 0.75}] * 3})
    core.edit(config, second)
    second_record = core.media_record_path(second, "剪辑")
    assert first_record != second_record
    assert first_record.read_bytes() == first_bytes
    assert legacy.read_text("utf-8") == '{"historical": true}'
    assert core.sha(movie) == original
    for output, record_path, seams in (
        (first, first_record, [0.5]),
        (second, second_record, [0.75, 1.5]),
    ):
        record = json.loads(record_path.read_text("utf-8"))
        assert record["sha256"] == core.sha(output)
        assert [s["at_seconds"] for s in record["seams"]] == seams
        session = json.loads(review.prepare(tmp_path, [output], record_path).read_text("utf-8"))
        assert session["media"][0]["sha256"] == record["sha256"]
        assert [s["at_seconds"] for s in session["seams"]] == seams
    # Old explicit record paths remain readable; there is no historical rewrite.
    old_record = tmp_path / "旧版.剪辑记录.json"
    old_record.write_bytes(first_bytes)
    session = json.loads(review.prepare(tmp_path, [first], old_record).read_text("utf-8"))
    assert session["seams"][0]["at_seconds"] == 0.5


def test_watermark_records_preserve_each_container_version(movie, tmp_path):
    first, second = tmp_path / "发布版.mp4", tmp_path / "发布版.mkv"
    core.watermark(movie, first)
    record_path = core.media_record_path(first, "水印")
    original = record_path.read_bytes()
    core.watermark(movie, second)
    assert record_path.read_bytes() == original
    for output in (first, second):
        record = json.loads(core.media_record_path(output, "水印").read_text("utf-8"))
        assert record["output"] == str(output)
        assert record["output_sha256"] == core.sha(output)


@pytest.mark.parametrize("kind", ["剪辑", "水印"])
def test_orphan_record_blocks_export_before_encoding(movie, tmp_path, monkeypatch, kind):
    output = tmp_path / "未覆盖.mp4"
    record = core.media_record_path(output, kind)
    record.write_bytes(b"original immutable record")
    config = tmp_path / "剪辑.yaml"
    core.write_yaml(config, {"clips": [{"path": movie.name}]})
    run = subprocess.run

    def forbid_encoding(args, *pargs, **kwargs):
        assert "libx264" not in args, "existing record must be rejected before encoding"
        return run(args, *pargs, **kwargs)

    monkeypatch.setattr(core.subprocess, "run", forbid_encoding)
    with pytest.raises(ValueError, match="媒体记录已存在"):
        if kind == "剪辑":
            core.edit(config, output)
        else:
            core.watermark(movie, output)
    assert not output.exists()
    assert record.read_bytes() == b"original immutable record"


def test_concurrent_publish_keeps_one_media_and_its_own_record(movie, tmp_path, monkeypatch):
    output = tmp_path / "并发导出.mp4"
    candidates = [tmp_path / f"candidate-{i}.mp4" for i in range(2)]
    for candidate in candidates:
        shutil.copyfile(movie, candidate)
    barrier = threading.Barrier(2)
    link = core.os.link

    def concurrent_link(source, destination):
        barrier.wait(timeout=10)
        return link(source, destination)

    monkeypatch.setattr(core.os, "link", concurrent_link)

    def publish(index):
        try:
            core.publish(
                candidates[index],
                output,
                record=("剪辑", lambda _: {"writer": index, "sha256": core.sha(movie)}),
            )
            return index, None
        except ValueError as error:
            return index, str(error)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(publish, range(2)))
    winners = [index for index, error in results if error is None]
    failures = [error for _, error in results if error is not None]
    assert len(winners) == len(failures) == 1
    assert "媒体记录被其他任务占用" in failures[0]
    record = json.loads(core.media_record_path(output, "剪辑").read_text("utf-8"))
    assert record == {"writer": winners[0], "sha256": core.sha(output)}
    assert not candidates[winners[0]].exists()
    assert candidates[1 - winners[0]].exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_media_collision_after_record_write_preserves_winner_and_removes_own_record(
    movie, tmp_path, monkeypatch
):
    output, candidate = tmp_path / "被抢占.mp4", tmp_path / "候选.mp4"
    shutil.copyfile(movie, candidate)
    rename = Path.rename

    def race_media_publish(source, destination):
        if source == candidate:
            Path(destination).write_bytes(b"another publisher's media")
            raise FileExistsError("output was claimed during record publication")
        return rename(source, destination)

    monkeypatch.setattr(Path, "rename", race_media_publish)
    with pytest.raises(FileExistsError):
        core.publish(candidate, output, record=("剪辑", lambda _: {"status": "candidate"}))
    assert output.read_bytes() == b"another publisher's media"
    assert candidate.exists()
    assert not core.media_record_path(output, "剪辑").exists()


def test_seam_uses_rendered_time_for_non_frame_aligned_cuts(tmp_path):
    clips = []
    for color in ("red", "blue"):
        path = tmp_path / f"{color}.mp4"
        core.ffmpeg(
            ["-f", "lavfi", "-i", f"color={color}:s=64x64:r=24:d=1", "-c:v", "libx264", path]
        )
        clips.append({"path": path.name, "in_seconds": 0.2, "out_seconds": 0.9})
    config = tmp_path / "时间线.yaml"
    core.write_yaml(config, {"clips": clips})
    output = core.edit(config, tmp_path / "结果.mp4")
    record = json.loads(core.media_record_path(output, "剪辑").read_text("utf-8"))
    pixels = core.ffmpeg(
        ["-i", output, "-vf", "scale=1:1", "-an", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
    )
    first_blue = next(i // 3 for i in range(0, len(pixels), 3) if pixels[i + 2] > pixels[i])
    assert abs(record["seams"][0]["at_seconds"] - first_blue / 24) <= 1 / 24
    assert record["clips"][0]["duration"] != record["clips"][0]["requested_duration"]


def decoded_audio(path):
    return array(
        "f",
        core.ffmpeg(
            [
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


def test_edit_cli_uses_actual_frame_boundaries_for_slow_audio_and_video(tmp_path):
    source = tmp_path / "同步闪白与声音.mkv"
    core.ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "color=black:s=320x180:r=24:d=0.5",
            "-f",
            "lavfi",
            "-i",
            r"aevalsrc=if(gte(t\,0.083333333)\,0.5*sin(2*PI*1000*t)\,0):s=48000:d=0.5",
            "-vf",
            "drawbox=color=white:t=fill:enable='gte(n,2)'",
            "-c:v",
            "ffv1",
            "-c:a",
            "pcm_s16le",
            source,
        ]
    )
    original = core.sha(source)
    outputs = []
    for name, requested_start in (("非整帧", 0.001), ("实际帧起点", 0.042)):
        config, output = tmp_path / f"{name}.yaml", tmp_path / f"{name}.mp4"
        core.write_yaml(
            config,
            {
                "clips": [
                    {
                        "path": source.name,
                        "in_seconds": requested_start,
                        "out_seconds": 0.25,
                        "speed": 0.125,
                    }
                ]
            },
        )
        process = tool_cli("剪辑.py", config, "--output", output)
        assert process.returncode == 0, process.stderr
        outputs.append(output)
    # The same decoded source frames must produce the same sound and picture,
    # regardless of which requested timestamp within the preceding frame was used.
    assert decoded_audio(outputs[0]) == decoded_audio(outputs[1])
    pixels = core.ffmpeg(
        [
            "-i",
            outputs[0],
            "-vf",
            "scale=1:1",
            "-an",
            "-pix_fmt",
            "gray",
            "-f",
            "rawvideo",
            "-",
        ]
    )
    first_white = next(i for i, value in enumerate(pixels) if value > 200) / 24
    samples = decoded_audio(outputs[0])
    tone_start = next(
        i / 48000
        for i in range(0, len(samples) - 480, 480)
        if sum(x * x for x in samples[i : i + 480]) / 480 > 0.05**2
    )
    # Extreme slow pitch processing has an analysis window, but must not add the
    # previously observed extra one-third-second AV offset.
    assert abs(tone_start - first_white) < 0.09
    record = json.loads(core.media_record_path(outputs[0], "剪辑").read_text("utf-8"))
    clip = record["clips"][0]
    assert (clip["requested_in"], clip["requested_out"]) == (0.001, 0.25)
    assert (clip["in"], clip["out"]) == (0.042, 0.25)
    assert (clip["source_frame_start"], clip["source_frame_end_exclusive"]) == (1, 6)
    assert clip["source_time_base"] == "1/1000"
    assert core.sha(source) == original


@pytest.mark.parametrize("video_start,audio_start", [(0, 0), (0, 0.25), (0.25, 0), (5, 5)])
def test_edit_cli_preserves_internal_audio_gap_offsets_and_tail(tmp_path, video_start, audio_start):
    source, config, output = (tmp_path / p for p in ("缺口.mkv", "剪辑.yaml", "结果.mp4"))
    core.ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=64x64:r=24:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=500:sample_rate=48000:duration=1.5",
            "-vf",
            f"setpts=PTS+{video_start}/TB",
            "-af",
            f"asetnsamples=n=480,asetpts='PTS+({audio_start}+gte(N,24000)*0.5)/TB'",
            "-fps_mode",
            "passthrough",
            "-c:v",
            "ffv1",
            "-c:a",
            "pcm_s16le",
            source,
        ]
    )
    before = core.sha(source)
    core.write_yaml(config, {"clips": [{"path": source.name, "out_seconds": 2, "speed": 1}]})
    process = tool_cli("剪辑.py", config, "--output", output)
    assert process.returncode == 0, process.stderr
    samples = decoded_audio(output)
    gap_start = 0.5 + audio_start - video_start

    def rms(start, end):
        region = samples[round(start * 48000) : round(end * 48000)]
        assert len(region) == round((end - start) * 48000)
        return math.sqrt(sum(x * x for x in region) / len(region))

    assert rms(gap_start - 0.2, gap_start - 0.1) > 0.05
    assert rms(gap_start + 0.05, gap_start + 0.45) < 0.0001
    assert rms(gap_start + 0.55, gap_start + 0.65) > 0.05
    assert len(samples) / 48000 >= 2
    assert float(core.probe(output)["video"]["duration"]) == 2
    if video_start > audio_start:
        assert rms(1.8, 1.95) < 0.0001
    else:
        assert rms(1.8, 1.95) > 0.05
    assert core.sha(source) == before


def test_edit_rejects_interval_without_a_decoded_frame(movie, tmp_path):
    config, output = tmp_path / "空帧区间.yaml", tmp_path / "不应发布.mp4"
    core.write_yaml(
        config,
        {
            "clips": [
                {
                    "path": movie.name,
                    "in_seconds": 0.001,
                    "out_seconds": 0.002,
                }
            ]
        },
    )
    process = tool_cli("剪辑.py", config, "--output", output)
    assert process.returncode != 0 and "没有实际视频帧" in process.stderr
    assert not output.exists()


@pytest.mark.parametrize("speed", [0.125, 0.25, 0.5, 0.75, 1, 1.33, 2, 8])
def test_edit_speed_matrix_keeps_transients_pitch_and_treble(tmp_path, speed):
    source, config, output = (tmp_path / p for p in ("双音同步源片.mkv", "变速.yaml", "结果.mp4"))
    core.ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "color=black:s=64x64:r=24:d=2",
            "-f",
            "lavfi",
            "-i",
            r"aevalsrc=gte(t\,0.25)*(0.15*sin(2*PI*1000*t)+0.15*sin(2*PI*12000*t)):s=48000:d=2",
            "-vf",
            "drawbox=color=white:t=fill:enable='gte(n,6)'",
            "-c:v",
            "ffv1",
            "-c:a",
            "pcm_s16le",
            source,
        ]
    )
    original = core.sha(source)
    core.write_yaml(
        config,
        {
            "clips": [
                {
                    "path": source.name,
                    "in_seconds": 0.001,
                    "out_seconds": 2,
                    "speed": speed,
                }
            ]
        },
    )
    process = tool_cli("剪辑.py", config, "--output", output)
    assert process.returncode == 0, process.stderr
    samples = decoded_audio(output)
    pixels = core.ffmpeg(
        [
            "-i",
            output,
            "-vf",
            "scale=1:1",
            "-an",
            "-pix_fmt",
            "gray",
            "-f",
            "rawvideo",
            "-",
        ]
    )
    first_white = next((i / 24 for i, value in enumerate(pixels) if value > 200))
    tone_start = next(
        i / 48000
        for i in range(0, len(samples) - 48, 48)
        if sum(x * x for x in samples[i : i + 48]) / 48 > 0.025**2
    )
    assert abs(tone_start - first_white) < 0.09
    # Check both low and high tones after the onset/processor window. A pitch
    # label or the low tone alone would miss early high-frequency downsampling.
    # The processor can ramp the attack envelope; assess steady-state spectral
    # preservation separately from the independently checked transient timing.
    window_start = round(min(tone_start + 0.3, len(samples) / 48000 - 0.08) * 48000)
    window = samples[window_start : window_start + 1920]
    assert len(window) == 1920

    def amplitude(hz):
        return (
            2
            * abs(
                sum(
                    value
                    * complex(
                        math.cos(2 * math.pi * hz * i / 48000),
                        math.sin(2 * math.pi * hz * i / 48000),
                    )
                    for i, value in enumerate(window)
                )
            )
            / len(window)
        )

    assert amplitude(1000) > 0.07
    assert amplitude(12000) > 0.07
    if speed != 1:
        assert amplitude(1000 * speed) < 0.015
    record = json.loads(core.media_record_path(output, "剪辑").read_text("utf-8"))
    clip = record["clips"][0]
    assert clip["audio_working_sample_rate"] >= max(48000, 48000 * speed)
    assert clip["audio_speed"] == speed
    assert len(samples) / 48000 >= len(pixels) / 24
    assert record["dynamic_review"] == "pending"
    assert core.sha(source) == original


def test_audio_speed_requires_rubberband_instead_of_silent_fallback(monkeypatch):
    monkeypatch.setattr(core, "ffmpeg", lambda *args, **kwargs: b" T.. volume A->A volume\n")
    with pytest.raises(ValueError, match="rubberband"):
        core.audio_speed_filter(0.5, 48000)
    assert core.audio_speed_filter(1, 48000) == ("", 48000, 1.0)


def test_edit_audio_validator_rejects_missing_tail(tmp_path):
    candidate = tmp_path / "少了半秒音轨.mp4"
    core.ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "color=black:s=64x64:r=24:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=500:sample_rate=48000:duration=1.5",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            candidate,
        ]
    )
    with pytest.raises(ValueError, match="未覆盖"):
        core.validate_edit_audio(candidate, 48)


@pytest.fixture
def score(movie, tmp_path):
    notes = tmp_path / "音符.yaml"
    core.write_yaml(
        notes,
        {
            "duration_seconds": 3,
            "notes": [{"start_seconds": 0, "duration_seconds": 3, "midi_note": 60}],
        },
    )
    wav = music.create_sketch(notes, tmp_path / "器乐草稿.wav")
    core.write_yaml(
        tmp_path / "materials.yaml",
        {
            "assets": {
                "MUSIC-01": {
                    "kind": "audio",
                    "state": "ready",
                    "path": wav.name,
                    "sha256": core.sha(wav),
                }
            }
        },
    )
    plan = {
        "timeline": {
            "video_path": movie.name,
            "video_sha256": core.sha(movie),
            "time_origin": "edited_timeline_start",
            "time_unit": "seconds",
            "duration_seconds": core.probe(movie)["duration"],
            "verified": True,
        },
        "materials_manifest": "materials.yaml",
        "dialogue": {"source_has_embedded_music": False},
        "music": {
            "cues": [
                {
                    "cue_id": "C01",
                    "start_seconds": 1,
                    "end_seconds": 3,
                    "purpose": "测试淡变",
                    "entry_trigger": "测试",
                    "exit_trigger": "结束",
                    "instrumentation": "sine",
                    "source_asset_id": "MUSIC-01",
                    "source_in_seconds": 0,
                    "gain_db": -12,
                    "fade_in_seconds": 0.2,
                    "fade_out_seconds": 0.2,
                    "dialogue_ducking": {
                        "method": "regions",
                        "gain_db": -12,
                        "regions": [{"start_seconds": 1.5, "end_seconds": 2}],
                    },
                }
            ],
            "no_music_regions": [{"start_seconds": 0, "end_seconds": 1, "reason": "开场无音乐"}],
        },
    }
    path = tmp_path / "配乐方案.yaml"
    core.write_yaml(path, plan)
    return path, plan


def test_mix_stream_copies_video_and_keeps_sources(movie, tmp_path, score):
    path, _ = score
    original = core.sha(movie)
    output = music.mix(path, tmp_path / "混音.mp4")
    assert core.sha(movie) == original
    assert stream_hash(movie, "0:v:0") == stream_hash(output, "0:v:0")
    assert stream_hash(movie, "0:a:0") != stream_hash(output, "0:a:0")
    record = json.loads(core.media_record_path(output, "混音").read_text("utf-8"))
    assert record["actual_listening"] == "pending"


@pytest.mark.parametrize(
    "problem", ["stale_cut", "embedded_music", "silent_overlap", "short_source"]
)
def test_score_rejects_invalid_timeline(score, problem):
    path, data = score
    if problem == "stale_cut":
        data["timeline"]["video_sha256"] = "0" * 64
    elif problem == "embedded_music":
        data["dialogue"]["source_has_embedded_music"] = True
    elif problem == "silent_overlap":
        data["music"]["no_music_regions"][0]["end_seconds"] = 2
    else:
        data["music"]["cues"][0]["source_in_seconds"] = 2
    core.write_yaml(path, data)
    with pytest.raises(ValueError):
        music.validate(path)


def test_review_range_record_and_hash_invalidation(movie, tmp_path):
    core.write_yaml(tmp_path / "project.yaml", {"name": "测试"})
    config = review.prepare(tmp_path, [movie])
    httpd = review.server(config, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    url, query = httpd.review_url.split("?", 1)
    try:
        with httpx.Client(trust_env=False) as client:
            assert client.get(url + "api/session").status_code == 403
            session = client.get(url + "api/session?" + query).json()
            item = session["media"][0]
            reply = client.get(url + "media?" + query + "&id=0", headers={"Range": "bytes=-16"})
            assert reply.status_code == 206 and reply.content == movie.read_bytes()[-16:]
            bad = client.get(url + "media?" + query + "&id=0", headers={"Range": "bytes=99999999-"})
            assert bad.status_code == 416
            payload = {
                "media_id": "0",
                "sha256": item["sha256"],
                "dimension": "listening",
                "verdict": "pending",
                "reviewer": "test",
                "note": "尚未实际听音",
                "start_seconds": 0,
                "end_seconds": 1,
            }
            assert client.post(url + "api/review?" + query, json=payload).status_code == 200
            movie.write_bytes(movie.read_bytes() + b"changed")
            assert client.get(url + "api/session?" + query).status_code == 409
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()
