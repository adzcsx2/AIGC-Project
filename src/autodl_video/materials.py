"""Offline readiness and reference binding checks for short-drama production."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from .asset_bindings import shot_identity_issues, validate_pin
from .characters import VoiceApproval, check_shot_voices, shot_voice_issues
from .config import load_yaml
from .errors import AutoDLError
from .paths import project_owner, resolve_media_path

DOCUMENTS = ("brief", "style", "script", "storyboard")
KINDS = {"character", "scene", "prop", "keyframe", "audio", "video"}
MEDIA_TYPES = {"image", "audio", "video"}


def local_path(base: Path, value: object, *, root: Path | None = None) -> Path:
    if not isinstance(value, str) or not value.strip() or "://" in value:
        raise AutoDLError("Expected a local file path")
    path = Path(value)
    return resolve_media_path(base / path, root)


def _file_issue(
    base: Path, item: dict, *, image: bool = False, root: Path | None = None
) -> str | None:
    if item.get("kind") == "character" and item.get("purpose") == "historical_source":
        return "Historical character sources cannot replace the current reviewed three-view board"
    if item.get("state") != "ready":
        return "待补充或待检查：state 尚未标记为 ready"
    try:
        path = local_path(base, item.get("path"), root=root)
        if not path.is_file() or path.stat().st_size == 0:
            return "文件不存在或为空"
        validate_pin(item, path)
        if image:
            with path.open("rb") as stream:
                header = stream.read(12)
            if not (
                header.startswith(b"\x89PNG\r\n\x1a\n")
                or header.startswith(b"\xff\xd8\xff")
                or (header.startswith(b"RIFF") and header[8:12] == b"WEBP")
            ):
                return "需要真实的 PNG/JPEG/WebP 图片，提示词文本不算图片"
    except AutoDLError as exc:
        return str(exc)
    except (OSError, ValueError):
        return "需要可读取的本地文件路径"
    return None


def _read(path: Path) -> dict:
    data = load_yaml(path)
    if type(data.get("schema_version")) is not int or data["schema_version"] not in (1, 2):
        raise AutoDLError("materials schema_version must be 1 or 2")
    for key in ("documents", "assets", "shots"):
        value = data.get(key)
        if not isinstance(value, dict) or not value:
            raise AutoDLError(f"materials.{key} must be a nonempty mapping")
        if any(not isinstance(k, str) or not k.strip() for k in value):
            raise AutoDLError(f"materials.{key} IDs must be nonempty strings")
        if any(not isinstance(v, dict) for v in value.values()):
            raise AutoDLError(f"materials.{key} entries must be mappings")
    for key, asset in data["assets"].items():
        if not isinstance(asset.get("kind"), str) or asset["kind"] not in KINDS:
            raise AutoDLError(f"Asset {key}: unknown kind")
        if type(asset.get("required", True)) is not bool:
            raise AutoDLError(f"Asset {key}: required must be a boolean")
    return data


def _confirmation_issue(base: Path, data: dict, *, root: Path | None = None) -> str | None:
    # Version 1 remains readable for historical configs and task recovery.
    if data["schema_version"] == 1:
        return None
    receipt = data.get("creative_confirmation")
    if not isinstance(receipt, dict) or receipt.get("state") != "confirmed":
        return "文案确认：补全后的剧本需先取得用户确认，再进行后续制作"
    record = receipt.get("confirmation_ref")
    if not isinstance(record, str) or not record.strip():
        return "文案确认：缺少用户确认记录的位置或说明"
    expected = receipt.get("script_sha256")
    if (
        not isinstance(expected, str)
        or len(expected) != 64
        or any(char not in "0123456789abcdef" for char in expected)
    ):
        return "文案确认：缺少已确认剧本的有效 SHA-256"
    try:
        script = local_path(base, data["documents"].get("script", {}).get("path"), root=root)
        owner = project_owner(base, root=root)
        if owner is not None and project_owner(script, root=root) != owner:
            return "文案确认：已确认剧本必须归档到本作品内；跨作品借鉴需取得本作品确认"
        actual = hashlib.sha256(script.read_bytes()).hexdigest()
    except (AutoDLError, OSError, ValueError):
        return "文案确认：无法读取已确认的剧本文件"
    if actual != expected:
        return "文案确认：剧本已变化，旧确认不适用；请确认本次修改后更新记录"
    return None


def _check(path: Path, data: dict, shot_id: str | None, *, root: Path | None = None) -> dict:
    issues = []
    missing = []
    confirmation_issue = _confirmation_issue(path.parent, data, root=root)
    if confirmation_issue:
        issues.append(confirmation_issue)
    assets = data["assets"]
    # Voice choices wait only on dependent shots; visual prerequisites retain their policy.
    scoped_voices = {
        key
        for key, item in assets.items()
        if data.get("voice_policy")
        and item.get("kind") == "audio"
        and item.get("purpose") == "character_voice"
    }
    required = {
        key
        for key, item in assets.items()
        if item.get("required", True) and key not in scoped_voices
    }
    shots = data["shots"]
    if shot_id is not None and shot_id not in shots:
        raise AutoDLError(f"Unknown shot_id: {shot_id}")
    # The creator requested all prerequisites before stage 4, including other shots.
    for key, shot in shots.items():
        dependencies = shot.get("required_assets")
        bindings = shot.get("reference_bindings")
        if (
            not isinstance(dependencies, list)
            or not dependencies
            or any(not isinstance(v, str) for v in dependencies)
        ):
            raise AutoDLError(f"Shot {key}: required_assets must be a nonempty list of IDs")
        if (
            not isinstance(bindings, dict)
            or not bindings
            or any(not isinstance(k, str) or not isinstance(v, str) for k, v in bindings.items())
        ):
            raise AutoDLError(f"Shot {key}: reference_bindings must map input fields to asset IDs")
        for asset_id in set(dependencies) | set(bindings.values()):
            if shot_id is not None and key != shot_id and asset_id in scoped_voices:
                continue
            if asset_id not in assets:
                issues.append(f"{key}: 未登记素材 {asset_id}")
            else:
                required.add(asset_id)
    for key in [shot_id] if shot_id is not None else shots:
        issues.extend(shot_voice_issues(path, data, key, root=root))
        issues.extend(shot_identity_issues(path, data, key, root=root))
    for key in DOCUMENTS:
        item = data["documents"].get(key, {})
        reason = _file_issue(path.parent, item, root=root)
        if reason:
            issues.append(f"document:{key}: {reason}")
    for asset_id in sorted(required):
        asset = assets[asset_id]
        reason = _file_issue(
            path.parent, asset, image=asset["kind"] not in {"audio", "video"}, root=root
        )
        if reason:
            issues.append(f"{asset_id}: {reason}")
            missing.append(
                {"id": asset_id, "reason": reason, "generation_prompt": asset.get("prompt")}
            )
    return {
        "ready": not issues,
        "manifest": str(path),
        "shot_id": shot_id,
        "required_asset_count": len(required),
        "issues": issues,
        "missing_assets": missing,
    }


def check_materials(
    manifest_path: str | Path, shot_id: str | None = None, *, root: Path | None = None
) -> dict:
    path = resolve_media_path(Path(manifest_path), root)
    return _check(path, _read(path), shot_id, root=root)


def assert_shot_ready(
    manifest_path: Path,
    shot_id: str,
    inputs: dict,
    rules: dict,
    base_dir: Path,
    *,
    root: Path | None = None,
    captured_pins: dict | None = None,
) -> dict[str, VoiceApproval]:
    manifest_path = resolve_media_path(manifest_path, root)
    data = _read(manifest_path)
    if shot_id not in data["shots"]:
        raise AutoDLError(f"Unknown shot_id: {shot_id}")
    voices = check_shot_voices(manifest_path, data, shot_id, rules, root=root)
    if voices.issues:
        raise AutoDLError("人物声音尚未就绪：\n" + "\n".join(voices.issues))
    report = _check(manifest_path, data, shot_id, root=root)
    if not report["ready"]:
        raise AutoDLError("素材未齐备，不能生成视频：\n" + "\n".join(report["issues"]))
    bindings = data["shots"][shot_id]["reference_bindings"]
    media_inputs = {key for key in inputs if rules.get(key, {}).get("type") in MEDIA_TYPES}
    if media_inputs != set(bindings):
        raise AutoDLError("镜头参考绑定必须与 YAML 中实际提供的全部媒体字段一致")
    image_count = 0
    for field, asset_id in bindings.items():
        kind = data["assets"][asset_id]["kind"]
        expected = kind if kind in {"audio", "video"} else "image"
        if rules.get(field, {}).get("type") != expected:
            raise AutoDLError(f"{field}: 素材类型与模型输入不匹配")
        actual = local_path(base_dir, inputs[field], root=root)
        registered = local_path(manifest_path.parent, data["assets"][asset_id]["path"], root=root)
        if actual != registered:
            raise AutoDLError(f"{field}: 实际文件与素材 {asset_id} 的登记路径不一致")
        image_count += expected == "image"
    if not image_count:
        raise AutoDLError("当前短剧图生视频流程需要至少一张已就绪参考图")
    if captured_pins is not None:
        captured_pins.update(
            {
                field: copy.deepcopy(data["assets"][asset_id]["library_ref"])
                for field, asset_id in bindings.items()
                if data["assets"][asset_id].get("library_ref") is not None
            }
        )
    return voices.approvals


def check_config_materials(
    config: dict,
    rules: dict,
    base_dir: Path,
    *,
    root: Path | None = None,
    captured_pins: dict | None = None,
) -> dict[str, VoiceApproval]:
    linked = {"materials_manifest", "shot_id"} & config.keys()
    if not linked:
        return {}
    if len(linked) != 2 or not isinstance(config["shot_id"], str) or not config["shot_id"]:
        raise AutoDLError("materials_manifest and a nonempty shot_id must be provided together")
    manifest = local_path(base_dir, config["materials_manifest"], root=root)
    inputs = config.get("inputs", {})
    if not isinstance(inputs, dict):
        raise AutoDLError("inputs must be a mapping")
    return assert_shot_ready(
        manifest, config["shot_id"], inputs, rules, base_dir, root=root, captured_pins=captured_pins
    )
