"""用户批准的中世纪角色/悬崖作品资产接入；默认预览，--apply执行一次可恢复迁移。"""

import argparse
import hashlib
import json
import struct
import wave
from pathlib import Path

from autodl_video.asset_bindings import digest_file
from autodl_video.asset_library import (
    bind_character,
    check_library,
    check_project,
    import_asset,
    init_library,
    read_library,
    register_asset,
    register_entity,
    yaml_text,
)
from autodl_video.config import atomic_json, atomic_text, load_yaml
from autodl_video.errors import AutoDLError
from autodl_video.locking import resource_lock

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "projects/悬崖上的小气球"
ENTRY = WORK / "project.yaml"
REPORT = WORK / "06-记录/资产管理/共享资产接入-20261111.json"
BACKUP = WORK / "99-历史/共享资产接入前-20261111"


def relative(path):
    return path.resolve().relative_to(ROOT).as_posix()


def evidence(path):
    return {"path": relative(path), "sha256": digest_file(path)}


def technical(path):
    result = {"status": "file_hash_verified_not_sensory_review"}
    if path.suffix.lower() == ".png":
        with path.open("rb") as stream:
            head = stream.read(24)
        if head.startswith(b"\x89PNG\r\n\x1a\n"):
            result["width"], result["height"] = struct.unpack(">II", head[16:24])
    if path.suffix.lower() == ".wav":
        with wave.open(str(path), "rb") as audio:
            result.update(
                sample_rate=audio.getframerate(),
                channels=audio.getnchannels(),
                duration=audio.getnframes() / audio.getframerate(),
            )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    project = load_yaml(ENTRY)
    manifest = WORK / project["materials_manifest"]
    materials = load_yaml(manifest)
    girl_path = WORK / project["characters"]["CHAR-GIRL"]
    dragon_path = WORK / project["characters"]["CHAR-DRAGON"]
    girl = load_yaml(girl_path)
    roof = ROOT / "projects/一小片屋檐"
    roof_project = load_yaml(roof / "project.yaml")
    roof_materials = load_yaml(roof / roof_project["materials_manifest"])
    root_girl = load_yaml(roof / roof_project["characters"]["CHAR-GIRL"])
    tree = ROOT / "projects/巨树下的拥抱"
    tree_project = load_yaml(tree / "project.yaml")
    root_dragon = load_yaml(tree / tree_project["characters"]["CHAR-DRAGON"])
    style = ROOT / "docs/视觉规范/中世纪写实风格规范.md"
    style_ref = {
        "path_base": "repository",
        **evidence(style),
        "role": "source_style_only_current_work_uses_project_documents_style",
    }
    mapping = {
        "CHAR-GIRL": (
            "MEDIEVAL-GIRL-BOARD",
            "04",
            "中世纪小女孩灰蓝披风参考板",
            "character",
            "MEDIEVAL-GIRL",
            "blue-cloak",
            "identity_board",
        ),
        "CHAR-DRAGON": (
            "PINK-DRAGON-BOARD",
            "03",
            "粉色幼龙身份参考板",
            "character",
            "PINK-BABY-DRAGON",
            "juvenile",
            "identity_board",
        ),
        "SCENE-TREE": (
            "GIANT-TREE-CLEARING",
            "03",
            "巨树林间空地环境",
            "scene",
            "GIANT-TREE-LOCATION",
            None,
            "environment_and_style",
        ),
        "SCENE-CLIFF": (
            "WIND-CLIFF-WIDE",
            "02",
            "风铃崖环境总览候选",
            "scene",
            "WIND-CLIFF-LOCATION",
            None,
            "environment_candidate",
        ),
        "SCENE-VALLEY": (
            "WIND-CLIFF-VALLEY",
            "01",
            "风铃崖向下雾谷候选",
            "scene",
            "WIND-CLIFF-LOCATION",
            None,
            "environment_candidate",
        ),
        "SCENE-AERIAL": (
            "WIND-CLIFF-AERIAL",
            "01",
            "风铃崖谷外回望候选",
            "scene",
            "WIND-CLIFF-LOCATION",
            None,
            "environment_candidate",
        ),
        "VOICE-GIRL": (
            "MEDIEVAL-GIRL-VOICE",
            "02",
            "中世纪小女孩甜美英文声样",
            "voice",
            "MEDIEVAL-GIRL",
            "sweet-slow",
            "character_voice",
        ),
    }
    for local_id in mapping:
        item = materials["assets"][local_id]
        source = (manifest.parent / item["path"]).resolve()
        if digest_file(source) != item["sha256"]:
            raise AutoDLError(f"源素材哈希不一致：{local_id}")
    voice = girl["voice"]
    receipt_path = WORK / voice["approval"]["confirmation_ref"]
    receipt = json.loads(receipt_path.read_text("utf-8-sig"))
    if (
        voice["status"] != "approved"
        or receipt["character_id"] != "CHAR-GIRL"
        or receipt["sample_sha256"] != materials["assets"]["VOICE-GIRL"]["sha256"]
        or voice["approval"]["sample_sha256"] != receipt["sample_sha256"]
    ):
        raise AutoDLError("已有声音确认不完整，不建立虚假通过记录")
    if not args.apply:
        print(
            json.dumps(
                {"target": str(ENTRY), "imports": mapping, "source_hashes_verified": True},
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if REPORT.exists():
        result = check_project(ENTRY, root=ROOT)
        if not result["valid"]:
            raise AutoDLError("试点已接入但当前检查失败，请按报告定向修复")
        print(json.dumps({"already_migrated": True, "report": str(REPORT)}, ensure_ascii=False))
        return
    # Keep original bytes of the current entry, manifest and both character files.
    # Existing backups from an interrupted attempt remain the original snapshot.
    with resource_lock(ENTRY, root=ROOT):
        for original in (ENTRY, manifest, girl_path, dragon_path):
            target = BACKUP / original.relative_to(WORK)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                with target.open("xb") as output:
                    output.write(original.read_bytes())
    library = init_library(ROOT)

    def add_asset(source, spec):
        _, data = read_library(library, root=ROOT)
        prior = data["assets"].get(spec["asset_id"], {}).get("revisions", {}).get(spec["revision"])
        if prior:
            if (
                prior["sha256"] != digest_file(source)
                or prior.get("entity_id") != spec["entity_id"]
            ):
                raise AutoDLError("已有库版本与本次来源不同，禁止覆盖")
            return prior
        return register_asset(library, source, spec, root=ROOT)

    for local_id, values in mapping.items():
        asset_id, revision, label, category, entity_id, variant_id, purpose = values
        item = materials["assets"][local_id]
        source = (manifest.parent / item["path"]).resolve()
        review = {
            "status": item.get("user_review", "inherited_source_record"),
            "source_material_state": item["state"],
            "note": "沿用原记录，不新增实看/试听或创作验收；待审候选保持待审。",
            "source_metadata": {
                k: item[k]
                for k in ("review_basis", "acceptance_ref", "review_record", "user_review")
                if k in item
            },
        }
        spec = {
            "asset_id": asset_id,
            "revision": revision,
            "label": label,
            "category": category,
            "media_type": "audio" if category == "voice" else "image",
            "entity_id": entity_id,
            "variant_id": variant_id,
            "purpose": purpose,
            "sha256": item["sha256"],
            "style_reference": style_ref if category != "voice" else None,
            "technical": technical(source),
            "review": review,
            "tags": [label, "中世纪", "悬崖上的小气球"],
            "provenance": {
                "path_base": "repository",
                "source_path": relative(source),
                "source_manifest_snapshot": relative(BACKUP / "materials.yaml"),
                "source_asset_id": local_id,
            },
            "rights": {"status": "source_records_preserved_scope_not_reassessed"},
        }
        if category == "voice":
            spec["review"]["approval_evidence"] = evidence(receipt_path)
            spec["review"]["approval_scope"] = "CHAR-GIRL同身份已选英文声样；中文效果未实测"
            spec["derived_from"] = [
                {
                    "asset_id": "MEDIEVAL-GIRL-VOICE",
                    "revision": "01",
                    "operation": "0.85倍语速保音高，本地处理",
                }
            ]
        add_asset(source, spec)
    # Keep the original audition as a different version, not another identity.
    candidate = voice["candidates"][0]
    source = WORK / candidate["path"]
    add_asset(
        source,
        {
            "asset_id": "MEDIEVAL-GIRL-VOICE",
            "revision": "01",
            "label": "中世纪小女孩甜美英文声样",
            "category": "voice",
            "media_type": "audio",
            "entity_id": "MEDIEVAL-GIRL",
            "purpose": "character_voice",
            "variant_id": "sweet-original",
            "sha256": candidate["sha256"],
            "technical": technical(source),
            "review": {"status": "superseded_candidate_not_selected", "evidence": []},
            "provenance": {
                "path_base": "repository",
                "source_path": relative(source),
                "generation_record": relative(WORK / candidate["generation_record"]),
            },
        },
    )
    face = roof_materials["assets"]["CHAR-GIRL-FACE"]
    face_source = roof / face["path"]
    add_asset(
        face_source,
        {
            "asset_id": "MEDIEVAL-GIRL-FACE",
            "revision": "01",
            "label": "中世纪小女孩原始面部",
            "category": "character",
            "media_type": "image",
            "entity_id": "MEDIEVAL-GIRL",
            "purpose": "face_identity_only",
            "sha256": face["sha256"],
            "technical": technical(face_source),
            "review": {"status": "inherited_source_record", "note": face["review"]},
            "provenance": {
                "path_base": "repository",
                "source_path": relative(face_source),
                "source_manifest": relative(roof / roof_project["materials_manifest"]),
                "source_asset_id": "CHAR-GIRL-FACE",
            },
        },
    )

    def add_entity(profile):
        _, data = read_library(library, root=ROOT)
        prior = data["entities"].get(profile["entity_id"], {}).get("revisions", {}).get("01")
        if prior:
            expected = hashlib.sha256(yaml_text(profile).encode()).hexdigest()
            if prior["sha256"] != expected:
                raise AutoDLError("已有实体主档版本与本次来源不同")
            return
        register_entity(library, profile, root=ROOT)

    add_entity(
        {
            "schema_version": 1,
            "entity_id": "MEDIEVAL-GIRL",
            "revision": "01",
            "category": "character",
            "label": "中世纪小女孩",
            "aliases": ["少女", "小女孩", "米娅"],
            "attributes": {
                "summary": "已有中世纪少女身份，名称依作品设定",
                "appearance": root_girl["attributes"]["appearance"],
                "personality": None,
                "anatomy": "人类女孩，身体与年龄感沿用已选参考",
                "scale": None,
            },
            "performance_traits": {
                "habits": [],
                "typical_reactions": [],
                "boundaries": [],
                "status": "未建立独立的已确认性格档案，按当前剧本表演",
            },
            "style_reference": style_ref,
            "identity_references": [
                {
                    "asset_id": "MEDIEVAL-GIRL-FACE",
                    "revision": "01",
                    "purpose": "面部身份；不继承肖像衣领和背景",
                }
            ],
            "looks": {
                "blue-cloak": {
                    "label": "灰蓝披风与麻布衣",
                    "clothing": "灰蓝披风、麻布上衣、长裤及旧靴",
                    "hair": "栗色发辫",
                    "accessories": [],
                    "board": {"asset_id": "MEDIEVAL-GIRL-BOARD", "revision": "04"},
                    "layout": "legacy_accepted_board_not_reaudited_as_current_three_view",
                }
            },
            "voice_profiles": {
                "sweet-slow": {
                    "label": "已选甜美慢速英文声线",
                    "sample": {"asset_id": "MEDIEVAL-GIRL-VOICE", "revision": "02"},
                    "language": "en",
                    "approval_evidence": evidence(receipt_path),
                    "scope": "原用户选定同身份声音；中文台词与口型效果待真实输出核验",
                }
            },
            "provenance": {
                "path_base": "repository",
                "sources": [
                    evidence(roof / roof_project["characters"]["CHAR-GIRL"]),
                    evidence(tree / tree_project["characters"]["CHAR-GIRL"]),
                ],
                "unresolved": ["年龄具体数值和稳定性格未确认，不从布局身高或外观推定"],
            },
        }
    )
    add_entity(
        {
            "schema_version": 1,
            "entity_id": "PINK-BABY-DRAGON",
            "revision": "01",
            "category": "character",
            "label": "粉色幼龙",
            "aliases": ["龙宝宝", "幼龙", "咕噜"],
            "attributes": {
                "summary": "已选粉色幼体龙身份",
                "appearance": root_dragon["attributes"]["appearance"],
                "personality": None,
                "scale": root_dragon["attributes"]["scale"],
                "anatomy": "四足、两只独立背翼、一条尾巴，每足三短爪",
            },
            "performance_traits": {"habits": [], "boundaries": [], "typical_reactions": []},
            "style_reference": style_ref,
            "looks": {
                "juvenile": {
                    "label": "粉色幼体",
                    "board": {"asset_id": "PINK-DRAGON-BOARD", "revision": "03"},
                    "layout": "legacy_accepted_five_view_board",
                }
            },
            "voice_profiles": {},
            "provenance": {
                "path_base": "repository",
                "sources": [evidence(tree / tree_project["characters"]["CHAR-DRAGON"])],
                "unresolved": ["跨作品飞行能力不同，保留各作品剧情设定，不强行统一"],
            },
        }
    )
    for entity_id, label, refs, state in (
        ("GIANT-TREE-LOCATION", "巨树林间空地", ["SCENE-TREE"], "source_selected"),
        (
            "WIND-CLIFF-LOCATION",
            "风铃崖",
            ["SCENE-CLIFF", "SCENE-VALLEY", "SCENE-AERIAL"],
            "candidate_pending_user_review",
        ),
    ):
        add_entity(
            {
                "schema_version": 1,
                "entity_id": entity_id,
                "revision": "01",
                "category": "scene",
                "label": label,
                "style_reference": style_ref,
                "spatial_anchors": {"status": "依所引视觉设定和环境图，不在迁移中补造几何数值"},
                "views": {
                    local: {
                        "asset_id": mapping[local][0],
                        "revision": mapping[local][1],
                        "purpose": mapping[local][-1],
                    }
                    for local in refs
                },
                "provenance": {
                    "path_base": "repository",
                    "source_manifest": relative(manifest),
                    "state_at_registration": state,
                    "visual_setting": evidence(WORK / project["documents"]["style"]),
                },
            }
        )
    imported = {}
    for local_id, values in mapping.items():
        imported[local_id] = import_asset(library, values[0], values[1], ENTRY, local_id, root=ROOT)
    # The face is discoverable locally as an optional source; it is not silently
    # added to shots or substituted for the actual identity board.
    import_asset(library, "MEDIEVAL-GIRL-FACE", "01", ENTRY, "CHAR-GIRL-FACE", root=ROOT)
    bind_character(
        library,
        "MEDIEVAL-GIRL",
        "01",
        ENTRY,
        "CHAR-GIRL",
        "blue-cloak",
        "CHAR-GIRL",
        root=ROOT,
        voice_profile_id="sweet-slow",
        voice_asset_id="VOICE-GIRL",
    )
    bind_character(
        library,
        "PINK-BABY-DRAGON",
        "01",
        ENTRY,
        "CHAR-DRAGON",
        "juvenile",
        "CHAR-DRAGON",
        root=ROOT,
    )
    with resource_lock(ENTRY, root=ROOT):
        current = load_yaml(ENTRY)
        current["asset_library"] = "../共享资产库/project.yaml"
        current.setdefault("documents", {})["asset_handoff"] = (
            "06-记录/资产管理/新架构素材定位与接续.md"
        )
        atomic_text(ENTRY, yaml_text(current))
    result = {
        "library": check_library(library, root=ROOT),
        "project": check_project(ENTRY, root=ROOT),
    }
    if not result["library"]["valid"] or not result["project"]["valid"]:
        raise AutoDLError("迁移后完整性检查失败，保留备份与当前证据，不报告完成")
    result.update(
        backup=relative(BACKUP),
        migration_date="2026-11-11",
        authorization="当前用户yes；实施资产架构并通知指定视频规划聊天继续",
        preserved="剧本/视觉设定/当前状态/镜头槽位/待审状态/声音确认/原任务记录未改",
        sources_preserved=True,
    )
    atomic_json(REPORT, result)
    print(
        json.dumps(
            {
                "valid": True,
                "report": str(REPORT),
                "library": str(library),
                "imported": list(imported),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
