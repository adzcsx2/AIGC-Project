import hashlib
import json
import os

import httpx
import pytest

from autodl_video.catalog import get_workflow, load_catalog, sync_catalog
from autodl_video.errors import AutoDLError
from autodl_video.storage import TaskStore, download_results


def test_sync_check_and_atomic_failure(project, detail):
    class Source:
        def workflows(self):
            return [{"uuid": "demo"}]

        def workflow(self, workflow_id):
            return detail

    path = project / "catalog/workflows.yaml"
    before = path.read_bytes()
    source = Source()
    assert sync_catalog(project, source, check=True)["changed"] == []
    assert before == path.read_bytes()
    detail["description"] = "updated upstream"
    assert sync_catalog(project, source, check=True)["changed"] == ["demo"]
    assert before == path.read_bytes()
    assert sync_catalog(project, source)["total"] == 1
    assert get_workflow(project, "demo")["description"] == "updated upstream"
    assert (project / "docs/工具与接口/models.md").exists()
    before = path.read_bytes()

    def fail(_):
        raise AutoDLError("upstream unavailable")

    source.workflow = fail
    with pytest.raises(AutoDLError):
        sync_catalog(project, source)
    assert path.read_bytes() == before


def test_invalid_catalog_and_missing_workflow(tmp_path, project):
    with pytest.raises(AutoDLError, match="Unknown workflow"):
        get_workflow(project, "unknown")
    with pytest.raises(AutoDLError, match="Catalog not found"):
        load_catalog(tmp_path / "not-present")


def test_task_store_persists_updates_and_rejects_traversal(tmp_path):
    store = TaskStore(tmp_path)
    assert store.list() == []
    store.save("task-1", workflow_id="demo")
    store.save("task-1", response={"status": "RUNNING"})
    record = store.read("task-1")
    assert record["workflow_id"] == "demo"
    assert record["response"]["status"] == "RUNNING"
    assert len(store.list()) == 1
    with pytest.raises(AutoDLError):
        store.read("../../secret")
    with pytest.raises(AutoDLError):
        store.read("missing")


def test_download_does_not_leak_auth_and_handles_redirects(tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        assert "authorization" not in request.headers
        if request.url.host == "cdn.example.org":
            return httpx.Response(302, headers={"location": "https://other.example.org/video.mp4"})
        return httpx.Response(200, content=b"test-video", headers={"content-type": "video/mp4"})

    files = download_results(
        {
            "task_id": "task-1",
            "results": [
                {
                    "url": "https://cdn.example.org/video.mp4",
                    "file_type": "../../unsafe",
                    "type": "video",
                }
            ],
        },
        tmp_path,
        transport=httpx.MockTransport(handler),
    )
    assert len(requests) == 2
    assert files[0].parent == tmp_path
    assert files[0].suffix == ".mp4"
    assert files[0].read_bytes() == b"test-video"


@pytest.mark.parametrize(
    "status,content,headers",
    [
        (403, b"expired", {}),
        (200, b"", {}),
        (200, b"error page", {"content-type": "text/html"}),
        (200, b"too big", {"content-length": "1000"}),
    ],
)
def test_download_failure_never_leaves_partial_file(tmp_path, status, content, headers):
    transport = httpx.MockTransport(
        lambda _: httpx.Response(status, content=content, headers=headers)
    )
    with pytest.raises(AutoDLError):
        download_results(
            {"task_id": "task-1", "results": ["https://example.org/file.mp4"]},
            tmp_path,
            transport=transport,
            max_bytes=20,
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("results", [[], [None], [{"url": "http://example.org/file.mp4"}]])
def test_invalid_download_result(tmp_path, results):
    with pytest.raises(AutoDLError):
        download_results({"task_id": "task-1", "results": results}, tmp_path)


def test_download_matches_archives_by_content_despite_new_order_and_count(tmp_path):
    (tmp_path / "project.yaml").write_text("name: work\n", encoding="utf-8")
    archive = tmp_path / "archive"
    archive.mkdir()
    first, second = archive / "镜头甲.mp4", archive / "镜头乙.mp4"
    first.write_bytes(b"remote-first")
    second.write_bytes(b"remote-second")
    remote = [b"remote-second", b"remote-first", b"remote-new", b"remote-first"]
    requests = []

    def handler(request):
        requests.append(request)
        assert "authorization" not in request.headers
        return httpx.Response(200, content=remote[int(request.url.path[1:])])

    destination = tmp_path / "output"
    files = download_results(
        {"task_id": "task-1", "results": [f"https://cdn.example/{i}" for i in range(4)]},
        destination, transport=httpx.MockTransport(handler), existing_files=[first, second],
    )
    assert len(requests) == len(files) == 4
    assert files[:2] == [second, first]
    assert files[3] == first
    assert [p.read_bytes() for p in files] == remote
    assert list(destination.iterdir()) == [files[2]]


def test_download_recovers_missing_and_changed_files_without_overwriting(tmp_path):
    corrupt = tmp_path / "已归档.mp4"
    corrupt.write_bytes(b"damaged!")
    missing = tmp_path / "丢失.mp4"
    occupied = tmp_path / "task-1_01.mp4"
    occupied.write_bytes(b"user-edit")
    # The historical predictable temporary name may even be a hard link to a master.
    old_partial = tmp_path / "task-1_01.mp4.part"
    os.link(occupied, old_partial)
    remote = [b"original", b"second"]  # same length as corrupt, different SHA-256
    data = {
        "task_id": "task-1",
        "results": [f"https://cdn.example/{i}.mp4" for i in range(2)],
    }
    transport = httpx.MockTransport(lambda request: httpx.Response(
        200, content=remote[int(request.url.path[1])],
    ))
    files = download_results(
        data, tmp_path, transport=transport, existing_files=[corrupt, missing],
    )
    assert len(files) == 2 and [p.read_bytes() for p in files] == remote
    assert files[0].name == "task-1_01-下载恢复-版本02.mp4"
    assert files[1].name == "task-1_02.mp4"
    assert corrupt.read_bytes() == b"damaged!"
    assert occupied.read_bytes() == old_partial.read_bytes() == b"user-edit"
    assert not missing.exists()
    before = set(tmp_path.iterdir())
    assert download_results(data, tmp_path, transport=transport, existing_files=files) == files
    assert set(tmp_path.iterdir()) == before


def test_download_does_not_reuse_another_work_archive(tmp_path):
    work, nested = tmp_path / "work", tmp_path / "work/another-work"
    nested.mkdir(parents=True)
    for folder in (work, nested):
        (folder / "project.yaml").write_text("name: independent\n", encoding="utf-8")
    foreign = nested / "镜头.mp4"
    foreign.write_bytes(b"same-bytes")
    destination = work / "output"
    files = download_results(
        {"task_id": "task-1", "results": ["https://cdn.example/file.mp4"]},
        destination, existing_files=[foreign], transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b"same-bytes")
        ),
    )
    assert files == [destination / "task-1_01.mp4"]
    assert foreign.read_bytes() == files[0].read_bytes()


@pytest.mark.parametrize("patch", [{"task_id": "another-task"}, {"files": [None]}])
def test_task_archive_metadata_rejects_wrong_identity_or_invalid_paths(tmp_path, patch):
    store = TaskStore(tmp_path)
    store.save("task-1")
    record = store.directory / "task-1.json"
    record.write_text(json.dumps({"task_id": "task-1", **patch}), encoding="utf-8")
    with pytest.raises(AutoDLError, match="Invalid"):
        store.read("task-1")


def test_direct_download_resolves_destination_before_writing(project):
    work = project / "projects/工具验证"
    registry = project / ".autodl/path-map.json"
    registry.parent.mkdir()
    registry.write_text(json.dumps({
        "files": {}, "directories": {"outputs/legacy": "projects/工具验证/04-输出"},
    }), encoding="utf-8")
    saved = download_results(
        {"task_id": "direct", "results": ["https://cdn.example/result.mp4"]},
        project / "outputs/legacy", root=project,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"original")),
    )
    assert saved == [work / "04-输出/direct_01.mp4"]
    assert saved[0].read_bytes() == b"original"
    assert not (project / "outputs").exists()


def test_direct_download_publication_collision_reuses_equal_winner(tmp_path, monkeypatch):
    real_link = os.link
    calls = 0

    def collide(source, target):
        nonlocal calls
        calls += 1
        if calls == 1:
            target.write_bytes(source.read_bytes())
            raise FileExistsError("another downloader published first")
        real_link(source, target)

    monkeypatch.setattr("autodl_video.storage.os.link", collide)
    result = download_results(
        {"task_id": "race", "results": ["https://cdn.example/result.mp4"]}, tmp_path,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"original")),
    )
    assert result == [tmp_path / "race_01.mp4"]
    assert list(tmp_path.iterdir()) == result
    assert calls == 1


def test_journal_only_recovers_complete_hash_matching_files(tmp_path):
    valid = tmp_path / "完整.mp4"
    valid.write_bytes(b"complete")
    changed = tmp_path / "不完整.mp4"
    changed.write_bytes(b"comp")
    digest = hashlib.sha256(b"complete").hexdigest()
    journal = [{"path": str(path), "size": 8, "sha256": digest, "state": "pending"}
               for path in (valid, changed, tmp_path / "missing.mp4")]
    store = TaskStore(tmp_path)
    store.save("interrupted", download_journal=journal)
    record = store.read("interrupted")
    assert not record.get("files")
    assert store.recovery_files(record) == [valid]
    journal[0]["state"] = []
    store.save("interrupted", download_journal=journal)
    with pytest.raises(AutoDLError, match="Invalid download journal"):
        store.read("interrupted")
