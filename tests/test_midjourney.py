import json

import httpx
import pytest
import yaml

from autodl_video.cli import main
from autodl_video.errors import AutoDLError, SubmissionUncertain, TaskFailed, TaskTimeout
from autodl_video.midjourney import MidjourneyClient, MidjourneyProject

SECRET = "dummy-proxy-secret"
TASK = "1234567890123456"


@pytest.fixture
def mj_root(tmp_path, monkeypatch):
    monkeypatch.delenv("MJ_SERVER", raising=False)
    monkeypatch.delenv("MJ_API_SECRET", raising=False)
    (tmp_path / ".env").write_text(f"MJ_API_SECRET={SECRET}\n", encoding="utf-8")
    return tmp_path


def fake_client(monkeypatch, handler, *, read_retries=0):
    monkeypatch.setattr(
        MidjourneyClient,
        "from_project",
        classmethod(
            lambda cls, root: cls(
                SECRET, transport=httpx.MockTransport(handler), read_retries=read_retries
            )
        ),
    )


def write_config(root, **values):
    path = root / "生图.yaml"
    path.write_text(yaml.safe_dump({"prompt": "银发精灵", **values}), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "server",
    [
        "http://example.com",
        "https://user:password@example.com",
        "https://example.com/mj",
        "https://example.com?key=hidden",
        "http://127.0.0.1:bad",
        "file:///tmp/proxy",
    ],
)
def test_reject_invalid_or_unencrypted_remote_origin(server):
    with pytest.raises(AutoDLError):
        MidjourneyClient(SECRET, server=server)


def test_settings_missing_secret_and_environment_precedence(mj_root, monkeypatch):
    with MidjourneyClient.from_project(mj_root) as client:
        assert str(client.http.base_url) == "http://127.0.0.1:6013"
    monkeypatch.setenv("MJ_API_SECRET", "override-secret")
    monkeypatch.setenv("MJ_SERVER", "https://example.com")
    with MidjourneyClient.from_project(mj_root) as client:
        assert client._secret == "override-secret"
    monkeypatch.delenv("MJ_API_SECRET")
    (mj_root / ".env").write_text("# 未填写\n", encoding="utf-8")
    with pytest.raises(AutoDLError, match="MJ_API_SECRET"):
        MidjourneyClient.from_project(mj_root)


def test_offline_preview_never_loads_credentials_or_network(mj_root, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("offline operation loaded a client")

    monkeypatch.setattr(MidjourneyClient, "from_project", forbidden)
    # A recognizable PNG header is enough for the existing media validator.
    image = mj_root / "角色-银发法师.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    path = write_config(mj_root, reference_images=[image.name])
    report = MidjourneyProject(mj_root).generate(path, dry_run=True)
    assert report["dry_run"] is True
    assert "local file" in report["reference_images"][0]
    assert "base64," not in json.dumps(report)
    assert not (mj_root / ".autodl").exists()
    assert main(["--project", str(mj_root), "mj", "validate", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["dry_run"]
    assert main(["--project", str(mj_root), "mj", "run", str(path), "--dry-run"]) == 0


@pytest.mark.parametrize(
    "values",
    [
        {"prompt": ""},
        {"reference_images": "角色.png"},
        {"reference_images": ["https://example.com/image.png"]},
        {"reference_images": ["不存在.png"]},
        {"timeout": False},
        {"poll_interval": float("inf")},
        {"output_dir": "assets/双精灵对决"},
        {"output_dir": ""},
        {"unexpected": "value"},
    ],
)
def test_invalid_config_blocked_offline(mj_root, values):
    with pytest.raises(AutoDLError):
        MidjourneyProject(mj_root).generate(write_config(mj_root, **values), dry_run=True)


def test_protocol_headers_payload_id_persistence_and_get_only_resume(mj_root, monkeypatch, capsys):
    posts = []
    seen = []
    project = MidjourneyProject(mj_root)
    image = mj_root / "角色.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")

    def handler(request):
        seen.append(request)
        assert request.headers["mj-api-secret"] == SECRET
        assert "authorization" not in request.headers
        if request.method == "POST":
            body = json.loads(request.content)
            posts.append(body)
            assert body["base64Array"][0].startswith("data:image/png;base64,")
            assert body["notifyHook"] == ""
            assert body["state"]
            return httpx.Response(200, json={"code": 22, "result": TASK})
        assert project.store.read(TASK)["response"]["status"] in {"SUBMITTED", "SUCCESS"}
        return httpx.Response(
            200, json={"id": TASK, "status": "SUCCESS", "imageUrl": "https://cdn.example/a.png"}
        )

    fake_client(monkeypatch, handler)
    monkeypatch.setattr(
        "autodl_video.midjourney.download_results",
        lambda data, destination: [destination / "原始图片.png"],
    )
    path = write_config(mj_root, reference_images=[image.name])
    result = project.generate(path)
    assert result["status"] == "SUCCESS"
    assert len(posts) == 1
    attempt = json.loads(next((mj_root / ".autodl/midjourney/attempts").glob("*.json")).read_text())
    assert attempt["state"] == "SUBMITTED"
    assert SECRET not in json.dumps(attempt)
    assert not (mj_root / ".autodl/tasks").exists()
    seen.clear()
    assert project.resume(TASK)["task_id"] == TASK
    assert project.download(TASK)["files"]
    assert all(request.method == "GET" for request in seen)
    prefix = ["--project", str(mj_root), "mj"]
    assert main(prefix + ["status", TASK]) == 0
    capsys.readouterr()
    assert main(prefix + ["list"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["task_id"] == TASK
    assert main(prefix + ["wait", TASK]) == 0
    capsys.readouterr()
    assert main(prefix + ["download", TASK]) == 0


@pytest.mark.parametrize("operation", ["U2", "V4", "R"])
def test_explicit_change_and_existing_task_code(mj_root, monkeypatch, operation):
    seen = []

    def handler(request):
        seen.append(request)
        assert request.url.path == "/mj/submit/simple-change"
        assert json.loads(request.content)["content"] == f"{TASK} {operation}"
        return httpx.Response(200, json={"code": 21, "result": TASK})

    fake_client(monkeypatch, handler)
    result = MidjourneyProject(mj_root).change(TASK, operation, wait=False)
    assert result["task_id"] == TASK
    assert len(seen) == 1
    with pytest.raises(AutoDLError):
        MidjourneyProject(mj_root).change(TASK, "U5")


@pytest.mark.parametrize(
    "failure", ["timeout", "500", "408", "redirect", "html", "list", "no-id", "bool-code"]
)
def test_uncertain_submission_never_retried_and_is_recorded(mj_root, monkeypatch, failure):
    calls = []

    def handler(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("connection lost")
        if failure in {"500", "408"}:
            return httpx.Response(int(failure))
        if failure == "redirect":
            return httpx.Response(303, headers={"Location": "https://unrelated.example/new-task"})
        if failure == "html":
            return httpx.Response(200, text="not json")
        body = {"list": [], "no-id": {"code": 1}, "bool-code": {"code": True, "result": TASK}}
        return httpx.Response(200, json=body[failure])

    fake_client(monkeypatch, handler, read_retries=3)
    with pytest.raises(SubmissionUncertain):
        MidjourneyProject(mj_root).generate(write_config(mj_root))
    assert len(calls) == 1
    attempt = json.loads(next((mj_root / ".autodl/midjourney/attempts").glob("*.json")).read_text())
    assert attempt["state"] == "UNCERTAIN"
    assert not (mj_root / ".autodl/midjourney/tasks").exists()


def test_rejection_is_redacted_and_recorded(mj_root, monkeypatch):
    fake_client(
        monkeypatch,
        lambda request: httpx.Response(
            200, json={"code": 23, "description": f"full {SECRET} data:image/png;base64,hidden"}
        ),
    )
    with pytest.raises(AutoDLError) as error:
        MidjourneyProject(mj_root).generate(write_config(mj_root))
    assert SECRET not in str(error.value)
    assert "base64,hidden" not in str(error.value)
    attempt = json.loads(next((mj_root / ".autodl/midjourney/attempts").glob("*.json")).read_text())
    assert attempt["state"] == "REJECTED"


def test_task_store_failure_keeps_submitted_id_and_never_resubmits(mj_root, monkeypatch):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"code": 1, "result": TASK})

    def cannot_save(*args, **kwargs):
        raise OSError("task directory unavailable")

    fake_client(monkeypatch, handler)
    project = MidjourneyProject(mj_root)
    monkeypatch.setattr(project.store, "save", cannot_save)
    with pytest.raises(AutoDLError, match=TASK):
        project.generate(write_config(mj_root))
    assert len(seen) == 1
    attempt = json.loads(next((mj_root / ".autodl/midjourney/attempts").glob("*.json")).read_text())
    assert attempt["state"] == "SUBMITTED" and attempt["task_id"] == TASK


def test_get_retries_and_redirect_does_not_forward_secret(monkeypatch):
    monkeypatch.setattr("autodl_video.midjourney.time.sleep", lambda seconds: None)
    seen = []

    def handler(request):
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json=[])

    with MidjourneyClient(SECRET, transport=httpx.MockTransport(handler)) as client:
        assert client.doctor()["代理任务记录数"] == 0
    assert len(seen) == 2
    seen.clear()

    def redirect(request):
        seen.append(request)
        return httpx.Response(302, headers={"Location": "https://unrelated.example/steal"})

    with MidjourneyClient(SECRET, transport=httpx.MockTransport(redirect)) as client:
        with pytest.raises(AutoDLError, match="302"):
            client.doctor()
    assert len(seen) == 1


@pytest.mark.parametrize(
    "body", [None, {"id": "wrong", "status": "SUCCESS"}, {"id": TASK, "status": "unknown"}]
)
def test_missing_or_mismatched_task_never_becomes_new_job(body):
    with MidjourneyClient(
        SECRET, transport=httpx.MockTransport(lambda req: httpx.Response(200, json=body))
    ) as client:
        with pytest.raises(AutoDLError):
            client.query(TASK)


def test_polling_pending_failure_timeout_and_invalid_timing(monkeypatch):
    monkeypatch.setattr("autodl_video.midjourney.time.sleep", lambda seconds: None)
    statuses = iter(["NOT_START", "SUBMITTED", "IN_PROGRESS", "SUCCESS"])

    def handler(request):
        return httpx.Response(200, json={"id": TASK, "status": next(statuses)})

    with MidjourneyClient(SECRET, transport=httpx.MockTransport(handler)) as client:
        assert client.wait(TASK)["status"] == "SUCCESS"
        with pytest.raises(AutoDLError):
            client.wait(TASK, poll_interval=False)
    with MidjourneyClient(
        SECRET,
        transport=httpx.MockTransport(
            lambda req: httpx.Response(
                200, json={"id": TASK, "status": "FAILURE", "failReason": SECRET}
            )
        ),
    ) as client:
        with pytest.raises(TaskFailed) as error:
            client.wait(TASK)
        assert SECRET not in str(error.value)
    clock = iter([0, 1])
    monkeypatch.setattr("autodl_video.midjourney.time.monotonic", lambda: next(clock))
    with MidjourneyClient(
        SECRET,
        transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json={"id": TASK, "status": "IN_PROGRESS"})
        ),
    ) as client:
        with pytest.raises(TaskTimeout, match="autodl mj wait"):
            client.wait(TASK, timeout=0.1)


def test_doctor_cli_is_get_only(mj_root, monkeypatch, capsys):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=[])

    fake_client(monkeypatch, handler)
    assert main(["--project", str(mj_root), "mj", "doctor"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["代理任务记录数"] == 0
    assert len(seen) == 1 and seen[0].method == "GET"
