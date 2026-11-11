"""Exercise whitebox output preflight without loading Blender or rendering media."""

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools/视频工具/制作喝奶白模.py"


@pytest.fixture
def saved_tools():
    spec = importlib.util.spec_from_file_location(
        "whitebox_saved_safety", SCRIPT.with_name("whitebox_saved.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unsupported_blur_animation_is_rejected_without_clearing_other_animation(saved_tools):
    class UnsupportedAction:
        name = "未知动画"

    target = SimpleNamespace(
        use_dof=True,
        bl_rna=SimpleNamespace(properties={"use_dof": SimpleNamespace(type="BOOLEAN")}),
    )
    action = UnsupportedAction()
    retained = SimpleNamespace(data_path="lens")
    animation = SimpleNamespace(action=action, nla_tracks=[], drivers=[retained])
    owner = SimpleNamespace(
        name="相机", path_resolve=lambda path: target, animation_data=animation
    )
    with pytest.raises(ValueError, match="无法读取模糊开关动画通道"):
        saved_tools.disable_animated_boolean(owner, "dof.use_dof")
    assert target.use_dof
    assert animation.action is action
    assert animation.drivers == [retained]


def test_render_validation_failure_never_publishes_or_retries(saved_tools, tmp_path):
    render = SimpleNamespace(filepath="original render path")
    calls = []

    def render_once(**options):
        calls.append(options)
        Path(render.filepath).write_bytes(b"unverified blurred render")

    def reject_blur():
        raise ValueError("求值后模糊开关重新启用")

    bpy = SimpleNamespace(
        context=SimpleNamespace(scene=SimpleNamespace(render=render)),
        ops=SimpleNamespace(render=SimpleNamespace(render=render_once)),
    )
    destination = tmp_path / "送模.png"
    with pytest.raises(ValueError, match="模糊开关重新启用"):
        saved_tools.render_still_new(bpy, destination, validate_render=reject_blur)
    assert len(calls) == 1
    assert render.filepath == "original render path"
    assert not destination.exists()
    assert list(tmp_path.iterdir()) == []


def registered_project(tmp_path):
    project = tmp_path / "作品"
    project.mkdir()
    (project / "project.yaml").write_text("name: 作品\n", encoding="utf-8")
    return project


@pytest.fixture
def whitebox(monkeypatch):
    def unexpected_scene_access(**kwargs):
        pytest.fail("Rejected output must not modify the Blender scene")

    monkeypatch.setitem(
        sys.modules,
        "bpy",
        SimpleNamespace(
            ops=SimpleNamespace(
                object=SimpleNamespace(
                    select_all=unexpected_scene_access,
                )
            )
        ),
    )
    monkeypatch.setitem(sys.modules, "mathutils", SimpleNamespace(Matrix=object, Vector=object))
    spec = importlib.util.spec_from_file_location("whitebox_output_safety", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "version",
    ["", ".", "..", "../../../../../越界", r"..\逃逸", "01/02", "01:02", "01 ", "01\n"],
)
def test_build_rejects_unsafe_versions_before_any_scene_or_file_changes(
    whitebox, tmp_path, version
):
    project = tmp_path / "作品"
    with pytest.raises(ValueError, match="版本.*不能包含路径"):
        whitebox.build(SimpleNamespace(project=project, version=version, mode="stills"))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("occupied_index", range(4))
def test_build_rejects_any_occupied_output_and_preserves_existing_bytes(
    whitebox, tmp_path, occupied_index
):
    project = registered_project(tmp_path)
    paths = whitebox.output_paths(project, "01")
    occupied = paths[occupied_index]
    if occupied_index in (1, 2):
        occupied.mkdir(parents=True)
        original = occupied / "已有帧.png"
    else:
        occupied.parent.mkdir(parents=True)
        original = occupied
    original.write_bytes(b"existing production data")
    before = set(tmp_path.rglob("*"))

    # No config is needed: a used version must fail before config or Blender access.
    with pytest.raises(FileExistsError, match="请换未使用版本"):
        whitebox.build(SimpleNamespace(project=project, version="01", mode="animation"))

    assert set(tmp_path.rglob("*")) == before
    assert original.read_bytes() == b"existing production data"
    assert all(not path.exists() for index, path in enumerate(paths) if index != occupied_index)


def test_unused_version_is_available_without_touching_existing_version(whitebox, tmp_path):
    project = registered_project(tmp_path)
    old = whitebox.output_paths(project, "01")[0]
    old.parent.mkdir(parents=True)
    old.write_bytes(b"original blend")
    before = set(tmp_path.rglob("*"))

    paths = whitebox.output_paths(project, "02_修正版")

    assert len(paths) == 4
    assert all(path.is_absolute() and path.is_relative_to(project.resolve()) for path in paths)
    assert all(not path.exists() and "02_修正版" in path.name for path in paths)
    assert old.read_bytes() == b"original blend"
    assert set(tmp_path.rglob("*")) == before


def test_resolved_output_outside_project_is_rejected_before_writes(whitebox, tmp_path, monkeypatch):
    project = registered_project(tmp_path).resolve()
    before = set(tmp_path.rglob("*"))
    redirected = project / "03-制作/中间数据/白模帧序列-版本02"
    original_resolve = Path.resolve

    def resolve_with_external_target(path, *args, **kwargs):
        if path == redirected:
            return tmp_path / "外部目录"
        return original_resolve(path, *args, **kwargs)

    # Model canonical resolution through a directory link without requiring OS privileges.
    monkeypatch.setattr(Path, "resolve", resolve_with_external_target)
    with pytest.raises(ValueError, match="当前作品"):
        whitebox.build(SimpleNamespace(project=project, version="02", mode="stills"))
    assert set(tmp_path.rglob("*")) == before


def test_pose_interpolation_keeps_adjacent_pairing_and_rejects_mismatched_vectors(whitebox):
    keys = [{"t": 0, "point": [0, 2, 4]}, {"t": 2, "point": [2, 4, 6]}]
    assert whitebox.interpolate(keys, 1) == {"t": 1, "point": [1, 3, 5]}
    assert whitebox.interpolate(keys, 3) == keys[-1]
    keys[-1]["point"] = [2, 4]
    with pytest.raises(ValueError, match="zip"):
        whitebox.interpolate(keys, 1)


def test_build_rejects_config_owned_by_nested_project_before_outputs(whitebox, tmp_path):
    project = registered_project(tmp_path)
    directory = project / "03-制作/制作计划"
    directory.mkdir(parents=True)
    (directory / "project.yaml").write_text("name: 别的作品\n", encoding="utf-8")
    (directory / "白模动作配置.json").write_text("{}", encoding="utf-8")
    before = set(project.rglob("*"))
    with pytest.raises(ValueError, match="当前作品"):
        whitebox.build(SimpleNamespace(project=project, version="新", mode="stills"))
    assert set(project.rglob("*")) == before


@pytest.fixture
def inspection_and_dressing(tmp_path, monkeypatch):
    project = registered_project(tmp_path)
    source = project / "03-制作/三维工程/龙宝宝喝奶-动作白模-版本03.blend"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"saved source scene")

    class Identity:
        translation = (0, 0, 1)

        def __matmul__(self, point):
            return point

    point = SimpleNamespace(x=0.5, y=0.5, z=1)
    mouth = SimpleNamespace(
        matrix_world=Identity(),
        data=SimpleNamespace(
            vertices=[SimpleNamespace(co=point)],
        ),
    )
    mouth.evaluated_get = lambda _: mouth
    mouth.to_mesh = lambda: mouth.data
    mouth.to_mesh_clear = lambda: None
    scene = SimpleNamespace(
        frame_start=1,
        frame_end=281,
        frame_set=lambda frame: None,
        camera=SimpleNamespace(data=SimpleNamespace(clip_start=0.1, clip_end=100)),
        render=SimpleNamespace(fps=24, fps_base=1),
    )
    fake_bpy = SimpleNamespace(
        app=SimpleNamespace(binary_path="blender"),
        data=SimpleNamespace(
            filepath=str(source),
            is_dirty=False,
            actions=[],
            objects={
                "幼龙-短吻": mouth,
                "控制-头部": SimpleNamespace(matrix_world=Identity()),
            },
        ),
        context=SimpleNamespace(
            scene=scene,
            view_layer=SimpleNamespace(update=lambda: None),
            evaluated_depsgraph_get=lambda: object(),
        ),
    )
    monkeypatch.setitem(sys.modules, "bpy", fake_bpy)
    monkeypatch.setitem(sys.modules, "mathutils", SimpleNamespace(Vector=object))
    monkeypatch.setitem(sys.modules, "bpy_extras", SimpleNamespace())
    monkeypatch.setitem(
        sys.modules,
        "bpy_extras.object_utils",
        SimpleNamespace(
            world_to_camera_view=lambda scene, camera, point: point,
        ),
    )
    modules = []
    for name in ("检查喝奶白模", "布置喝奶中世纪场景"):
        spec = importlib.util.spec_from_file_location(name, SCRIPT.with_name(name + ".py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Unit doubles model the worker boundary; a real Blender regression below
        # proves that the child actually reloads disk without touching the caller.
        monkeypatch.setattr(module, "load_saved", lambda *_: scene)
        modules.append(module)
    monkeypatch.setattr(
        modules[0],
        "launch_saved",
        lambda _b, _s, args: modules[0].inspect_saved(args[0], args[2], args[4]),
    )
    monkeypatch.setattr(modules[0], "require_viewport_evaluation", lambda *_: None)
    return SimpleNamespace(
        project=project, source=source, bpy=fake_bpy, inspection=modules[0], dressing=modules[1]
    )


def directory_link(link, target):
    """Exercise actual canonical path resolution, including Windows junctions."""
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


@pytest.mark.parametrize("case", ["unsaved", "dirty", "missing", "other_project"])
def test_inspection_rejects_invalid_saved_source(inspection_and_dressing, tmp_path, case):
    env = inspection_and_dressing
    if case == "unsaved":
        env.bpy.data.filepath = ""
    elif case == "dirty":
        env.bpy.data.is_dirty = True
    elif case == "missing":
        env.source.unlink()
    else:
        other = tmp_path / "其他作品.blend"
        other.write_bytes(b"other scene")
        env.bpy.data.filepath = str(other)
    with pytest.raises(ValueError):
        env.inspection.inspect(env.project)
    assert not (env.project / "05-检查与验收").exists()


def test_inspection_binds_saved_bytes_and_keeps_all_old_records(inspection_and_dressing):
    env = inspection_and_dressing
    old = env.project / "05-检查与验收/白模工程检查-版本03.json"
    old.parent.mkdir()
    old.write_bytes(b"original inspection")
    out = env.inspection.inspect(env.project)
    report = json.loads(out.read_text("utf-8"))
    assert env.source.stem in out.name
    assert report["blend"] == str(env.source.resolve())
    assert report["blend_sha256"] == hashlib.sha256(env.source.read_bytes()).hexdigest()
    assert "不代表" in report["caveat"]
    before = out.read_bytes()
    with pytest.raises(FileExistsError):
        env.inspection.inspect(env.project)
    assert out.read_bytes() == before
    assert old.read_bytes() == b"original inspection"


@pytest.mark.parametrize("change", ["file", "unsaved_scene"])
def test_inspection_rejects_source_change_during_sampling(inspection_and_dressing, change):
    env = inspection_and_dressing
    if change == "file":
        env.bpy.context.scene.frame_set = lambda frame: env.source.write_bytes(b"changed source")
    else:
        env.bpy.context.scene.frame_set = lambda frame: setattr(env.bpy.data, "is_dirty", True)
    with pytest.raises(ValueError, match="源工程已变化"):
        env.inspection.inspect(env.project)
    assert not (env.project / "05-检查与验收").exists()


def test_inspection_exclusive_write_preserves_report_created_during_sampling(
    inspection_and_dressing,
):
    env = inspection_and_dressing
    _, out = env.inspection.inspection_paths(env.project)

    def concurrent_report(frame):
        if frame == 1:
            out.parent.mkdir()
            out.write_bytes(b"concurrent inspection")

    env.bpy.context.scene.frame_set = concurrent_report
    with pytest.raises(FileExistsError):
        env.inspection.inspect(env.project)
    assert out.read_bytes() == b"concurrent inspection"


def test_inspection_rejects_output_directory_junction(inspection_and_dressing, tmp_path):
    env = inspection_and_dressing
    outside = tmp_path / "外部检查"
    outside.mkdir()
    directory_link(env.project / "05-检查与验收", outside)
    with pytest.raises(ValueError, match="当前作品"):
        env.inspection.inspect(env.project)
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("occupied_index", range(3))
def test_dressing_rejects_every_occupied_destination_before_scene_changes(
    inspection_and_dressing,
    monkeypatch,
    occupied_index,
):
    env = inspection_and_dressing
    _, _, paths = env.dressing.preflight(env.project, "02")
    occupied = paths[occupied_index]
    if occupied_index == 0:
        occupied.write_bytes(b"existing engine")
        original = occupied
    else:
        occupied.mkdir(parents=True)
        original = occupied / "已有帧.png"
        original.write_bytes(b"existing frame")
    before = original.read_bytes()
    monkeypatch.setattr(
        sys, "argv", ["blender", "--", "--project", str(env.project), "--version", "02"]
    )
    with pytest.raises(FileExistsError):
        env.dressing.main()
    assert original.read_bytes() == before
    assert not hasattr(env.bpy.context.scene.render, "engine")
    assert all(not path.exists() for index, path in enumerate(paths) if index != occupied_index)


@pytest.mark.parametrize("category", ["engine", "stills", "frames"])
def test_dressing_rejects_all_output_directory_junctions(
    inspection_and_dressing,
    tmp_path,
    category,
):
    env = inspection_and_dressing
    outside = tmp_path / "外部目录"
    if category == "engine":
        link = env.source.parent
        link.rename(outside)
    else:
        outside.mkdir()
        link = env.project / ("05-检查与验收" if category == "stills" else "03-制作/中间数据")
    directory_link(link, outside)
    before = set(outside.iterdir())
    with pytest.raises(ValueError, match="当前作品"):
        env.dressing.preflight(env.project, "02")
    assert set(outside.iterdir()) == before


@pytest.mark.parametrize(
    "case",
    [
        "unsaved",
        "dirty",
        "wrong_version",
        "other_project",
        "frames",
        "fps",
        "fps_base",
        "first_frame",
    ],
)
def test_dressing_rejects_wrong_source_or_timeline_before_outputs(
    inspection_and_dressing,
    tmp_path,
    case,
):
    env = inspection_and_dressing
    if case == "unsaved":
        env.bpy.data.filepath = ""
    elif case == "dirty":
        env.bpy.data.is_dirty = True
    elif case in {"wrong_version", "other_project"}:
        source = (
            env.source.with_name("龙宝宝喝奶-动作白模-版本02.blend")
            if case == "wrong_version"
            else tmp_path / env.source.name
        )
        source.write_bytes(b"wrong source")
        env.bpy.data.filepath = str(source)
    elif case == "frames":
        env.bpy.context.scene.frame_end = 2
    elif case == "first_frame":
        env.bpy.context.scene.frame_start = 2
    else:
        setattr(env.bpy.context.scene.render, case, 30 if case == "fps" else 1.001)
    with pytest.raises(ValueError):
        env.dressing.preflight(env.project, "02")
    assert not (env.project / "05-检查与验收").exists()
    assert not (env.project / "03-制作/中间数据").exists()


def test_dressing_new_version_retains_actual_source_provenance(inspection_and_dressing):
    env = inspection_and_dressing
    source, source_hash, paths = env.dressing.preflight(env.project, "02")
    assert source == env.source.resolve()
    assert source_hash == hashlib.sha256(env.source.read_bytes()).hexdigest()
    assert len(paths) == 3
    assert all(path.is_relative_to(env.project.resolve()) and not path.exists() for path in paths)


def test_dressing_dispatches_saved_source_before_modifying_caller(
    inspection_and_dressing,
    monkeypatch,
):
    env = inspection_and_dressing
    calls = []
    monkeypatch.setattr(env.dressing, "launch_saved", lambda *args: calls.append(args) or "")
    monkeypatch.setattr(
        sys, "argv", ["blender", "--", "--project", str(env.project), "--version", "02"]
    )
    env.dressing.main()
    assert len(calls) == 1
    assert "--saved-source" in calls[0][2]
    assert env.source.resolve() in calls[0][2]
    assert not hasattr(env.bpy.context.scene.render, "engine")
    assert not (env.project / "05-检查与验收").exists()


@pytest.mark.parametrize("category", ["03-制作/三维工程", "05-检查与验收"])
@pytest.mark.parametrize("entry", ["build", "inspection", "dressing"])
def test_legacy_preflight_rejects_nearest_nested_project_owner(
    inspection_and_dressing, whitebox, category, entry,
):
    env = inspection_and_dressing
    nested = env.project / category
    nested.mkdir(parents=True, exist_ok=True)
    (nested / "project.yaml").write_text("name: 另一个作品\n", encoding="utf-8")
    before = set(env.project.rglob("*"))
    with pytest.raises(ValueError, match="当前作品"):
        if entry == "build":
            whitebox.output_paths(env.project, "新")
        elif entry == "inspection":
            env.inspection.inspection_paths(env.project)
        else:
            env.dressing.preflight(env.project, "新")
    assert set(env.project.rglob("*")) == before


@pytest.mark.parametrize("kind", ["blend", "record", "frame"])
@pytest.mark.skipif(not Path(r"D:\blender-5.3.0\blender.exe").exists(), reason="本机Blender未安装")
def test_real_legacy_build_preserves_outputs_created_during_construction(tmp_path, kind):
    result = subprocess.run(
        [
            r"D:\blender-5.3.0\blender.exe", "--background", "--factory-startup",
            "--disable-autoexec", "--python-exit-code", "1", "--python",
            str(SCRIPT.parents[2] / "tests/fixtures/whitebox_publish.py"), "--",
            str(tmp_path / "作品"), kind,
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"CONCURRENT_OUTPUT_PRESERVED={kind}" in result.stdout


@pytest.fixture
def forest(tmp_path, monkeypatch):
    # Preflight rejection must precede any scene read/write or child launch.
    monkeypatch.setitem(sys.modules, "bpy", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "mathutils", SimpleNamespace(Vector=object))
    monkeypatch.setitem(sys.modules, "bpy_extras", SimpleNamespace())
    monkeypatch.setitem(
        sys.modules, "bpy_extras.object_utils", SimpleNamespace(world_to_camera_view=object)
    )
    spec = importlib.util.spec_from_file_location(
        "forest_safety", SCRIPT.with_name("制作森林喝奶固定引导.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    project = tmp_path / "森林作品"
    project.mkdir()
    (project / "project.yaml").write_text("name: 森林作品\n", encoding="utf-8")
    engine = project / "03-制作/三维工程"
    engine.mkdir(parents=True)
    for name in ("龙宝宝喝奶-动作白模-版本03.blend", "龙宝宝喝奶-森林固定机位-版本测试.blend"):
        (engine / name).write_bytes(b"saved fixture")
    plate = project / "底图.png"
    plate.write_bytes(b"fixture")
    return module, project, plate


@pytest.mark.parametrize(
    "stage,category",
    [
        (stage, category)
        for stage in ("prepare", "finish")
        for category in ("engine", "stills", "nested")
    ]
    + [("finish", "frames")],
)
def test_forest_rejects_escaped_or_nested_owner_before_scene_access(
    forest, tmp_path, stage, category
):
    module, project, plate = forest
    outside = tmp_path / "其他作品"
    outside.mkdir()
    (outside / "project.yaml").write_text("name: 其他作品\n", encoding="utf-8")
    if category == "engine":
        link = project / "03-制作/三维工程"
        target = outside / "三维工程"
        link.rename(target)
        directory_link(link, target)
    elif category == "nested":
        link = project / "05-检查与验收"
        link.mkdir()
        (link / "project.yaml").write_text("name: 嵌套作品\n", encoding="utf-8")
    else:
        link = project / ("05-检查与验收" if category == "stills" else "03-制作/中间数据")
        directory_link(link, outside)
    before = {p: p.read_bytes() for p in outside.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="当前作品"):
        module.dispatch(project, stage, "测试", plate)
    assert {p: p.read_bytes() for p in outside.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize(
    "stage,key",
    [(stage, key) for stage in ("prepare", "finish") for key in ("destination", "stills", "record")]
    + [("finish", "frames")],
)
def test_forest_checks_every_occupied_output_before_scene_access(forest, stage, key):
    module, project, plate = forest
    version = "准备" if stage == "prepare" else "测试"
    paths = module.preflight(project, stage, version, plate)
    occupied = paths[key]
    occupied.parent.mkdir(parents=True, exist_ok=True)
    occupied.write_bytes(b"existing output")
    before = set(project.rglob("*"))
    with pytest.raises(FileExistsError):
        module.dispatch(project, stage, version, plate)
    assert set(project.rglob("*")) == before
    assert occupied.read_bytes() == b"existing output"


def test_forest_rejects_other_project_plate_and_changed_plate(forest, tmp_path):
    module, project, plate = forest
    outside = tmp_path / "别片底图.png"
    outside.write_bytes(b"external plate")
    with pytest.raises(ValueError, match="当前作品"):
        module.finish(project, outside, "测试")
    paths = module.preflight(project, "finish", "测试", plate)
    old_hash = module.sha(plate)
    plate.write_bytes(b"changed")
    with pytest.raises(ValueError, match="底图发生变化"):
        module.check_inputs(paths, module.sha(paths["source"]), old_hash)


def test_forest_save_never_replaces_a_concurrently_created_blend(forest):
    module, project, plate = forest
    destination = module.preflight(project, "finish", "测试", plate)["destination"]

    def save_copy(filepath, copy):
        assert copy is True
        Path(filepath).write_bytes(b"new saved scene")
        destination.write_bytes(b"another task's scene")

    bpy_double = SimpleNamespace(
        ops=SimpleNamespace(wm=SimpleNamespace(save_as_mainfile=save_copy))
    )
    with pytest.raises(FileExistsError):
        module.save_new(bpy_double, destination)
    assert destination.read_bytes() == b"another task's scene"


@pytest.mark.parametrize("stage", ["prepare", "finish"])
@pytest.mark.parametrize("case", ["dirty", "unsaved", "other_source"])
def test_forest_rejects_invalid_caller_without_loading_or_editing_scene(forest, stage, case):
    module, project, plate = forest
    version = "准备" if stage == "prepare" else "测试"
    source = module.preflight(project, stage, version, plate)["source"]
    module.bpy = SimpleNamespace(
        data=SimpleNamespace(
            filepath="" if case == "unsaved" else str(source if case == "dirty" else plate),
            is_dirty=case == "dirty",
        )
    )
    before = set(project.rglob("*"))
    with pytest.raises(ValueError):
        module.dispatch(project, stage, version, plate)
    assert set(project.rglob("*")) == before


@pytest.mark.parametrize("stage", ["prepare", "finish"])
@pytest.mark.skipif(not Path(r"D:\blender-5.3.0\blender.exe").exists(), reason="本机Blender未安装")
def test_real_forest_stages_reload_disk_and_preserve_caller_memory(tmp_path, stage):
    result = subprocess.run(
        [
            r"D:\blender-5.3.0\blender.exe",
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--python-exit-code",
            "1",
            "--python",
            str(SCRIPT.parents[2] / "tests/fixtures/whitebox_forest.py"),
            "--",
            str(tmp_path / "森林作品"),
            stage,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"FOREST_RELOAD_OK={stage}" in result.stdout
