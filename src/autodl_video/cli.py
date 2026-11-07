"""CLI for catalog management, YAML execution and resumable tasks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from .catalog import get_workflow, load_catalog, sync_catalog
from .client import AutoDLClient
from .config import atomic_text, project_root
from .errors import AutoDLError
from .materials import check_materials
from .runner import VideoProject


def print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def template(workflow_id: str, workflow: dict) -> dict:
    inputs = {}
    for name, rule in workflow["input_rules"].items():
        if not rule.get("required") and name not in {"duration", "resolution"}:
            continue
        kind = rule["type"]
        if kind in {"image", "audio", "video"}:
            inputs[name] = {
                "image": "../assets/reference.png",
                "audio": "../assets/voice.wav",
                "video": "../assets/reference.mp4",
            }[kind]
        elif "default" in rule:
            inputs[name] = rule["default"]
        elif kind in {"prompt", "string"}:
            inputs[name] = "请填写要生成的内容"
        elif kind == "enum":
            option = rule["options"][0]
            inputs[name] = option["label"] if isinstance(option, dict) else option
        elif kind == "boolean":
            inputs[name] = False
        elif kind in {"number", "integer"}:
            inputs[name] = rule.get("min", 0)
        else:
            raise AutoDLError(f"Cannot template unsupported type: {kind}")
    return {"workflow_id": workflow_id, "inputs": inputs, "output_dir": "outputs"}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="autodl", description="AutoDL YAML 视频/音频工具")
    result.add_argument("--project", help="项目根目录，默认自动查找")
    commands = result.add_subparsers(dest="command", required=True)
    models = commands.add_parser("models", help="同步和查询模型目录")
    model_commands = models.add_subparsers(dest="action", required=True)
    sync = model_commands.add_parser("sync", help="同步全部工作流和参数")
    sync.add_argument("--check", action="store_true", help="只检查变化；有变化退出码为 1")
    listing = model_commands.add_parser("list", help="列出模型")
    listing.add_argument("--search", default="", help="按名称、ID 或分类过滤")
    listing.add_argument("--json", action="store_true")
    show = model_commands.add_parser("show", help="查看参数、价格和说明")
    show.add_argument("workflow_id")
    generate = model_commands.add_parser("template", help="创建任意工作流的 YAML 模板")
    generate.add_argument("workflow_id")
    generate.add_argument("--output", type=Path)
    run = commands.add_parser("run", help="运行 YAML，可能产生 API 费用")
    run.add_argument("config", type=Path)
    run.add_argument("--dry-run", action="store_true", help="只做离线校验和预览")
    run.add_argument("--no-wait", action="store_true", help="提交后返回 task_id")
    run.add_argument("--max-cost", help="按最新最高时段价格估算的预算，单位人民币")
    validate = commands.add_parser("validate", help="离线校验 YAML，不调用 API")
    validate.add_argument("config", type=Path)
    materials = commands.add_parser("materials", help="检查短剧文档与素材是否齐备")
    material_commands = materials.add_subparsers(dest="action", required=True)
    check = material_commands.add_parser("check", help="离线输出缺图清单，不调用 API")
    check.add_argument("manifest", type=Path)
    check.add_argument("--shot", help="核对镜头 ID；仍检查整份清单的必要素材")
    task = commands.add_parser("task", help="恢复查询和下载，不会重新提交任务")
    task_commands = task.add_subparsers(dest="action", required=True)
    task_commands.add_parser("list", help="列出本地任务记录")
    for name in ("status", "wait", "download"):
        action = task_commands.add_parser(name)
        action.add_argument("task_id")
        if name != "status":
            action.add_argument("--output-dir", type=Path)
        if name == "wait":
            action.add_argument("--timeout", type=float, default=1800)
            action.add_argument("--poll-interval", type=float, default=3)
    return result


def main(argv: list[str] | None = None) -> int:
    # Keep Chinese prompts and model names readable in Windows PowerShell pipes.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    root = project_root(args.project)
    project = VideoProject(root)
    last_status = None

    def progress(data: dict) -> None:
        nonlocal last_status
        status = data.get("status")
        if status != last_status:
            print(f"task_id={data.get('task_id')} status={status}", file=sys.stderr, flush=True)
            last_status = status

    try:
        if args.command == "materials":
            report = check_materials(args.manifest, args.shot)
            print_json(report)
            return 0 if report["ready"] else 1
        if args.command == "models":
            if args.action == "sync":
                with AutoDLClient() as client:
                    changes = sync_catalog(root, client, check=args.check)
                print_json(changes)
                return int(
                    args.check and any(changes[key] for key in ("added", "changed", "removed"))
                )
            if args.action == "list":
                workflows = load_catalog(root)["workflows"]
                rows = [
                    {"workflow_id": key, "name": item["name"], "category": item["category"]}
                    for key, item in workflows.items()
                    if args.search.lower() in f"{key} {item['name']} {item['category']}".lower()
                ]
                if args.json:
                    print_json(rows)
                else:
                    for row in rows:
                        print(f"{row['workflow_id']}\t{row['name']}\t{row['category']}")
                return 0
            item = get_workflow(root, args.workflow_id)
            if args.action == "show":
                print(yaml.safe_dump(item, allow_unicode=True, sort_keys=False))
            else:
                text = yaml.safe_dump(
                    template(args.workflow_id, item), allow_unicode=True, sort_keys=False
                )
                if args.output:
                    if args.output.exists():
                        raise AutoDLError(f"Template output already exists: {args.output}")
                    atomic_text(args.output, text)
                    print(f"Created {args.output}")
                else:
                    print(text)
            return 0
        if args.command in {"run", "validate"}:
            print_json(
                project.generate(
                    args.config,
                    dry_run=args.command == "validate" or args.dry_run,
                    wait=not getattr(args, "no_wait", False),
                    max_cost_cny=getattr(args, "max_cost", None),
                    on_update=progress,
                )
            )
            return 0
        if args.action == "list":
            print_json(
                [
                    {
                        "task_id": item["task_id"],
                        "workflow_id": item.get("workflow_id"),
                        "status": item.get("response", {}).get("status"),
                        "files": item.get("files", []),
                    }
                    for item in project.store.list()
                ]
            )
        elif args.action == "status":
            print_json(project.status(args.task_id))
        elif args.action == "download":
            print_json(project.download(args.task_id, output_dir=args.output_dir))
        else:
            print_json(
                project.resume(
                    args.task_id,
                    output_dir=args.output_dir,
                    timeout=args.timeout,
                    poll_interval=args.poll_interval,
                    on_update=progress,
                )
            )
        return 0
    except AutoDLError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Local file error: {type(exc).__name__}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(
            "Stopped locally. Check local task/attempt records before submitting again.",
            file=sys.stderr,
        )
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
