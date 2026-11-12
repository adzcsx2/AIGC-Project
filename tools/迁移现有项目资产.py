"""Consolidate existing project inputs into the library with versioned local manifests."""

import hashlib
import json
from pathlib import Path

from autodl_video.asset_bindings import digest_file
from autodl_video.asset_library import (
    import_asset,
    read_library,
    register_asset,
    yaml_text,
)
from autodl_video.config import atomic_json, atomic_text, load_yaml
from autodl_video.locking import resource_lock
from autodl_video.paths import resolve_media_path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "projects/共享资产库/project.yaml"


def main():
    report = []
    for entry in sorted((ROOT / "projects").glob("*/project.yaml")):
        project = load_yaml(entry)
        if project.get("project_type") == "asset_library" or not project.get("materials_manifest"):
            report.append({"project": entry.parent.name, "action": "kept_explicit_selection"})
            continue
        manifest = resolve_media_path(entry.parent / project["materials_manifest"], ROOT)
        data = load_yaml(manifest)
        candidates = []
        for aid, item in data.get("assets", {}).items():
            if item.get("library_ref") or not item.get("path"):
                continue
            source = resolve_media_path(manifest.parent / item["path"], ROOT)
            if not source.is_file() or not source.is_relative_to(entry.parent / "02-素材"):
                continue
            if source.suffix.lower() not in {
                ".png",
                ".jpg",
                ".jpeg",
                ".webp",
                ".wav",
                ".mp3",
                ".flac",
            }:
                continue
            candidates.append((aid, item, source))
        if not candidates:
            report.append({"project": entry.parent.name, "action": "already_located"})
            continue
        new_manifest = manifest.with_name(manifest.stem + "-资产归位01.yaml")
        with resource_lock(entry, root=ROOT):
            current = load_yaml(entry)
            if current["materials_manifest"] != project["materials_manifest"]:
                raise RuntimeError("Project selection changed during migration")
            if not new_manifest.exists():
                atomic_text(new_manifest, yaml_text(data))
            elif load_yaml(new_manifest) != data:
                raise RuntimeError("Prepared migration manifest differs; existing file preserved")
            current["materials_manifest"] = new_manifest.relative_to(entry.parent).as_posix()
            selection = current.setdefault("production_selection", {})
            choices = selection.setdefault("candidates", [project["materials_manifest"]])
            if current["materials_manifest"] not in choices:
                choices.append(current["materials_manifest"])
            atomic_text(entry, yaml_text(current))
        for aid, item, source in candidates:
            token = hashlib.sha256((entry.parent.name + "/" + aid).encode()).hexdigest()[:16]
            global_id = "MIGRATED-" + token
            kind = item.get("kind", "keyframe")
            category = {
                "character": "character",
                "scene": "scene",
                "prop": "prop",
                "audio": "dialogue",
            }.get(kind, "compositing")
            media_type = "audio" if kind == "audio" else "image"
            spec = {
                "asset_id": global_id,
                "revision": "01",
                "label": f"{entry.parent.name}-{source.stem}",
                "category": category,
                "media_type": media_type,
                "purpose": "historical_source"
                if kind == "character"
                else item.get("purpose", "project_input"),
                "provenance": {
                    "path_base": "repository",
                    "source_manifest": manifest.relative_to(ROOT).as_posix(),
                    "source_asset_id": aid,
                    "source_path": source.relative_to(ROOT).as_posix(),
                },
                "sha256": digest_file(source),
                "review": {
                    "status": "inherited_no_new_acceptance",
                    "original_state": item.get("state"),
                },
            }
            if kind == "character":
                spec["lifecycle"] = "archived"
            _, catalogue = read_library(LIB, root=ROOT)
            if global_id not in catalogue["assets"]:
                register_asset(LIB, source, spec, root=ROOT)
            else:
                if catalogue["assets"][global_id]["revisions"]["01"]["sha256"] != spec["sha256"]:
                    raise RuntimeError("Existing library revision differs from the source")
            imported = import_asset(LIB, global_id, "01", entry, aid, root=ROOT, kind=kind)
            if imported["sha256"] != spec["sha256"]:
                raise RuntimeError("Imported bytes differ from the migration source")
        # Character reference manifests follow the new selected manifest, preserving local IDs.
        for relative in project.get("characters", {}).values():
            char_file = entry.parent / relative
            character = load_yaml(char_file)
            changed = False
            for reference in character.get("visual_references", []):
                if not isinstance(reference, dict) or not reference.get("manifest"):
                    continue
                if (entry.parent / reference["manifest"]).resolve() == manifest.resolve():
                    reference["manifest"] = new_manifest.relative_to(entry.parent).as_posix()
                    changed = True
            if character.get("library_binding"):
                character["library_binding"]["materials_manifest"] = new_manifest.relative_to(
                    entry.parent
                ).as_posix()
                changed = True
            if changed:
                backup = entry.parent / "99-历史/资产归位前01" / relative
                if not backup.exists():
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    backup.write_bytes(char_file.read_bytes())
                atomic_text(char_file, yaml_text(character))
        report.append(
            {
                "project": entry.parent.name,
                "imported": len(candidates),
                "original_manifest_preserved": str(manifest),
                "manifest": str(new_manifest),
            }
        )
    destination = LIB.parent / "06-记录/迁移记录/现有项目资产归位01.json"
    atomic_json(
        destination,
        {
            "projects": report,
            "source_media_deleted": False,
            "scope": "explicitly selected inputs only; unselected branches retained",
        },
    )
    print(
        json.dumps(
            {
                "projects": len(report),
                "registered": sum(row.get("imported", 0) for row in report),
                "report": str(destination),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
