import runpy
import shutil
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from threading import Event

import pytest
import yaml

from autodl_video.characters import characters
from autodl_video.errors import AutoDLError


@pytest.fixture
def character_tool(tmp_path):
    repository = Path(__file__).resolve().parents[1]
    init = runpy.run_path(str(repository / "tools/角色.py"))["init_character"]
    template = tmp_path / "templates/short-drama/角色.yaml"
    template.parent.mkdir(parents=True)
    shutil.copy2(repository / "templates/short-drama/角色.yaml", template)
    work = tmp_path / "projects/测试作品"
    work.mkdir(parents=True)
    entry = work / "project.yaml"
    entry.write_text(yaml.safe_dump({
        "schema_version": 1, "name": "测试作品", "characters": {},
        "current": {"stage": "draft", "issues": ["保留原问题"]},
    }, allow_unicode=True), encoding="utf-8")
    init(entry, "EXISTING", "既有人物", root=tmp_path)
    return init, entry, tmp_path


@pytest.mark.parametrize("same_id", [False, True])
def test_character_init_serializes_reread_and_duplicate_check(character_tool, monkeypatch, same_id):
    init, entry, root = character_tool
    pending, release, second_entered = Event(), Event(), Event()
    original_write = init.__globals__["atomic_text"]
    original_lock = init.__globals__["resource_lock"]
    existing = characters(entry)["EXISTING"]

    def hold_first_write(path, text):
        if not pending.is_set():
            pending.set()
            assert release.wait(5)
        original_write(path, text)

    def observe_lock(*args, **kwargs):
        if pending.is_set():
            second_entered.set()
        return original_lock(*args, **kwargs)

    monkeypatch.setitem(init.__globals__, "atomic_text", hold_first_write)
    monkeypatch.setitem(init.__globals__, "resource_lock", observe_lock)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(init, entry, "A", "人物甲", root=root)
        assert pending.wait(5)
        second = pool.submit(init, entry, "A" if same_id else "B", "人物乙", root=root)
        try:
            assert second_entered.wait(5)
            with pytest.raises(TimeoutError):
                second.result(timeout=0.1)
        finally:
            release.set()
        first.result(timeout=5)
        if same_id:
            with pytest.raises(AutoDLError, match="人物ID已存在"):
                second.result(timeout=5)
        else:
            second.result(timeout=5)
    registry = characters(entry)
    assert set(registry) == ({"EXISTING", "A"} if same_id else {"EXISTING", "A", "B"})
    assert registry["EXISTING"] == existing
    assert registry["A"]["display_name"] is None
    assert yaml.safe_load(entry.read_text("utf-8"))["current"]["issues"] == ["保留原问题"]
    if same_id:
        assert not (entry.parent / "01-文档/角色/人物乙.yaml").exists()


@pytest.mark.parametrize("failure", [PermissionError, KeyboardInterrupt])
def test_character_init_failed_index_write_rolls_back_and_retries(
    character_tool, monkeypatch, failure,
):
    init, entry, root = character_tool
    original = entry.read_bytes()
    dest = entry.parent / "01-文档/角色/新人物.yaml"

    def fail(*_):
        raise failure("synthetic index publication failure")

    with monkeypatch.context() as scoped:
        scoped.setitem(init.__globals__, "atomic_text", fail)
        with pytest.raises(failure):
            init(entry, "NEW", "新人物", root=root)
    assert entry.read_bytes() == original
    assert not dest.exists()
    assert not list(dest.parent.glob(".character-*"))
    assert init(entry, "NEW", "新人物", root=root) == dest
    assert set(characters(entry)) == {"EXISTING", "NEW"}


def test_character_init_never_replaces_an_existing_profile(character_tool):
    init, entry, root = character_tool
    before = entry.read_bytes()
    dest = entry.parent / "01-文档/角色/既有人物.yaml"
    profile = dest.read_bytes()
    with pytest.raises(AutoDLError, match="档案文件已存在"):
        init(entry, "OTHER", "既有人物", root=root)
    assert entry.read_bytes() == before
    assert dest.read_bytes() == profile


def test_character_init_rollback_preserves_a_replacement_file(character_tool, monkeypatch):
    init, entry, root = character_tool
    before = entry.read_bytes()
    dest = entry.parent / "01-文档/角色/新人物.yaml"

    def replace_then_fail(*_):
        dest.unlink()
        dest.write_bytes(b"independent replacement")
        raise PermissionError("synthetic failure after independent replacement")

    monkeypatch.setitem(init.__globals__, "atomic_text", replace_then_fail)
    with pytest.raises(PermissionError):
        init(entry, "NEW", "新人物", root=root)
    assert entry.read_bytes() == before
    assert dest.read_bytes() == b"independent replacement"
