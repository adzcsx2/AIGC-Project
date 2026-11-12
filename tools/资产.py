"""离线共享资产管理：登记版本、查找素材、导入作品并检查绑定。"""

import argparse
import json
import sys
from pathlib import Path

from autodl_video.asset_library import (
    CATEGORIES,
    bind_character,
    check_library,
    check_project,
    import_asset,
    init_library,
    list_assets,
    read_library,
    register_asset,
    register_entity,
    revision_record,
    usages,
)
from autodl_video.config import load_yaml
from autodl_video.errors import AutoDLError

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--library", type=Path, help="默认projects/共享资产库/project.yaml")
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("init", help="建立资产库，不创建剧本或生成任务")
    listing = actions.add_parser("list", help="分类/中文名称/标签查找，返回真实绝对路径")
    listing.add_argument("--category", choices=CATEGORIES)
    listing.add_argument("--query", default="")
    show = actions.add_parser("show")
    show.add_argument("id")
    show.add_argument("--revision", required=True)
    show.add_argument("--entity", action="store_true")
    register = actions.add_parser("register", help="使用资产登记模板登记一个不可覆盖的新版本")
    register.add_argument("source", type=Path)
    register.add_argument("--spec", type=Path, required=True)
    entity = actions.add_parser("register-entity")
    entity.add_argument("profile", type=Path)
    importing = actions.add_parser("import", help="锁定指定版本到作品的当前素材清单")
    importing.add_argument("project", type=Path)
    importing.add_argument("--asset", required=True)
    importing.add_argument("--revision", required=True)
    importing.add_argument("--local-id", required=True)
    importing.add_argument("--path", help="相对作品根目录，默认保留已有本地路径")
    importing.add_argument(
        "--kind", choices=["character", "scene", "prop", "keyframe", "audio", "video"]
    )
    bind = actions.add_parser("bind-character", help="将既有角色绑定到共享身份/造型快照")
    bind.add_argument("project", type=Path)
    bind.add_argument("--character", required=True)
    bind.add_argument("--entity", required=True)
    bind.add_argument("--revision", required=True)
    bind.add_argument("--look", required=True)
    bind.add_argument("--board-asset", required=True)
    bind.add_argument("--voice-profile")
    bind.add_argument("--voice-asset")
    checking = actions.add_parser("check", help="只做结构/文件/哈希检查，不作创作验收")
    checking.add_argument("--project", type=Path)
    uses = actions.add_parser("uses", help="查询明确选中制作分支中的使用关系")
    uses.add_argument("id")
    uses.add_argument("--revision")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    library = (args.library or root / "projects/共享资产库/project.yaml").resolve()
    try:
        if args.action == "init":
            if args.library and library != root / "projects/共享资产库/project.yaml":
                raise AutoDLError("init仅初始化默认共享资产库；不覆盖自定义项目")
            result = {"project": str(init_library(root))}
        elif args.action == "list":
            result = list_assets(library, root=root, category=args.category, query=args.query)
        elif args.action == "show":
            _, data = read_library(library, root=root)
            result = revision_record(
                data, "entities" if args.entity else "assets", args.id, args.revision
            )
        elif args.action == "register":
            result = register_asset(library, args.source, load_yaml(args.spec), root=root)
        elif args.action == "register-entity":
            result = register_entity(library, load_yaml(args.profile), root=root)
        elif args.action == "import":
            result = import_asset(
                library,
                args.asset,
                args.revision,
                args.project,
                args.local_id,
                root=root,
                destination=args.path,
                kind=args.kind,
            )
        elif args.action == "bind-character":
            result = bind_character(
                library,
                args.entity,
                args.revision,
                args.project,
                args.character,
                args.look,
                args.board_asset,
                root=root,
                voice_profile_id=args.voice_profile,
                voice_asset_id=args.voice_asset,
            )
        elif args.action == "uses":
            result = usages(root, args.id, revision=args.revision)
        else:
            result = (
                check_project(args.project, root=root)
                if args.project
                else check_library(
                    library,
                    root=root,
                )
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if isinstance(result, dict) and result.get("valid") is False else 0
    except (AutoDLError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
