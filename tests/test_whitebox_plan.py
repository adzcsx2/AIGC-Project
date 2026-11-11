"""Whitebox plan boundaries, fail-closed evidence and one-to-one cut matching."""

import importlib.util
import json
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import httpx
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools/视频工具"
sys.path.insert(0, str(TOOLS))
import whitebox_core as core  # noqa: E402


@pytest.fixture
def work(tmp_path):
    project = tmp_path / "作品"
    project.mkdir()
    (project / "project.yaml").write_text("name: 白模验证\n", encoding="utf-8")
    blend = project / "03-制作/三维工程/测试.blend"
    blend.parent.mkdir(parents=True)
    blend.write_bytes(b"test saved blend")
    plan = {
        "schema_version": 1,
        "fps": {"num": 24, "den": 1},
        "frame_count": 8,
        "source": {"blend": blend.relative_to(project).as_posix(), "sha256": core.sha(blend)},
        "subjects": {"A": {"objects": ["主体甲"]}, "B": {"objects": ["主体乙"]}},
        "shots": [
            {
                "id": "C1",
                "start_frame": 0,
                "end_frame": 4,
                "camera": "机位甲",
                "camera_motion": "fixed",
                "subjects": ["A", "B"],
            },
            {
                "id": "C2",
                "start_frame": 4,
                "end_frame": 8,
                "camera": "机位乙",
                "camera_motion": "fixed",
                "subjects": ["A", "B"],
            },
        ],
    }
    path = project / "03-制作/制作计划/白模计划.yaml"
    path.parent.mkdir(parents=True)
    return project, blend, path, plan


def save(work):
    _, _, path, data = work
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return core.load_plan(path)


@pytest.mark.parametrize(
    "change",
    [
        "gap",
        "overlap",
        "duplicate",
        "bool_frame",
        "missing_subject",
        "wrong_hash",
        "missing_camera",
        "unknown_field",
    ],
)
def test_plan_rejects_broken_inputs_before_outputs(work, change):
    project, _, _, data = work
    if change == "gap":
        data["shots"][1]["start_frame"] = 5
    elif change == "overlap":
        data["shots"][1]["start_frame"] = 3
    elif change == "duplicate":
        data["shots"][1]["id"] = "C1"
    elif change == "bool_frame":
        data["frame_count"] = True
    elif change == "missing_subject":
        data["shots"][0]["subjects"] = ["missing"]
    elif change == "wrong_hash":
        data["source"]["sha256"] = "0" * 64
    elif change == "missing_camera":
        data["shots"][0]["camera"] = ""
    else:
        data["freame_count"] = 8
    with pytest.raises(ValueError):
        save(work)
    assert not (project / "04-输出").exists()


def test_source_cannot_escape_or_belong_to_another_project(work, tmp_path):
    other = tmp_path / "别的作品"
    other.mkdir()
    (other / "source.blend").write_bytes(b"scene")
    work[3]["source"] = {
        "blend": str(other / "source.blend"),
        "sha256": core.sha(other / "source.blend"),
    }
    with pytest.raises(ValueError, match="当前作品"):
        save(work)


def test_version_occupied_preserves_everything(work):
    context = save(work)
    paths = core.new_run(context, "01", render=True)
    sentinel = paths["output"] / "原文件.mp4"
    sentinel.write_bytes(b"preserve")
    with pytest.raises(FileExistsError):
        core.new_run(context, "01", render=True)
    assert sentinel.read_bytes() == b"preserve"
    with pytest.raises(ValueError):
        core.new_run(context, "../越界")


def test_cut_match_never_reuses_one_detection_or_hides_nearby_extra():
    missing = core.match_cuts([1.0, 1.2], [1.1], 0.15)
    assert len(missing["matches"]) == 1 and len(missing["missing"]) == 1
    extra = core.match_cuts([1.0], [1.0, 1.28], 0.15)
    assert extra["extra"] == [1.28]
    assert core.match_cuts([1.0, 1.2], [1.05, 1.21], 0.15)["missing"] == []


def test_cut_match_finds_maximum_monotone_assignment():
    result = core.match_cuts([1.0, 1.15], [0.87, 1.02], 0.15)
    assert len(result["matches"]) == 2
    assert not result["missing"] and not result["extra"]


def test_failed_decode_is_not_a_single_shot_success(work, monkeypatch):
    context = save(work)
    movie = work[0] / "坏视频.mp4"
    movie.write_bytes(b"not video")

    def fail(_):
        raise ValueError("解码失败")

    monkeypatch.setattr(core, "decode_check", fail)
    with pytest.raises(ValueError, match="解码失败"):
        core.verify_cuts(context, movie)


def test_changed_input_invalidates_evidence(work):
    context = save(work)
    work[1].write_bytes(b"different scene")
    with pytest.raises(ValueError, match="旧检查失效"):
        core.check_evidence(context["dependencies"])


def test_current_review_rejects_changed_plan_dependency(work, monkeypatch):
    context = save(work)
    spec = importlib.util.spec_from_file_location("whitebox_review_test", TOOLS / "审片.py")
    review = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(review)
    work[2].write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="已变化"):
        review.prepare(work[0], [], dependencies=context["dependencies"])


@pytest.mark.skipif(
    not Path(r"D:\blender-5.3.0\blender.exe").exists() or not shutil.which("ffmpeg"),
    reason="本机Blender/FFmpeg未安装",
)
def test_real_blender_two_pass_render_and_fresh_reload(work):
    project, blend, path, plan = work
    blender = Path(r"D:\blender-5.3.0\blender.exe")
    subprocess.run(
        [
            str(blender),
            "--background",
            "--factory-startup",
            "--python-exit-code",
            "1",
            "--python",
            str(ROOT / "tests/fixtures/whitebox_scene.py"),
            "--",
            str(blend),
        ],
        check=True,
        capture_output=True,
    )
    plan["source"]["sha256"] = core.sha(blend)
    plan["preview_scale"] = 50
    context = save(work)
    original = blend.read_bytes()
    paths = core.new_run(context, "验证", render=True)
    bundle_path, bundle = core.execute_blender(context, paths, blender, render=True)
    assert bundle["status"] == "checks_passed"
    report = json.loads((paths["evidence"] / "场景检查.json").read_text("utf-8"))
    assert report["sampled_frames"] == 8
    assert report["samples"][3]["camera"] == "机位甲"
    assert report["samples"][4]["camera"] == "机位乙"
    assert len([a for a in bundle["artifacts"] if a["path"].endswith(".mp4")]) == 2
    assert blend.read_bytes() == original
    assert core.validate_bundle(context, bundle_path)["user_acceptance"] == "pending"
    plan["notes"] = "changed after review"
    fresh = save(work)
    with pytest.raises(ValueError, match="当前计划"):
        core.validate_bundle(fresh, bundle_path)


@pytest.mark.skipif(not Path(r"D:\blender-5.3.0\blender.exe").exists(), reason="本机Blender未安装")
def test_real_blender_geometry_probes(tmp_path):
    result = subprocess.run(
        [
            r"D:\blender-5.3.0\blender.exe",
            "--background",
            "--factory-startup",
            "--python-exit-code",
            "1",
            "--python",
            str(ROOT / "tests/fixtures/whitebox_probe.py"),
            "--",
            str(tmp_path / "重载验证.blend"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"curve_sampled": true' in result.stdout


@pytest.mark.parametrize("offset", [0, 5])
def test_real_cut_detection_uses_video_pts_and_preserves_nearby_cuts(work, offset):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg未安装")
    project, _, _, plan = work
    plan["frame_count"] = 48
    plan["shots"][0]["end_frame"] = 24
    plan["shots"][1].update(start_frame=24, end_frame=48)
    context = save(work)
    movie = project / "测试切镜.mkv"
    core.run(
        [
            core.executable("ffmpeg"),
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=black:s=64x64:r=24:d=1",
            "-f",
            "lavfi",
            "-i",
            "color=white:s=64x64:r=24:d=1",
            "-filter_complex",
            f"[0:v][1:v]concat=n=2:v=1:a=0,setpts=PTS+{offset}/TB[v]",
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            movie,
        ]
    )
    report = core.verify_cuts(context, movie)
    assert report["status"] == "detected_match"
    assert report["detected"] == [1.0]
    assert report["visual_review"] == "pending"


def test_real_cut_detection_and_pts_use_the_same_video_stream(work):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg未安装")
    project, _, _, plan = work
    plan["frame_count"] = 48
    plan["shots"][0]["end_frame"] = 24
    plan["shots"][1].update(start_frame=24, end_frame=48)
    context = save(work)
    movie = project / "不同切点的双视频轨.mkv"
    core.run(
        [
            core.executable("ffmpeg"), "-v", "error",
            "-f", "lavfi", "-i", "color=black:s=64x64:r=24:d=2",
            "-f", "lavfi", "-i", "color=black:s=96x96:r=24:d=1",
            "-f", "lavfi", "-i", "color=white:s=96x96:r=24:d=1",
            "-filter_complex", "[1:v][2:v]concat=n=2:v=1:a=0[cut]",
            "-map", "0:v", "-map", "[cut]", "-c:v", "libx264",
            "-disposition:v:0", "0", "-disposition:v:1", "0", movie,
        ]
    )
    report = core.verify_cuts(context, movie)
    assert report["video_stream_index"] == core.probe(movie)["video"]["index"] == 0
    assert report["duration_matches"]
    assert report["status"] == "mismatch"
    assert report["detected"] == [] and report["missing"] == [1.0]


def test_review_http_rejects_stale_dependencies_and_separates_new_records(work, monkeypatch):
    context = save(work)
    spec = importlib.util.spec_from_file_location("whitebox_review_http", TOOLS / "审片.py")
    review = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(review)
    movie = work[0] / "视频.mp4"
    movie.write_bytes(b"HTTP test fixture")
    monkeypatch.setattr(
        review, "probe", lambda _: {"duration": 1, "video": {"avg_frame_rate": "24/1"}}
    )
    monkeypatch.setattr(review, "decode_check", lambda _: None)
    config = review.prepare(work[0], [movie], dependencies=context["dependencies"])
    previous = json.loads(config.read_text("utf-8"))["records"]
    httpd = review.server(config, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = httpd.review_url.replace("/?token=", "/api/session?token=")
        with httpx.Client(trust_env=False) as client:
            assert client.get(endpoint).status_code == 200
            work[3]["notes"] = "updated"
            fresh = save(work)
            response = client.get(endpoint)
            assert response.status_code == 409
            assert "失效" in response.json()["error"]
        new = review.prepare(work[0], [movie], dependencies=fresh["dependencies"])
        assert json.loads(new.read_text("utf-8"))["records"] != previous
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def regression_scene(work, case):
    blender = Path(r"D:\blender-5.3.0\blender.exe")
    if not blender.is_file():
        pytest.skip("本机Blender未安装")
    result = subprocess.run(
        [
            str(blender),
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--python-exit-code",
            "1",
            "--python",
            str(ROOT / "tests/fixtures/whitebox_regression.py"),
            "--",
            str(work[1]),
            case,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    work[3]["source"]["sha256"] = core.sha(work[1])
    work[3]["preview_scale"] = 50
    return blender, save(work)


@pytest.mark.parametrize(
    "case",
    [
        "viewport_object",
        "viewport_eye",
        "viewport_collection",
        "viewport_layer",
        "external",
        "cache",
        "nodes",
    ],
)
def test_real_blender_rejects_unreliable_evaluation_and_dependencies(work, case):
    blender, context = regression_scene(work, case)
    paths = core.new_run(context, "反例")
    with pytest.raises(ValueError, match="Blender检查/渲染失败"):
        core.execute_blender(context, paths, blender)
    log = (paths["work"] / "Blender执行日志.txt").read_text("utf-8", errors="replace")
    expected = (
        ("视口禁用",)
        if case.startswith("viewport_")
        else (("未打包外部文件",) if case == "external" else ("未打包外部文件", "暂不支持"))
    )
    assert any(message in log for message in expected)
    assert not (paths["evidence"] / "白模检查包.json").exists()


@pytest.mark.parametrize(
    "case",
    [
        "render_layer_mismatch", "multiple_render_layers", "layer_exclude", "layer_holdout",
        "layer_indirect", "object_holdout", "object_shadow_catcher",
    ],
)
def test_real_blender_rejects_unproven_render_layer_visibility(work, case):
    blender, context = regression_scene(work, case)
    paths = core.new_run(context, "图层反例", render=True)
    with pytest.raises(ValueError, match="Blender检查/渲染失败"):
        core.execute_blender(context, paths, blender, render=True)
    log = (paths["work"] / "Blender执行日志.txt").read_text("utf-8", errors="replace")
    assert any(text in log for text in ("唯一启用渲染图层", "Exclude", "Holdout"))
    assert not (paths["evidence"] / "白模检查包.json").exists()
    assert not list(paths["output"].glob("*.mp4"))


@pytest.mark.parametrize(
    "case,kind", [("clip_near", "cropped"), ("clip_far", "cropped"), ("sensor", "camera_motion")]
)
def test_real_blender_checks_actual_camera_volume_and_projection(work, case, kind):
    blender, _ = regression_scene(work, case)
    for shot in work[3]["shots"]:
        shot["framing"] = {"A": {"inside": True}, "B": {"inside": True}}
    context = save(work)
    paths = core.new_run(context, "反例", render=True)
    _, bundle = core.execute_blender(context, paths, blender, render=True)
    report = json.loads((paths["evidence"] / "场景检查.json").read_text("utf-8"))
    assert bundle["status"] == "checks_failed"
    assert any(failure["kind"] == kind for failure in report["failures"])
    assert not list(paths["output"].glob("*.mp4"))


def test_real_blender_packed_displacement_is_bound_to_blend(work):
    blender, context = regression_scene(work, "packed")
    work[1].with_suffix(".png").unlink()  # Saved packed bytes are sufficient.
    paths = core.new_run(context, "打包")
    _, bundle = core.execute_blender(context, paths, blender)
    assert bundle["status"] == "checks_passed"


@pytest.mark.parametrize("case", ["keyframe", "nla", "driver"])
@pytest.mark.skipif(not Path(r"D:\blender-5.3.0\blender.exe").exists(), reason="本机Blender未安装")
def test_real_blender_blur_overrides_survive_frame_and_render_evaluation(tmp_path, case):
    result = subprocess.run(
        [
            r"D:\blender-5.3.0\blender.exe", "--background", "--factory-startup",
            "--disable-autoexec", "--python-exit-code", "1", "--python",
            str(ROOT / "tests/fixtures/whitebox_blur.py"), "--", str(tmp_path / "测试.blend"),
            case,
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ANIMATED_BLUR_DISABLED_OK=" in result.stdout


def test_real_blender_blur_dependency_cannot_change_camera_or_fall_back(work):
    blender, context = regression_scene(work, "blur_camera_dependency")
    before = work[1].read_bytes()
    paths = core.new_run(context, "模糊依赖拒绝", render=True)
    with pytest.raises(ValueError, match="Blender检查/渲染失败"):
        core.execute_blender(context, paths, blender, render=True)
    log = (paths["work"] / "Blender执行日志.txt").read_text("utf-8", errors="replace")
    assert "改变了实际几何或相机" in log
    assert not list(paths["output"].glob("*.mp4"))
    assert not list(paths["work"].rglob("*.png"))
    assert not (paths["evidence"] / "白模检查包.json").exists()
    assert work[1].read_bytes() == before


def test_real_blender_model_grays_replace_layer_material_override(work):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg未安装")
    blender, _ = regression_scene(work, "material_override")
    grays = {"A": 0.15, "B": 0.55}
    for sid, gray in grays.items():
        work[3]["subjects"][sid]["model_gray"] = gray
    context = save(work)
    original = work[1].read_bytes()
    paths = core.new_run(context, "图层材质覆盖", render=True)
    bundle_path, bundle = core.execute_blender(context, paths, blender, render=True)
    assert bundle["status"] == "checks_passed"
    assert len([a for a in bundle["artifacts"] if a["path"].endswith(".mp4")]) == 2
    report = json.loads((paths["evidence"] / "场景检查.json").read_text("utf-8"))
    assert report["sampled_frames"] == 8
    width, height = 160, 90
    for sample in report["samples"]:
        frame = paths["work"] / "送模版" / f"帧-{sample['frame']:06d}.png"
        pixels = subprocess.run(
            [core.executable("ffmpeg"), "-v", "error", "-i", str(frame),
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            check=True, capture_output=True,
        ).stdout
        assert len(pixels) == width * height * 3
        assert all(
            max(pixels[index:index + 3]) - min(pixels[index:index + 3]) <= 1
            for index in range(0, len(pixels), 3)
        ), "The source layer material override leaked into the model pass"
        for sid, gray in grays.items():
            x0, y0, x1, y1 = sample["subjects"][sid]["bounds"]
            x = int((x0 + x1) / 2 * width)
            y = height - 1 - int((y0 + y1) / 2 * height)
            rgb = pixels[(y * width + x) * 3:(y * width + x) * 3 + 3]
            expected = round((1.055 * gray ** (1 / 2.4) - 0.055) * 255)
            assert all(abs(value - expected) <= 2 for value in rgb), (sid, sample, rgb)
    assert work[1].read_bytes() == original
    assert core.validate_bundle(context, bundle_path)["user_acceptance"] == "pending"


def test_real_blender_export_preserves_non_square_pixel_display_aspect(work):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg未安装")
    blender, context = regression_scene(work, "sar")
    paths = core.new_run(context, "非方形像素", render=True)
    _, bundle = core.execute_blender(context, paths, blender, render=True)
    assert bundle["status"] == "checks_passed"
    for artifact in bundle["artifacts"]:
        if artifact["path"].endswith(".mp4"):
            stream = core.probe(artifact["path"])["video"]
            assert (stream["width"], stream["height"]) == (64, 64)
            assert stream["sample_aspect_ratio"] == "2:1"
            assert stream["display_aspect_ratio"] == "2:1"


@pytest.mark.parametrize("case", ["legacy", "legacy_clip"])
def test_real_legacy_inspection_preserves_live_changes_and_reads_disk(work, case):
    regression_scene(work, case)


def test_real_blender_rejects_later_visible_text_before_dual_export(work):
    blender, context = regression_scene(work, "animated_font")
    inspect_paths = core.new_run(context, "文字几何")
    _, bundle = core.execute_blender(context, inspect_paths, blender)
    assert bundle["status"] == "checks_passed"  # Inspection does not promise a clean export.
    paths = core.new_run(context, "文字导出", render=True)
    with pytest.raises(ValueError, match="Blender检查/渲染失败"):
        core.execute_blender(context, paths, blender, render=True)
    log = (paths["work"] / "Blender执行日志.txt").read_text("utf-8", errors="replace")
    assert "第3帧含可见文字对象" in log
    assert not list(paths["output"].glob("*.mp4"))
    assert not (paths["evidence"] / "白模检查包.json").exists()


@pytest.mark.skipif(not Path(r"D:\blender-5.3.0\blender.exe").exists(), reason="本机Blender未安装")
def test_real_animated_curve_bounds_use_evaluated_geometry():
    result = subprocess.run(
        [
            r"D:\blender-5.3.0\blender.exe",
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--python-exit-code",
            "1",
            "--python",
            str(ROOT / "tests/fixtures/whitebox_curve_bounds.py"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ANIMATED_CURVE_BOUNDS_OK" in result.stdout


@pytest.mark.parametrize(
    "case", ["display_static", "display_keyframes", "display_nla", "display_driver",
             "display_output_override"],
)
def test_real_blender_display_contract_matches_clean_pixels_throughout(work, case):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg未安装")
    # Render an independent clean source with identical geometry and camera
    # animation. Compare real output pixels, so gray stamps also fail this test.
    project = work[0].parent / "中性对照"
    project.mkdir()
    (project / "project.yaml").write_text("name: 中性对照\n", encoding="utf-8")
    blend = project / work[1].relative_to(work[0])
    path = project / work[2].relative_to(work[0])
    path.parent.mkdir(parents=True)
    baseline = (project, blend, path, json.loads(json.dumps(work[3])))
    outputs = []
    reports = []
    for dataset, source_case in ((baseline, "display_clean"), (work, case)):
        blender, _ = regression_scene(dataset, source_case)
        for sid, gray in (("A", 0.15), ("B", 0.55)):
            dataset[3]["subjects"][sid]["model_gray"] = gray
        for shot in dataset[3]["shots"]:
            shot["camera_motion"] = "moving"
        context = save(dataset)
        source_bytes = dataset[1].read_bytes()
        paths = core.new_run(context, "显示合同", render=True)
        bundle_path, bundle = core.execute_blender(context, paths, blender, render=True)
        assert bundle["status"] == "checks_passed"
        assert dataset[1].read_bytes() == source_bytes
        assert core.validate_bundle(context, bundle_path)["user_acceptance"] == "pending"
        outputs.append(paths["work"])
        reports.append(json.loads((paths["evidence"] / "场景检查.json").read_text("utf-8")))
    assert reports[0]["geometry_camera_sha256"] == reports[1]["geometry_camera_sha256"]
    for name in ("审片版", "送模版"):
        for frame in range(8):
            pixels = []
            for folder in outputs:
                image = folder / name / f"帧-{frame:06d}.png"
                raw = subprocess.run(
                    [core.executable("ffmpeg"), "-v", "error", "-i", str(image),
                     "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                    check=True, capture_output=True,
                ).stdout
                assert len(raw) == 160 * 90 * 3
                pixels.append(raw)
            assert pixels[0] == pixels[1], (case, name, frame)


def test_real_blender_display_dependency_rejects_geometry_changes(work):
    blender, context = regression_scene(work, "display_camera_dependency")
    source_bytes = work[1].read_bytes()
    paths = core.new_run(context, "显示依赖拒绝", render=True)
    with pytest.raises(ValueError, match="Blender检查/渲染失败"):
        core.execute_blender(context, paths, blender, render=True)
    log = (paths["work"] / "Blender执行日志.txt").read_text("utf-8", errors="replace")
    assert "改变了实际几何或相机" in log
    assert work[1].read_bytes() == source_bytes
    assert not list(paths["work"].rglob("*.png"))
    assert not (paths["evidence"] / "白模检查包.json").exists()


def test_real_blender_render_time_display_change_is_never_published(work):
    regression_scene(work, "display_guard")
    assert not work[1].with_name("不得发布.png").exists()
