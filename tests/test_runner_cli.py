import json

import httpx
import pytest
import yaml

from autodl_video.cli import main
from autodl_video.client import AutoDLClient
from autodl_video.errors import AutoDLError, SubmissionUncertain
from autodl_video.runner import VideoProject


def test_dry_run_is_offline_and_has_no_state(project, config, monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("dry run made a network request or loaded the Token")

    monkeypatch.setattr("autodl_video.runner.AutoDLClient", fail)
    monkeypatch.setattr("autodl_video.runner.load_token", fail)
    result = VideoProject(project).generate(config, dry_run=True)
    assert result["dry_run"] is True
    assert result["estimated_max_cost_cny"] == "0.04"
    assert not (project / ".autodl").exists()


@pytest.mark.parametrize(
    "change",
    [
        {"max_cost_cny": 0.01},
        {"timeout": 0},
        {"poll_interval": True},
        {"output_dir": ""},
        {"typo": 1},
    ],
)
def test_config_and_budget_fail_before_submit(project, config, change):
    data = yaml.safe_load(config.read_text("utf-8"))
    data.update(change)
    config.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(AutoDLError):
        VideoProject(project).generate(config, dry_run=True)
    assert not (project / ".autodl").exists()


def fake_clients(monkeypatch, detail, handler):
    def factory(token=""):
        return AutoDLClient(token, transport=httpx.MockTransport(handler), read_retries=0)

    monkeypatch.setattr("autodl_video.runner.AutoDLClient", factory)


def test_paid_preflight_submission_persist_wait_and_download(project, config, detail, monkeypatch):
    seen = []

    def handler(request):
        seen.append(request)
        if "/workflows/" in request.url.path:
            assert "authorization" not in request.headers
            data = detail
        elif request.method == "POST":
            body = json.loads(request.content)
            assert "workflow_id" not in body and "inputs" not in body
            assert body["duration"] == 1
            data = {"task_id": "task-1", "status": "QUEUED"}
        else:
            # The task ID was persisted before even the first query.
            assert (project / ".autodl/tasks/task-1.json").exists()
            data = {
                "task_id": "task-1",
                "status": "completed",
                "results": [{"url": "https://cdn.example.org/result.mp4"}],
            }
        return httpx.Response(200, json={"code": "Success", "data": data})

    fake_clients(monkeypatch, detail, handler)
    monkeypatch.setattr(
        "autodl_video.runner.download_results",
        lambda data, destination: [destination / "task-1.mp4"],
    )
    project_api = VideoProject(project)
    result = project_api.generate(config)
    assert result["status"] == "COMPLETED"
    assert len(result["files"]) == 1
    assert len([r for r in seen if r.method == "POST"]) == 1
    assert project_api.store.read("task-1")["files"] == result["files"]
    attempt = json.loads(next((project / ".autodl/attempts").glob("*.json")).read_text())
    assert attempt["state"] == "SUBMITTED"
    assert "fake-test-token" not in json.dumps(attempt)
    seen.clear()
    assert project_api.resume("task-1")["task_id"] == "task-1"
    assert project_api.download("task-1")["task_id"] == "task-1"
    assert all(r.method == "GET" for r in seen)


def test_live_price_change_blocks_submission(project, config, detail, monkeypatch):
    detail["billing_config"]["minimax_h3"][0]["price"] = 200
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"code": "Success", "data": detail})

    fake_clients(monkeypatch, detail, handler)
    with pytest.raises(AutoDLError, match="exceeds budget"):
        VideoProject(project).generate(config)
    assert len(seen) == 1
    assert not (project / ".autodl").exists()


def test_uncertain_submission_is_recorded_once(project, config, detail, monkeypatch):
    posts = []

    def handler(request):
        if "/workflows/" in request.url.path:
            return httpx.Response(200, json={"code": "Success", "data": detail})
        posts.append(request)
        raise httpx.ReadTimeout("connection interrupted")

    fake_clients(monkeypatch, detail, handler)
    with pytest.raises(SubmissionUncertain):
        VideoProject(project).generate(config)
    assert len(posts) == 1
    attempt = json.loads(next((project / ".autodl/attempts").glob("*.json")).read_text())
    assert attempt["state"] == "UNCERTAIN"
    assert list((project / ".autodl").glob("tasks/*.json")) == []


def test_cli_list_template_validate_and_errors(project, config, capsys):
    prefix = ["--project", str(project)]
    assert main(prefix + ["models", "list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["workflow_id"] == "demo"
    assert main(prefix + ["models", "show", "demo"]) == 0
    assert "input_rules" in capsys.readouterr().out
    output = project / "new.yaml"
    assert main(prefix + ["models", "template", "demo", "--output", str(output)]) == 0
    assert yaml.safe_load(output.read_text("utf-8"))["workflow_id"] == "demo"
    assert main(prefix + ["models", "template", "demo", "--output", str(output)]) == 2
    assert main(prefix + ["validate", str(config)]) == 0
    assert main(prefix + ["run", str(config), "--dry-run"]) == 0
    assert main(prefix + ["task", "list"]) == 0
    assert main(prefix + ["models", "show", "missing"]) == 2
