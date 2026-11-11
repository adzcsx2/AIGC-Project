import hashlib
import json

import pytest
import yaml

from autodl_video.cli import main
from autodl_video.errors import AutoDLError
from autodl_video.materials import assert_shot_ready, check_materials
from autodl_video.runner import VideoProject


@pytest.fixture
def materials(project):
    folder = project / "episode"
    folder.mkdir()
    for name in ("brief", "style", "script", "storyboard"):
        (folder / f"{name}.md").write_text("已确认的内容", encoding="utf-8")
    for name in ("character", "scene"):
        (folder / f"{name}.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    return folder / "materials.yaml", {
        "schema_version": 1,
        "documents": {
            name: {"path": f"{name}.md", "state": "ready"}
            for name in ("brief", "style", "script", "storyboard")
        },
        "assets": {
            "CHAR-01": {"kind": "character", "path": "character.png", "state": "ready"},
            "SCENE-01": {"kind": "scene", "path": "scene.png", "state": "ready"},
        },
        "shots": {
            "SHOT-01": {
                "required_assets": ["CHAR-01", "SCENE-01"],
                "reference_bindings": {"ref_image_0": "CHAR-01", "ref_image_1": "SCENE-01"},
            }
        },
    }


def save(materials):
    path, data = materials
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_ready_and_cli(materials, project, capsys):
    path = save(materials)
    assert check_materials(path)["ready"]
    assert main(["--project", str(project), "materials", "check", str(path)]) == 0
    assert '"ready": true' in capsys.readouterr().out


def test_materials_check_resolves_migrated_manifest_entry(materials, project, capsys):
    path = save(materials)
    registry = project / ".autodl/path-map.json"
    registry.parent.mkdir()
    registry.write_text(
        json.dumps({"files": {"assets/materials.yaml": path.relative_to(project).as_posix()}}),
        encoding="utf-8",
    )
    legacy = project / "assets/materials.yaml"
    report = check_materials(legacy, root=project)
    assert report["ready"]
    assert report["manifest"] == str(path.resolve())
    assert main(["--project", str(project), "materials", "check", str(legacy)]) == 0
    assert json.loads(capsys.readouterr().out)["ready"]
    assert not legacy.exists()
    # The Python default discovers the same map in an ordinary checkout.
    (project / "pyproject.toml").write_text('name = "autodl-aigc"', encoding="utf-8")
    assert check_materials(legacy)["ready"]


def test_config_cannot_borrow_other_work_manifest_with_same_work_images(
    materials, project, monkeypatch
):
    path, data = materials
    (path.parent / "project.yaml").write_text("name: Manifest owner\n", encoding="utf-8")
    work = project / "current-work"
    work.mkdir()
    (work / "project.yaml").write_text("name: Current work\n", encoding="utf-8")
    for asset in data["assets"].values():
        image = work / asset["path"]
        image.write_bytes((path.parent / asset["path"]).read_bytes())
        asset["path"] = str(image)
    save(materials)
    rules = {field: {"type": "image"} for field in data["shots"]["SHOT-01"]["reference_bindings"]}
    catalog_path = project / "catalog/workflows.yaml"
    catalog_path.write_text(yaml.safe_dump({
        "schema_version": 1, "workflows": {"demo": {"input_rules": rules}},
    }), encoding="utf-8")
    config = work / "shot.yaml"
    config.write_text(yaml.safe_dump({
        "workflow_id": "demo", "materials_manifest": str(path), "shot_id": "SHOT-01",
        "inputs": {field: data["assets"][asset]["path"]
                   for field, asset in data["shots"]["SHOT-01"]["reference_bindings"].items()},
    }), encoding="utf-8")

    def forbidden(*args, **kwargs):
        pytest.fail("Manifest ownership must fail before network")

    monkeypatch.setattr("autodl_video.runner.AutoDLClient", forbidden)
    with pytest.raises(AutoDLError, match="不同作品"):
        VideoProject(project).generate(config)


@pytest.mark.parametrize("state", ["missing", "provided", None])
def test_existing_unreviewed_image_is_not_ready(materials, state):
    materials[1]["assets"]["CHAR-01"]["state"] = state
    report = check_materials(save(materials))
    assert not report["ready"]
    assert report["missing_assets"][0]["id"] == "CHAR-01"


def test_prompt_is_not_an_image_and_cli_missing(materials, project, capsys):
    path, data = materials
    (path.parent / "prompt.md").write_text("a cinematic portrait", encoding="utf-8")
    data["assets"]["CHAR-01"]["path"] = "prompt.md"
    data["assets"]["CHAR-01"]["prompt"] = "a cinematic portrait"
    save(materials)
    assert main(["--project", str(project), "materials", "check", str(path)]) == 1
    assert "a cinematic portrait" in capsys.readouterr().out


@pytest.mark.parametrize("path_value", [None, "", "https://example.com/person.png", "absent.png"])
def test_missing_or_remote_image_blocks(materials, path_value):
    materials[1]["assets"]["CHAR-01"]["path"] = path_value
    assert not check_materials(save(materials))["ready"]


def test_unknown_asset_and_other_shot_dependency_block(materials):
    materials[1]["shots"]["SHOT-02"] = {
        "required_assets": ["MISSING"],
        "reference_bindings": {"ref_image_0": "MISSING"},
    }
    report = check_materials(save(materials), "SHOT-01")
    assert not report["ready"]
    assert "MISSING" in report["issues"][0]


def test_optional_assets_only_block_when_used(materials):
    materials[1]["assets"]["PROP-01"] = {"kind": "prop", "required": False}
    assert check_materials(save(materials))["ready"]
    materials[1]["shots"]["SHOT-01"]["required_assets"].append("PROP-01")
    assert not check_materials(save(materials))["ready"]


def test_missing_document_blocks(materials):
    del materials[1]["documents"]["script"]
    report = check_materials(save(materials))
    assert not report["ready"]
    assert "document:script" in report["issues"][0]


@pytest.mark.parametrize("invalid", ["yes", 1, [], None])
def test_required_flag_is_strict(materials, invalid):
    materials[1]["assets"]["CHAR-01"]["required"] = invalid
    with pytest.raises(AutoDLError, match="boolean"):
        check_materials(save(materials))


@pytest.mark.parametrize("section", ["documents", "assets", "shots"])
def test_bad_structure_is_readable_error(materials, section):
    materials[1][section] = []
    with pytest.raises(AutoDLError, match=section):
        check_materials(save(materials))


def test_unknown_shot(materials):
    with pytest.raises(AutoDLError, match="Unknown shot_id"):
        check_materials(save(materials), "absent")


def test_bindings_check_identity_and_every_media_input(materials):
    path = save(materials)
    rules = {"ref_image_0": {"type": "image"}, "ref_image_1": {"type": "image"}}
    inputs = {"ref_image_0": "character.png", "ref_image_1": "scene.png"}
    assert_shot_ready(path, "SHOT-01", inputs, rules, path.parent)
    inputs["ref_image_0"] = "scene.png"
    with pytest.raises(AutoDLError, match="登记路径"):
        assert_shot_ready(path, "SHOT-01", inputs, rules, path.parent)
    inputs.pop("ref_image_1")
    with pytest.raises(AutoDLError, match="全部媒体"):
        assert_shot_ready(path, "SHOT-01", inputs, rules, path.parent)


def test_retargeting_binds_character_and_video(materials):
    path, data = materials
    (path.parent / "reference.mp4").write_bytes(b"test video fixture")
    data["assets"]["VIDEO-01"] = {"kind": "video", "path": "reference.mp4", "state": "ready"}
    shot = data["shots"]["SHOT-01"]
    shot["required_assets"].append("VIDEO-01")
    shot["reference_bindings"] = {"ref_image": "CHAR-01", "ref_video": "VIDEO-01"}
    save(materials)
    rules = {"ref_image": {"type": "image"}, "ref_video": {"type": "video"}}
    inputs = {"ref_image": "character.png", "ref_video": "reference.mp4"}
    assert_shot_ready(path, "SHOT-01", inputs, rules, path.parent)
    # A video field must not silently receive a character-image binding.
    shot["reference_bindings"]["ref_video"] = "CHAR-01"
    save(materials)
    with pytest.raises(AutoDLError, match="素材类型"):
        assert_shot_ready(path, "SHOT-01", inputs, rules, path.parent)


def test_gate_blocks_before_network_or_credentials(materials, config, project, monkeypatch):
    path, data = materials
    data["assets"]["CHAR-01"]["state"] = "missing"
    save(materials)
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    cfg.update(materials_manifest="episode/materials.yaml", shot_id="SHOT-01")
    config.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    def forbidden(*args, **kwargs):
        pytest.fail("Materials gate must run before network and credentials")

    monkeypatch.setattr("autodl_video.runner.AutoDLClient", forbidden)
    monkeypatch.setattr("autodl_video.runner.load_token", forbidden)
    for dry_run in (True, False):
        with pytest.raises(AutoDLError, match="素材未齐备"):
            VideoProject(project).generate(config, dry_run=dry_run)


@pytest.mark.parametrize("schema_version", [1, 2])
def test_linked_ready_config_dry_run(materials, config, project, schema_version):
    if schema_version == 2:
        confirm_script(materials)
    save(materials)
    catalog_path = project / "catalog/workflows.yaml"
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    rules = catalog["workflows"]["demo"]["input_rules"]
    rules.update(ref_image_0={"type": "image"}, ref_image_1={"type": "image"})
    catalog_path.write_text(yaml.safe_dump(catalog), encoding="utf-8")
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    cfg.update(materials_manifest="episode/materials.yaml", shot_id="SHOT-01")
    cfg["inputs"].update(ref_image_0="episode/character.png", ref_image_1="episode/scene.png")
    config.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    assert VideoProject(project).generate(config, dry_run=True)["dry_run"]


@pytest.mark.parametrize("field", ["materials_manifest", "shot_id"])
def test_manifest_and_shot_are_paired(config, project, field):
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    cfg[field] = "example"
    config.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    with pytest.raises(AutoDLError, match="together"):
        VideoProject(project).generate(config, dry_run=True)


def confirm_script(materials):
    path, data = materials
    data["schema_version"] = 2
    data["creative_confirmation"] = {
        "state": "confirmed",
        "script_sha256": hashlib.sha256((path.parent / "script.md").read_bytes()).hexdigest(),
        "confirmation_ref": "用户已确认此版补全文案，聊天记录 2026-11-09/动作草案v1",
    }


def test_confirmed_script_revision_is_ready_but_edit_invalidates_it(materials):
    confirm_script(materials)
    path = save(materials)
    assert check_materials(path)["ready"]
    (path.parent / "script.md").write_text("新增反击与结局，尚待确认", encoding="utf-8")
    report = check_materials(path)
    assert not report["ready"]
    assert any("已变化" in issue for issue in report["issues"])


@pytest.mark.parametrize("receipt", [None, {}, "confirmed", {"state": "pending"}])
def test_new_manifest_requires_real_confirmation_metadata(materials, receipt):
    materials[1].update(schema_version=2, creative_confirmation=receipt)
    report = check_materials(save(materials))
    assert not report["ready"]
    assert any("文案确认" in issue for issue in report["issues"])


@pytest.mark.parametrize("field", ["script_sha256", "confirmation_ref"])
def test_confirmation_needs_revision_and_user_record(materials, field):
    confirm_script(materials)
    materials[1]["creative_confirmation"][field] = ""
    assert not check_materials(save(materials))["ready"]


@pytest.mark.parametrize("dry_run", [True, False])
def test_unconfirmed_draft_blocks_before_network(materials, config, project, monkeypatch, dry_run):
    materials[1]["schema_version"] = 2
    save(materials)
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    cfg.update(materials_manifest="episode/materials.yaml", shot_id="SHOT-01")
    config.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    def forbidden(*args, **kwargs):
        pytest.fail("Unconfirmed draft must not access credentials or network")

    monkeypatch.setattr("autodl_video.runner.AutoDLClient", forbidden)
    monkeypatch.setattr("autodl_video.runner.load_token", forbidden)
    with pytest.raises(AutoDLError, match="文案确认"):
        VideoProject(project).generate(config, dry_run=dry_run)


def test_v2_confirmation_does_not_replace_visual_readiness(materials):
    confirm_script(materials)
    materials[1]["assets"]["CHAR-01"]["state"] = "provided"
    assert not check_materials(save(materials))["ready"]


@pytest.mark.parametrize("dry_run", [True, False])
def test_confirmed_script_cannot_belong_to_another_work(
    materials, project, monkeypatch, capsys, dry_run
):
    path, data = materials
    (path.parent / "project.yaml").write_text("name: 当前作品\n", encoding="utf-8")
    other = project / "另一作品"
    other.mkdir()
    (other / "project.yaml").write_text("name: 另一作品\n", encoding="utf-8")
    foreign_script = other / "剧本.md"
    foreign_script.write_bytes((path.parent / "script.md").read_bytes())
    confirm_script(materials)
    data["documents"]["script"]["path"] = str(foreign_script)
    data["creative_confirmation"]["confirmation_ref"] = "另一作品的剧本确认"
    save(materials)
    config = path.parent / "镜头.yaml"
    config.write_text(yaml.safe_dump({
        "workflow_id": "demo", "materials_manifest": "materials.yaml", "shot_id": "SHOT-01",
        "inputs": {"prompt": "A quiet scene."},
    }), encoding="utf-8")

    def forbidden(*args, **kwargs):
        pytest.fail("Foreign script confirmation must fail before network or credentials")

    monkeypatch.setattr("autodl_video.runner.AutoDLClient", forbidden)
    monkeypatch.setattr("autodl_video.runner.load_token", forbidden)
    with pytest.raises(AutoDLError, match="已确认剧本必须归档到本作品"):
        VideoProject(project).generate(config, dry_run=dry_run)
    assert main(["--project", str(project), "materials", "check", str(path)]) == 1
    assert "已确认剧本必须归档到本作品" in capsys.readouterr().out
    assert not (project / ".autodl").exists()


def test_owned_script_allows_explicit_shared_style_and_new_local_confirmation(materials, project):
    path, data = materials
    (path.parent / "project.yaml").write_text("name: 当前作品\n", encoding="utf-8")
    common_style = project / "公共风格规范.md"
    common_style.write_text("公共材质与摄影规范", encoding="utf-8")
    data["documents"]["style"]["path"] = str(common_style)
    confirm_script(materials)
    data["creative_confirmation"]["confirmation_ref"] = "当前作品的本版剧本确认"
    assert check_materials(save(materials))["ready"]


def test_nested_other_work_script_is_not_part_of_parent_work(materials):
    path, data = materials
    (path.parent / "project.yaml").write_text("name: 当前作品\n", encoding="utf-8")
    nested = path.parent / "另一作品"
    nested.mkdir()
    (nested / "project.yaml").write_text("name: 另一作品\n", encoding="utf-8")
    script = nested / "剧本.md"
    script.write_bytes((path.parent / "script.md").read_bytes())
    confirm_script(materials)
    data["documents"]["script"]["path"] = "另一作品/剧本.md"
    assert not check_materials(save(materials))["ready"]
