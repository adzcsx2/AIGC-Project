"""Temporary project fixtures for the six authored production tools' evidence gates."""

import hashlib
import importlib
import importlib.util
import json
import math
import runpy
import shutil
import subprocess
import sys
import threading
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools/视频工具"
sys.path.insert(0, str(TOOLS))

safety = importlib.import_module("project_tool_safety")
saved = importlib.import_module("whitebox_saved")


def module(filename):
    spec = importlib.util.spec_from_file_location(filename[:-3], TOOLS / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "临时作品"
    root.mkdir()
    (root / "project.yaml").write_text("name: 临时作品\n", encoding="utf-8")
    return root


@pytest.fixture
def fake_blender(monkeypatch):
    scene = SimpleNamespace(
        render=SimpleNamespace(
            engine="CYCLES",
            resolution_x=64,
            resolution_y=48,
            resolution_percentage=100,
            fps=24,
            fps_base=1,
            filepath="original",
        ),
        frame_start=1,
        frame_end=768,
        frame_set=lambda frame: None,
    )
    bpy = SimpleNamespace(context=SimpleNamespace(scene=scene))
    monkeypatch.setitem(sys.modules, "bpy", bpy)
    monkeypatch.setitem(
        sys.modules,
        "mathutils",
        SimpleNamespace(
            Matrix=object,
            Vector=lambda value: value,
            Quaternion=object,
        ),
    )
    return bpy


def test_json_binding_hashes_the_bytes_actually_parsed(project, monkeypatch):
    path = project / "配置.json"
    old = b'{"value":1}'
    path.write_bytes(old)
    parsed, digest = safety.read_json_bound(path)
    assert parsed == {"value": 1}
    assert digest == hashlib.sha256(old).hexdigest()
    read = Path.read_bytes

    def change_after_read(self):
        payload = read(self)
        if self == path:
            self.write_bytes(b'{"value":2}')
        return payload

    monkeypatch.setattr(Path, "read_bytes", change_after_read)
    with pytest.raises(ValueError, match="变化"):
        safety.read_json_bound(path)


def test_config_changed_during_private_save_never_publishes(project, fake_blender, monkeypatch):
    config = project / "配置.json"
    config.write_text("{}", encoding="utf-8")
    digest = saved.sha(config)
    output = project / "新工程.blend"

    def save_then_change(bpy, path, owner):
        path.write_bytes(b"private blend")
        config.write_text('{"changed":true}', encoding="utf-8")

    monkeypatch.setattr(safety, "save_new", save_then_change)
    with pytest.raises(ValueError, match="变化"):
        safety.save_checked(
            fake_blender, output, project, lambda: safety.require_hash(config, digest)
        )
    assert not output.exists()
    assert not list(project.glob(".工程保存-*"))


def test_dragon_main_rejects_configuration_changed_during_build(project, fake_blender, monkeypatch):
    tool = module("制作龙宝宝睡醒舔奶.py")
    config = project / "配置.json"
    config.write_text('{"used":1}', encoding="utf-8")

    def build(value):
        assert value == {"used": 1}
        config.write_text('{"unused":2}', encoding="utf-8")
        return []

    monkeypatch.setattr(tool, "build", build)
    monkeypatch.setattr(
        sys,
        "argv",
        ["tool", "--", "--project", str(project), "--config", "配置.json", "--version", "测试"],
    )
    with pytest.raises(ValueError, match="变化"):
        tool.main()
    assert not list(project.rglob("*.blend"))
    assert not list(project.rglob("*制作采样*.json"))


def forest_fixture(project, fake_blender, monkeypatch):
    tool = module("布置睡醒舔奶森林.py")
    for name in ("来源.blend", "底图.png"):
        (project / name).write_bytes(b"source")
    blend = project / "03-制作/三维工程/龙宝宝-睡醒舔奶-森林引导测试.blend"
    blend.parent.mkdir(parents=True)
    blend.write_bytes(b"saved forest")
    frames = project / "03-制作/中间数据/睡醒舔奶-森林序列测试"
    frames.mkdir(parents=True)
    binding = safety.sequence_binding(
        fake_blender.context.scene, blend, saved.sha(blend), frames, project
    )
    record = project / "05-检查与验收/睡醒舔奶-森林引导测试.json"
    saved.write_json_new(
        record,
        {"blend": str(blend.relative_to(project)), "sha256": saved.sha(blend), "sequence": binding},
        project,
    )
    saved.write_json_new(frames / "序列绑定.json", binding, project)

    def load(bpy, source, digest):
        safety.require_hash(source, digest)
        return bpy.context.scene

    monkeypatch.setattr(tool, "load_saved", load)
    monkeypatch.setattr(tool, "configure_gpu", lambda scene: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tool",
            "--",
            "--project",
            str(project),
            "--source",
            "来源.blend",
            "--plate",
            "底图.png",
            "--version",
            "测试",
            "--render",
            "--start",
            "1",
            "--end",
            "2",
        ],
    )
    return tool, blend, frames, record


@pytest.mark.parametrize("change", ["blend", "engine", "size", "fps", "legacy", "range"])
def test_forest_resume_rejects_unbound_or_changed_sequence(
    project, fake_blender, monkeypatch, change
):
    tool, blend, frames, record = forest_fixture(project, fake_blender, monkeypatch)
    if change == "blend":
        blend.write_bytes(b"different blend")
    elif change == "engine":
        monkeypatch.setattr(sys, "argv", [*sys.argv, "--engine", "BLENDER_EEVEE"])
    elif change == "size":
        fake_blender.context.scene.render.resolution_x = 128
    elif change == "fps":
        fake_blender.context.scene.render.fps_base = 1.001
    elif change == "legacy":
        value = json.loads(record.read_text("utf-8"))
        del value["sequence"]
        record.write_text(json.dumps(value), encoding="utf-8")
        (frames / "帧0001.png").write_bytes(b"legacy frame")
    else:
        monkeypatch.setattr(sys, "argv", [*sys.argv, "--end", "769"])
    with pytest.raises(ValueError):
        tool.main()
    assert not (frames / "帧0002.png").exists()


@pytest.mark.parametrize("changed", [False, True])
def test_forest_validates_saved_hash_before_each_frame_publication(
    project,
    fake_blender,
    monkeypatch,
    changed,
):
    tool, blend, frames, _ = forest_fixture(project, fake_blender, monkeypatch)

    def render(**kwargs):
        Path(fake_blender.context.scene.render.filepath).write_bytes(b"frame")
        if changed:
            blend.write_bytes(b"changed while rendering")

    fake_blender.ops = SimpleNamespace(render=SimpleNamespace(render=render))
    if changed:
        with pytest.raises(ValueError, match="变化"):
            tool.main()
        assert not list(frames.glob("*.png"))
    else:
        tool.main()
        assert [f.name for f in frames.glob("*.png")] == ["帧0001.png", "帧0002.png"]
    assert fake_blender.context.scene.render.filepath == "original"


@pytest.mark.parametrize(
    "field,value", [("fps", 30), ("fps_base", 1.001), ("frame_start", 2), ("frame_end", 767)]
)
def test_geometry_rejects_unsupported_timeline_before_sampling(
    project,
    fake_blender,
    monkeypatch,
    field,
    value,
):
    source = project / "工程.blend"
    source.write_bytes(b"blend")
    scene = fake_blender.context.scene
    setattr(scene.render if field.startswith("fps") else scene, field, value)
    monkeypatch.setattr(saved, "load_saved", lambda *args: scene)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tool",
            "--",
            "--project",
            str(project),
            "--source",
            "工程.blend",
            "--output",
            "报告.json",
        ],
    )
    with pytest.raises(ValueError, match="时间轴"):
        runpy.run_path(str(TOOLS / "核查睡醒舔奶几何.py"))
    assert not (project / "报告.json").exists()


def test_report_rechecks_source_after_serializing(project, monkeypatch):
    source = project / "工程.blend"
    source.write_bytes(b"original blend")
    digest = saved.sha(source)
    original = safety.json_staging

    def mutate(*args):
        staging = original(*args)
        source.write_bytes(b"another blend")
        return staging

    monkeypatch.setattr(safety, "json_staging", mutate)
    with pytest.raises(ValueError, match="变化"):
        safety.write_json_checked(
            project / "报告.json",
            {"sha256": digest},
            project,
            lambda: safety.require_hash(source, digest),
        )
    assert not (project / "报告.json").exists()


@pytest.mark.parametrize("changed", [False, True])
def test_geometry_report_stays_bound_to_loaded_scene(
    project,
    fake_blender,
    monkeypatch,
    changed,
):
    source = project / "工程.blend"
    source.write_bytes(b"original scene")
    digest = saved.sha(source)
    scene = fake_blender.context.scene

    class Point:
        def __init__(self, values):
            self.x, self.y = values[:2]
            self.z = values[2] if len(values) == 3 else 0

        def __sub__(self, other):
            return Point((self.x - other.x, self.y - other.y, self.z - other.z))

        @property
        def length(self):
            return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    class Matrix:
        translation = Point((0, 0, 0.1))

        def __matmul__(self, value):
            return value

    mesh = SimpleNamespace(vertices=[SimpleNamespace(co=Point((0, 0, 0.2)))])
    evaluated = SimpleNamespace(
        matrix_world=Matrix(), to_mesh=lambda: mesh, to_mesh_clear=lambda: None
    )
    obj = SimpleNamespace(evaluated_get=lambda graph: evaluated)

    class Objects(dict):
        def __missing__(self, key):
            return obj

    objects = Objects(
        {
            "奶面": SimpleNamespace(matrix_world=Matrix()),
            "控制-头部": SimpleNamespace(location=(0, 0, 0.5)),
            "幼龙-上眼睑-1": SimpleNamespace(
                data=SimpleNamespace(
                    shape_keys=SimpleNamespace(key_blocks={"闭眼": SimpleNamespace(value=0.2)})
                )
            ),
        }
    )
    fake_blender.data = SimpleNamespace(objects=objects)
    fake_blender.context.evaluated_depsgraph_get = lambda: None
    monkeypatch.setitem(sys.modules, "mathutils", SimpleNamespace(Vector=Point))

    def load(bpy, path, expected):
        assert expected == digest
        return scene

    def frame_set(frame):
        if changed and frame == 768:
            source.write_bytes(b"another scene")

    scene.frame_set = frame_set
    monkeypatch.setattr(saved, "load_saved", load)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tool",
            "--",
            "--project",
            str(project),
            "--source",
            "工程.blend",
            "--output",
            "报告.json",
        ],
    )
    if changed:
        with pytest.raises(ValueError, match="变化"):
            runpy.run_path(str(TOOLS / "核查睡醒舔奶几何.py"))
        assert not (project / "报告.json").exists()
    else:
        runpy.run_path(str(TOOLS / "核查睡醒舔奶几何.py"))
        data = json.loads((project / "报告.json").read_text("utf-8"))
        assert data["sha256"] == digest
        assert len(data["samples"]) == 28
        assert data["samples"][-1]["time"] == 767 / 24


def test_bundle_collision_rolls_back_only_this_writer(project, tmp_path, monkeypatch):
    staged = [tmp_path / name for name in ("sample", "track", "record")]
    for path in staged:
        path.write_bytes(path.name.encode())
    targets = [project / "new" / name for name in ("sample.wav", "track.wav", "record.json")]
    publish = safety.publish_new

    def collide(source, target, owner):
        if target == targets[-1]:
            target.write_bytes(b"other writer record")
        publish(source, target, owner)

    monkeypatch.setattr(safety, "publish_new", collide)
    with pytest.raises(FileExistsError):
        safety.publish_bundle(list(zip(staged, targets, strict=True)), project)
    assert not targets[0].exists() and not targets[1].exists()
    assert targets[2].read_bytes() == b"other writer record"


def test_concurrent_bundle_preserves_one_complete_winner(project, tmp_path):
    targets = [project / "new" / name for name in ("sample.wav", "track.wav", "record.json")]
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
    barrier = threading.Barrier(2)

    def writer(index):
        staged = [tmp_path / f"{index}-{n}" for n in range(3)]
        for item in staged:
            item.write_bytes(str(index).encode())
        barrier.wait(timeout=5)
        try:
            safety.publish_bundle(list(zip(staged, targets, strict=True)), project)
        except FileExistsError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(writer, range(2)))
    assert sum(results) == 1
    assert len({target.read_bytes() for target in targets}) == 1


def test_burp_creates_missing_record_directory_and_keeps_review_pending(project, monkeypatch):
    tool = module("制作幼龙饱嗝.py")
    monkeypatch.setattr(sys, "argv", ["tool", "--project", str(project)])
    tool.main()
    data = json.loads((project / "06-记录/饱嗝音效制作04.json").read_text("utf-8"))
    assert data["actual_listening"] == data["user_acceptance"] == "pending"
    assert data["dialogue"] is data["music"] is False
    for field, duration in (("sample", 0.31), ("track", 32)):
        path = project / data[field]
        assert saved.sha(path) == data[f"{field}_sha256"]
        with wave.open(str(path)) as audio:
            assert audio.getnchannels() == 1 and audio.getframerate() == 48000
            assert audio.getnframes() == round(duration * 48000)
    assert not list(project.glob(".饱嗝制作-*"))


def test_burp_write_failure_leaves_no_published_files(project, monkeypatch):
    tool = module("制作幼龙饱嗝.py")
    original = tool.write_wave
    calls = []

    def fail_on_track(path, *args):
        original(path, *args)
        calls.append(path)
        if len(calls) == 2:
            raise OSError("disk failure")

    monkeypatch.setattr(tool, "write_wave", fail_on_track)
    monkeypatch.setattr(sys, "argv", ["tool", "--project", str(project)])
    with pytest.raises(OSError, match="disk failure"):
        tool.main()
    assert not list(project.rglob("*.wav")) and not list(project.rglob("*.json"))
    assert not list(project.glob(".饱嗝制作-*"))


@pytest.mark.parametrize("tool_name", ["制作幼龙饱嗝.py", "编码睡醒舔奶引导.py"])
def test_project_tools_reject_nested_project_outputs(project, monkeypatch, tool_name):
    nested = project / ("02-素材" if "饱嗝" in tool_name else "frames")
    nested.mkdir()
    (nested / "project.yaml").write_text("name: other", encoding="utf-8")
    tool = module(tool_name)
    with pytest.raises(ValueError, match="当前作品"):
        if "饱嗝" in tool_name:
            monkeypatch.setattr(sys, "argv", ["tool", "--project", str(project)])
            tool.main()
        else:
            tool.encode(project, "frames", "test")


@pytest.fixture
def encode_fixture(project):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("local ffmpeg/ffprobe not installed")
    tool = module("编码睡醒舔奶引导.py")
    frames = project / "frames"
    frames.mkdir()
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=red:s=64x48",
            "-frames:v",
            "1",
            "-update",
            "1",
            str(frames / "帧0001.png"),
        ],
        check=True,
        capture_output=True,
    )
    for index in range(2, 25):
        shutil.copyfile(frames / "帧0001.png", frames / f"帧{index:04d}.png")
    audio = project / "02-素材/音频/睡醒舔奶-32秒声音引导04.wav"
    audio.parent.mkdir(parents=True)
    with wave.open(str(audio), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(48000)
        stream.writeframes(b"\x00\x00" * 48000)
    blend = project / "工程.blend"
    blend.write_bytes(b"short test scene")
    scene = SimpleNamespace(
        render=SimpleNamespace(
            engine="CYCLES",
            resolution_x=64,
            resolution_y=48,
            resolution_percentage=100,
            fps=24,
            fps_base=1,
        ),
        frame_start=1,
        frame_end=24,
    )
    binding = safety.sequence_binding(scene, blend, saved.sha(blend), frames, project)
    saved.write_json_new(frames / "序列绑定.json", binding, project)
    return tool, frames, audio


def run_short_fixture(tool, project, frames):
    return tool.encode(
        project, frames, "临时测试", frame_count=24, segment_ranges=((0, 16), (12, 24))
    )


def test_encoder_rejects_nested_output_before_encoding(project, encode_fixture, monkeypatch):
    tool, frames, _ = encode_fixture
    output_folder = project / "04-输出/处理过程"
    output_folder.mkdir(parents=True)
    (output_folder / "project.yaml").write_text("name: other", encoding="utf-8")
    monkeypatch.setattr(tool, "run", lambda args: pytest.fail("must reject before encoding"))
    with pytest.raises(ValueError, match="当前作品"):
        run_short_fixture(tool, project, frames)


def test_encoder_keeps_actual_snapshot_pixels_when_live_source_is_replaced_and_restored(
    project,
    encode_fixture,
    monkeypatch,
):
    tool, frames, audio = encode_fixture
    source = frames / "帧0001.png"
    before = source.read_bytes()
    audio_before = audio.read_bytes()
    run = tool.run
    modified = []

    def replace_during_encode(cmd):
        if cmd[0] == "ffmpeg" and "-framerate" in cmd:
            source.write_bytes(b"not an image")
            audio.write_bytes(b"not audio")
            modified.append(True)
            try:
                return run(cmd)
            finally:
                source.write_bytes(before)
                audio.write_bytes(audio_before)
        return run(cmd)

    monkeypatch.setattr(tool, "run", replace_during_encode)
    outputs, record = run_short_fixture(tool, project, frames)
    assert modified == [True]
    evidence = json.loads(record.read_text("utf-8"))
    assert evidence["source_frame_ranges"] == [[0, 16], [12, 24]]
    assert evidence["overlap_seconds"] == [0.5, 16 / 24]
    assert evidence["dynamic_review"] == evidence["actual_listening"] == "pending"
    for item, path, count in zip(evidence["outputs"], outputs, [24, 16, 12], strict=True):
        assert item["sha256"] == saved.sha(path)
        assert int(item["probe"]["streams"][0]["nb_read_frames"]) == count
    assert len(evidence["source_inputs"]) == 27
    binding = next(i for i in evidence["source_inputs"] if i["path"].endswith("帧0001.png"))
    assert binding["sha256"] == hashlib.sha256(before).hexdigest()
    pixels = run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(outputs[0]),
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ]
    )
    assert pixels[0] > 220 and pixels[1] < 20 and pixels[2] < 20
    assert source.read_bytes() == before and audio.read_bytes() == audio_before
    assert not list(project.glob(".引导编码-*"))


@pytest.mark.parametrize("failure", ["encode", "changed", "record_collision"])
def test_encoder_failures_never_leave_unowned_public_media(
    project,
    encode_fixture,
    monkeypatch,
    failure,
):
    tool, frames, _ = encode_fixture
    run = tool.run
    record = project / "05-检查与验收/睡醒舔奶-引导编码检查临时测试.json"

    def inject(cmd):
        if cmd[0] == "ffmpeg" and "-framerate" in cmd:
            if failure == "encode":
                Path(cmd[-1]).write_bytes(b"partial mp4")
                raise subprocess.CalledProcessError(1, cmd)
            result = run(cmd)
            if failure == "changed":
                (frames / "帧0001.png").write_bytes(b"changed")
            else:
                record.parent.mkdir(parents=True)
                record.write_text("other writer", encoding="utf-8")
            return result
        return run(cmd)

    monkeypatch.setattr(tool, "run", inject)
    with pytest.raises((subprocess.CalledProcessError, ValueError, FileExistsError)):
        run_short_fixture(tool, project, frames)
    assert not list(project.rglob("*.mp4"))
    if failure == "record_collision":
        assert record.read_text("utf-8") == "other writer"
    else:
        assert not record.exists()
    assert not list(project.glob(".引导编码-*"))
