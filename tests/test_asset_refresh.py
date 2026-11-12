import json
import runpy
import sys
from pathlib import Path

import pytest
import yaml

from autodl_video.asset_bindings import BOARD_CHECKS, BOARD_LAYOUT, digest_file


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


@pytest.mark.parametrize("completed,mismatch", [(True, False), (False, True)])
def test_completed_refresh_preserves_rejection_and_advanced_profile(
    tmp_path, monkeypatch, completed, mismatch
):
    library = tmp_path / "projects/共享资产库"
    entry = library / "project.yaml"
    save(
        entry,
        {
            "project_type": "asset_library",
            "library_id": "TEST-LIB",
            "asset_catalog": "资产索引.yaml",
        },
    )
    assets = {}
    arguments = []
    for role, aid, revision in (
        ("girl", "MEDIEVAL-GIRL-BOARD", "05"),
        ("dragon", "PINK-DRAGON-BOARD", "04"),
    ):
        image = library / (role + ".png")
        image.write_bytes(b"fixture-image-" + role.encode())
        review = library / "05-检查与验收" / (role + ".json")
        review.parent.mkdir(parents=True, exist_ok=True)
        review.write_text(
            json.dumps(
                {
                    "image_sha256": digest_file(image),
                    "layout": BOARD_LAYOUT,
                    "reviewed_by": "assistant",
                    "verdict": "passed",
                    "checks": dict.fromkeys(BOARD_CHECKS, True),
                }
            ),
            encoding="utf-8",
        )
        assets[aid] = {
            "label": role,
            "category": "character",
            "revisions": {revision: {"path": image.name, "sha256": digest_file(image)}},
        }
        arguments.extend(["--" + role, str(image), "--" + role + "-review", str(review)])
    save(
        library / "资产索引.yaml",
        {
            "schema_version": 1,
            "kind": "asset_library",
            "library_id": "TEST-LIB",
            "entities": {},
            "assets": assets,
        },
    )
    record = library / "06-记录/迁移记录/三视图替换01.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    if completed:
        record.write_text('{"completed": true}', encoding="utf-8")
    if mismatch:
        incoming = tmp_path / "incoming-girl.png"
        incoming.write_bytes(b"different-reviewed-incoming-image")
        incoming_review = library / "05-检查与验收/incoming-girl.json"
        proof = json.loads(Path(arguments[3]).read_text("utf-8"))
        proof["image_sha256"] = digest_file(incoming)
        incoming_review.write_text(json.dumps(proof), encoding="utf-8")
        arguments[1], arguments[3] = str(incoming), str(incoming_review)
    work = tmp_path / "projects/悬崖上的小气球"
    save(
        work / "project.yaml",
        {
            "name": "作品",
            "materials_manifest": "newer.yaml",
            "characters": {"GIRL": "01-文档/角色/女孩.yaml"},
        },
    )
    save(
        work / "newer.yaml", {"assets": {"BOARD": {"state": "rejected", "user_review": "rejected"}}}
    )
    save(
        work / "01-文档/角色/女孩.yaml",
        {
            "schema_version": 1,
            "character_id": "GIRL",
            "label": "女孩",
            "attributes": {"appearance": "newer profile 03"},
        },
    )
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    main = runpy.run_path(str(Path(__file__).parents[1] / "tools/刷新共享三视图.py"))["main"]
    monkeypatch.setitem(main.__globals__, "ROOT", tmp_path)
    monkeypatch.setitem(main.__globals__, "LIB", entry)
    monkeypatch.setattr(sys, "argv", ["refresh", *arguments])
    if mismatch:
        with pytest.raises(RuntimeError, match="Occupied target revision differs"):
            main()
    else:
        main()
    assert all(path.read_bytes() == content for path, content in before.items())
