"""Offline readiness and reference binding checks for short-drama production."""

from __future__ import annotations

from pathlib import Path

from .config import load_yaml
from .errors import AutoDLError

DOCUMENTS = ("brief", "style", "script", "storyboard")
KINDS = {"character", "scene", "prop", "keyframe", "audio", "video"}
MEDIA_TYPES = {"image", "audio", "video"}


def local_path(base: Path, value: object) -> Path:
    if not isinstance(value, str) or not value.strip() or "://" in value:
        raise AutoDLError("Expected a local file path")
    path = Path(value)
    return (base / path).resolve()


def _file_issue(base: Path, item: dict, *, image: bool = False) -> str | None:
    if item.get("state") != "ready":
        return "待补充或待检查：state 尚未标记为 ready"
    try:
        path = local_path(base, item.get("path"))
        if not path.is_file() or path.stat().st_size == 0:
            return "文件不存在或为空"
        if image:
            with path.open("rb") as stream:
                header = stream.read(12)
            if not (
                header.startswith(b"\x89PNG\r\n\x1a\n")
                or header.startswith(b"\xff\xd8\xff")
                or (header.startswith(b"RIFF") and header[8:12] == b"WEBP")
            ):
                return "需要真实的 PNG/JPEG/WebP 图片，提示词文本不算图片"
    except (AutoDLError, OSError, ValueError):
        return "需要可读取的本地文件路径"
    return None


def _read(path: Path) -> dict:
    data = load_yaml(path)
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise AutoDLError("materials schema_version must be 1")
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


def _check(path: Path, data: dict, shot_id: str | None) -> dict:
    issues = []
    missing = []
    assets = data["assets"]
    required = {key for key, item in assets.items() if item.get("required", True)}
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
            if asset_id not in assets:
                issues.append(f"{key}: 未登记素材 {asset_id}")
            else:
                required.add(asset_id)
    for key in DOCUMENTS:
        item = data["documents"].get(key, {})
        reason = _file_issue(path.parent, item)
        if reason:
            issues.append(f"document:{key}: {reason}")
    for asset_id in sorted(required):
        asset = assets[asset_id]
        reason = _file_issue(path.parent, asset, image=asset["kind"] not in {"audio", "video"})
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


def check_materials(manifest_path: str | Path, shot_id: str | None = None) -> dict:
    path = Path(manifest_path).resolve()
    return _check(path, _read(path), shot_id)


def assert_shot_ready(
    manifest_path: Path, shot_id: str, inputs: dict, rules: dict, base_dir: Path
) -> None:
    data = _read(manifest_path)
    report = _check(manifest_path, data, shot_id)
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
        actual = local_path(base_dir, inputs[field])
        registered = local_path(manifest_path.parent, data["assets"][asset_id]["path"])
        if actual != registered:
            raise AutoDLError(f"{field}: 实际文件与素材 {asset_id} 的登记路径不一致")
        image_count += expected == "image"
    if not image_count:
        raise AutoDLError("当前短剧图生视频流程需要至少一张已就绪参考图")


def check_config_materials(config: dict, rules: dict, base_dir: Path) -> None:
    linked = {"materials_manifest", "shot_id"} & config.keys()
    if not linked:
        return
    if len(linked) != 2 or not isinstance(config["shot_id"], str) or not config["shot_id"]:
        raise AutoDLError("materials_manifest and a nonempty shot_id must be provided together")
    manifest = local_path(base_dir, config["materials_manifest"])
    inputs = config.get("inputs", {})
    if not isinstance(inputs, dict):
        raise AutoDLError("inputs must be a mapping")
    assert_shot_ready(manifest, config["shot_id"], inputs, rules, base_dir)
