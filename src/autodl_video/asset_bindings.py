"""Offline, pinned asset/character references. Never resolve a moving latest version."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path

from .character_language import language_code
from .config import load_yaml
from .errors import AutoDLError
from .paths import project_owner, resolve_media_path

BOARD_LAYOUT = "front_closeup_headless_front_body_full_back"
BOARD_CHECKS = (
    "exactly_three_views",
    "headless_front_only",
    "full_rear_with_head",
    "front_portrait",
    "identity",
    "style",
    "anatomy",
    "grounding",
    "framing",
)


def validate_board_contract(item: dict, path: Path, *, base: Path) -> None:
    """Verify recorded human/assistant visual evidence, not infer content from PNG bytes."""
    if item.get("purpose") != "identity_board":
        return
    contract = item.get("board_contract")
    if (
        not isinstance(contract, dict)
        or type(contract.get("version")) is not int
        or contract["version"] != 1
        or contract.get("layout") != BOARD_LAYOUT
    ):
        raise AutoDLError("Identity boards require the current exact three-view contract")
    expected = checked_digest(item.get("sha256"))
    if contract.get("image_sha256") != expected or digest_file(path) != expected:
        raise AutoDLError("Character-board evidence does not match the actual image")
    evidence_path = owned_path(base, contract.get("evidence_path"))
    if digest_file(evidence_path) != checked_digest(contract.get("evidence_sha256")):
        raise AutoDLError("Character-board review evidence changed")
    try:
        review = json.loads(evidence_path.read_text("utf-8-sig"))
    except (ValueError, OSError):
        raise AutoDLError("Character-board review evidence is unreadable") from None
    if (
        not isinstance(review, dict)
        or review.get("image_sha256") != expected
        or review.get("layout") != BOARD_LAYOUT
        or review.get("verdict") != "passed"
        or review.get("reviewed_by") not in {"assistant", "user"}
        or not isinstance(review.get("checks"), dict)
        or any(review["checks"].get(key) is not True for key in BOARD_CHECKS)
    ):
        raise AutoDLError("Exact three-view visual review is missing or has unresolved findings")


def digest_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked_digest(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise AutoDLError("资产版本需要完整小写 SHA-256")
    return value


def owned_path(work: Path, value: object, *, root: Path | None = None) -> Path:
    if not isinstance(value, str) or not value.strip() or "://" in value:
        raise AutoDLError("需要作品内本地路径")
    path = resolve_media_path(work / value, root)
    if not path.is_relative_to(work.resolve()) or project_owner(path, root=root) != work.resolve():
        raise AutoDLError("资产及锁定版本必须归档到本作品内")
    return path


def validate_pin(asset: dict, path: Path) -> None:
    """Only opt-in library pins add checks; old manifests retain their contract."""
    pin = asset.get("library_ref")
    if pin is None:
        return
    if not isinstance(pin, dict) or any(
        not isinstance(pin.get(key), str) or not pin[key].strip()
        for key in ("library_id", "asset_id", "revision", "library")
    ):
        raise AutoDLError("library_ref需要资产库、资产ID和明确版本，不能使用浮动引用")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", pin["revision"]) or pin[
        "revision"
    ].lower() in {"latest", "current"}:
        raise AutoDLError("共享素材必须锁定明确版本")
    expected = checked_digest(pin.get("sha256"))
    if asset.get("sha256") != expected or digest_file(path) != expected:
        raise AutoDLError("素材字节与锁定共享版本不一致；另存新版本后重新选用")
    media = (
        "audio"
        if asset.get("kind") == "audio"
        else ("video" if asset.get("kind") == "video" else "image")
    )
    if pin.get("media_type") != media:
        raise AutoDLError("共享资产媒体类型与本作品素材类型不一致")
    board = {
        **asset,
        "purpose": pin.get("purpose", asset.get("purpose")),
        "board_contract": pin.get("board_contract", asset.get("board_contract")),
    }
    owner = project_owner(path)
    if board["purpose"] == "identity_board" and asset.get("lifecycle") != "archived":
        if owner is None:
            raise AutoDLError("Character-board review must belong to a project")
        validate_board_contract(board, path, base=owner)


def capture_payload_pins(config: dict, base: Path, *, root: Path) -> dict[str, dict]:
    """Capture expected digests before media encoding, not after files may change."""
    if not config.get("materials_manifest") or not config.get("shot_id"):
        return {}
    manifest = resolve_media_path(base / config["materials_manifest"], root)
    data = load_yaml(manifest)
    pins = {}
    for slot, asset_id in data["shots"][config["shot_id"]]["reference_bindings"].items():
        asset = data["assets"][asset_id]
        if asset.get("library_ref") is not None:
            path = resolve_media_path(manifest.parent / asset["path"], root)
            validate_pin(asset, path)
            pins[slot] = dict(asset["library_ref"])
    return pins


def validate_asset_payload(payload: dict, pins: dict[str, dict]) -> None:
    for slot, pin in pins.items():
        try:
            header, encoded = payload[slot].split(",", 1)
            if not header.startswith("data:") or not header.endswith(";base64"):
                raise ValueError
            actual = hashlib.sha256(base64.b64decode(encoded, validate=True)).hexdigest()
        except (KeyError, AttributeError, ValueError, TypeError):
            raise AutoDLError(f"{slot}: 无法核对实际提交的共享素材字节") from None
        if actual != pin["sha256"]:
            raise AutoDLError(f"{slot}: 实际提交素材与锁定版本不一致，未提交任务")


def resolve_character(data: dict, work: Path, *, root: Path | None = None) -> dict:
    binding = data.get("library_binding")
    if binding is None:
        return data
    if not isinstance(binding, dict):
        raise AutoDLError("library_binding必须为版本绑定映射")
    snapshot = owned_path(work, binding.get("profile"), root=root)
    if digest_file(snapshot) != checked_digest(binding.get("profile_sha256")):
        raise AutoDLError("共享角色快照已变化，不能自动继承新版本")
    shared = load_yaml(snapshot)
    if (
        type(shared.get("schema_version")) is not int
        or shared.get("schema_version") != 1
        or shared.get("category") != "character"
        or shared.get("entity_id") != binding.get("entity_id")
        or shared.get("revision") != binding.get("revision")
        or not binding.get("library_id")
    ):
        raise AutoDLError("共享角色身份、版本或schema不匹配")
    look = shared.get("looks", {}).get(binding.get("look_id"))
    if not isinstance(look, dict):
        raise AutoDLError("未找到已选角色造型；换装需明确选择造型ID")
    # Long-lived identity belongs to the frozen master. Project-specific story
    # capabilities, scale for blocking, names and speech usage stay local.
    local = data.get("attributes") or {}
    stable = {"summary", "appearance", "personality", "anatomy", "scale"}
    if not isinstance(local, dict) or stable & local.keys():
        raise AutoDLError("共享角色固定属性由主档维护，作品只保存剧情属性")
    manifest = owned_path(work, binding.get("materials_manifest"), root=root)
    assets = load_yaml(manifest).get("assets", {})

    def selected_asset(local_id: object, expected: dict, *, check_file: bool = True) -> dict:
        item = assets.get(local_id, {})
        pin = item.get("library_ref") or {}
        if any(pin.get(key) != expected.get(key) for key in ("asset_id", "revision")):
            raise AutoDLError("已选角色造型/声音与素材清单的共享版本不一致")
        if pin.get("library_id") != binding["library_id"]:
            raise AutoDLError("角色与素材属于不同资产库")
        if pin.get("entity_id") != binding["entity_id"]:
            raise AutoDLError("角色素材绑定了另一个全局身份")
        path = owned_path(work, str(manifest.parent / item.get("path", "")), root=root)
        if check_file:
            validate_pin(item, path)
        return item

    board = selected_asset(binding.get("board_asset_id"), look.get("board", {}))
    if board.get("kind") != "character":
        raise AutoDLError("角色造型必须绑定人物参考素材")
    refs = data.get("visual_references") or []
    if not any(
        isinstance(ref, dict)
        and ref.get("asset_id") == binding.get("board_asset_id")
        and owned_path(work, ref.get("manifest"), root=root) == manifest
        for ref in refs
    ):
        raise AutoDLError("visual_references未引用已选造型素材")
    voice_id = binding.get("voice_profile_id")
    if voice_id is not None:
        voice_profile = shared.get("voice_profiles", {}).get(voice_id)
        if not isinstance(voice_profile, dict):
            raise AutoDLError("未找到已选声线版本")
        sample = selected_asset(
            binding.get("voice_asset_id"), voice_profile.get("sample", {}), check_file=False
        )
        voice = data.get("voice") or {}
        expected = owned_path(work, str(manifest.parent / sample["path"]), root=root)
        if (
            sample.get("kind") != "audio"
            or sample.get("purpose") != "character_voice"
            or owned_path(work, voice.get("reference_audio"), root=root) != expected
        ):
            raise AutoDLError("角色所选声音与共享声线样本不一致")
        # Confirmation stays local, checked by the existing voice gate. A library
        # entry or a matching name never fabricates approval.
    result = dict(data)
    result["language"] = language_code(data.get("language", shared.get("language", "en")))
    result["attributes"] = {**shared.get("attributes", {}), **local}
    result["resolved_look"] = look
    result["looks"] = shared.get("looks", {})
    result["voice_profiles"] = shared.get("voice_profiles", {})
    result["style_reference"] = shared.get("style_reference")
    return result


def shot_identity_issues(
    manifest: Path, data: dict, shot_id: str, *, root: Path | None = None
) -> list[str]:
    """Match each used shared character's selected look to actual identity inputs."""
    from .characters import characters

    work = project_owner(manifest, root=root)
    if work is None or not any(
        item.get("library_ref") is not None for item in data["assets"].values()
    ):
        return []
    project = load_yaml(work / "project.yaml")
    if not project.get("characters"):
        return []
    # Legacy characters keep the previous contract.
    if not isinstance(project["characters"], dict):
        return [f"{shot_id}: project.characters必须为映射"]
    try:
        raw = [
            load_yaml(owned_path(work, value, root=root))
            for value in project["characters"].values()
        ]
    except (AutoDLError, OSError) as exc:
        return [f"{shot_id}: {exc}"]
    if not any(item.get("library_binding") is not None for item in raw):
        return []
    try:
        registry = characters(work / "project.yaml", root=root)
    except (AutoDLError, OSError) as exc:
        return [f"{shot_id}: {exc}"]
    shot, assets = data["shots"][shot_id], data["assets"]
    overrides = shot.get("character_looks", {})
    if not isinstance(overrides, dict) or any(key not in registry for key in overrides):
        return [f"{shot_id}: character_looks需要登记人物ID到造型选择的映射"]
    used = set(shot.get("required_assets", [])) | set(shot["reference_bindings"].values())
    issues = []
    for cid, character in registry.items():
        binding = character.get("library_binding")
        if binding is None:
            continue
        appears = any(
            (assets.get(aid, {}).get("library_ref") or {}).get("entity_id") == binding["entity_id"]
            for aid in used
        )
        if not appears and cid not in overrides:
            continue
        choice = overrides.get(
            cid, {"look_id": binding["look_id"], "board_asset_id": binding["board_asset_id"]}
        )
        if not isinstance(choice, dict):
            issues.append(f"{shot_id}/{cid}: 造型选择需包含look_id及board_asset_id")
            continue
        look = character["looks"].get(choice.get("look_id"))
        board_id = choice.get("board_asset_id")
        board = assets.get(board_id, {})
        pin = board.get("library_ref") or {}
        expected = look.get("board", {}) if isinstance(look, dict) else {}
        if (
            not expected
            or board_id not in shot["reference_bindings"].values()
            or board.get("kind") != "character"
            or pin.get("library_id") != binding["library_id"]
            or pin.get("entity_id") != binding["entity_id"]
            or any(pin.get(key) != expected.get(key) for key in ("asset_id", "revision"))
        ):
            issues.append(f"{shot_id}/{cid}: 实际身份输入与已选造型不一致或未传入人物板")
    return issues
