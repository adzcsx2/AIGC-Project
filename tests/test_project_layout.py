"""Project version boundaries and path-preserving migration regressions."""

import importlib.util
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
import yaml

TOOLS = Path(__file__).resolve().parents[1] / "tools"


def load_tool(filename):
    spec = importlib.util.spec_from_file_location(filename.stem, filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


entrypoints = load_tool(TOOLS / "建立项目入口.py")
references = load_tool(TOOLS / "更新迁移引用.py")
migration = load_tool(TOOLS / "目录整理.py")
project_cli = load_tool(TOOLS / "项目.py")


def put(path, text="fixture"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_entrypoint_uses_one_manifest_instead_of_alphabetical_document_names(tmp_path, monkeypatch):
    project = tmp_path / "projects/作品"
    documents = {}
    for key, name in (("brief", "需求"), ("style", "视觉设定"), ("script", "剧本"),
                      ("storyboard", "分镜")):
        selected = put(project / f"01-文档/原版/{name}-英文版.md", f"selected {key}")
        put(project / f"01-文档/修订版/{name}.md", f"unselected {key}")
        documents[key] = {"path": selected.relative_to(project).as_posix(), "state": "ready"}
    put(project / "materials.yaml", yaml.safe_dump(
        {"documents": documents, "assets": {},
         "creative_confirmation": {"state": "confirmed", "confirmation_ref": "剧本确认"}},
        allow_unicode=True,
    ))
    put(tmp_path / ".autodl/reorganization/20261110/manifest.json", json.dumps({"rows": []}))
    script = project / documents["script"]["path"]
    before = script.read_bytes()
    monkeypatch.setattr(entrypoints, "ROOT", tmp_path)

    entrypoints.main()

    entry = yaml.safe_load((project / "project.yaml").read_text("utf-8"))
    assert entry["documents"] == {key: item["path"] for key, item in documents.items()}
    assert entry["materials_manifest"] == "materials.yaml"
    assert entry["production_selection"]["basis"] == "only_available_manifest"
    assert entry["last_accepted_delivery"] is None
    assert entry["current"]["version"] is None
    assert script.read_bytes() == before


def test_multiple_manifest_versions_are_candidates_not_an_implicit_current(tmp_path):
    script = put(tmp_path / "剧本.md")
    content = yaml.safe_dump({
        "documents": {"script": {"path": str(script)}}, "assets": {},
    })
    old = put(tmp_path / "materials.yaml", content)
    selected = put(tmp_path / "03-制作/制作计划/修订版/素材清单.yaml", content)
    put(tmp_path / "99-历史/素材清单.yaml", content)
    put(tmp_path / "01-文档/角色/人物.yaml", "character_id: PERSON\n")

    candidates = entrypoints.find_materials_manifests(tmp_path, list(tmp_path.rglob("*.yaml")))
    context = entrypoints.production_context(tmp_path, candidates)

    assert set(candidates) == {old, selected}
    assert context["documents"] == {}
    assert context["materials_manifest"] is None
    assert context["production_selection"]["state"] == "unselected"
    assert set(context["production_selection"]["candidates"]) == {
        "materials.yaml", "03-制作/制作计划/修订版/素材清单.yaml",
    }
    explicit = entrypoints.production_context(tmp_path, candidates, selected)
    assert explicit["materials_manifest"] == "03-制作/制作计划/修订版/素材清单.yaml"
    assert explicit["documents"] == {"script": "剧本.md"}
    assert explicit["production_selection"]["basis"] == "explicit_selection"


def test_entrypoint_refuses_to_replace_existing_selection_and_delivery(tmp_path, monkeypatch):
    original = "materials_manifest: 已选清单.yaml\nlast_accepted_delivery: 已确认记录.json\n"
    entry = put(tmp_path / "projects/作品/project.yaml", original)
    put(tmp_path / ".autodl/reorganization/20261110/manifest.json", json.dumps({"rows": []}))
    monkeypatch.setattr(entrypoints, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="Existing entrypoint"):
        entrypoints.main()
    assert entry.read_text("utf-8") == original


def test_explicit_manifest_selection_must_be_a_project_candidate(tmp_path):
    outside = put(tmp_path.parent / "other-selection.yaml", "documents: {}\nassets: {}\n")
    with pytest.raises(ValueError, match="不在当前作品"):
        entrypoints.production_context(tmp_path, [], outside)


def test_no_manifest_does_not_guess_a_document_version(tmp_path):
    put(tmp_path / "剧本.md")
    assert entrypoints.documents_from_manifest(tmp_path, None) == {}


@pytest.mark.parametrize("path", ["../其他作品/剧本.md", "不存在.md"])
def test_manifest_document_must_exist_inside_the_project(tmp_path, path):
    project = tmp_path / "作品"
    put(tmp_path / "其他作品/剧本.md")
    manifest = put(
        project / "materials.yaml", yaml.safe_dump({"documents": {"script": {"path": path}}})
    )
    with pytest.raises(ValueError, match="不存在或超出"):
        entrypoints.documents_from_manifest(project, manifest)


@pytest.mark.parametrize(
    ("value", "target", "expected"),
    [
        ("../.agents/skills/fight/SKILL.md", ".agents/skills/fight/SKILL.md",
         "../../.agents/skills/fight/SKILL.md"),
        ("archive/备份/索引.json#sha256", "docs/archive/备份/索引.json",
         "../archive/备份/索引.json#sha256"),
    ],
)
def test_moved_document_rebases_links_to_unmoved_targets(tmp_path, value, target, expected):
    put(tmp_path / target)
    result = references.remap_reference(
        value, tmp_path / "docs/记录.md", tmp_path / "docs/维护记录/记录.md",
        root=tmp_path, paths={}, dirs={}, rebase_unmoved=True,
    )
    assert result == expected


def test_moved_target_keeps_fragment_and_repository_output_paths(tmp_path):
    old, new = tmp_path / "docs/记录.md", tmp_path / "docs/维护记录/记录.md"
    mapping = {"docs/旧.md": "docs/工作流/新.md", "outputs/片": "projects/作品/04-输出"}
    assert references.remap_reference(
        "旧.md#正文", old, new, root=tmp_path, paths=mapping, dirs={},
    ) == "../工作流/新.md#正文"
    assert references.remap_reference(
        "outputs/片", old, new, root=tmp_path, paths=mapping, dirs={}, key="output_dir",
    ) == "projects/作品/04-输出"


@pytest.mark.parametrize("value", ["https://example.test/a#b", "#local", "未找到.md", "docs"])
def test_reference_rewrite_does_not_change_external_unknown_or_ordinary_scalar(tmp_path, value):
    (tmp_path / "docs").mkdir()
    assert references.remap_reference(
        value, tmp_path / "docs/记录.md", tmp_path / "docs/维护记录/记录.md",
        root=tmp_path, paths={}, dirs={},
    ) == value


@pytest.mark.parametrize("suffix", [".py", ".ps1", ".vpy"])
def test_archive_named_programs_still_go_to_shared_tools(suffix):
    path = Path(f"projects/作品/历史版本/检查并归档{suffix}")
    assert migration.target(path) == Path(
        f"tools/视频工具/历史脚本/作品/projects/历史版本/检查并归档{suffix}"
    )
    assert migration.category(Path("历史版本/记录.md"), "projects") == "99-历史/旧版文档与配置"


@pytest.mark.parametrize("suffix", [".py", ".ps1", ".vpy"])
def test_interface_verification_programs_go_to_shared_tools(suffix):
    path = Path(f"projects/接口验证/u24白模输入-20261109/接口兼容探测{suffix}")
    assert migration.target(path) == Path(
        "tools/视频工具/历史脚本/接口验证/projects/"
        f"u24白模输入-20261109/接口兼容探测{suffix}"
    )


@pytest.mark.parametrize("name", ["候选请求.yaml", "单次提交记录.json", "测试结论.md"])
def test_interface_verification_evidence_stays_in_docs(name):
    path = Path(f"projects/接口验证/u24白模输入-20261109/{name}")
    assert migration.target(path) == Path(f"docs/验证记录/接口验证/u24白模输入-20261109/{name}")


@pytest.mark.parametrize("value", ["assets/旧片.mp4", "projects/弃用作品/04-输出/成片.mp4"])
def test_where_reports_retired_missing_project_without_changing_historical_mapping(
    tmp_path, monkeypatch, capsys, value,
):
    target = "projects/弃用作品/04-输出/成片.mp4"
    registry = put(tmp_path / ".autodl/path-map.json", json.dumps({
        "files": {"assets/旧片.mp4": target},
        "retired_projects": {"projects/弃用作品": {"state": "retired"}},
    }))
    before = registry.read_bytes()
    monkeypatch.setattr(project_cli, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["项目.py", "where", value])

    project_cli.main()

    result = capsys.readouterr()
    assert Path(result.out.strip()) == tmp_path / target
    assert "已按用户确认弃用" in result.err and "文件不要求存在" in result.err
    assert registry.read_bytes() == before
    assert not (tmp_path / "projects/弃用作品").exists()


@pytest.mark.parametrize("recreated", [False, True])
def test_where_does_not_retire_unrelated_or_recreated_project(
    tmp_path, monkeypatch, capsys, recreated,
):
    target = "projects/弃用作品/04-输出/成片.mp4" if recreated else "projects/其他作品/成片.mp4"
    put(tmp_path / ".autodl/path-map.json", json.dumps({
        "files": {"assets/旧片.mp4": target},
        "retired_projects": {"projects/弃用作品": {"state": "retired"}},
    }))
    if recreated:
        put(tmp_path / "projects/弃用作品/project.yaml", "name: 新作品\n")
    monkeypatch.setattr(project_cli, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["项目.py", "where", "assets/旧片.mp4"])

    project_cli.main()

    result = capsys.readouterr()
    assert Path(result.out.strip()) == tmp_path / target
    assert result.err == ""


def test_project_init_losing_concurrent_creator_preserves_accepted_entry(tmp_path, monkeypatch):
    pending, release = Event(), Event()
    original_link = project_cli.os.link

    def hold_first_publication(source, destination):
        if not pending.is_set():
            pending.set()
            assert release.wait(5)
        original_link(source, destination)

    monkeypatch.setattr(project_cli.os, "link", hold_first_publication)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(project_cli.init_project, "并发作品", root=tmp_path)
        try:
            assert pending.wait(5)
            second = pool.submit(project_cli.init_project, "并发作品", root=tmp_path)
            entry = second.result(timeout=5)
            accepted = yaml.safe_load(entry.read_text("utf-8"))
            accepted["current"]["stage"] = "accepted"
            accepted["characters"] = {"HERO": "01-文档/角色/主角.yaml"}
            entry.write_text(yaml.safe_dump(accepted, allow_unicode=True), encoding="utf-8")
            expected = entry.read_bytes()
        finally:
            release.set()
        with pytest.raises(ValueError, match="作品已有 project.yaml"):
            first.result(timeout=5)
    assert entry.read_bytes() == expected
    assert not list(entry.parent.glob(".project-*"))


@pytest.mark.parametrize("phase", ["write", "publish"])
@pytest.mark.parametrize("failure", [PermissionError, KeyboardInterrupt])
def test_project_init_failure_leaves_no_partial_entry_and_can_retry(
    tmp_path, monkeypatch, phase, failure,
):
    project = tmp_path / "projects/失败重试作品"
    entry = project / "project.yaml"
    original_write = Path.write_text

    def partial_write(path, text, **kwargs):
        original_write(path, text[:12], **kwargs)
        raise failure("synthetic staging write failure")

    def fail_publication(*_):
        raise failure("synthetic publication failure")

    with monkeypatch.context() as scoped:
        if phase == "write":
            scoped.setattr(Path, "write_text", partial_write)
        else:
            scoped.setattr(project_cli.os, "link", fail_publication)
        with pytest.raises(failure):
            project_cli.init_project("失败重试作品", root=tmp_path)
    assert not entry.exists()
    assert not list(project.glob(".project-*"))
    assert project_cli.init_project("失败重试作品", root=tmp_path) == entry
    assert yaml.safe_load(entry.read_text("utf-8"))["current"]["stage"] == "draft"
    assert not list(project.glob(".project-*"))


def test_project_init_preserves_existing_entry(tmp_path):
    entry = put(tmp_path / "projects/已有作品/project.yaml", "current: {stage: accepted}\n")
    expected = entry.read_bytes()
    with pytest.raises(ValueError, match="作品已有 project.yaml"):
        project_cli.init_project("已有作品", root=tmp_path)
    assert entry.read_bytes() == expected
    assert not list(entry.parent.glob(".project-*"))


@pytest.mark.parametrize("junction_scope", ["project", "projects"])
def test_project_init_rejects_junction_outside_repository(tmp_path, junction_scope):
    root = tmp_path / "repository"
    outside = tmp_path / "outside"
    sentinel = put(outside / "保留.txt", "keep outside bytes")
    junction = root / "projects"
    if junction_scope == "project":
        junction /= "穿界作品"
    junction.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
            check=True, capture_output=True,
        )
    else:
        junction.symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises(ValueError, match="作品目录必须位于仓库 projects 内"):
            project_cli.init_project("穿界作品", root=root)
        assert sorted(outside.iterdir()) == [sentinel]
        assert sentinel.read_text("utf-8") == "keep outside bytes"
    finally:
        if sys.platform == "win32":
            junction.rmdir()
        else:
            junction.unlink()


def test_verified_reference_original_is_an_input_not_a_generated_segment():
    assert migration.target(Path("assets/云宫挥杆/视频/原片-高尔夫白模.mp4")) == Path(
        "projects/云宫挥杆/02-素材/参考原片/原片-高尔夫白模.mp4"
    )


@pytest.mark.parametrize("name", ["原片对标生成结果.mp4", "原片-高尔夫白模.mp4"])
def test_original_keyword_or_same_basename_does_not_classify_unverified_video_as_input(name):
    assert migration.target(Path(f"assets/其他作品/视频/{name}")) == Path(
        f"projects/其他作品/04-输出/原始片段/视频/{name}"
    )
