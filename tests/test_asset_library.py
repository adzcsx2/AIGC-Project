import base64
import copy
import json
import runpy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import yaml

from autodl_video import asset_library as lib
from autodl_video.asset_bindings import (
    BOARD_CHECKS,
    BOARD_LAYOUT,
    capture_payload_pins,
    digest_file,
    shot_identity_issues,
    validate_asset_payload,
    validate_pin,
)
from autodl_video.characters import characters, voice_queue
from autodl_video.client import AutoDLClient
from autodl_video.config import load_yaml
from autodl_video.errors import AutoDLError
from autodl_video.materials import check_materials
from autodl_video.runner import VideoProject


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def register_test_asset(entry, source, spec, *, root):
    spec = copy.deepcopy(spec)
    if spec.get("purpose") == "identity_board":
        digest = digest_file(source)
        evidence = entry.parent / f"05-检查与验收/{digest}-{uuid4().hex}.json"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(
            json.dumps(
                {
                    "image_sha256": digest,
                    "layout": BOARD_LAYOUT,
                    "reviewed_by": "assistant",
                    "verdict": "passed",
                    "checks": dict.fromkeys(BOARD_CHECKS, True),
                }
            ),
            encoding="utf-8",
        )
        spec["board_contract"] = {
            "version": 1,
            "layout": BOARD_LAYOUT,
            "image_sha256": digest,
            "evidence_path": evidence.relative_to(entry.parent).as_posix(),
            "evidence_sha256": digest_file(evidence),
        }
    return lib.register_asset(entry, source, spec, root=root)


@pytest.fixture
def library(tmp_path):
    entry = lib.init_library(tmp_path)
    source = tmp_path / "女孩.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\nboard-1")
    spec = {
        "asset_id": "GIRL-BOARD",
        "revision": "1",
        "label": "女孩灰披风板",
        "category": "character",
        "media_type": "image",
        "purpose": "identity_board",
        "entity_id": "GIRL",
        "variant_id": "cloak",
        "provenance": {"source": "fixture"},
        "tags": ["灰披风"],
    }
    record = register_test_asset(entry, source, spec, root=tmp_path)
    profile = {
        "schema_version": 1,
        "entity_id": "GIRL",
        "revision": "1",
        "category": "character",
        "label": "小女孩",
        "aliases": ["米娅"],
        "attributes": {"appearance": "固定身份", "personality": None},
        "looks": {
            "cloak": {"label": "灰披风", "board": {"asset_id": "GIRL-BOARD", "revision": "1"}}
        },
        "voice_profiles": {},
        "style_reference": {"source": "shared-style"},
    }
    lib.register_entity(entry, profile, root=tmp_path)
    work = tmp_path / "projects/测试作品"
    project = work / "project.yaml"
    save(
        project,
        {
            "schema_version": 1,
            "name": "测试作品",
            "materials_manifest": "materials.yaml",
            "characters": {"LOCAL-GIRL": "01-文档/角色/女孩.yaml"},
            "current": {"issues": ["既有问题"]},
        },
    )
    save(
        work / "01-文档/角色/女孩.yaml",
        {
            "schema_version": 1,
            "character_id": "LOCAL-GIRL",
            "label": "披风女孩",
            "display_name": "米娅",
            "attributes": {"appearance": "旧摘要", "story_capability": "只属于本故事"},
            "speech_usage": "none",
            "voice": None,
            "visual_references": [{"manifest": "materials.yaml", "asset_id": "LOCAL-BOARD"}],
        },
    )
    save(
        work / "materials.yaml",
        {
            "schema_version": 1,
            "documents": {
                key: {"path": key + ".md", "state": "ready"}
                for key in ("brief", "style", "script", "storyboard")
            },
            "assets": {},
            "shots": {
                "S1": {
                    "required_assets": ["LOCAL-BOARD"],
                    "reference_bindings": {"ref_image_0": "LOCAL-BOARD"},
                }
            },
        },
    )
    for key in ("brief", "style", "script", "storyboard"):
        (work / (key + ".md")).write_text("fixture", encoding="utf-8")
    return tmp_path, entry, source, spec, record, profile, project


def import_and_bind(library):
    root, entry, _, _, _, _, project = library
    item = lib.import_asset(entry, "GIRL-BOARD", "1", project, "LOCAL-BOARD", root=root)
    lib.bind_character(entry, "GIRL", "1", project, "LOCAL-GIRL", "cloak", "LOCAL-BOARD", root=root)
    return item


def test_search_import_resolve_and_dependencies(library):
    root, entry, _, _, record, _, project = library
    result = lib.list_assets(entry, root=root, category="character", query="灰披风")
    assert {item["id"] for item in result} == {"GIRL", "GIRL-BOARD"}
    assert all(Path(item["path"]).is_file() for item in result)
    assert {item["type"] for item in lib.list_assets(entry, root=root, query="米娅")} == {
        "entities",
        "assets",
    }
    item = import_and_bind(library)
    assert item["state"] == "provided"  # Registration/import is not acceptance.
    assert Path(project.parent / item["path"]).samefile(entry.parent / record["path"])
    resolved = characters(project, root=root)["LOCAL-GIRL"]
    assert resolved["attributes"]["appearance"] == "固定身份"
    assert resolved["attributes"]["story_capability"] == "只属于本故事"
    assert resolved["display_name"] == "米娅"
    assert not voice_queue(project, root=root)
    assert lib.check_project(project, root=root)["valid"]
    assert lib.usages(root, "GIRL-BOARD")["uses"][0]["shots"] == ["S1"]
    assert lib.usages(root, "GIRL")["uses"][0]["character_id"] == "LOCAL-GIRL"
    assert load_yaml(project)["current"]["issues"] == ["既有问题"]


def test_new_revision_does_not_change_existing_work(library):
    root, entry, _, spec, _, profile, project = library
    import_and_bind(library)
    before = characters(project, root=root)
    source2 = root / "新造型.png"
    source2.write_bytes(b"\x89PNG\r\n\x1a\nboard-2")
    register_test_asset(entry, source2, {**spec, "revision": "2"}, root=root)
    new_profile = copy.deepcopy(profile)
    new_profile["revision"] = "2"
    new_profile["looks"]["cloak"]["board"]["revision"] = "2"
    lib.register_entity(entry, new_profile, root=root)
    assert characters(project, root=root) == before
    assert lib.check_project(project, root=root)["valid"]
    with pytest.raises(AutoDLError, match="已锁定另一版本"):
        lib.import_asset(entry, "GIRL-BOARD", "2", project, "LOCAL-BOARD", root=root)


def test_shared_language_inheritance_and_project_override(library):
    root, entry, _, _, _, profile, project = library
    lib.import_asset(entry, "GIRL-BOARD", "1", project, "LOCAL-BOARD", root=root)
    new = {**profile, "revision": "2", "language": "zh-Hans"}
    lib.register_entity(entry, new, root=root)
    lib.bind_character(
        entry, "GIRL", "2", project, "LOCAL-GIRL", "cloak", "LOCAL-BOARD", root=root
    )
    assert characters(project, root=root)["LOCAL-GIRL"]["language"] == "zh-Hans"
    local = project.parent / "01-文档/角色/女孩.yaml"
    data = load_yaml(local)
    data["language"] = "en-US"
    save(local, data)
    assert characters(project, root=root)["LOCAL-GIRL"]["language"] == "en-US"
    data.pop("language")
    save(local, data)
    assert characters(project, root=root)["LOCAL-GIRL"]["language"] == "zh-Hans"


def test_shared_character_language_default_and_validation(library):
    root, entry, _, _, _, profile, _ = library
    record = lib.register_entity(entry, {**profile, "revision": "2"}, root=root)
    assert load_yaml(entry.parent / record["path"])["language"] == "en"
    with pytest.raises(AutoDLError, match="language"):
        lib.register_entity(entry, {**profile, "revision": "3", "language": []}, root=root)


def test_different_outfit_selection_is_checked(library):
    root, entry, _, spec, _, profile, project = library
    import_and_bind(library)
    source2 = root / "冬装.png"
    source2.write_bytes(b"\x89PNG\r\n\x1a\nwinter")
    register_test_asset(
        entry,
        source2,
        {**spec, "asset_id": "WINTER", "label": "女孩冬装", "variant_id": "winter"},
        root=root,
    )
    new = copy.deepcopy(profile)
    new["revision"] = "2"
    new["looks"]["winter"] = {"board": {"asset_id": "WINTER", "revision": "1"}}
    lib.register_entity(entry, new, root=root)
    with pytest.raises(AutoDLError, match="造型/声音"):
        lib.bind_character(
            entry, "GIRL", "2", project, "LOCAL-GIRL", "winter", "LOCAL-BOARD", root=root
        )
    assert characters(project, root=root)["LOCAL-GIRL"]["library_binding"]["revision"] == "1"


def test_same_label_never_merges_identity(library):
    root, entry, _, spec, _, profile, _ = library
    other = root / "另一个女孩.png"
    other.write_bytes(b"\x89PNG\r\n\x1a\nother")
    register_test_asset(
        entry, other, {**spec, "asset_id": "OTHER-BOARD", "entity_id": "OTHER"}, root=root
    )
    new = copy.deepcopy(profile)
    new["entity_id"] = "OTHER"
    new["looks"]["cloak"]["board"]["asset_id"] = "OTHER-BOARD"
    lib.register_entity(entry, new, root=root)
    _, data = lib.read_library(entry, root=root)
    assert set(data["entities"]) == {"GIRL", "OTHER"}
    assert lib.check_library(entry, root=root)["valid"]


def test_modified_media_fails_readiness_and_payload_check(library):
    root, entry, _, _, _, _, project = library
    item = import_and_bind(library)
    path = project.parent / item["path"]
    data = load_yaml(project.parent / "materials.yaml")
    data["assets"]["LOCAL-BOARD"]["state"] = "ready"
    save(project.parent / "materials.yaml", data)
    assert check_materials(project.parent / "materials.yaml", root=root)["ready"]
    pins = capture_payload_pins(
        {"materials_manifest": "materials.yaml", "shot_id": "S1"}, project.parent, root=root
    )
    original_payload = {
        "ref_image_0": "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()
    }
    validate_asset_payload(original_payload, pins)
    # Replace the local pathname, do not mutate shared hard-link bytes.
    path.unlink()
    path.write_bytes(b"\x89PNG\r\n\x1a\nwrong")
    assert not lib.check_project(project, root=root)["valid"]
    assert not check_materials(project.parent / "materials.yaml", root=root)["ready"]
    assert lib.check_library(entry, root=root)["valid"]
    with pytest.raises(AutoDLError, match="未提交"):
        validate_asset_payload(
            {
                "ref_image_0": "data:image/png;base64,"
                + base64.b64encode(path.read_bytes()).decode()
            },
            pins,
        )


def test_pinned_profile_does_not_require_live_library(library):
    root, entry, _, _, _, _, project = library
    import_and_bind(library)
    entry.rename(entry.with_name("入口暂不可用.yaml"))
    assert characters(project, root=root)["LOCAL-GIRL"]["resolved_look"]
    assert lib.check_project(project, root=root)["valid"]


def test_voice_binding_reuses_real_approval_but_does_not_invent_it(library):
    root, entry, _, _, _, profile, project = library
    import_and_bind(library)
    audio = root / "声音.wav"
    audio.write_bytes(b"RIFF-voice-sample")
    register_test_asset(
        entry,
        audio,
        {
            "asset_id": "VOICE",
            "revision": "1",
            "label": "女孩声音",
            "category": "voice",
            "media_type": "audio",
            "purpose": "character_voice",
            "entity_id": "GIRL",
            "provenance": {"source": "fixture"},
        },
        root=root,
    )
    new = copy.deepcopy(profile)
    new["revision"] = "2"
    new["voice_profiles"]["sweet"] = {"sample": {"asset_id": "VOICE", "revision": "1"}}
    lib.register_entity(entry, new, root=root)
    sample = lib.import_asset(entry, "VOICE", "1", project, "VOICE-LOCAL", root=root)
    char_path = project.parent / "01-文档/角色/女孩.yaml"
    character = load_yaml(char_path)
    character["speech_usage"] = "dialogue"
    character["voice"] = {"status": "audition_pending", "reference_audio": sample["path"]}
    save(char_path, character)
    lib.bind_character(
        entry,
        "GIRL",
        "2",
        project,
        "LOCAL-GIRL",
        "cloak",
        "LOCAL-BOARD",
        voice_profile_id="sweet",
        voice_asset_id="VOICE-LOCAL",
        root=root,
    )
    assert len(voice_queue(project, root=root)) == 1
    character = load_yaml(char_path)
    character["voice"].update(
        status="approved",
        approval={
            "character_id": "LOCAL-GIRL",
            "sample_sha256": digest_file(audio),
            "confirmation_ref": "fixture-confirmation",
        },
    )
    save(char_path, character)
    assert not voice_queue(project, root=root)
    character["voice"]["approval"]["character_id"] = "OTHER"
    save(char_path, character)
    assert voice_queue(project, root=root)
    # A missing voice sample must not block a non-speaking shot's identity.
    (project.parent / sample["path"]).unlink()
    character["speech_usage"] = "none"
    save(char_path, character)
    assert characters(project, root=root)["LOCAL-GIRL"]["resolved_look"]
    assert voice_queue(project, root=root) == []


@pytest.mark.parametrize("same_id", [False, True])
def test_concurrent_registration_preserves_both_or_rejects_duplicate(library, same_id):
    root, entry, source, spec, _, _, _ = library

    def register(item_id):
        return register_test_asset(entry, source, {**spec, "asset_id": item_id}, root=root)

    with ThreadPoolExecutor(2) as pool:
        results = [pool.submit(register, "A"), pool.submit(register, "A" if same_id else "B")]
        successes = 0
        for future in results:
            try:
                future.result(timeout=10)
                successes += 1
            except AutoDLError as exc:
                assert same_id and "已存在" in str(exc)
    assert successes == (1 if same_id else 2)
    _, data = lib.read_library(entry, root=root)
    assert set(data["assets"]) == ({"GIRL-BOARD", "A"} if same_id else {"GIRL-BOARD", "A", "B"})


def test_import_failure_rolls_back_only_new_media_and_retry_works(library, monkeypatch):
    root, entry, _, _, _, _, project = library
    manifest = project.parent / "materials.yaml"
    original = manifest.read_bytes()
    destination = "02-素材/人物/测试导入.png"

    def fail(*_):
        raise PermissionError("synthetic publication failure")

    with monkeypatch.context() as scoped:
        scoped.setattr(lib, "atomic_text", fail)
        with pytest.raises(PermissionError):
            lib.import_asset(
                entry, "GIRL-BOARD", "1", project, "LOCAL-BOARD", root=root, destination=destination
            )
    assert not (project.parent / destination).exists()
    assert manifest.read_bytes() == original
    assert lib.check_library(entry, root=root)["valid"]
    lib.import_asset(
        entry, "GIRL-BOARD", "1", project, "LOCAL-BOARD", root=root, destination=destination
    )


def test_import_never_overwrites_existing_different_bytes(library):
    root, entry, _, _, _, _, project = library
    destination = project.parent / "02-素材/人物/保留.png"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"keep-me")
    with pytest.raises(AutoDLError, match="已存在"):
        lib.import_asset(
            entry,
            "GIRL-BOARD",
            "1",
            project,
            "LOCAL-BOARD",
            root=root,
            destination=str(destination),
        )
    assert destination.read_bytes() == b"keep-me"


@pytest.mark.parametrize("destination", ["../外部.png", "../另一作品/图片.png", "project.yaml"])
def test_import_rejects_paths_outside_asset_directory(library, destination):
    root, entry, _, _, _, _, project = library
    with pytest.raises(AutoDLError):
        lib.import_asset(
            entry, "GIRL-BOARD", "1", project, "LOCAL-BOARD", root=root, destination=destination
        )


def test_legacy_character_and_material_remain_readable(library):
    root, _, source, _, _, _, project = library
    assert characters(project, root=root)["LOCAL-GIRL"]["attributes"]["appearance"] == "旧摘要"
    validate_pin({"kind": "character"}, source)


def test_cli_lists_real_paths_and_reports_failed_check(library, capsys):
    root, _, _, _, _, _, project = library
    main = runpy.run_path(str(Path(__file__).parents[1] / "tools/资产.py"))["main"]
    assert main(["--root", str(root), "list", "--query", "灰披风"]) == 0
    assert Path(json.loads(capsys.readouterr().out)[0]["path"]).is_file()
    item = import_and_bind(library)
    (project.parent / item["path"]).unlink()
    assert main(["--root", str(root), "check", "--project", str(project)]) == 1
    assert json.loads(capsys.readouterr().out)["valid"] is False


def test_shot_outfit_must_match_the_actual_identity_slot(library):
    root, entry, _, spec, _, profile, project = library
    import_and_bind(library)
    source2 = root / "冬装.png"
    source2.write_bytes(b"\x89PNG\r\n\x1a\nwinter")
    register_test_asset(
        entry,
        source2,
        {**spec, "asset_id": "WINTER", "label": "女孩冬装", "variant_id": "winter"},
        root=root,
    )
    new = copy.deepcopy(profile)
    new["revision"] = "2"
    new["looks"]["winter"] = {"board": {"asset_id": "WINTER", "revision": "1"}}
    lib.register_entity(entry, new, root=root)
    lib.import_asset(entry, "WINTER", "1", project, "WINTER-LOCAL", root=root)
    lib.bind_character(entry, "GIRL", "2", project, "LOCAL-GIRL", "cloak", "LOCAL-BOARD", root=root)
    manifest = project.parent / "materials.yaml"
    data = load_yaml(manifest)
    data["shots"]["S1"]["character_looks"] = {
        "LOCAL-GIRL": {"look_id": "winter", "board_asset_id": "WINTER-LOCAL"}
    }
    assert shot_identity_issues(manifest, data, "S1", root=root)
    data["shots"]["S1"]["reference_bindings"]["ref_image_0"] = "WINTER-LOCAL"
    data["shots"]["S1"]["required_assets"] = ["WINTER-LOCAL"]
    assert not shot_identity_issues(manifest, data, "S1", root=root)
    lib.bind_character(
        entry, "GIRL", "2", project, "LOCAL-GIRL", "winter", "WINTER-LOCAL", root=root
    )
    refs = characters(project, root=root)["LOCAL-GIRL"]["visual_references"]
    assert any(ref["asset_id"] == "WINTER-LOCAL" for ref in refs)
    assert all(ref["asset_id"] != "LOCAL-BOARD" for ref in refs)


@pytest.mark.parametrize("tamper", [False, True, "manifest_race"])
def test_runner_validates_frozen_bytes_and_records_library_versions(library, monkeypatch, tamper):
    root, _, _, _, _, _, project = library
    item = import_and_bind(library)
    manifest = project.parent / "materials.yaml"
    data = load_yaml(manifest)
    data["assets"]["LOCAL-BOARD"]["state"] = "ready"
    save(manifest, data)
    config = project.parent / "生成.yaml"
    rules = {"ref_image_0": {"type": "image"}}
    save(
        root / "catalog/workflows.yaml",
        {"schema_version": 1, "workflows": {"demo": {"input_rules": rules}}},
    )
    save(
        config,
        {
            "workflow_id": "demo",
            "materials_manifest": "materials.yaml",
            "shot_id": "S1",
            "inputs": {"ref_image_0": item["path"]},
        },
    )
    requests = []

    def handler(request):
        requests.append(request)
        response = (
            {"uuid": "demo", "input_rules": rules}
            if request.method == "GET"
            else {"task_id": "asset-test", "status": "QUEUED"}
        )
        return httpx.Response(200, json={"code": "Success", "data": response})

    monkeypatch.setattr(
        "autodl_video.runner.AutoDLClient",
        lambda token="": AutoDLClient(token, transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr("autodl_video.runner.load_token", lambda _: "mock-token")
    if tamper == "manifest_race":
        original_destination = VideoProject._generation_destination
        calls = []

        def replace_after_readiness(self, *args):
            result = original_destination(self, *args)
            calls.append(1)
            if len(calls) == 2:
                image = project.parent / item["path"]
                image.unlink()
                image.write_bytes(b"\x89PNG\r\n\x1a\nunreviewed-new-image")
                updated = load_yaml(manifest)
                asset = updated["assets"]["LOCAL-BOARD"]
                asset["state"] = "provided"
                asset["sha256"] = digest_file(image)
                asset["library_ref"]["sha256"] = asset["sha256"]
                asset["library_ref"]["revision"] = "NEW"
                save(manifest, updated)
            return result

        monkeypatch.setattr(VideoProject, "_generation_destination", replace_after_readiness)
        with pytest.raises(AutoDLError, match="实际提交素材与锁定版本不一致"):
            VideoProject(root).generate(config, wait=False)
        assert all(request.method == "GET" for request in requests)
    elif tamper:
        from autodl_video import runner

        original = runner.validate_inputs

        def changed_payload(*args, **kwargs):
            payload = original(*args, **kwargs)
            if kwargs.get("encode_media", True):
                payload["ref_image_0"] = (
                    "data:image/png;base64," + base64.b64encode(b"wrong-bytes-after-check").decode()
                )
            return payload

        monkeypatch.setattr(runner, "validate_inputs", changed_payload)
        with pytest.raises(AutoDLError, match="实际提交素材与锁定版本不一致"):
            VideoProject(root).generate(config, wait=False)
        assert all(request.method == "GET" for request in requests)
        assert not (root / ".autodl/tasks").exists()
    else:
        VideoProject(root).generate(config, wait=False)
        saved = json.loads((root / ".autodl/tasks/asset-test.json").read_text("utf-8"))
        assert saved["asset_pins"]["ref_image_0"]["asset_id"] == "GIRL-BOARD"
        assert saved["asset_pins"]["ref_image_0"]["sha256"] == item["sha256"]
        assert [request.method for request in requests] == ["GET", "POST"]


def test_init_failure_preserves_replacement_index_and_recovery(tmp_path, monkeypatch):
    original = lib._exclusive_text

    def fail_entry(path, text):
        if path.name == "project.yaml":
            raise PermissionError("synthetic init failure")
        original(path, text)

    with monkeypatch.context() as scoped:
        scoped.setattr(lib, "_exclusive_text", fail_entry)
        with pytest.raises(PermissionError):
            lib.init_library(tmp_path)
    assert not (tmp_path / "projects/共享资产库/资产索引.yaml").exists()
    first = lib.init_library(tmp_path)
    second = lib.init_library(tmp_path, name="另一个资产库")
    assert load_yaml(first)["library_id"] != load_yaml(second)["library_id"]


@pytest.mark.parametrize("field,value", [("category", []), ("media_type", {})])
def test_invalid_asset_metadata_is_domain_error(library, field, value):
    root, entry, source, spec, _, _, _ = library
    with pytest.raises(AutoDLError, match="分类或媒体类型"):
        register_test_asset(entry, source, {**spec, "asset_id": "NEW", field: value}, root=root)


def test_library_reports_missing_derived_dependency(library):
    root, entry, source, spec, _, _, _ = library
    register_test_asset(
        entry,
        source,
        {**spec, "asset_id": "DERIVED", "derived_from": [{"asset_id": "UNKNOWN", "revision": "1"}]},
        root=root,
    )
    report = lib.check_library(entry, root=root)
    assert not report["valid"] and "UNKNOWN" in report["issues"][0]


def test_identity_board_requires_current_visual_evidence(library):
    root, entry, source, spec, _, _, _ = library
    with pytest.raises(AutoDLError, match="exact three-view contract"):
        lib.register_asset(entry, source, {**spec, "asset_id": "NO-REVIEW"}, root=root)
    imported = import_and_bind(library)
    review = library[-1].parent / imported["library_ref"]["board_contract"]["evidence_path"]
    review.write_text("{}", encoding="utf-8")
    assert not lib.check_project(library[-1], root=root)["valid"]
