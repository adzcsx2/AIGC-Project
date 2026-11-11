import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event

import httpx
import pytest
import yaml

from autodl_video.cli import main, template
from autodl_video.client import AutoDLClient
from autodl_video.errors import AutoDLError, SubmissionUncertain
from autodl_video.paths import ensure_project_output, project_owner, resolve_media_path
from autodl_video.runner import VideoProject
from autodl_video.storage import download_results


def test_dry_run_is_offline_and_has_no_state(project, config, monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("dry run made a network request or loaded the Token")

    monkeypatch.setattr("autodl_video.runner.AutoDLClient", fail)
    monkeypatch.setattr("autodl_video.runner.load_token", fail)
    result = VideoProject(project).generate(config, dry_run=True)
    assert result["dry_run"] is True
    assert result["estimated_max_cost_cny"] == "0.04"
    assert not (project / ".autodl").exists()


def test_default_output_belongs_to_current_work(project, config):
    work = project / 'projects/测试作品'
    work.mkdir(parents=True)
    (work / 'project.yaml').write_text('schema_version: 1\nname: 测试作品\n', encoding='utf-8')
    moved = work / '03-制作/生成配置/镜头01.yaml'
    moved.parent.mkdir(parents=True)
    data = yaml.safe_load(config.read_text('utf-8'))
    data.pop('output_dir', None)
    moved.write_text(yaml.safe_dump(data), encoding='utf-8')
    result = VideoProject(project).generate(moved, dry_run=True)
    assert result['output_dir'] == str((work/'04-输出/原始片段/镜头01').resolve())


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
        lambda data, destination, **kwargs: [destination / "task-1.mp4"],
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


def make_work(project, name="作品甲"):
    work = project / "projects" / name
    work.mkdir(parents=True)
    (work / "project.yaml").write_text(f"name: {name}\n", encoding="utf-8")
    return work


@pytest.mark.parametrize("destination", ["outputs/new", "projects/作品乙/04-输出"])
def test_owned_config_rejects_output_outside_work_before_network(
    project, config, monkeypatch, destination
):
    work = make_work(project)
    make_work(project, "作品乙")
    data = yaml.safe_load(config.read_text("utf-8"))
    data["output_dir"] = destination
    moved = work / "镜头.yaml"
    moved.write_text(yaml.safe_dump(data), encoding="utf-8")

    def forbidden(*args, **kwargs):
        pytest.fail("Output ownership must be checked before network or credentials")

    monkeypatch.setattr("autodl_video.runner.AutoDLClient", forbidden)
    monkeypatch.setattr("autodl_video.runner.load_token", forbidden)
    with pytest.raises(AutoDLError, match="输出必须"):
        VideoProject(project).generate(moved)
    data["output_dir"] = str(work / "04-输出/同作品")
    moved.write_text(yaml.safe_dump(data), encoding="utf-8")
    assert VideoProject(project).generate(moved, dry_run=True)["output_dir"] == data["output_dir"]


def test_output_helper_checks_all_owners_and_resolves_migration(project):
    work = make_work(project)
    other = make_work(project, "作品乙")
    (project / ".autodl").mkdir()
    (project / ".autodl/path-map.json").write_text(
        json.dumps({"files": {"old/shot.yaml": "projects/作品甲/镜头.yaml"}, "directories": {}}),
        encoding="utf-8",
    )
    old = project / "old/shot.yaml"
    assert project_owner(old, root=project) == work
    assert ensure_project_output(work / "new.mp4", old, root=project) == work / "new.mp4"
    with pytest.raises(AutoDLError, match="不同作品"):
        ensure_project_output(work / "new.mp4", old, other / "video.mp4", root=project)
    with pytest.raises(AutoDLError, match="输出必须"):
        ensure_project_output(other / "new.mp4", old, root=project)
    external = project / "standalone"
    assert ensure_project_output(external / "out.mp4", external / "in.mp4", root=project)


def completed_task_api(project, monkeypatch):
    data = {"task_id": "task-1", "status": "SUCCESS"}

    class CompletedClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def wait(self, *args, **kwargs):
            return data

        def query(self, *args, **kwargs):
            return data

    monkeypatch.setattr("autodl_video.runner.AutoDLClient", lambda *_: CompletedClient())
    monkeypatch.setattr("autodl_video.runner.load_token", lambda *_: "fixture-token")
    monkeypatch.setattr(
        "autodl_video.runner.download_results", lambda _, dest, **kwargs: [dest / "task-1.mp4"]
    )
    return VideoProject(project)


@pytest.mark.parametrize("action", ["resume", "download"])
def test_task_recovers_unmapped_old_directory_from_config_owner(project, monkeypatch, action):
    work = make_work(project)
    api = completed_task_api(project, monkeypatch)
    api.store.save("task-1", config_path=str(work / "镜头.yaml"), output_dir="outputs/unmapped")
    result = getattr(api, action)("task-1")
    expected = work / "04-输出/原始片段/镜头"
    assert Path(result["files"][0]).parent == expected
    assert api.store.read("task-1")["output_dir"] == str(expected)
    assert not (project / "outputs").exists()


@pytest.mark.parametrize("action", ["resume", "download"])
def test_task_maps_explicit_legacy_output_and_rejects_cross_work(
    project, monkeypatch, action
):
    work = make_work(project)
    other = make_work(project, "作品乙")
    api = completed_task_api(project, monkeypatch)
    api.store.save("task-1", config_path=str(work / "镜头.yaml"), output_dir=str(work / "04-输出"))
    (project / ".autodl/path-map.json").write_text(
        json.dumps({"files": {}, "directories": {"outputs/old": "projects/作品甲/04-输出"}}),
        encoding="utf-8",
    )
    # API output paths stay relative to its explicit repository, independent of cwd.
    monkeypatch.chdir(other)
    result = getattr(api, action)("task-1", output_dir="outputs/old")
    assert Path(result["files"][0]).parent == work / "04-输出"
    with pytest.raises(AutoDLError, match="输出必须"):
        getattr(api, action)("task-1", output_dir=other / "04-输出")


@pytest.mark.parametrize("action", ["resume", "download"])
def test_unknown_task_requires_destination_instead_of_guessing_a_work(
    project, monkeypatch, action
):
    api = completed_task_api(project, monkeypatch)
    with pytest.raises(AutoDLError, match="无法确定"):
        getattr(api, action)("task-1")
    assert not api.store.directory.exists()
    explicit = make_work(project) / "04-输出"
    assert Path(getattr(api, action)("task-1", output_dir=explicit)["files"][0]).parent == explicit


def test_template_places_inputs_with_the_output_config_work(project):
    work = make_work(project)
    output = work / "03-制作/生成配置/镜头.yaml"
    workflow = {"input_rules": {"ref_image": {"type": "image", "required": True}}}
    result = template("demo", workflow, output_path=output, root=project)
    path = (output.parent / result["inputs"]["ref_image"]).resolve()
    assert path == work / "02-素材/人物/参考图片.png"
    assert "output_dir" not in result


@pytest.mark.parametrize("kind,suffix", [("image", "png"), ("audio", "wav"), ("video", "mp4")])
def test_generation_checks_media_owners_without_a_manifest(
    project, config, monkeypatch, kind, suffix
):
    work = make_work(project)
    other = make_work(project, "作品乙")
    catalog_path = project / "catalog/workflows.yaml"
    catalog = yaml.safe_load(catalog_path.read_text("utf-8"))
    catalog["workflows"]["demo"]["input_rules"]["reference"] = {"type": kind}
    catalog_path.write_text(yaml.safe_dump(catalog), encoding="utf-8")
    media = other / f"reference.{suffix}"
    media.write_bytes(b"fixture-media")
    data = yaml.safe_load(config.read_text("utf-8"))
    data["inputs"]["reference"] = str(media)
    owned_config = work / "shot.yaml"
    owned_config.write_text(yaml.safe_dump(data), encoding="utf-8")

    def forbidden(*args, **kwargs):
        pytest.fail("Media ownership must be checked before network or credentials")

    monkeypatch.setattr("autodl_video.runner.AutoDLClient", forbidden)
    monkeypatch.setattr("autodl_video.runner.load_token", forbidden)
    api = VideoProject(project)
    with pytest.raises(AutoDLError, match="不同作品"):
        api.generate(owned_config)
    same_work = work / media.name
    same_work.write_bytes(media.read_bytes())
    data["inputs"]["reference"] = same_work.name
    owned_config.write_text(yaml.safe_dump(data), encoding="utf-8")
    assert api.generate(owned_config, dry_run=True)["dry_run"]
    # Unknown standalone sources and explicit standalone outputs remain supported.
    data["inputs"]["reference"] = str(project / media.name)
    (project / media.name).write_bytes(media.read_bytes())
    owned_config.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(AutoDLError, match="本作品"):
        api.generate(owned_config)
    standalone = project.parent / "standalone-results"
    data["output_dir"] = str(standalone)
    config.write_text(yaml.safe_dump(data), encoding="utf-8")
    assert api.generate(config, dry_run=True)["output_dir"] == str(standalone)


def test_generation_rechecks_ownership_against_live_media_rules(
    project, config, detail, monkeypatch
):
    work = make_work(project)
    other = make_work(project, "作品乙")
    media = other / "reference.png"
    media.write_bytes(b"fixture-media")
    catalog_path = project / "catalog/workflows.yaml"
    catalog = yaml.safe_load(catalog_path.read_text("utf-8"))
    catalog["workflows"]["demo"]["input_rules"]["reference"] = {"type": "string"}
    catalog_path.write_text(yaml.safe_dump(catalog), encoding="utf-8")
    detail["input_rules"]["reference"] = {"type": "image"}
    data = yaml.safe_load(config.read_text("utf-8"))
    data["inputs"]["reference"] = str(media)
    owned_config = work / "shot.yaml"
    owned_config.write_text(yaml.safe_dump(data), encoding="utf-8")
    seen = []

    def handler(request):
        seen.append(request)
        assert request.method == "GET"
        return httpx.Response(200, json={"code": "Success", "data": detail})

    fake_clients(monkeypatch, detail, handler)
    with pytest.raises(AutoDLError, match="不同作品"):
        VideoProject(project).generate(owned_config)
    assert len(seen) == 1
    assert not (project / ".autodl").exists()


@pytest.mark.parametrize("action", ["resume", "download"])
@pytest.mark.parametrize(
    "legacy", ["outputs/old", "assets/old", "输入/old", "old-results", "projects/unregistered"]
)
def test_unowned_historical_task_requires_explicit_destination(
    project, monkeypatch, action, legacy
):
    api = completed_task_api(project, monkeypatch)
    api.store.save("task-1", output_dir=legacy)
    record = (api.store.directory / "task-1.json").read_bytes()
    with pytest.raises(AutoDLError, match="无法确定"):
        getattr(api, action)("task-1")
    assert (api.store.directory / "task-1.json").read_bytes() == record
    assert not (project / legacy).exists()
    with pytest.raises(AutoDLError, match="project.yaml"):
        getattr(api, action)("task-1", output_dir=project / legacy)
    archived = make_work(project) / "04-输出"
    result = getattr(api, action)("task-1", output_dir=archived)
    assert Path(result["files"][0]).parent == archived
    assert Path(getattr(api, action)("task-1")["files"][0]).parent == archived


@pytest.mark.parametrize("action", ["resume", "download"])
def test_historical_external_standalone_destination_remains_resumable(
    project, monkeypatch, action
):
    api = completed_task_api(project, monkeypatch)
    external = project.parent / "external-standalone-output"
    api.store.save("task-1", output_dir=str(external))
    assert Path(getattr(api, action)("task-1")["files"][0]).parent == external


@pytest.mark.parametrize("destination", ["outputs/new", "old-results", "projects/unregistered"])
def test_unowned_generation_cannot_write_unowned_repository_directory(
    project, config, monkeypatch, destination
):
    data = yaml.safe_load(config.read_text("utf-8"))
    data["output_dir"] = destination
    config.write_text(yaml.safe_dump(data), encoding="utf-8")

    def forbidden(*args, **kwargs):
        pytest.fail("Repository output ownership must fail before network")

    monkeypatch.setattr("autodl_video.runner.AutoDLClient", forbidden)
    with pytest.raises(AutoDLError, match="project.yaml"):
        VideoProject(project).generate(config)
    assert not (project / ".autodl").exists()


def test_first_example_in_checkout_without_private_projects(tmp_path):
    repository = Path(__file__).resolve().parents[1]
    checkout = tmp_path / "checkout"
    for relative in (
        "pyproject.toml", "catalog/workflows.yaml", "examples/text-to-video.yaml", "tools/项目.py",
    ):
        target = checkout / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repository / relative, target)
    shutil.copytree(
        repository / "src", checkout / "src", ignore=shutil.ignore_patterns("__pycache__")
    )
    env = {**os.environ, "PYTHONPATH": str(checkout / "src"), "PYTHONUTF8": "1"}
    for key in ("AUTODL_API_KEY", "AUTODL_APIKEY", "AUTODL_TOKEN"):
        env.pop(key, None)

    def execute(*args):
        return subprocess.run(
            [sys.executable, *args], cwd=checkout, env=env,
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )

    command = ("-m", "autodl_video", "validate", "examples/text-to-video.yaml")
    before = execute(*command)
    assert before.returncode == 2 and "project.yaml" in before.stderr
    assert not (checkout / "projects").exists()
    initialized = execute("tools/项目.py", "init", "工具验证")
    assert initialized.returncode == 0, initialized.stderr
    entry = checkout / "projects/工具验证/project.yaml"
    original = entry.read_bytes()
    after = execute(*command)
    assert after.returncode == 0, after.stderr
    report = json.loads(after.stdout)
    assert report["dry_run"]
    destination = checkout / "projects/工具验证/04-输出/原始片段/文生视频样片"
    assert Path(report["output_dir"]) == destination
    assert entry.read_bytes() == original
    assert not destination.exists()
    assert not (checkout / ".autodl").exists()
    assert not (checkout / ".env").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows paths are case insensitive")
def test_windows_legacy_case_variants_resolve_files_and_directory_prefixes(project):
    work = make_work(project)
    (project / ".autodl").mkdir()
    (project / ".autodl/path-map.json").write_text(json.dumps({
        "files": {"assets/Mixed/Image.png": "projects/作品甲/图片.png"},
        "directories": {"outputs/Mixed": "projects/作品甲/04-输出"},
    }), encoding="utf-8")
    (work / "图片.png").write_bytes(b"canonical-media")
    for alias in ("ASSETS/mixed/IMAGE.PNG", "assets/MIXED/Image.png"):
        assert resolve_media_path(project / alias, project) == work / "图片.png"
    for alias in ("OUTPUTS/mixed", "outputs/MIXED"):
        assert resolve_media_path(project / alias / "新片段.mp4", project) == (
            work / "04-输出/新片段.mp4"
        )
    # Directory prefixes must still match whole components.
    unrelated = project / "OUTPUTS/MixedExtra/新片段.mp4"
    assert resolve_media_path(unrelated, project) == unrelated


@pytest.mark.parametrize("action", ["download", "resume"])
def test_migrated_task_download_reuses_verified_archive_and_honors_output_override(
    project, monkeypatch, action,
):
    work = make_work(project)
    archive = work / "04-输出/原始片段"
    archive.mkdir(parents=True)
    canonical = archive / "镜头01-云台起势-版本01.mp4"
    payload = b"downloaded-original-video"
    canonical.write_bytes(payload)
    before_stat = canonical.stat()
    (project / ".autodl").mkdir()
    (project / ".autodl/path-map.json").write_text(json.dumps({
        "files": {
            "outputs/legacy/task-1_01.mp4": canonical.relative_to(project).as_posix(),
        },
        "directories": {"outputs/legacy": archive.relative_to(project).as_posix()},
    }), encoding="utf-8")
    api = VideoProject(project)
    api.store.save("task-1", output_dir="outputs/legacy", files=["outputs/legacy/task-1_01.mp4"])
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "GET"
        return httpx.Response(200, json={"code": "Success", "data": {
            "task_id": "task-1", "status": "SUCCESS",
            "results": ["https://cdn.example/result.mp4"],
        }})

    monkeypatch.setattr(
        "autodl_video.runner.AutoDLClient",
        lambda token="": AutoDLClient(token, transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr("autodl_video.runner.load_token", lambda root: "mock-token")
    cdn_requests = []

    def cdn(request):
        cdn_requests.append(request)
        assert "authorization" not in request.headers
        return httpx.Response(200, content=payload)

    monkeypatch.setattr(
        "autodl_video.runner.download_results",
        lambda data, dest, **kwargs: download_results(
            data, dest, transport=httpx.MockTransport(cdn), **kwargs,
        ),
    )
    assert getattr(api, action)("task-1")["files"] == [str(canonical)]
    assert getattr(api, action)("task-1")["files"] == [str(canonical)]
    assert list(archive.iterdir()) == [canonical]
    assert api.store.read("task-1")["files"] == [str(canonical)]
    assert canonical.stat().st_ino == before_stat.st_ino
    assert canonical.stat().st_mtime_ns == before_stat.st_mtime_ns
    assert len(cdn_requests) == 2  # existence alone never proves result identity
    explicit = work / "04-输出/单独恢复"
    result = getattr(api, action)("task-1", output_dir=explicit)
    assert result["files"] == [str(explicit / "task-1_01.mp4")]
    assert Path(result["files"][0]).read_bytes() == canonical.read_bytes() == payload
    assert not (project / "outputs").exists()
    assert len(requests) == len(cdn_requests) == 3


def recovery_api(project, monkeypatch, response, media):
    """Real public API orchestration and storage with only HTTP/Token replaced."""
    requests = []

    def query(request):
        requests.append(request.method)
        return httpx.Response(200, json={"code": "Success", "data": response()})

    monkeypatch.setattr(
        "autodl_video.runner.AutoDLClient",
        lambda token="": AutoDLClient(token, transport=httpx.MockTransport(query)),
    )
    monkeypatch.setattr("autodl_video.runner.load_token", lambda _: "mock-token")
    monkeypatch.setattr(
        "autodl_video.runner.download_results",
        lambda data, dest, **kwargs: download_results(
            data, dest, transport=httpx.MockTransport(media), **kwargs,
        ),
    )
    return VideoProject(project), requests


@pytest.mark.parametrize("explicit", [False, True])
def test_public_download_keeps_partial_results_across_reordered_retry(
    project, monkeypatch, explicit,
):
    work = make_work(project)
    original = work / "original"
    original.mkdir()
    old = original / "旧归档.mp4"
    old.write_bytes(b"A")
    destination = work / "retry" if explicit else original
    phase = 0

    def response():
        names = ["a", "b"] if phase == 0 else ["b", "a", "c", "a"]
        return {"task_id": "partial", "status": "SUCCESS", "results": [
            f"https://cdn.example/{name}.mp4" for name in names
        ]}

    def media(request):
        if phase == 0 and request.url.path == "/b.mp4":
            return httpx.Response(403)
        return httpx.Response(200, content=request.url.path[1].upper().encode())

    api, requests = recovery_api(project, monkeypatch, response, media)
    api.store.save("partial", output_dir=str(original), files=[str(old)])
    kwargs = {"output_dir": destination} if explicit else {}
    with pytest.raises(AutoDLError, match="Download failed"):
        api.download("partial", **kwargs)
    partial = api.store.read("partial")
    assert len(partial["files"]) == 1
    assert Path(partial["files"][0]).parent == destination
    assert all(row["state"] == "published" for row in partial["download_journal"])
    phase = 1
    # No override is needed to continue an explicitly selected destination.
    result = api.download("partial")
    paths = [Path(value) for value in result["files"]]
    assert [path.read_bytes() for path in paths] == [b"B", b"A", b"C", b"A"]
    assert paths[1] == paths[3]
    assert all(path.parent == destination for path in paths)
    assert len(list(destination.iterdir())) == 3
    assert old.read_bytes() == b"A"
    assert requests == ["GET", "GET"]


@pytest.mark.parametrize("publish_first", [False, True])
def test_public_download_recovers_interrupted_publication_journal(
    project, monkeypatch, publish_first,
):
    work = make_work(project)
    destination = work / "out"
    phase = 0

    def response():
        names = ["a", "b"] if phase == 0 else ["b", "a"]
        return {"task_id": "crash", "status": "SUCCESS", "results": [
            f"https://cdn.example/{name}.mp4" for name in names
        ]}

    api, _ = recovery_api(
        project, monkeypatch, response,
        lambda request: httpx.Response(200, content=request.url.path[1].upper().encode()),
    )
    api.store.save("crash", output_dir=str(destination))
    real_link = os.link

    def interrupt(source, target):
        if publish_first:
            real_link(source, target)
        raise KeyboardInterrupt("process interrupted before progress was saved")

    with monkeypatch.context() as scoped:
        scoped.setattr("autodl_video.storage.os.link", interrupt)
        with pytest.raises(KeyboardInterrupt):
            api.download("crash")
    record = api.store.read("crash")
    assert not record.get("files")
    assert record["download_journal"][0]["state"] == "pending"
    assert len(api.store.recovery_files(record)) == int(publish_first)
    assert (destination / "crash_01.mp4").exists() == publish_first
    phase = 1
    result = api.download("crash")
    assert [Path(value).read_bytes() for value in result["files"]] == [b"B", b"A"]
    assert len(list(destination.iterdir())) == 2
    assert all(row["state"] == "published"
               for row in api.store.read("crash")["download_journal"])


def test_recovery_journal_keeps_results_when_response_count_shrinks(project, monkeypatch):
    work = make_work(project)
    names = ["a", "b"]
    api, _ = recovery_api(
        project, monkeypatch,
        lambda: {"task_id": "count", "status": "SUCCESS", "results": [
            f"https://cdn.example/{name}.mp4" for name in names
        ]},
        lambda request: httpx.Response(200, content=request.url.path[1].upper().encode()),
    )
    api.store.save("count", output_dir=str(work / "out"))
    first = api.download("count")["files"]
    names[:] = ["b"]
    assert api.download("count")["files"] == [first[1]]
    names[:] = ["b", "a"]
    assert api.download("count")["files"] == [first[1], first[0]]
    assert len(list((work / "out").iterdir())) == 2


def test_simultaneous_public_downloads_reuse_task_archive(project, monkeypatch):
    work = make_work(project)
    barrier = Barrier(2)
    responses = iter((["a", "b"], ["b", "a"]))

    def response():
        names = next(responses)
        barrier.wait(timeout=5)
        return {"task_id": "concurrent", "status": "SUCCESS", "results": [
            f"https://cdn.example/{name}.mp4" for name in names
        ]}

    api, requests = recovery_api(
        project, monkeypatch, response,
        lambda request: httpx.Response(200, content=request.url.path[1].upper().encode()),
    )
    api.store.save("concurrent", output_dir=str(work / "out"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(api.download, "concurrent") for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]
    assert set(results[0]["files"]) == set(results[1]["files"])
    assert len(list((work / "out").iterdir())) == 2
    assert requests == ["GET", "GET"]


def test_status_update_does_not_overwrite_concurrent_download_progress(project, monkeypatch):
    api = VideoProject(project)
    api.store.save("status", response={"status": "RUNNING"})
    reading, resume = Event(), Event()
    original_read = api.store.read

    def stale_read(task_id):
        record = original_read(task_id)
        if not reading.is_set():
            reading.set()
            assert resume.wait(timeout=5)
        return record

    monkeypatch.setattr(api.store, "read", stale_read)
    file = make_work(project) / "完整结果.mp4"
    file.write_bytes(b"result")
    with ThreadPoolExecutor(max_workers=2) as pool:
        status = pool.submit(api.store.save, "status", response={"status": "SUCCESS"})
        assert reading.wait(timeout=5)
        progress = pool.submit(api.store.save, "status", files=[str(file)])
        resume.set()
        status.result(timeout=5)
        progress.result(timeout=5)
    assert original_read("status")["files"] == [str(file)]
    assert original_read("status")["response"] == {"status": "SUCCESS"}


@pytest.mark.parametrize("action", ["download", "resume"])
def test_file_only_task_owner_recovers_and_rejects_foreign_override(
    project, monkeypatch, action,
):
    work, other = make_work(project), make_work(project, "作品乙")
    archive = work / "归档"
    archive.mkdir()
    file = archive / "完整结果.mp4"
    file.write_bytes(b"result")
    api, requests = recovery_api(
        project, monkeypatch,
        lambda: {"task_id": "owned", "status": "SUCCESS",
                 "results": ["https://cdn.example/result.mp4"]},
        lambda _: httpx.Response(200, content=b"result"),
    )
    api.store.save("owned", output_dir="outputs/unmapped", files=[str(file)])
    before = (api.store.directory / "owned.json").read_bytes()
    with pytest.raises(AutoDLError, match="输出必须"):
        getattr(api, action)("owned", output_dir=other / "out")
    assert requests == []
    assert (api.store.directory / "owned.json").read_bytes() == before
    assert getattr(api, action)("owned")["files"] == [str(file)]
    assert not (project / "outputs").exists()
    foreign = other / "另一个结果.mp4"
    foreign.write_bytes(b"other")
    api.store.save("owned", files=[str(file), str(foreign)])
    with pytest.raises(AutoDLError, match="不同作品"):
        getattr(api, action)("owned", output_dir=archive)
    assert len(requests) == 1
