import json
import shutil
import subprocess

import pytest

from autodl_video.cli import main
from autodl_video.errors import AutoDLError
from autodl_video.reference import prepare_reference, probe_video


@pytest.fixture
def source_video(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe are needed for local media integration tests")
    path = tmp_path / "原片 with audio.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-n",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x96:rate=12:duration=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


def test_mute_preserves_original_and_video_stream(source_video, tmp_path):
    original = source_video.read_bytes()
    before = probe_video(source_video)
    destination = tmp_path / "输出" / "silent.mp4"
    after = prepare_reference(source_video, destination)
    assert before["has_audio"] and not after["has_audio"]
    assert source_video.read_bytes() == original
    assert after["video_stream_copied"]
    for field in ("width", "height", "fps", "codec", "duration"):
        assert after[field] == before[field]

    # Compare compressed video payloads; removal must not alter the motion frames.
    def video_payload(path):
        return subprocess.check_output(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(path),
                "-map",
                "0:v:0",
                "-c",
                "copy",
                "-f",
                "data",
                "-",
            ]
        )

    assert video_payload(source_video) == video_payload(destination)


def test_accurate_trim_and_cli(source_video, tmp_path, project, capsys):
    destination = tmp_path / "clip.mp4"
    args = ["--project", str(project), "media"]
    assert main([*args, "inspect", str(source_video)]) == 0
    assert '"has_audio": true' in capsys.readouterr().out
    assert (
        main(
            [
                *args,
                "prepare",
                str(source_video),
                "--output",
                str(destination),
                "--start",
                "0.5",
                "--duration",
                "1",
            ]
        )
        == 0
    )
    result = probe_video(destination)
    assert not result["has_audio"]
    assert result["duration"] == pytest.approx(1, abs=1 / 12)


def test_existing_output_is_preserved(source_video, tmp_path):
    destination = tmp_path / "existing.mp4"
    destination.write_bytes(b"preserve existing work")
    with pytest.raises(AutoDLError, match="already exists"):
        prepare_reference(source_video, destination)
    assert destination.read_bytes() == b"preserve existing work"
    with pytest.raises(AutoDLError, match="already exists"):
        prepare_reference(source_video, source_video)


def test_no_silent_padding(source_video, tmp_path):
    destination = tmp_path / "overlong.mp4"
    with pytest.raises(AutoDLError, match="exceeds source"):
        prepare_reference(source_video, destination, start=1, duration=2)
    assert not destination.exists()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start": -1},
        {"duration": 0},
        {"duration": float("nan")},
        {"start": float("inf")},
        {"start": True},
    ],
)
def test_invalid_times_do_not_invoke_media_tools(tmp_path, kwargs, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid times must be rejected before running tools")

    monkeypatch.setattr("autodl_video.reference.probe_video", forbidden)
    with pytest.raises(AutoDLError, match="finite"):
        prepare_reference(tmp_path / "source.mp4", tmp_path / "out.mp4", **kwargs)


def test_probe_rejects_non_video(tmp_path):
    path = tmp_path / "fake.mp4"
    path.write_text("This is not a depth video or a video", encoding="utf-8")
    with pytest.raises(AutoDLError, match="ffprobe"):
        probe_video(path)


def test_migrated_media_paths_work_through_api_and_cli(source_video, project, capsys):
    work = project / "projects/作品甲"
    work.mkdir()
    (work / "project.yaml").write_text("name: 作品甲\n", encoding="utf-8")
    source = work / "原片.mp4"
    shutil.copy2(source_video, source)
    original = source.read_bytes()
    registry = project / ".autodl/path-map.json"
    registry.parent.mkdir()
    registry.write_text(json.dumps({
        "files": {"assets/old.mp4": "projects/作品甲/原片.mp4"},
        "directories": {"outputs/old": "projects/作品甲/04-输出"},
    }), encoding="utf-8")
    legacy = project / "assets/old.mp4"
    assert probe_video(legacy, root=project)["path"] == str(source)
    prepared = prepare_reference(legacy, project / "outputs/old/api.mp4", root=project)
    assert prepared["path"] == str(work / "04-输出/api.mp4")
    prefix = ["--project", str(project), "media"]
    assert main([*prefix, "inspect", str(legacy)]) == 0
    assert json.loads(capsys.readouterr().out)["path"] == str(source)
    assert main([
        *prefix, "prepare", str(legacy), "--output", str(project / "outputs/old/cli.mp4"),
    ]) == 0
    assert json.loads(capsys.readouterr().out)["path"] == str(work / "04-输出/cli.mp4")
    assert source.read_bytes() == original
    assert not (project / "assets").exists()
    assert not (project / "outputs").exists()


@pytest.mark.parametrize("output", ["outputs/out.mp4", "projects/作品乙/out.mp4"])
def test_media_rejects_other_output_owner_before_tools(project, monkeypatch, capsys, output):
    for name in ("作品甲", "作品乙"):
        work = project / "projects" / name
        work.mkdir()
        (work / "project.yaml").write_text(f"name: {name}\n", encoding="utf-8")
    source = project / "projects/作品甲/原片.mp4"
    source.write_bytes(b"source must not be touched")
    destination = project / output

    def forbidden(*args, **kwargs):
        pytest.fail("Output ownership must be checked before ffprobe or ffmpeg")

    monkeypatch.setattr("autodl_video.reference.probe_video", forbidden)
    with pytest.raises(AutoDLError, match="输出必须"):
        prepare_reference(source, destination, root=project)
    assert main([
        "--project", str(project), "media", "prepare", str(source),
        "--output", str(destination),
    ]) == 2
    assert "输出必须" in capsys.readouterr().err
    assert not destination.exists()
    assert source.read_bytes() == b"source must not be touched"
