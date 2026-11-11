"""Build compact entrypoints; never infer approvals from a migration."""

import json
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def documents_from_manifest(project: Path, manifest: Path | None) -> dict[str, str]:
    """Use one selected manifest as the document version boundary; never guess by name."""
    if manifest is None:
        return {}
    project, manifest = project.resolve(), manifest.resolve()
    if not manifest.is_relative_to(project):
        raise ValueError("素材清单必须位于当前作品内")
    data = yaml.safe_load(manifest.read_text("utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("documents"), dict):
        raise ValueError(f"素材清单缺少 documents: {manifest}")
    documents = {}
    for key in ("brief", "script", "storyboard", "style"):
        item = data["documents"].get(key)
        if item is None:
            continue
        value = item.get("path") if isinstance(item, dict) else None
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"素材清单文档路径无效: {key}")
        target = (manifest.parent / value).resolve()
        if not target.is_relative_to(project) or not target.is_file():
            raise ValueError(f"素材清单文档不存在或超出当前作品: {key}")
        documents[key] = target.relative_to(project).as_posix()
    return documents


def find_materials_manifests(project: Path, files: list[Path]) -> list[Path]:
    """Discover live manifests by their contract, including Chinese filenames."""
    manifests = []
    for path in files:
        relative = path.relative_to(project)
        if path.suffix.lower() not in {".yaml", ".yml"} or "99-历史" in relative.parts:
            continue
        data = yaml.safe_load(path.read_text("utf-8-sig"))
        if (isinstance(data, dict) and isinstance(data.get("documents"), dict)
                and isinstance(data.get("assets"), dict)):
            manifests.append(path.resolve())
    return sorted(manifests)


def production_context(project: Path, manifests: list[Path], selected: Path | None = None):
    """A sole candidate is unambiguous; multiple candidates need an explicit selection.

    Selection identifies document provenance, never creative or delivery approval.
    Existing entrypoints are not passed here or rewritten by this one-time tool.
    """
    project = project.resolve()
    manifests = sorted({path.resolve() for path in manifests})
    if any(not path.is_relative_to(project) or not path.is_file() for path in manifests):
        raise ValueError("素材清单不存在或超出当前作品")
    if selected is not None:
        selected = (project / selected).resolve()
        if selected not in manifests:
            raise ValueError("显式选择不在当前作品素材清单候选中")
        basis = "explicit_selection"
    elif len(manifests) == 1:
        selected, basis = manifests[0], "only_available_manifest"
    else:
        basis = "multiple_candidates" if manifests else "no_manifest"
    return {
        "documents": documents_from_manifest(project, selected),
        "materials_manifest": selected.relative_to(project).as_posix() if selected else None,
        "production_selection": {
            "state": "selected" if selected else "unselected",
            "basis": basis,
            "candidates": [path.relative_to(project).as_posix() for path in manifests],
        },
    }


def main():
    manifest = json.loads(
        (ROOT / ".autodl/reorganization/20261110/manifest.json").read_text("utf-8")
    )
    for project in (ROOT / "projects").iterdir():
        if not project.is_dir():
            continue
        if (project / "project.yaml").exists():
            raise ValueError(f"Existing entrypoint: {project}")
        files = sorted(p for p in project.rglob("*") if p.is_file())

        def rel(p, project=project):
            return p.relative_to(project).as_posix()

        materials = find_materials_manifests(project, files)
        context = production_context(project, materials)
        own_rows = [r for r in manifest["rows"] if r["new"].startswith(f"projects/{project.name}/")]
        index = project / "06-记录/目录索引.yaml"
        write(
            index,
            {
                "schema_version": 1,
                "materials_manifests": [rel(p) for p in materials],
                "files": [rel(p) for p in files],
            },
        )
        history = project / "99-历史/迁移记录/路径映射.json"
        history.parent.mkdir(parents=True, exist_ok=True)
        history.write_text(json.dumps(own_rows, ensure_ascii=False, indent=2), encoding="utf-8")
        entry = {
            "schema_version": 1,
            "name": project.name,
            "aliases": ["elf-duel"] if project.name == "双精灵对决" else [],
            "current": {
                "stage": "imported_existing_project",
                "version": None,
                "next_step": "按本轮目标读取文档及最近验收记录；迁移不授权新生成",
                "issues": [],
            },
            **context,
            "last_accepted_delivery": None,
            "index": rel(index),
            "paths": {
                "documents": "01-文档",
                "assets": "02-素材",
                "production": "03-制作",
                "outputs": "04-输出",
                "review": "05-检查与验收",
                "records": "06-记录",
                "history": "99-历史",
            },
            "audio": {
                "generation_policy": "dialogue_only",
                "music_plan": None,
                "mix_config": None,
                "mix_result": None,
                "review": None,
            },
            "watermark": {"text": "@CallMeQueenAI", "apply_to_delivery": False},
            "migration": {
                "mapping": rel(history),
                "immutable_originals": "../../.autodl/reorganization/20261110/snapshot.json",
            },
        }
        if project.name == "一小片屋檐":
            review = next(p for p in files if p.name == "旧版九段-接缝验收-版本02.json")
            evidence = json.loads(review.read_text("utf-8"))
            entry["current"] = {
                "stage": evidence["phase"],
                "version": "旧版九段-版本02-60fps预览",
                "current_video": os.path.relpath(evidence["output"], project).replace("\\", "/"),
                "sha256": evidence["sha256"],
                "review_record": rel(review),
                "next_step": (
                    "继续时先读取音乐未通过反馈，核查干净对白来源并规划全片配乐；本轮未重混旧片"
                ),
                "issues": [
                    "用户不接受片段音乐不连续；声音未通过",
                    "动态连续观看与实际听音待复核",
                    "旧制作状态混有风格归档与预览进度，已保留来源，不视为新生成授权",
                ],
            }
            entry["audio"]["review"] = rel(review)
        if project.name == "云宫挥杆":
            entry["current"]["issues"].append(
                "一个旧引导视频因文件权限拒绝访问，迁移未处理记录已保留"
            )
        write(project / "project.yaml", entry)
        (project / "README.md").write_text(
            f"# {project.name}\n\n先读 [project.yaml](project.yaml)，"
            "再按引用读取文档、素材清单和验收记录。\n\n素材状态和输入绑定只在 materials.yaml 维护；"
            "创作正文在 01-文档，配置在 03-制作，视频在 04-输出，审片证据在 05-检查与验收。"
            "历史脚本统一归 tools/视频工具/历史脚本，仅供追溯；新处理使用统一工具。\n",
            encoding="utf-8",
        )
    print("Project entrypoints written")


if __name__ == "__main__":
    main()
