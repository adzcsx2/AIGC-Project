import json
import os
import stat

import pytest
import yaml

from autodl_video.asset_bindings import digest_file
from autodl_video.asset_cleanup import apply_cleanup, unlink_verified, write_plan
from autodl_video.errors import AutoDLError


def put(path, content=b"duplicate"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_cleanup_deletes_only_unreferenced_duplicates(tmp_path):
    asset = tmp_path / "projects/作品/02-素材"
    keep = put(asset / "保留.png")
    extra = put(asset / "冗余.png")
    unique = put(asset / "独有.png", b"unique")
    frame = put(asset / "000001.png")
    put(tmp_path / "docs/history.md", "keep: 保留.png".encode())
    plan_file = tmp_path / "plan.json"
    write_plan(tmp_path, plan_file)
    plan = json.loads(plan_file.read_text("utf-8"))
    assert [row["path"] for row in plan["delete"]] == [extra.relative_to(tmp_path).as_posix()]
    result = apply_cleanup(plan, root=tmp_path, journal=tmp_path / "journal.json")
    assert len(result["deleted"]) == 1
    assert keep.exists() and unique.exists() and frame.exists() and not extra.exists()


def test_new_historical_reference_blocks_stale_cleanup(tmp_path):
    asset = tmp_path / "projects/作品/02-素材"
    put(asset / "保留.png")
    put(asset / "冗余.png")
    plan_file = tmp_path / "plan.json"
    write_plan(tmp_path, plan_file)
    plan = json.loads(plan_file.read_text("utf-8"))
    put(tmp_path / ".autodl/tasks/old.json", json.dumps({"image": "冗余.png"}).encode())
    with pytest.raises(AutoDLError, match="dependencies changed"):
        apply_cleanup(plan, root=tmp_path, journal=tmp_path / "journal.json")


def test_cleanup_cannot_overwrite_existing_journal(tmp_path):
    put(tmp_path / "project.yaml", b"important")
    with pytest.raises(AutoDLError, match="new JSON journal"):
        apply_cleanup({"root": str(tmp_path)}, root=tmp_path, journal=tmp_path / "project.yaml")
    assert (tmp_path / "project.yaml").read_bytes() == b"important"


@pytest.mark.parametrize("suffix", ["json", "yaml"])
def test_escaped_supplementary_unicode_reference_is_protected(tmp_path, suffix):
    asset = tmp_path / "projects/作品/02-素材"
    put(asset / "保留.png")
    referenced = put(asset / "女孩\U0001f600.png")
    data = {"image": str(referenced)}
    encoded = json.dumps(data) if suffix == "json" else yaml.safe_dump(data)
    put(tmp_path / f".autodl/tasks/old.{suffix}", encoded.encode())
    plan_file = tmp_path / "plan.json"
    write_plan(tmp_path, plan_file)
    plan = json.loads(plan_file.read_text("utf-8"))
    assert all(row["path"] != referenced.relative_to(tmp_path).as_posix() for row in plan["delete"])


def test_readonly_duplicate_unlink_preserves_canonical_attributes(tmp_path):
    canonical = put(tmp_path / "原图.png")
    alias = tmp_path / "副本.png"
    os.link(canonical, alias)
    canonical.chmod(stat.S_IREAD)
    expected = digest_file(canonical)
    try:
        unlink_verified(alias, boundary=tmp_path, expected=expected, keeper=canonical)
        assert not alias.exists() and digest_file(canonical) == expected
        if os.name == "nt":
            assert canonical.stat().st_file_attributes & 1
    finally:
        canonical.chmod(stat.S_IWRITE | stat.S_IREAD)


def test_verified_unlink_does_not_delete_replacement_during_hash(tmp_path, monkeypatch):
    from autodl_video import asset_cleanup

    path = put(tmp_path / "副本.png")
    replacement = put(tmp_path / "唯一新图.png", b"new-unique")
    actual_hash = asset_cleanup.hashlib.file_digest
    attempts = []

    def try_replace(stream, algorithm):
        try:
            os.replace(replacement, path)
        except PermissionError:
            attempts.append("blocked")
        return actual_hash(stream, algorithm)

    expected = digest_file(path)
    monkeypatch.setattr(asset_cleanup.hashlib, "file_digest", try_replace)
    unlink_verified(path, boundary=tmp_path, expected=expected)
    assert attempts == ["blocked"] and replacement.read_bytes() == b"new-unique"


def test_keeper_change_before_protection_retains_target_bytes(tmp_path, monkeypatch):
    from autodl_video import asset_cleanup

    target = put(tmp_path / "duplicate.png")
    keeper = put(tmp_path / "keeper.png")
    original = target.read_bytes()
    expected = digest_file(target)
    actual_hash = asset_cleanup.hashlib.file_digest
    changed = []

    def change_keeper(stream, algorithm):
        result = actual_hash(stream, algorithm)
        if not changed:
            keeper.write_bytes(b"new-unique-user-image")
            changed.append(True)
        return result

    monkeypatch.setattr(asset_cleanup.hashlib, "file_digest", change_keeper)
    with pytest.raises(AutoDLError, match="keeper changed"):
        unlink_verified(target, boundary=tmp_path, expected=expected, keeper=keeper)
    assert target.read_bytes() == original
    assert keeper.read_bytes() == b"new-unique-user-image"


@pytest.mark.parametrize("hardlink", [False, True])
def test_keeper_cannot_change_during_verified_unlink(tmp_path, monkeypatch, hardlink):
    from autodl_video import asset_cleanup

    target = put(tmp_path / "duplicate.png")
    keeper = tmp_path / "keeper.png"
    if hardlink:
        os.link(target, keeper)
    else:
        put(keeper)
    expected = digest_file(target)
    actual_hash = asset_cleanup.hashlib.file_digest
    calls = []
    blocked = []

    def attempt_write(stream, algorithm):
        calls.append(1)
        if len(calls) == 2:
            try:
                keeper.write_bytes(b"new-unique-user-image")
            except PermissionError:
                blocked.append(True)
        return actual_hash(stream, algorithm)

    monkeypatch.setattr(asset_cleanup.hashlib, "file_digest", attempt_write)
    unlink_verified(target, boundary=tmp_path, expected=expected, keeper=keeper)
    assert not target.exists() and keeper.read_bytes() == b"duplicate" and blocked == [True]
