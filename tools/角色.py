"""List character voices; never generates audio or fabricates user approval."""

import argparse
import json
import os
import tempfile
from pathlib import Path

import yaml

from autodl_video.characters import project_path, voice_queue
from autodl_video.config import atomic_text, load_yaml
from autodl_video.errors import AutoDLError
from autodl_video.locking import resource_lock
from autodl_video.paths import resolve_media_path

ROOT = Path(__file__).resolve().parents[1]


def init_character(
    project_file: Path, character_id: str, label: str, *, root: Path = ROOT
) -> Path:
    """Publish one new profile and its index while preserving every existing entry."""
    if not character_id.strip() or not label.strip():
        raise AutoDLError("init需要非空--id和--label")
    if any(c in label for c in '/\\:*?"<>|') or label in {".", ".."}:
        raise AutoDLError("label不能包含路径或Windows文件名特殊字符")
    project_file = resolve_media_path(project_file, root)
    if project_file.name != "project.yaml":
        raise AutoDLError("人物必须登记到作品的project.yaml入口")
    with resource_lock(project_file, root=root):
        project = load_yaml(project_file)
        registry = project.setdefault("characters", {})
        if not isinstance(registry, dict):
            raise AutoDLError("project.characters必须是人物ID到档案路径的映射")
        if character_id in registry:
            raise AutoDLError("此人物ID已存在")
        relative = f"01-文档/角色/{label}.yaml"
        dest = project_path(project_file.parent, relative, repository_root=root)
        profile = load_yaml(root / "templates/short-drama/角色.yaml")
        profile.update(character_id=character_id, label=label)
        profile_text = yaml.safe_dump(profile, allow_unicode=True, sort_keys=False)
        registry[character_id] = relative
        project_text = yaml.safe_dump(project, allow_unicode=True, sort_keys=False)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".character-", dir=dest.parent) as folder:
            staged = Path(folder) / "profile.yaml"
            staged.write_text(profile_text, encoding="utf-8", newline="\n")
            try:
                # Atomic exclusive publication cannot overwrite an existing profile.
                os.link(staged, dest)
            except FileExistsError:
                raise AutoDLError("此人物档案文件已存在，请核对原登记") from None
            try:
                atomic_text(project_file, project_text)
            except BaseException:
                # Only remove the exact file we just created, never another writer's
                # replacement or an existing profile. The original index stays intact.
                if (
                    dest.is_file()
                    and dest.samefile(staged)
                    and dest.read_bytes() == profile_text.encode("utf-8")
                ):
                    dest.unlink()
                raise
    return dest


def main():
    parser = argparse.ArgumentParser(description="人物独立YAML与待试听清单")
    parser.add_argument("action", choices=["queue", "init"])
    parser.add_argument("project", type=Path, help="作品project.yaml")
    parser.add_argument("--id", dest="character_id")
    parser.add_argument("--label", help="人物中文识别描述，例如青衣女子")
    args = parser.parse_args()
    args.project = resolve_media_path(args.project, ROOT)
    if args.action == "queue":
        print(json.dumps(voice_queue(args.project, root=ROOT), ensure_ascii=False, indent=2))
        return
    if not args.character_id or not args.label:
        parser.error("init需要--id和--label")
    try:
        dest = init_character(args.project, args.character_id, args.label)
    except AutoDLError as exc:
        parser.error(str(exc))
    print(dest)


if __name__ == "__main__":
    main()
