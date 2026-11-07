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
    assert (project / "docs/models.md").exists()
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
