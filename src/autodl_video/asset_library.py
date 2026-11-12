"""Versioned local asset library, controlled imports and dependency discovery."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

import yaml

from .asset_bindings import (
    digest_file,
    owned_path,
    resolve_character,
    validate_board_contract,
    validate_pin,
)
from .catalog import utc_now
from .character_language import language_code
from .config import atomic_text, load_yaml
from .errors import AutoDLError
from .locking import resource_lock

CATEGORIES = {
    "character": "角色",
    "wardrobe": "服装与配饰",
    "scene": "场景与地点",
    "prop": "道具与载具",
    "voice": "角色声音",
    "dialogue": "对白与旁白",
    "ambience": "环境声",
    "sfx": "音效与非语言声",
    "music": "音乐",
    "motion": "动作与白模",
    "camera": "摄影参考",
    "compositing": "合成辅助",
    "graphics": "字幕与包装",
    "footage": "镜头素材与成片",
}
FOLDERS = {
    "character": "人物",
    "wardrobe": "服装与配饰",
    "scene": "场景",
    "prop": "道具",
    "voice": "音频/角色声音",
    "dialogue": "音频/对白",
    "ambience": "音频/环境声",
    "sfx": "音频/音效",
    "music": "音频/配乐",
    "motion": "动作与白模",
    "camera": "摄影参考",
    "compositing": "合成辅助",
    "graphics": "字幕与包装",
    "footage": "参考原片",
}
ENTITY_FOLDERS = {"character": "角色", "scene": "场景", "prop": "道具"}
MEDIA_TYPES = {"image", "audio", "video", "document", "project"}
STABLE_ATTRIBUTES = {"summary", "appearance", "personality", "anatomy", "scale"}


def yaml_text(data: dict) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def identifier(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", value):
        raise AutoDLError("ID/版本必须是稳定的英文数字标识，不能包含路径")
    if value.lower() in {"latest", "current"}:
        raise AutoDLError("需要明确版本，不接受latest/current")
    return value


def label_name(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or not re.search(r"[\u4e00-\u9fff]", value)
        or any(c in value for c in '/\\:*?"<>|')
        or value.endswith((".", " "))
    ):
        raise AutoDLError("名称需含中文且不能包含路径或Windows文件名特殊字符")
    return value


def _relative(path: Path, base: Path) -> str:
    return Path(os.path.relpath(path, base)).as_posix()


def _record_digest(record: dict) -> str:
    encoded = json.dumps(record, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _exclusive_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".asset-", dir=path.parent) as folder:
        staged = Path(folder) / "record"
        staged.write_text(text, encoding="utf-8", newline="\n")
        try:
            os.link(staged, path)
        except FileExistsError:
            raise AutoDLError(f"文件已存在，保留原版本：{path}") from None


def init_library(root: Path, name: str = "共享资产库") -> Path:
    root = root.resolve()
    label_name(name)
    work = (root / "projects" / name).resolve()
    if not work.is_relative_to(root / "projects"):
        raise AutoDLError("资产库必须位于本仓库projects内")
    work.mkdir(parents=True, exist_ok=True)
    entry = work / "project.yaml"
    with resource_lock(entry, root=root):
        if entry.exists():
            read_library(entry, root=root)
            return entry
        index = work / "资产索引.yaml"
        # Recover an empty index left by an interrupted init, without overwriting
        # any user-authored or already-populated catalogue.
        if index.exists():
            initial = load_yaml(index)
            if (
                initial.get("schema_version") != 1
                or initial.get("kind") != "asset_library"
                or initial.get("assets") != {}
                or initial.get("entities") != {}
            ):
                raise AutoDLError("已有未接入的资产目录，保留原文件并检查入口")
            library_id = identifier(initial.get("library_id"))
            created = None
            expected = digest_file(index)
        else:
            library_id = "LIB-" + uuid.uuid4().hex
            content = yaml_text(
                {
                    "schema_version": 1,
                    "kind": "asset_library",
                    "library_id": library_id,
                    "categories": CATEGORIES,
                    "entities": {},
                    "assets": {},
                }
            )
            _exclusive_text(index, content)
            info = index.stat()
            created = (info.st_dev, info.st_ino)
            expected = hashlib.sha256(content.encode()).hexdigest()
        try:
            _exclusive_text(
                entry,
                yaml_text(
                    {
                        "schema_version": 1,
                        "project_type": "asset_library",
                        "name": name,
                        "library_id": library_id,
                        "asset_catalog": "资产索引.yaml",
                        "documents": {},
                        "characters": {},
                        "materials_manifest": None,
                        "current": {
                            "stage": "asset_management",
                            "next_step": "登记并按版本复用素材",
                        },
                    }
                ),
            )
        except BaseException:
            # Only the just-created empty catalogue belongs to this transaction.
            _rollback_file(index, created, expected)
            raise
    return entry


def read_library(entry: Path, *, root: Path) -> tuple[Path, dict]:
    entry = entry.resolve()
    if entry.name != "project.yaml" or not entry.is_relative_to(root.resolve() / "projects"):
        raise AutoDLError("资产库必须使用projects下的project.yaml入口")
    project = load_yaml(entry)
    if project.get("project_type") != "asset_library":
        raise AutoDLError("该入口不是共享资产库")
    index = owned_path(entry.parent, project.get("asset_catalog"), root=root)
    data = load_yaml(index)
    if (
        data.get("schema_version") != 1
        or data.get("kind") != "asset_library"
        or data.get("library_id") != project.get("library_id")
    ):
        raise AutoDLError("资产库索引schema或身份不匹配")
    identifier(data.get("library_id"))
    for key in ("assets", "entities"):
        if not isinstance(data.get(key), dict):
            raise AutoDLError(f"资产库{key}必须是映射")
    return index, data


def revision_record(data: dict, section: str, item_id: str, revision: str) -> dict:
    identifier(item_id)
    identifier(revision)
    try:
        record = data[section][item_id]["revisions"][revision]
    except (KeyError, TypeError):
        raise AutoDLError(f"没有此{section}版本：{item_id}@{revision}") from None
    if not isinstance(record, dict):
        raise AutoDLError("版本记录必须为映射")
    return record


def _publish_media(source: Path, destination: Path, expected: str) -> tuple[int, int] | None:
    """Exclusive hard-link publication, same-byte reuse or cross-volume copy."""
    source = source.resolve(strict=True)
    if not source.is_file() or source.stat().st_size == 0 or digest_file(source) != expected:
        raise AutoDLError("源素材为空或与登记哈希不一致")
    if destination.exists():
        if not destination.is_file() or digest_file(destination) != expected:
            raise AutoDLError("目标已存在且内容不同，保留原文件")
        return None
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
    except FileExistsError:
        raise AutoDLError("目标被其他任务创建，未覆盖") from None
    except OSError as exc:
        if exc.errno != 18 and getattr(exc, "winerror", None) != 17:
            raise
        with tempfile.TemporaryDirectory(prefix=".asset-", dir=destination.parent) as folder:
            stage = Path(folder) / source.name
            shutil.copyfile(source, stage)
            if digest_file(stage) != expected:
                raise AutoDLError("复制期间源素材变化") from None
            os.link(stage, destination)
    info = destination.stat()
    identity = (info.st_dev, info.st_ino)
    if digest_file(destination) != expected or digest_file(source) != expected:
        _rollback_file(destination, identity, expected)
        raise AutoDLError("导入期间源素材变化，未登记")
    return identity


def _rollback_file(path: Path, identity: tuple[int, int] | None, digest: str) -> None:
    if identity is not None and path.is_file():
        current = path.stat()
        if (current.st_dev, current.st_ino) == identity and digest_file(path) == digest:
            path.unlink()


def register_asset(entry: Path, source: Path, spec: dict, *, root: Path) -> dict:
    """A new immutable file revision; no review state is inferred from file existence."""
    item_id, revision = identifier(spec.get("asset_id")), identifier(spec.get("revision"))
    name = label_name(spec.get("label"))
    category, media = spec.get("category"), spec.get("media_type")
    if (
        not isinstance(category, str)
        or category not in CATEGORIES
        or not isinstance(media, str)
        or media not in MEDIA_TYPES
    ):
        raise AutoDLError("未知资产分类或媒体类型")
    if not isinstance(spec.get("purpose"), str) or not spec["purpose"].strip():
        raise AutoDLError("资产必须明确参考用途")
    if not isinstance(spec.get("provenance"), dict) or not spec["provenance"]:
        raise AutoDLError("资产需要来源记录")
    source = source.resolve(strict=True)
    if not source.suffix or not re.fullmatch(r"\.[A-Za-z0-9]{1,10}", source.suffix):
        raise AutoDLError("保留真实、可识别的文件扩展名")
    expected = digest_file(source)
    if spec.get("sha256") is not None and spec["sha256"] != expected:
        raise AutoDLError("源素材与预期SHA-256不一致")
    validate_board_contract({**spec, "sha256": expected}, source, base=entry.resolve().parent)
    with resource_lock(entry, root=root):
        index, data = read_library(entry, root=root)
        group = data["assets"].get(item_id)
        if group and (group["label"] != name or group["category"] != category):
            raise AutoDLError("同一资产ID不能变更分类或身份名称")
        if group and revision in group["revisions"]:
            raise AutoDLError("资产版本已存在；新增版本或复用旧版，不能覆盖")
        folder = (
            f"99-历史/来源资产/{name}"
            if spec.get("lifecycle") == "archived"
            else f"02-素材/{FOLDERS[category]}/{name}"
        )
        relative = f"{folder}/{name}-{item_id}-版本{revision}{source.suffix}"
        dest = owned_path(entry.parent, relative, root=root)
        record = copy.deepcopy(spec)
        record.update(
            path=relative,
            sha256=expected,
            size_bytes=source.stat().st_size,
            registered_at=utc_now(),
        )
        record.setdefault("technical", {"status": "unverified"})
        record.setdefault("review", {"status": "unreviewed", "evidence": []})
        record.setdefault("rights", {"status": "unknown", "source": None})
        record.setdefault("tags", [])
        record.setdefault("derived_from", [])
        # Reuse an existing same-byte library file even when source is another copy.
        duplicate = next(
            (
                r
                for g in data["assets"].values()
                for r in g["revisions"].values()
                if r["sha256"] == expected
            ),
            None,
        )
        if duplicate:
            source = owned_path(entry.parent, duplicate["path"], root=root)
        created = _publish_media(source, dest, expected)
        try:
            group = data["assets"].setdefault(
                item_id,
                {
                    "label": name,
                    "category": category,
                    "revisions": {},
                },
            )
            group["revisions"][revision] = record
            atomic_text(index, yaml_text(data))
        except BaseException:
            _rollback_file(dest, created, expected)
            raise
        return record


def register_entity(entry: Path, profile: dict, *, root: Path) -> dict:
    profile = dict(profile)
    entity_id = identifier(profile.get("entity_id"))
    revision = identifier(profile.get("revision"))
    name = label_name(profile.get("label"))
    category = profile.get("category")
    if (
        not isinstance(category, str)
        or category not in ENTITY_FOLDERS
        or type(profile.get("schema_version")) is not int
        or profile["schema_version"] != 1
    ):
        raise AutoDLError("实体需为角色、场景或道具的schema 1档案")
    with resource_lock(entry, root=root):
        index, data = read_library(entry, root=root)
        existing = data["entities"].get(entity_id)
        if existing and (existing["category"] != category or existing["label"] != name):
            raise AutoDLError("全局身份ID已属于另一个实体")
        if existing and revision in existing["revisions"]:
            raise AutoDLError("实体版本已存在，不可覆盖")
        if category == "character":
            profile["language"] = language_code(profile.get("language", "en"))
            if not isinstance(profile.get("attributes"), dict):
                raise AutoDLError("角色需要固定属性映射，未知属性可为null")
            looks = profile.get("looks")
            if not isinstance(looks, dict) or not looks:
                raise AutoDLError("角色至少登记一个明确造型")
            voices = profile.get("voice_profiles", {})
            if (
                any(
                    not isinstance(look, dict) or not isinstance(look.get("board"), dict)
                    for look in looks.values()
                )
                or not isinstance(voices, dict)
                or any(
                    not isinstance(voice, dict) or not isinstance(voice.get("sample"), dict)
                    for voice in voices.values()
                )
            ):
                raise AutoDLError("造型需board引用，声线需sample引用")
            refs = [(look["board"], "image") for look in looks.values()]
            refs += [(voice["sample"], "audio") for voice in voices.values()]
            for ref, media in refs:
                asset = revision_record(data, "assets", ref.get("asset_id"), ref.get("revision"))
                if asset.get("entity_id") != entity_id or asset["media_type"] != media:
                    raise AutoDLError("角色引用素材的全局身份或媒体类型不匹配")
                if media == "image":
                    if asset.get("purpose") != "identity_board":
                        raise AutoDLError("A character look requires a reviewed identity board")
                    validate_board_contract(
                        asset, owned_path(entry.parent, asset["path"], root=root), base=entry.parent
                    )
        relative = f"01-文档/{ENTITY_FOLDERS[category]}/{name}-{entity_id}-版本{revision}.yaml"
        dest = owned_path(entry.parent, relative, root=root)
        content = yaml_text(profile)
        expected = hashlib.sha256(content.encode()).hexdigest()
        if dest.exists():
            if digest_file(dest) != expected:
                raise AutoDLError("实体版本文件已存在且不同，保留原稿")
            created = None
        else:
            _exclusive_text(dest, content)
            info = dest.stat()
            created = (info.st_dev, info.st_ino)
        try:
            record = {"path": relative, "sha256": expected, "registered_at": utc_now()}
            data["entities"].setdefault(
                entity_id,
                {
                    "label": name,
                    "category": category,
                    "revisions": {},
                },
            )["revisions"][revision] = record
            atomic_text(index, yaml_text(data))
        except BaseException:
            _rollback_file(dest, created, expected)
            raise
        return record


def _manifest(project_file: Path, root: Path) -> Path:
    project = load_yaml(project_file)
    if project.get("project_type") == "asset_library":
        raise AutoDLError("使用素材的目标必须是制作作品")
    return owned_path(project_file.parent, project.get("materials_manifest"), root=root)


def import_asset(
    entry: Path,
    item_id: str,
    revision: str,
    project_file: Path,
    local_id: str,
    *,
    root: Path,
    destination: str | None = None,
    kind: str | None = None,
) -> dict:
    identifier(local_id)
    entry, project_file = entry.resolve(), project_file.resolve()
    if project_file.name != "project.yaml" or entry == project_file:
        raise AutoDLError("导入需要另一个制作作品的project.yaml")
    # Library revisions are immutable; do not acquire its lock while holding a
    # project lock. Every project writer locks project first, manifest second.
    _, catalogue = read_library(entry, root=root)
    record = revision_record(catalogue, "assets", item_id, revision)
    if record["media_type"] not in {"image", "audio", "video"}:
        raise AutoDLError("制作清单目前只接收图片/音频/视频；工程保留在资产库按用途引用")
    source = owned_path(entry.parent, record["path"], root=root)
    with resource_lock(project_file, root=root):
        manifest = _manifest(project_file, root)
        with resource_lock(manifest, root=root):
            data = load_yaml(manifest)
            previous = data.setdefault("assets", {}).get(local_id, {})
            pin = previous.get("library_ref")
            if pin and (pin.get("asset_id"), pin.get("revision"), pin.get("library_id")) != (
                item_id,
                revision,
                catalogue["library_id"],
            ):
                raise AutoDLError("本地资产ID已锁定另一版本；新版本使用新的本地ID")
            if previous.get("sha256") not in (None, record["sha256"]):
                raise AutoDLError("不能用不同内容覆盖本作品已有素材")
            if destination is None:
                old = manifest.parent / previous.get("path", "")
                if previous.get("path") and old.resolve().is_relative_to(project_file.parent):
                    destination = _relative(old.resolve(), project_file.parent)
                else:
                    destination = record["path"]
            dest = owned_path(project_file.parent, destination, root=root)
            if not dest.is_relative_to(project_file.parent / "02-素材"):
                raise AutoDLError("导入媒体必须位于本作品02-素材内")
            if dest.suffix.lower() != source.suffix.lower():
                raise AutoDLError("导入须保留真实扩展名")
            label_name(dest.stem)
            if previous.get("path"):
                original = (manifest.parent / previous["path"]).resolve()
                if not original.is_file() or digest_file(original) != record["sha256"]:
                    raise AutoDLError("已有素材路径内容不同或缺失，不能静默替换")
            media_kind = record["media_type"]
            if media_kind == "image":
                media_kind = (
                    kind
                    or previous.get("kind")
                    or {
                        "character": "character",
                        "scene": "scene",
                        "prop": "prop",
                    }.get(record["category"], "keyframe")
                )
                if media_kind not in {"character", "scene", "prop", "keyframe"}:
                    raise AutoDLError("图片素材类型无效")
            elif kind and kind != media_kind:
                raise AutoDLError("kind与真实媒体类型不一致")
            created = _publish_media(source, dest, record["sha256"])
            try:
                item = dict(previous)
                item.update(
                    kind=media_kind, path=_relative(dest, manifest.parent), sha256=record["sha256"]
                )
                item.setdefault("state", "provided")
                item.setdefault("required", False)
                item.setdefault("purpose", record["purpose"])
                item["library_ref"] = {
                    "library": _relative(entry, project_file.parent),
                    "library_id": catalogue["library_id"],
                    "asset_id": item_id,
                    "revision": revision,
                    "sha256": record["sha256"],
                    "media_type": record["media_type"],
                    "entity_id": record.get("entity_id"),
                    "variant_id": record.get("variant_id"),
                    "purpose": record["purpose"],
                    "source_record_sha256": _record_digest(record),
                }
                if record.get("board_contract"):
                    contract = copy.deepcopy(record["board_contract"])
                    evidence_source = owned_path(entry.parent, contract["evidence_path"], root=root)
                    evidence_dest = owned_path(
                        project_file.parent,
                        f"05-检查与验收/角色板依据/{item_id}-{revision}.json",
                        root=root,
                    )
                    _publish_media(evidence_source, evidence_dest, contract["evidence_sha256"])
                    contract["evidence_path"] = _relative(evidence_dest, project_file.parent)
                    item["library_ref"]["board_contract"] = contract
                validate_pin(item, dest)
                data["assets"][local_id] = item
                atomic_text(manifest, yaml_text(data))
            except BaseException:
                _rollback_file(dest, created, record["sha256"])
                raise
            return item


def bind_character(
    entry: Path,
    entity_id: str,
    revision: str,
    project_file: Path,
    character_id: str,
    look_id: str,
    board_asset_id: str,
    *,
    root: Path,
    voice_profile_id: str | None = None,
    voice_asset_id: str | None = None,
) -> dict:
    entry, project_file = entry.resolve(), project_file.resolve()
    _, catalogue = read_library(entry, root=root)
    record = revision_record(catalogue, "entities", entity_id, revision)
    source = owned_path(entry.parent, record["path"], root=root)
    if digest_file(source) != record["sha256"]:
        raise AutoDLError("共享角色主档哈希不匹配")
    shared = load_yaml(source)
    if shared.get("category") != "character":
        raise AutoDLError("所选实体不是角色")
    with resource_lock(project_file, root=root):
        project = load_yaml(project_file)
        manifest = _manifest(project_file, root)
        char_path = owned_path(
            project_file.parent, project.get("characters", {}).get(character_id), root=root
        )
        with resource_lock(manifest, root=root):
            with resource_lock(char_path, root=root):
                local = load_yaml(char_path)
                local["language"] = language_code(
                    local.get("language", shared.get("language", "en"))
                )
                if local.get("character_id") != character_id:
                    raise AutoDLError("作品角色ID不匹配")
                current = local.get("library_binding")
                if current and current.get("entity_id") != entity_id:
                    raise AutoDLError("不能把既有角色静默改绑为另一个全局身份")
                snapshot = owned_path(
                    project_file.parent, f"01-文档/角色/共享版本/{source.name}", root=root
                )
                created = _publish_media(source, snapshot, record["sha256"])
                try:
                    local["library_binding"] = {
                        "library": _relative(entry, project_file.parent),
                        "library_id": catalogue["library_id"],
                        "entity_id": entity_id,
                        "revision": revision,
                        "profile": _relative(snapshot, project_file.parent),
                        "profile_sha256": record["sha256"],
                        "look_id": look_id,
                        "board_asset_id": board_asset_id,
                        "materials_manifest": _relative(manifest, project_file.parent),
                        "voice_profile_id": voice_profile_id,
                        "voice_asset_id": voice_asset_id,
                    }
                    refs = local.get("visual_references") or []
                    old_board = (current or {}).get("board_asset_id")
                    if old_board and old_board != board_asset_id:
                        refs = [
                            ref
                            for ref in refs
                            if not (isinstance(ref, dict) and ref.get("asset_id") == old_board)
                        ]
                    if not any(
                        isinstance(ref, dict) and ref.get("asset_id") == board_asset_id
                        for ref in refs
                    ):
                        refs.append(
                            {
                                "manifest": _relative(manifest, project_file.parent),
                                "asset_id": board_asset_id,
                                "purpose": "当前共享身份与所选造型参考",
                            }
                        )
                    local["visual_references"] = refs
                    attributes = local.get("attributes") or {}
                    removed = {
                        key: attributes[key] for key in STABLE_ATTRIBUTES if key in attributes
                    }
                    # Preserve former prose as a migration source, not a second active identity.
                    if removed:
                        local.setdefault("registration_history", []).append(
                            {
                                "event": "bound_shared_identity",
                                "attributes_before": removed,
                                "at": utc_now(),
                            }
                        )
                    local["attributes"] = {
                        k: v for k, v in attributes.items() if k not in STABLE_ATTRIBUTES
                    }
                    resolve_character(local, project_file.parent, root=root)
                    atomic_text(char_path, yaml_text(local))
                except BaseException:
                    _rollback_file(snapshot, created, record["sha256"])
                    raise
                return local


def list_assets(
    entry: Path, *, root: Path, category: str | None = None, query: str = ""
) -> list[dict]:
    _, data = read_library(entry, root=root)
    aliases = {}
    if query:
        for entity_id, entity in data["entities"].items():
            terms = [entity["label"]]
            for record in entity["revisions"].values():
                path = owned_path(entry.parent, record["path"], root=root)
                if path.is_file() and digest_file(path) == record["sha256"]:
                    profile = load_yaml(path)
                    terms.extend(profile.get("aliases", []))
                    terms.extend(
                        look.get("label", "") for look in profile.get("looks", {}).values()
                    )
            aliases[entity_id] = terms
    result = []
    for section in ("entities", "assets"):
        for item_id, item in data[section].items():
            if category and item["category"] != category:
                continue
            for revision, record in item["revisions"].items():
                haystack = json.dumps(
                    [
                        item_id,
                        item["label"],
                        record.get("tags", []),
                        aliases.get(
                            item_id if section == "entities" else record.get("entity_id"), []
                        ),
                    ],
                    ensure_ascii=False,
                ).casefold()
                if query.casefold() not in haystack:
                    continue
                result.append(
                    {
                        "type": section,
                        "id": item_id,
                        "revision": revision,
                        "label": item["label"],
                        "category": item["category"],
                        "path": str(entry.parent / record["path"]),
                        "sha256": record["sha256"],
                    }
                )
    return result


def check_library(entry: Path, *, root: Path) -> dict:
    _, catalogue = read_library(entry, root=root)
    rows = list_assets(entry, root=root)
    issues = []
    for row in rows:
        try:
            path = owned_path(entry.parent, row["path"], root=root)
            if not path.is_file() or digest_file(path) != row["sha256"]:
                issues.append(f"{row['id']}@{row['revision']}: 文件缺失或哈希变化")
                continue
            if row["type"] == "entities":
                profile = load_yaml(path)
                refs = list(profile.get("identity_references", []))
                refs.extend(look["board"] for look in profile.get("looks", {}).values())
                refs.extend(voice["sample"] for voice in profile.get("voice_profiles", {}).values())
                refs.extend(profile.get("views", {}).values())
            else:
                record = revision_record(catalogue, "assets", row["id"], row["revision"])
                if record.get("lifecycle") != "archived":
                    validate_board_contract(record, path, base=entry.parent)
                refs = record.get("derived_from", [])
            for ref in refs:
                if not isinstance(ref, dict):
                    raise AutoDLError("资产依赖必须为带ID和版本的映射")
                revision_record(catalogue, "assets", ref.get("asset_id"), ref.get("revision"))
        except (OSError, AutoDLError) as exc:
            issues.append(f"{row['id']}: {exc}")
    return {
        "valid": not issues,
        "revision_count": len(rows),
        "issues": issues,
        "scope": "文件/版本完整性，不代表视觉、声音或创作验收",
    }


def check_project(project_file: Path, *, root: Path) -> dict:
    from .characters import characters

    project_file = project_file.resolve()
    issues = []
    manifest = _manifest(project_file, root)
    data = load_yaml(manifest)
    selected = []
    for local_id, item in data.get("assets", {}).items():
        pin = item.get("library_ref")
        if pin is None:
            continue
        try:
            path = owned_path(project_file.parent, str(manifest.parent / item["path"]), root=root)
            validate_pin(item, path)
            selected.append({"local_id": local_id, "path": str(path), **pin})
        except (OSError, AutoDLError) as exc:
            issues.append(f"{local_id}: {exc}")
    try:
        registry = characters(project_file, root=root)
    except (OSError, AutoDLError) as exc:
        issues.append(str(exc))
        registry = {}
    return {
        "valid": not issues,
        "issues": issues,
        "assets": selected,
        "characters": {key: value.get("library_binding") for key, value in registry.items()},
        "scope": "已选共享资产路径/哈希/身份/造型绑定，不代替materials生产就绪检查",
    }


def usages(root: Path, item_id: str, *, revision: str | None = None) -> dict:
    """Inspect explicitly selected production branches; never guess an active manifest."""
    found, issues = [], []
    for project_file in sorted((root / "projects").glob("*/project.yaml")):
        try:
            project = load_yaml(project_file)
            if project.get("project_type") == "asset_library":
                continue
            if project.get("materials_manifest"):
                manifest = _manifest(project_file, root)
                data = load_yaml(manifest)
                for local_id, asset in data.get("assets", {}).items():
                    pin = asset.get("library_ref") or {}
                    if pin.get("asset_id") == item_id and (
                        revision is None or pin.get("revision") == revision
                    ):
                        found.append(
                            {
                                "project": project["name"],
                                "manifest": str(manifest),
                                "local_id": local_id,
                                "revision": pin["revision"],
                                "shots": [
                                    sid
                                    for sid, shot in data.get("shots", {}).items()
                                    if local_id in shot.get("required_assets", [])
                                    or local_id in shot.get("reference_bindings", {}).values()
                                ],
                            }
                        )
            for cid, relative in project.get("characters", {}).items():
                profile = owned_path(project_file.parent, relative, root=root)
                pin = load_yaml(profile).get("library_binding") or {}
                if pin.get("entity_id") == item_id and (
                    revision is None or pin.get("revision") == revision
                ):
                    found.append(
                        {
                            "project": project["name"],
                            "character_id": cid,
                            "profile": str(profile),
                            "revision": pin["revision"],
                        }
                    )
        except (OSError, AutoDLError) as exc:
            issues.append({"project": str(project_file), "issue": str(exc)})
    return {"uses": found, "issues": issues, "scope": "各作品明确选中的当前制作分支"}
