import base64
import copy
import hashlib
import json

import httpx
import pytest
import yaml

from autodl_video.characters import characters, shot_voice_issues, voice_issue, voice_queue
from autodl_video.cli import main
from autodl_video.client import AutoDLClient
from autodl_video.errors import AutoDLError
from autodl_video.materials import assert_shot_ready, check_materials
from autodl_video.runner import VideoProject
from autodl_video.schema import validate_inputs


def save(path, data):
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


@pytest.fixture
def voices(tmp_path):
    profile = {
        "schema_version": 1,
        "character_id": "GIRL",
        "label": "少女",
        "display_name": None,
        "speech_usage": "dialogue",
        "voice": {"status": "unconfigured", "reference_audio": None, "approval": None},
    }
    save(tmp_path / "少女.yaml", profile)
    save(tmp_path / "project.yaml", {"characters": {"GIRL": "少女.yaml"}})
    for name in ["brief", "style", "script", "storyboard"]:
        (tmp_path / f"{name}.md").write_text("内容", encoding="utf-8")
    (tmp_path / "图.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    data = {
        "schema_version": 1,
        "voice_policy": {"version": 1, "project": "project.yaml"},
        "documents": {
            k: {"path": f"{k}.md", "state": "ready"}
            for k in ["brief", "style", "script", "storyboard"]
        },
        "assets": {
            "IMAGE": {"kind": "character", "path": "图.png", "state": "ready"},
            "VOICE": {
                "kind": "audio",
                "purpose": "character_voice",
                "required": False,
                "path": "声音.wav",
                "state": "missing",
            },
        },
        "shots": {
            "SILENT": {
                "required_assets": ["IMAGE"],
                "reference_bindings": {"img": "IMAGE"},
                "speakers": [],
                "voice_bindings": {},
            },
            "SPEAK": {
                "required_assets": ["IMAGE", "VOICE"],
                "reference_bindings": {"img": "IMAGE", "ref_audio_0": "VOICE"},
                "speakers": ["GIRL"],
                "voice_bindings": {"ref_audio_0": "GIRL"},
            },
        },
    }
    path = tmp_path / "materials.yaml"
    save(path, data)
    return path, data, profile


def approve(voices):
    path, data, profile = voices
    sample = path.parent / "声音.wav"
    sample.write_bytes(b"RIFF-test-audio-fixture")
    profile["voice"] = {
        "status": "approved",
        "reference_audio": "声音.wav",
        "approval": {
            "character_id": "GIRL",
            "confirmation_ref": "测试用户确认",
            "sample_sha256": hashlib.sha256(sample.read_bytes()).hexdigest(),
        },
    }
    save(path.parent / "少女.yaml", profile)
    data["assets"]["VOICE"]["state"] = "ready"
    save(path, data)


def embedded_voice_fixture(voices):
    approve(voices)
    path, data, _ = voices
    work = path.parent
    (work / "引导.mp4").write_bytes(b"source-video-with-audio")
    (work / "对白.aac").write_bytes(b"encoded-selected-speaker")
    (work / "配音记录.json").write_text('{"task_id":"tts-existing-task"}', encoding="utf-8")
    data["assets"]["GUIDE"] = {"kind": "video", "path": "引导.mp4", "state": "ready"}
    data["assets"]["DIALOGUE"] = {"kind": "audio", "path": "对白.aac", "state": "ready"}

    def digest(name):
        return hashlib.sha256((work / name).read_bytes()).hexdigest()

    evidence = {
        "schema_version": 1,
        "kind": "embedded_source_audio",
        "character_id": "GIRL",
        "video_sha256": digest("引导.mp4"),
        "dialogue_sha256": digest("对白.aac"),
        "voice_sample_sha256": digest("声音.wav"),
        "audio_stream_copy_verified": True,
        "provenance": {"path": "配音记录.json", "sha256": digest("配音记录.json")},
    }
    (work / "音轨审计.json").write_text(json.dumps(evidence), encoding="utf-8")
    data["shots"]["EMBEDDED"] = {
        "required_assets": ["IMAGE", "GUIDE", "DIALOGUE", "VOICE"],
        "reference_bindings": {"img": "IMAGE", "ref_video": "GUIDE"},
        "speakers": ["GIRL"],
        "voice_bindings": {"ref_video": "GIRL"},
        "source_audio": {
            "character_id": "GIRL",
            "input_field": "ref_video",
            "dialogue_asset": "DIALOGUE",
            "evidence": {"path": "音轨审计.json", "sha256": digest("音轨审计.json")},
        },
    }
    save(path, data)
    return path, data


def test_embedded_track_uses_real_video_input_and_pins_sent_bytes(voices):
    from autodl_video.characters import validate_voice_payload

    path, _ = embedded_voice_fixture(voices)
    rules = {"img": {"type": "image"}, "ref_video": {"type": "video"}}
    approvals = assert_shot_ready(
        path, "EMBEDDED", {"img": "图.png", "ref_video": "引导.mp4"}, rules, path.parent
    )
    payload = {
        "ref_video": "data:video/mp4;base64,"
        + base64.b64encode(b"source-video-with-audio").decode()
    }
    validate_voice_payload(payload, approvals)
    payload["ref_video"] = "data:video/mp4;base64," + base64.b64encode(b"changed-video").decode()
    with pytest.raises(AutoDLError, match="实际提交"):
        validate_voice_payload(payload, approvals)


@pytest.mark.parametrize(
    "changed", ["引导.mp4", "对白.aac", "声音.wav", "音轨审计.json", "配音记录.json"]
)
def test_embedded_track_rejects_changed_provenance_or_media(voices, changed):
    path, data = embedded_voice_fixture(voices)
    with (path.parent / changed).open("ab") as f:
        f.write(b"changed")
    assert shot_voice_issues(path, data, "EMBEDDED", {"ref_video": {"type": "video"}})


def test_embedded_track_rejects_unapproved_speaker_and_nonvideo_field(voices):
    path, data = embedded_voice_fixture(voices)
    assert shot_voice_issues(path, data, "EMBEDDED", {"ref_video": {"type": "image"}})
    profile = yaml.safe_load((path.parent / "少女.yaml").read_text(encoding="utf-8"))
    profile["voice"]["status"] = "unconfigured"
    save(path.parent / "少女.yaml", profile)
    assert shot_voice_issues(path, data, "EMBEDDED", {"ref_video": {"type": "video"}})


def test_pending_voice_blocks_only_dependent_shot(voices):
    path, _, _ = voices
    assert check_materials(path, "SILENT")["ready"]
    assert not check_materials(path, "SPEAK")["ready"]
    assert not check_materials(path)["ready"]
    assert len(voice_queue(path.parent / "project.yaml")) == 1
    assert_shot_ready(path, "SILENT", {"img": "图.png"}, {"img": {"type": "image"}}, path.parent)


def test_approved_voice_passes_actual_binding_and_rename(voices):
    approve(voices)
    path, data, profile = voices
    profile["display_name"] = "小雨"
    save(path.parent / "少女.yaml", profile)
    rules = {"img": {"type": "image"}, "ref_audio_0": {"type": "audio"}}
    assert not shot_voice_issues(path, data, "SPEAK", rules)
    assert_shot_ready(
        path, "SPEAK", {"img": "图.png", "ref_audio_0": "声音.wav"}, rules, path.parent
    )
    assert not voice_queue(path.parent / "project.yaml")


def test_changed_sample_invalidates_confirmation(voices):
    approve(voices)
    path, _, profile = voices
    (path.parent / "声音.wav").write_bytes(b"another-voice")
    assert "失效" in voice_issue(path.parent, profile)
    assert not check_materials(path, "SPEAK")["ready"]


def test_wrong_character_or_missing_receipt_cannot_approve(voices):
    approve(voices)
    path, _, profile = voices
    profile["voice"]["approval"]["character_id"] = "OTHER"
    assert voice_issue(path.parent, profile)
    profile["voice"]["approval"] = None
    assert voice_issue(path.parent, profile)


def test_wrong_asset_and_unsupported_slot_rejected(voices):
    approve(voices)
    path, data, _ = voices
    data["assets"]["VOICE"]["path"] = "另一人.wav"
    issues = shot_voice_issues(path, data, "SPEAK", {"img": {"type": "image"}})
    assert any("没有此音频槽" in x for x in issues)
    assert any("不是GIRL" in x for x in issues)


def test_unknown_speaker_pending_speakers_and_capacity(voices):
    path, data, _ = voices
    data["shots"]["SILENT"]["speakers"] = None
    assert shot_voice_issues(path, data, "SILENT")
    data["shots"]["SPEAK"]["speakers"].append("OTHER")
    issues = shot_voice_issues(path, data, "SPEAK")
    assert any("未登记人物" in x for x in issues)
    assert any("一一对应" in x for x in issues)


def test_project_scope_and_character_id_checked(voices):
    path, _, profile = voices
    profile["character_id"] = "OTHER"
    save(path.parent / "少女.yaml", profile)
    with pytest.raises(AutoDLError, match="人物ID"):
        characters(path.parent / "project.yaml")
    save(path.parent / "project.yaml", {"characters": {"GIRL": "../外部.yaml"}})
    with pytest.raises(AutoDLError, match="本作品"):
        characters(path.parent / "project.yaml")


def test_legacy_manifest_keeps_its_contract(voices):
    path, data, _ = voices
    data.pop("voice_policy")
    assert not shot_voice_issues(path, data, "SPEAK")


@pytest.mark.parametrize("usage", ["none", "vocalization", "unknown", None])
def test_no_script_dialogue_does_not_require_voice(voices, usage):
    path, data, profile = voices
    profile["speech_usage"] = usage
    profile.pop("voice")
    save(path.parent / "少女.yaml", profile)
    assert not voice_queue(path.parent / "project.yaml")
    assert check_materials(path, "SILENT")["ready"]
    # A new speaking shot takes precedence over an older character usage summary.
    assert shot_voice_issues(path, data, "SPEAK")


def test_script_gains_dialogue_then_voice_is_needed(voices):
    path, _, profile = voices
    profile["speech_usage"] = "none"
    profile["voice"] = None
    save(path.parent / "少女.yaml", profile)
    assert not voice_queue(path.parent / "project.yaml")
    profile["speech_usage"] = "dialogue"
    save(path.parent / "少女.yaml", profile)
    assert [item["character_id"] for item in voice_queue(path.parent / "project.yaml")] == ["GIRL"]


def test_voice_approval_hashes_the_canonical_file_sent_to_api(voices):
    approve(voices)
    path, _, profile = voices
    root = path.parent
    (root / "pyproject.toml").write_text('name = "autodl-aigc"', encoding="utf-8")
    (root / ".autodl").mkdir()
    replacement = root / "迁移后的声音.wav"
    replacement.write_bytes(b"RIFF-unapproved-new-voice")
    (root / ".autodl/path-map.json").write_text(
        json.dumps({"files": {"声音.wav": replacement.name}, "directories": {}}),
        encoding="utf-8",
    )
    rules = {"img": {"type": "image"}, "ref_audio_0": {"type": "audio"}}
    inputs = {"img": "图.png", "ref_audio_0": "声音.wav"}
    # The old alias still exists, but its receipt cannot approve the bytes now transmitted.
    with pytest.raises(AutoDLError, match="失效"):
        assert_shot_ready(path, "SPEAK", inputs, rules, root)
    profile["voice"]["approval"].update(
        sample_sha256=hashlib.sha256(replacement.read_bytes()).hexdigest(),
        confirmation_ref="测试用户重新确认迁移目标声音",
    )
    save(root / "少女.yaml", profile)
    assert_shot_ready(path, "SPEAK", inputs, rules, root)
    encoded = validate_inputs(inputs, rules, base_dir=root)["ref_audio_0"]
    assert base64.b64decode(encoded.split(",", 1)[1]) == replacement.read_bytes()


def test_voice_policy_cannot_borrow_another_works_same_character_id(voices):
    path, data, _ = voices
    other = path.parent / "另一个作品"
    other.mkdir()
    sample = other / "声音.wav"
    sample.write_bytes(b"RIFF-other-character-voice")
    save(other / "project.yaml", {"characters": {"GIRL": "少女.yaml"}})
    save(
        other / "少女.yaml",
        {
            "schema_version": 1,
            "character_id": "GIRL",
            "label": "另一个少女",
            "voice": {
                "status": "approved",
                "reference_audio": "声音.wav",
                "approval": {
                    "character_id": "GIRL",
                    "confirmation_ref": "另一作品的用户确认",
                    "sample_sha256": hashlib.sha256(sample.read_bytes()).hexdigest(),
                },
            },
        },
    )
    data["voice_policy"]["project"] = "另一个作品/project.yaml"
    data["assets"]["VOICE"].update(path="另一个作品/声音.wav", state="ready")
    save(path, data)
    rules = {"img": {"type": "image"}, "ref_audio_0": {"type": "audio"}}
    with pytest.raises(AutoDLError, match="所属作品"):
        assert_shot_ready(
            path,
            "SPEAK",
            {"img": "图.png", "ref_audio_0": "另一个作品/声音.wav"},
            rules,
            path.parent,
        )


def test_voice_policy_requires_real_entry_but_allows_nested_manifests(voices):
    approve(voices)
    path, data, _ = voices
    fake = path.parent / "伪造入口.yaml"
    fake.write_bytes((path.parent / "project.yaml").read_bytes())
    data["voice_policy"]["project"] = fake.name
    assert any("真实project.yaml" in issue for issue in shot_voice_issues(path, data, "SPEAK"))
    nested = path.parent / "03-制作/制作计划"
    nested.mkdir(parents=True)
    data["voice_policy"]["project"] = "../../project.yaml"
    for section in ("documents", "assets"):
        for item in data[section].values():
            item["path"] = "../../" + item["path"]
    manifest = nested / "materials.yaml"
    save(manifest, data)
    assert_shot_ready(
        manifest,
        "SPEAK",
        {"img": "图.png", "ref_audio_0": "声音.wav"},
        {"img": {"type": "image"}, "ref_audio_0": {"type": "audio"}},
        path.parent,
    )


def voice_config(voices):
    path, _, _ = voices
    (path.parent / "catalog").mkdir(exist_ok=True)
    save(
        path.parent / "catalog/workflows.yaml",
        {
            "schema_version": 1,
            "workflows": {
                "demo": {
                    "input_rules": {
                        "img": {"type": "image"},
                        "ref_audio_0": {"type": "audio"},
                    }
                }
            },
        },
    )
    config = {
        "workflow_id": "demo",
        "materials_manifest": "materials.yaml",
        "shot_id": "SPEAK",
        "inputs": {"img": "图.png", "ref_audio_0": "声音.wav"},
    }
    save(path.parent / "shot.yaml", config)
    return path.parent / "shot.yaml", config


def test_config_cannot_borrow_another_works_voice_and_script_approval(voices, monkeypatch):
    approve(voices)
    path, _, profile = voices
    config_path, config = voice_config(voices)
    api = VideoProject(path.parent)
    assert api.generate(config_path, dry_run=True)["dry_run"]
    other = path.parent / "另一作品"
    other.mkdir()
    save(other / "project.yaml", {"characters": {"GIRL": "少女.yaml"}})
    save(other / "少女.yaml", {**profile, "voice": None})
    config["materials_manifest"] = "../materials.yaml"
    config["inputs"] = {"img": "../图.png", "ref_audio_0": "../声音.wav"}
    save(other / "shot.yaml", config)

    def forbidden(*args, **kwargs):
        pytest.fail("Cross-work inputs must fail before network or credentials")

    monkeypatch.setattr("autodl_video.runner.AutoDLClient", forbidden)
    monkeypatch.setattr("autodl_video.runner.load_token", forbidden)
    with pytest.raises(AutoDLError, match="不同作品"):
        api.generate(other / "shot.yaml")
    assert not api.store.directory.exists()


@pytest.mark.parametrize("references", [None, [], {"ref_audio_0": []}, {1: "VOICE"}])
def test_invalid_reference_bindings_raise_domain_errors(voices, references, capsys):
    approve(voices)
    path, data, _ = voices
    data["shots"]["SPEAK"]["reference_bindings"] = references
    save(path, data)
    assert any("reference_bindings" in x for x in shot_voice_issues(path, data, "SPEAK"))
    config_path, _ = voice_config(voices)
    with pytest.raises(AutoDLError, match="reference_bindings"):
        VideoProject(path.parent).generate(config_path, dry_run=True)
    assert main(["--project", str(path.parent), "validate", str(config_path)]) == 2
    assert "reference_bindings" in capsys.readouterr().err


def mock_voice_submission(voices, monkeypatch, *, shot_id="SPEAK", extra_purpose=None):
    path, data, _ = voices
    config_path, config = voice_config(voices)
    config["shot_id"] = shot_id
    if shot_id == "SILENT":
        config["inputs"].pop("ref_audio_0")
    rules = {"img": {"type": "image"}, "ref_audio_0": {"type": "audio"}}
    if extra_purpose is not None:
        (path.parent / "额外参考.wav").write_bytes(b"RIFF-extra-unapproved-reference")
        data["assets"]["EXTRA"] = {
            "kind": "audio",
            "purpose": extra_purpose,
            "required": False,
            "path": "额外参考.wav",
            "state": "ready",
        }
        data["shots"][shot_id]["reference_bindings"]["ref_audio_1"] = "EXTRA"
        config["inputs"]["ref_audio_1"] = "额外参考.wav"
        rules["ref_audio_1"] = {"type": "audio"}
    save(path, data)
    save(config_path, config)
    save(
        path.parent / "catalog/workflows.yaml",
        {
            "schema_version": 1,
            "workflows": {"demo": {"input_rules": rules}},
        },
    )
    requests = []

    def handler(request):
        requests.append(request)
        response = (
            {"uuid": "demo", "input_rules": rules}
            if request.method == "GET"
            else {"task_id": "voice-test", "status": "QUEUED"}
        )
        return httpx.Response(200, json={"code": "Success", "data": response})

    monkeypatch.setattr(
        "autodl_video.runner.AutoDLClient",
        lambda token="": AutoDLClient(token, transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr("autodl_video.runner.load_token", lambda _: "mock-token")
    return config_path, config, requests


def test_unbound_extra_character_voice_blocks_before_network(voices, monkeypatch):
    approve(voices)
    path, _, _ = voices
    config_path, _, requests = mock_voice_submission(
        voices,
        monkeypatch,
        extra_purpose="character_voice",
    )
    report = check_materials(path, "SPEAK")
    assert not report["ready"]
    assert any(
        "ref_audio_1" in issue and "缺少voice_bindings" in issue for issue in report["issues"]
    )
    with pytest.raises(AutoDLError, match="缺少voice_bindings"):
        VideoProject(path.parent).generate(config_path, wait=False)
    assert requests == []
    assert not (path.parent / ".autodl").exists()


@pytest.mark.parametrize("stale_binding", [False, True])
def test_silent_shot_removes_unused_voice_without_requesting_approval(
    voices,
    monkeypatch,
    stale_binding,
):
    path, data, profile = voices
    profile["speech_usage"] = "none"
    profile["voice"] = None
    save(path.parent / "少女.yaml", profile)
    data["shots"] = {"SILENT": data["shots"]["SILENT"]}
    config_path, config, requests = mock_voice_submission(
        voices,
        monkeypatch,
        shot_id="SILENT",
        extra_purpose="character_voice",
    )
    if stale_binding:
        data["shots"]["SILENT"]["voice_bindings"]["ref_audio_1"] = "GIRL"
        save(path, data)
    issues = check_materials(path, "SILENT")["issues"]
    assert any("本镜无人说话，请移除" in issue for issue in issues)
    assert not any("试听" in issue or "配置" in issue for issue in issues)
    assert not voice_queue(path.parent / "project.yaml")
    with pytest.raises(AutoDLError, match="本镜无人说话，请移除"):
        VideoProject(path.parent).generate(config_path, wait=False)
    assert requests == []
    assert not (path.parent / ".autodl").exists()
    data["shots"]["SILENT"]["reference_bindings"].pop("ref_audio_1")
    data["shots"]["SILENT"]["voice_bindings"].clear()
    config["inputs"].pop("ref_audio_1")
    save(path, data)
    save(config_path, config)
    assert check_materials(path, "SILENT")["ready"]
    assert VideoProject(path.parent).generate(config_path, wait=False)["task_id"] == "voice-test"
    posts = [request for request in requests if request.method == "POST"]
    assert len(posts) == 1
    assert set(json.loads(posts[0].content)) == {"img"}


@pytest.mark.parametrize("extra_purpose", [None, "ambient_sound", "emotion_reference"])
def test_approved_voice_and_other_audio_keep_submission_semantics(
    voices,
    monkeypatch,
    extra_purpose,
):
    approve(voices)
    path, _, _ = voices
    config_path, _, requests = mock_voice_submission(
        voices,
        monkeypatch,
        extra_purpose=extra_purpose,
    )
    assert check_materials(path, "SPEAK")["ready"]
    result = VideoProject(path.parent).generate(config_path, wait=False)
    assert result["task_id"] == "voice-test"
    posts = [request for request in requests if request.method == "POST"]
    assert len(posts) == 1
    payload = json.loads(posts[0].content)
    assert (
        base64.b64decode(payload["ref_audio_0"].split(",", 1)[1])
        == (path.parent / "声音.wav").read_bytes()
    )
    if extra_purpose is not None:
        assert (
            base64.b64decode(payload["ref_audio_1"].split(",", 1)[1])
            == (path.parent / "额外参考.wav").read_bytes()
        )
    assert (path.parent / ".autodl/tasks/voice-test.json").is_file()


@pytest.mark.parametrize("foreign_reference", ["profile", "audio"])
def test_nested_work_cannot_supply_character_or_voice_approval(
    voices,
    monkeypatch,
    capsys,
    foreign_reference,
):
    approve(voices)
    path, data, profile = voices
    nested = path.parent / "另一作品"
    nested.mkdir()
    save(nested / "project.yaml", {"characters": {"GIRL": "少女.yaml"}})
    save(nested / "少女.yaml", profile)
    (nested / "声音.wav").write_bytes((path.parent / "声音.wav").read_bytes())
    if foreign_reference == "profile":
        # The same bytes in this work do not transfer another work's approval.
        save(path.parent / "project.yaml", {"characters": {"GIRL": "另一作品/少女.yaml"}})
    else:
        profile["voice"]["reference_audio"] = "另一作品/声音.wav"
        save(path.parent / "少女.yaml", profile)
        data["assets"]["VOICE"]["path"] = "另一作品/声音.wav"
    config, _, requests = mock_voice_submission(voices, monkeypatch)
    if foreign_reference == "profile":
        with pytest.raises(AutoDLError, match="本作品"):
            voice_queue(path.parent / "project.yaml")
    else:
        assert "本作品" in voice_queue(path.parent / "project.yaml")[0]["issue"]
    assert not check_materials(path, "SPEAK")["ready"]
    with pytest.raises(AutoDLError, match="本作品"):
        VideoProject(path.parent).generate(config, wait=False)
    assert main(["--project", str(path.parent), "validate", str(config)]) == 2
    assert "本作品" in capsys.readouterr().err
    assert requests == []
    assert not (path.parent / ".autodl").exists()


def test_explicit_root_applies_to_all_migrated_references_and_transmitted_bytes(
    voices,
    monkeypatch,
    capsys,
):
    approve(voices)
    path, data, profile = voices
    root = path.parent
    data.update(
        schema_version=2,
        creative_confirmation={
            "state": "confirmed",
            "confirmation_ref": "本作品剧本确认",
            "script_sha256": hashlib.sha256((root / "script.md").read_bytes()).hexdigest(),
        },
    )
    aliases = {
        "legacy/project.yaml": "project.yaml",
        "legacy/materials.yaml": "materials.yaml",
        "legacy/girl.yaml": "少女.yaml",
        "legacy/voice.wav": "声音.wav",
        "legacy/image.png": "图.png",
    }
    for document in data["documents"].values():
        old = document["path"]
        document["path"] = "legacy/" + old
        aliases[document["path"]] = old
    data["voice_policy"]["project"] = "legacy/project.yaml"
    data["assets"]["IMAGE"]["path"] = "legacy/image.png"
    data["assets"]["VOICE"]["path"] = "legacy/voice.wav"
    profile["voice"]["reference_audio"] = "legacy/voice.wav"
    save(root / "少女.yaml", profile)
    save(root / "project.yaml", {"characters": {"GIRL": "legacy/girl.yaml"}})
    (root / ".autodl").mkdir()
    (root / ".autodl/path-map.json").write_text(
        json.dumps({"files": aliases, "directories": {}}),
        encoding="utf-8",
    )
    config_path, config, requests = mock_voice_submission(voices, monkeypatch)
    config.update(materials_manifest="legacy/materials.yaml")
    config["inputs"] = {"img": "legacy/image.png", "ref_audio_0": "legacy/voice.wav"}
    save(config_path, config)
    assert not (root / "pyproject.toml").exists()
    assert not voice_queue(root / "legacy/project.yaml", root=root)
    assert check_materials(root / "legacy/materials.yaml", "SPEAK", root=root)["ready"]
    assert main(["--project", str(root), "validate", str(config_path)]) == 0
    assert json.loads(capsys.readouterr().out)["dry_run"]
    assert requests == []
    assert VideoProject(root).generate(config_path, wait=False)["task_id"] == "voice-test"
    posts = [r for r in requests if r.method == "POST"]
    assert len(posts) == 1
    payload = json.loads(posts[0].content)
    for field, name in (("img", "图.png"), ("ref_audio_0", "声音.wav")):
        assert base64.b64decode(payload[field].split(",", 1)[1]) == (root / name).read_bytes()
    (root / "声音.wav").write_bytes(b"changed-canonical-voice")
    with pytest.raises(AutoDLError, match="失效"):
        VideoProject(root).generate(config_path, wait=False)
    assert len([r for r in requests if r.method == "POST"]) == 1


@pytest.mark.parametrize("changed_field", ["ref_audio_0", "ref_audio_1"])
@pytest.mark.parametrize("after_read", ["keep_changed", "restore_file", "replace_receipt"])
def test_submission_checks_frozen_voice_bytes_against_captured_approval(
    voices,
    monkeypatch,
    changed_field,
    after_read,
):
    approve(voices)
    manifest, data, profile = voices
    root = manifest.parent
    config_path, config, requests = mock_voice_submission(
        voices,
        monkeypatch,
        extra_purpose="character_voice",
    )
    second = copy.deepcopy(profile)
    second["character_id"] = "OTHER"
    second["voice"]["reference_audio"] = "额外参考.wav"
    second["voice"]["approval"].update(
        character_id="OTHER",
        sample_sha256=hashlib.sha256((root / "额外参考.wav").read_bytes()).hexdigest(),
    )
    save(root / "另一人物.yaml", second)
    save(root / "project.yaml", {"characters": {"GIRL": "少女.yaml", "OTHER": "另一人物.yaml"}})
    shot = data["shots"]["SPEAK"]
    shot["speakers"].append("OTHER")
    shot["voice_bindings"]["ref_audio_1"] = "OTHER"

    # The old input spelling must still hash the canonical bytes actually encoded.
    chosen = profile if changed_field == "ref_audio_0" else second
    character_file = root / ("少女.yaml" if changed_field == "ref_audio_0" else "另一人物.yaml")
    sample = root / chosen["voice"]["reference_audio"]
    original = sample.read_bytes()
    replacement = b"RIFF-unapproved-replacement"
    alias = "legacy/voice.wav"
    (root / ".autodl").mkdir()
    (root / ".autodl/path-map.json").write_text(
        json.dumps(
            {
                "files": {alias: sample.name},
                "directories": {},
            }
        ),
        encoding="utf-8",
    )
    chosen["voice"]["reference_audio"] = alias
    save(character_file, chosen)
    data["assets"][shot["reference_bindings"][changed_field]]["path"] = alias
    config["inputs"][changed_field] = alias
    save(manifest, data)
    save(config_path, config)
    actual_encode = base64.b64encode
    encoded_replacement = []

    def replace_during_encoding(value):
        if value.startswith(b"\x89PNG"):
            sample.write_bytes(replacement)
        if value == replacement:
            encoded_replacement.append(value)
            if after_read == "restore_file":
                sample.write_bytes(original)
            elif after_read == "replace_receipt":
                chosen["voice"]["approval"]["sample_sha256"] = hashlib.sha256(value).hexdigest()
                save(character_file, chosen)
        return actual_encode(value)

    def forbidden_token(_):
        pytest.fail("Changed request audio must fail before loading credentials")

    monkeypatch.setattr("autodl_video.schema.base64.b64encode", replace_during_encoding)
    monkeypatch.setattr("autodl_video.runner.load_token", forbidden_token)
    with pytest.raises(AutoDLError, match=f"{changed_field}/.*实际提交音频"):
        VideoProject(root).generate(config_path, wait=False)
    assert encoded_replacement == [replacement]
    assert [r.method for r in requests] == ["GET"]
    assert not (root / ".autodl/tasks").exists()
    assert not (root / ".autodl/attempts").exists()
