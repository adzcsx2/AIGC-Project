"""Project character identities and hash-bound voice selections (offline only)."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path

from .config import load_yaml
from .errors import AutoDLError
from .paths import project_owner, resolve_media_path


@dataclass(frozen=True)
class VoiceApproval:
    character_id: str
    reference_audio: Path
    sample_sha256: str
    confirmation_ref: str


@dataclass
class VoiceCheck:
    issues: list[str] = dataclass_field(default_factory=list)
    approvals: dict[str, VoiceApproval] = dataclass_field(default_factory=dict)


def validate_voice_payload(payload: dict, approvals: dict[str, VoiceApproval]) -> None:
    """Match the frozen request bytes to the receipt captured by the materials gate."""
    for name, approval in approvals.items():
        try:
            value = payload[name]
            if not isinstance(value, str):
                raise ValueError
            header, separator, encoded = value.partition(",")
            if not separator or not header.startswith("data:") or not header.endswith(";base64"):
                raise ValueError
            digest = hashlib.sha256(base64.b64decode(encoded, validate=True)).hexdigest()
        except (KeyError, ValueError):
            raise AutoDLError(f"{name}: 无法核对实际提交的人物声音字节") from None
        if digest != approval.sample_sha256:
            raise AutoDLError(
                f"{name}/{approval.character_id}: 实际提交音频与已确认的声音样本不一致；"
                "素材在准备请求期间发生变化，未提交任务"
            )


def project_path(root: Path, value: object, *, repository_root: Path | None = None) -> Path:
    if not isinstance(value, str) or not value.strip() or "://" in value:
        raise AutoDLError("角色文件需要项目内本地路径")
    path = resolve_media_path(root / value, repository_root)
    if (
        not path.is_relative_to(root.resolve())
        or project_owner(path, root=repository_root) != root.resolve()
    ):
        raise AutoDLError("角色与声音文件必须保存在本作品内")
    return path


def characters(project_file: Path, *, root: Path | None = None) -> dict[str, dict]:
    project_file = resolve_media_path(project_file, root)
    work = project_file.parent
    registry = load_yaml(project_file).get("characters", {})
    if not isinstance(registry, dict):
        raise AutoDLError("project.characters must map IDs to character YAML files")
    result = {}
    for character_id, relative in registry.items():
        if not isinstance(character_id, str) or not character_id.strip():
            raise AutoDLError("人物ID必须是非空字符串")
        path = project_path(work, relative, repository_root=root)
        data = load_yaml(path)
        if (
            type(data.get("schema_version")) is not int
            or data["schema_version"] != 1
            or data.get("character_id") != character_id
        ):
            raise AutoDLError(f"{character_id}: 人物ID或schema不匹配")
        if not isinstance(data.get("label"), str) or not data["label"].strip():
            raise AutoDLError(f"{character_id}: 缺少中文识别描述label")
        if data.get("display_name") is not None and not isinstance(data["display_name"], str):
            raise AutoDLError(f"{character_id}: display_name应为文本或null")
        if data.get("voice") is not None and not isinstance(data["voice"], dict):
            raise AutoDLError(f"{character_id}: voice应为配置映射或null")
        result[character_id] = data
    return result


def voice_issue(
    root: Path, character: dict, *, repository_root: Path | None = None
) -> str | None:
    voice = character.get("voice") or {}
    if voice.get("status") != "approved":
        return "尚未配置/试听确认声音；继续独立工作，最后集中试听"
    receipt = voice.get("approval")
    if (
        not isinstance(receipt, dict)
        or receipt.get("character_id") != character["character_id"]
        or not isinstance(receipt.get("confirmation_ref"), str)
        or not receipt["confirmation_ref"].strip()
    ):
        return "缺少绑定此人物的真实用户声音确认记录"
    try:
        sample = project_path(root, voice.get("reference_audio"), repository_root=repository_root)
        if sample.suffix.lower() not in {".mp3", ".wav", ".flac"} or sample.stat().st_size == 0:
            return "声音参考需要非空MP3/WAV/FLAC；格式/解码/实际听音另行检查"
        with sample.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != receipt.get("sample_sha256"):
            return "声音样本已变化，旧试听确认失效"
    except (AutoDLError, OSError):
        return "声音参考不存在、无法读取或不在本作品内"
    return None


def voice_queue(project_file: Path, *, root: Path | None = None) -> list[dict]:
    """Only script dialogue creates a voice-selection requirement."""
    project_file = resolve_media_path(project_file, root)
    return [
        {
            "character_id": cid,
            "label": item.get("display_name") or item["label"],
            "issue": issue,
            "speech_usage": item.get("speech_usage", "unknown"),
        }
        for cid, item in characters(project_file, root=root).items()
        if item.get("speech_usage") == "dialogue"
        if (issue := voice_issue(project_file.parent, item, repository_root=root))
    ]


def shot_voice_issues(
    manifest: Path, data: dict, shot_id: str, rules: dict | None = None,
    *, root: Path | None = None,
) -> list[str]:
    return check_shot_voices(manifest, data, shot_id, rules, root=root).issues


def check_shot_voices(
    manifest: Path, data: dict, shot_id: str, rules: dict | None = None,
    *, root: Path | None = None,
) -> VoiceCheck:
    """Opt-in voice contract for new reference-conditioned shots; legacy stays readable."""
    policy = data.get("voice_policy")
    if policy is None:
        return VoiceCheck()
    if (
        not isinstance(policy, dict)
        or type(policy.get("version")) is not int
        or policy["version"] != 1
    ):
        return VoiceCheck(["voice_policy.version must be 1"])
    value = policy.get("project")
    if not isinstance(value, str) or not value.strip():
        return VoiceCheck(["voice_policy.project需要project.yaml路径"])
    project = resolve_media_path(manifest.parent / value, root)
    owner = project_owner(manifest, root=root)
    if owner is None or project != owner / "project.yaml":
        return VoiceCheck(["voice_policy.project必须指向本清单所属作品的真实project.yaml入口"])
    work = project.parent
    try:
        registry = characters(project, root=root)
    except (AutoDLError, OSError) as exc:
        return VoiceCheck([str(exc)])
    shot = data["shots"][shot_id]
    references = shot.get("reference_bindings")
    if (
        not isinstance(references, dict)
        or not references
        or any(not isinstance(k, str) or not isinstance(v, str) for k, v in references.items())
    ):
        return VoiceCheck([f"{shot_id}: reference_bindings must map input fields to asset IDs"])
    speakers = shot.get("speakers")
    if not isinstance(speakers, list) or any(not isinstance(x, str) for x in speakers):
        return VoiceCheck([f"{shot_id}: speakers待核对；剧本中本镜无人说话时填写空列表"])
    bindings = shot.get("voice_bindings", {})
    if not isinstance(bindings, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) for k, v in bindings.items()
    ):
        return VoiceCheck([f"{shot_id}: voice_bindings必须是音频字段到人物ID的映射"])
    voice_fields = {
        field for field, asset_id in references.items()
        if data["assets"].get(asset_id, {}).get("purpose") == "character_voice"
    }
    if not speakers and voice_fields:
        return VoiceCheck([
            f"{shot_id}: 本镜无人说话，请移除无用的人物声音输入及对应绑定："
            + ", ".join(sorted(voice_fields))
        ])
    issues = []
    approvals = {}
    for field in sorted(voice_fields - bindings.keys()):
        issues.append(
            f"{shot_id}/{field}: 人物声音输入缺少voice_bindings；"
            "请绑定本镜说话人物，或移除无用输入"
        )
    if len(speakers) != len(set(speakers)):
        issues.append(f"{shot_id}: speakers有重复人物")
    if set(bindings.values()) != set(speakers) or len(bindings) != len(speakers):
        issues.append(f"{shot_id}: 每位说话人物需要独立声音槽，与speakers一一对应")
    for cid in speakers:
        if cid not in registry:
            issues.append(f"{shot_id}: 未登记人物 {cid}")
        elif reason := voice_issue(work, registry[cid], repository_root=root):
            issues.append(f"{shot_id}/{cid}: {reason}")
    for field, cid in bindings.items():
        if rules is not None and rules.get(field, {}).get("type") != "audio":
            issues.append(f"{shot_id}/{field}: 真实接口没有此音频槽，不可静默更换模型")
        asset_id = references.get(field)
        asset = data["assets"].get(asset_id, {})
        if asset.get("kind") != "audio" or asset.get("purpose") != "character_voice":
            issues.append(f"{shot_id}/{field}: 需要登记purpose=character_voice的audio素材")
            continue
        if cid not in registry:
            continue
        if reason := voice_issue(work, registry[cid], repository_root=root):
            issues.append(f"{shot_id}/{cid}: {reason}")
            continue
        try:
            actual = resolve_media_path(manifest.parent / asset["path"], root)
            expected = project_path(
                work, registry[cid]["voice"]["reference_audio"], repository_root=root
            )
            if actual != expected:
                issues.append(f"{shot_id}/{field}: 绑定音频不是{cid}已确认的声音文件")
            else:
                receipt = registry[cid]["voice"]["approval"]
                approvals[field] = VoiceApproval(
                    cid, expected, receipt["sample_sha256"], receipt["confirmation_ref"]
                )
        except (KeyError, TypeError, AutoDLError):
            issues.append(f"{shot_id}/{field}: 声音路径无效")
    return VoiceCheck(issues, approvals)
