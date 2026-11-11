"""Initialize a simple project or resolve a migrated path."""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import yaml

from autodl_video.paths import resolve_media_path

ROOT = Path(__file__).resolve().parents[1]


def retirement_notice(path: Path) -> str | None:
    registry = ROOT / ".autodl/path-map.json"
    if not registry.is_file():
        return None
    mapping = json.loads(registry.read_text("utf-8"))
    for name, record in mapping.get("retired_projects", {}).items():
        relative = Path(name)
        if len(relative.parts) != 2 or relative.parts[0] != "projects":
            continue
        project = (ROOT / relative).resolve()
        # A recreated directory belongs to a new incarnation, not this retirement.
        if (record.get("state") == "retired" and not project.exists()
                and project.is_relative_to(ROOT.resolve()) and path.is_relative_to(project)):
            return (
                f"作品「{project.name}」已按用户确认弃用，退出当前迁移验收；"
                "上方仅为历史目标路径，文件不要求存在。"
            )
    return None


def init_project(name: str, *, root: Path = ROOT) -> Path:
    """Publish a complete new entrypoint without replacing concurrent user work."""
    if Path(name).name != name or name in {".", ".."}:
        raise ValueError("作品名不能包含目录")
    projects = root.resolve() / "projects"
    project = (projects / name).resolve()
    if project == projects or not project.is_relative_to(projects):
        raise ValueError("作品目录必须位于仓库 projects 内")
    project.mkdir(parents=True, exist_ok=True)
    entry = project / "project.yaml"
    if entry.exists():
        raise ValueError("作品已有 project.yaml")
    text = yaml.safe_dump(
        {
            "schema_version": 1,
            "name": name,
            "current": {"stage": "draft", "next_step": "记录需求和当前任务授权", "issues": []},
            "documents": {},
            "characters": {},
            "materials_manifest": None,
            "audio": {"generation_policy": "dialogue_only", "music_plan": None},
            "watermark": {"text": "@CallMeQueenAI", "apply_to_delivery": False},
        },
        allow_unicode=True,
        sort_keys=False,
    )
    with tempfile.TemporaryDirectory(prefix=".project-", dir=project) as folder:
        staged = Path(folder) / "entry.yaml"
        staged.write_text(text, encoding="utf-8", newline="\n")
        try:
            # The exclusive publication, not the earlier check, resolves init races.
            os.link(staged, entry)
        except FileExistsError:
            raise ValueError("作品已有 project.yaml") from None
    return entry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["init", "where"])
    parser.add_argument("value")
    args = parser.parse_args()
    if args.action == "where":
        resolved = resolve_media_path(ROOT / args.value, ROOT)
        print(resolved)
        if notice := retirement_notice(resolved):
            print(notice, file=sys.stderr)
        return
    print(init_project(args.value, root=ROOT))


if __name__ == "__main__":
    main()
