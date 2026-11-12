"""Publish the two visually reviewed replacements and version current character bindings."""

import argparse
import copy
import json
import os
from pathlib import Path

from PIL import Image

from autodl_video.asset_bindings import BOARD_LAYOUT, digest_file, validate_board_contract
from autodl_video.asset_cleanup import unlink_verified
from autodl_video.asset_library import (
    bind_character,
    check_project,
    import_asset,
    read_library,
    register_asset,
    register_entity,
    yaml_text,
)
from autodl_video.config import atomic_json, atomic_text, load_yaml
from autodl_video.locking import resource_lock

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "projects/共享资产库/project.yaml"


def rel(path, base):
    return Path(os.path.relpath(path, base)).as_posix()


def require(condition, message="Migration source or destination changed"):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--girl", type=Path, required=True)
    parser.add_argument("--dragon", type=Path, required=True)
    parser.add_argument("--girl-review", type=Path, required=True)
    parser.add_argument("--dragon-review", type=Path, required=True)
    args = parser.parse_args()
    definitions = [
        ("MEDIEVAL-GIRL", "MEDIEVAL-GIRL-BOARD", "05", "blue-cloak", args.girl),
        ("PINK-BABY-DRAGON", "PINK-DRAGON-BOARD", "04", "juvenile", args.dragon),
    ]
    reviews = {
        "MEDIEVAL-GIRL": args.girl_review.resolve(),
        "PINK-BABY-DRAGON": args.dragon_review.resolve(),
    }
    for entity, _, _, _, source in definitions:
        evidence = reviews[entity]
        validate_board_contract(
            {
                "purpose": "identity_board",
                "sha256": digest_file(source),
                "board_contract": {
                    "version": 1,
                    "layout": BOARD_LAYOUT,
                    "image_sha256": digest_file(source),
                    "evidence_path": rel(evidence, LIB.parent),
                    "evidence_sha256": digest_file(evidence),
                },
            },
            source,
            base=LIB.parent,
        )
    index, data = read_library(LIB, root=ROOT)
    for _, aid, revision, _, source in definitions:
        occupied = data["assets"].get(aid, {}).get("revisions", {}).get(revision)
        if occupied is not None:
            require(
                occupied.get("sha256") == digest_file(source),
                "Occupied target revision differs; create a new explicit version",
            )
    migration_record = LIB.parent / "06-记录/迁移记录/三视图替换01.json"
    project_file = ROOT / "projects/悬崖上的小气球/project.yaml"
    if migration_record.exists():
        # A completed one-shot migration is a verified no-op. Never reinterpret
        # replay as approval of later rejected images or rollback of a newer profile.
        for _, aid, revision, _, source in definitions:
            record = data["assets"].get(aid, {}).get("revisions", {}).get(revision, {})
            require(
                record.get("sha256") == digest_file(source),
                "Completed migration inputs differ; create a new explicit version",
            )
        status = check_project(project_file, root=ROOT)
        require(status["valid"], "Current selection needs attention; replay will not overwrite it")
        print(
            json.dumps(
                {
                    "already_completed": True,
                    "no_changes": True,
                    "current_manifest": load_yaml(project_file)["materials_manifest"],
                }
            )
        )
        return
    # Index path relocation is logged; image bytes and historical profile hashes stay unchanged.
    migrations = []
    with resource_lock(LIB, root=ROOT):
        data = load_yaml(index)
        for aid, group in data["assets"].items():
            if group["category"] != "character":
                continue
            for rev, record in group["revisions"].items():
                if not record["path"].startswith("02-素材/人物/"):
                    continue
                if record.get("board_contract"):
                    continue
                source = LIB.parent / record["path"]
                target = LIB.parent / "99-历史/旧人物来源" / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                require(source.resolve().is_relative_to(LIB.parent.resolve()))
                require(target.resolve().is_relative_to(LIB.parent.resolve()))
                expected = record["sha256"]
                require(digest_file(source) == expected)
                if target.exists():
                    require(digest_file(target) == expected)
                else:
                    os.link(source, target)
                migrations.append(
                    {
                        "asset_id": aid,
                        "revision": rev,
                        "old_path": record["path"],
                        "new_path": rel(target, LIB.parent),
                        "sha256": expected,
                    }
                )
                record["path"] = rel(target, LIB.parent)
                record["lifecycle"] = "archived"
        atomic_text(index, yaml_text(data))
        # Remove only obsolete active-directory aliases after the same bytes are archived.
        for move in migrations:
            source = LIB.parent / move["old_path"]
            require(digest_file(LIB.parent / move["new_path"]) == move["sha256"])
            if source.exists():
                unlink_verified(
                    source,
                    boundary=LIB.parent,
                    expected=move["sha256"],
                    keeper=LIB.parent / move["new_path"],
                )
        # Resume after an interrupted unlink (for example a read-only hard link).
        archived = {
            Path(r["path"]).name: r
            for g in data["assets"].values()
            for r in g["revisions"].values()
            if r.get("lifecycle") == "archived"
        }
        for source in (LIB.parent / "02-素材/人物").rglob("*"):
            if source.is_file() and source.name in archived:
                record = archived[source.name]
                require(digest_file(LIB.parent / record["path"]) == record["sha256"])
                unlink_verified(
                    source,
                    boundary=LIB.parent,
                    expected=record["sha256"],
                    keeper=LIB.parent / record["path"],
                )
    for entity, aid, revision, look, source in definitions:
        _, data = read_library(LIB, root=ROOT)
        if revision not in data["assets"][aid]["revisions"]:
            old = next(iter(data["assets"][aid]["revisions"].values()))
            review_path = reviews[entity]
            digest = digest_file(source)
            with Image.open(source) as im:
                dimensions = im.size
            spec = {
                "asset_id": aid,
                "revision": revision,
                "label": old["label"],
                "category": "character",
                "media_type": "image",
                "purpose": "identity_board",
                "entity_id": entity,
                "variant_id": look,
                "sha256": digest,
                "style_reference": old["style_reference"],
                "board_contract": {
                    "version": 1,
                    "layout": BOARD_LAYOUT,
                    "image_sha256": digest,
                    "evidence_path": rel(review_path, LIB.parent),
                    "evidence_sha256": digest_file(review_path),
                },
                "technical": {"width": dimensions[0], "height": dimensions[1]},
                "review": {
                    "status": "assistant_visually_verified",
                    "evidence": rel(review_path, LIB.parent),
                },
                "tags": [old["label"], "strict-three-view"],
                "provenance": {
                    "source": str(source),
                    "method": "built_in_image_gen",
                    "authorization": "user requested all shared character images remade",
                },
            }
            register_asset(LIB, source, spec, root=ROOT)
        _, data = read_library(LIB, root=ROOT)
        if "02" not in data["entities"][entity]["revisions"]:
            previous = data["entities"][entity]["revisions"]["01"]
            profile = copy.deepcopy(load_yaml(LIB.parent / previous["path"]))
            profile["revision"] = "02"
            profile["looks"][look]["board"] = {"asset_id": aid, "revision": revision}
            profile["looks"][look]["layout"] = BOARD_LAYOUT
            if entity == "MEDIEVAL-GIRL":
                profile["identity_references"] = [
                    {
                        "asset_id": aid,
                        "revision": revision,
                        "purpose": "current strict three-view identity; original face archived",
                    }
                ]
            register_entity(LIB, profile, root=ROOT)
    # Version the current manifest; submitted historical configs continue using the original.
    work = ROOT / "projects/悬崖上的小气球"
    project_file = work / "project.yaml"
    with resource_lock(project_file, root=ROOT):
        project = load_yaml(project_file)
        original = work / project["materials_manifest"]
        new = work / "素材清单-三视图更新01.yaml"
        selected = load_yaml(original)
        # Preserve a newer explicitly selected migration/test branch on replay.
        if all(
            (selected.get("assets", {}).get(cid + "-THREEVIEW", {}).get("library_ref") or {}).get(
                "revision"
            )
            == rev
            for cid, rev in (("CHAR-GIRL", "05"), ("CHAR-DRAGON", "04"))
        ):
            new = original
        if original != new:
            manifest = load_yaml(original)
            for old_id in ("CHAR-GIRL", "CHAR-DRAGON", "CHAR-GIRL-FACE"):
                if old_id in manifest["assets"]:
                    manifest["assets"][old_id].update(
                        required=False, lifecycle="archived", state="superseded"
                    )
            replacements = {
                "CHAR-GIRL": "CHAR-GIRL-THREEVIEW",
                "CHAR-DRAGON": "CHAR-DRAGON-THREEVIEW",
            }
            for shot in manifest["shots"].values():
                shot["required_assets"] = [replacements.get(a, a) for a in shot["required_assets"]]
                shot["reference_bindings"] = {
                    k: replacements.get(a, a) for k, a in shot["reference_bindings"].items()
                }
            if new.exists():
                require(
                    load_yaml(new) == manifest, "Prepared manifest differs; preserve both versions"
                )
            else:
                atomic_text(new, yaml_text(manifest))
            project["materials_manifest"] = new.name
            project.setdefault("production_selection", {})["basis"] = (
                "user_requested_strict_three_view_replacement"
            )
            candidates = project["production_selection"].setdefault("candidates", [])
            if new.name not in candidates:
                candidates.append(new.name)
            atomic_text(project_file, yaml_text(project))
    for entity, aid, revision, look, _ in definitions:
        cid = "CHAR-GIRL" if entity == "MEDIEVAL-GIRL" else "CHAR-DRAGON"
        local_id = cid + "-THREEVIEW"
        current_manifest = work / load_yaml(project_file)["materials_manifest"]
        existed = local_id in load_yaml(current_manifest)["assets"]
        import_asset(LIB, aid, revision, project_file, local_id, root=ROOT)
        if not existed:
            with resource_lock(current_manifest, root=ROOT):
                materials = load_yaml(current_manifest)
                materials["assets"][local_id].update(
                    state="ready",
                    assistant_review="hash_bound_exact_three_view_review_passed",
                    user_review="existing_identity_reformat_requested_no_new_user_confirmation",
                )
                atomic_text(current_manifest, yaml_text(materials))
        character_file = work / load_yaml(project_file)["characters"][cid]
        binding = load_yaml(character_file).get("library_binding") or {}
        if binding.get("revision") not in {None, "01"}:
            continue
        bind_character(
            LIB,
            entity,
            "02",
            project_file,
            cid,
            look,
            local_id,
            root=ROOT,
            voice_profile_id="sweet-slow" if cid == "CHAR-GIRL" else None,
            voice_asset_id="VOICE-GIRL" if cid == "CHAR-GIRL" else None,
        )
    # Publish navigation only after all new versions can resolve.
    with resource_lock(LIB, root=ROOT):
        index, data = read_library(LIB, root=ROOT)
        for entity, aid, revision, _, _ in definitions:
            data["entities"][entity]["current_revision"] = "02"
            data["assets"][aid]["current_revision"] = revision
        atomic_text(index, yaml_text(data))
    if not migrations and migration_record.exists():
        migrations = json.loads(migration_record.read_text("utf-8")).get("archived", [])
    atomic_json(
        migration_record,
        {
            "archived": migrations,
            "new_versions": [
                {"entity_id": x[0], "asset_id": x[1], "revision": x[2]} for x in definitions
            ],
        },
    )
    print(
        json.dumps(
            {
                "replaced": 2,
                "archived_source_images": len(migrations),
                "current_manifest": str(new),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
