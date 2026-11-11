"""Validate, inspect, render and review a saved whitebox using a project YAML plan."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

from whitebox_core import (
    descriptor,
    execute_blender,
    inside,
    load_plan,
    new_run,
    validate_bundle,
    verify_cuts,
    write_new,
)

from autodl_video.errors import AutoDLError


def prepare_review(context, bundle_path):
    bundle = validate_bundle(context, bundle_path)
    videos = [Path(a["path"]) for a in bundle["artifacts"] if Path(a["path"]).suffix == ".mp4"]
    if not videos:
        raise ValueError("检查包没有预览视频，请先render")
    spec = importlib.util.spec_from_file_location(
        "whitebox_review", Path(__file__).with_name("审片.py")
    )
    review = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(review)
    dependencies = (
        bundle["dependencies"] + [bundle["job"]] + bundle["artifacts"]
        + [descriptor(Path(bundle_path).resolve())]
    )
    return review.prepare(
        context["project"], videos, dependencies=dependencies,
        implementation=bundle["implementation"],
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="作品内白模计划、实际工程检查和双版本预览")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "inspect", "render", "verify-cuts", "review", "check-bundle"):
        sub = commands.add_parser(name)
        sub.add_argument("plan", type=Path)
        if name in {"inspect", "render"}:
            sub.add_argument("--version", required=True)
            sub.add_argument("--blender", type=Path, default=Path(r"D:\blender-5.3.0\blender.exe"))
        if name == "verify-cuts":
            sub.add_argument("video", type=Path)
            sub.add_argument("--output", type=Path, required=True)
            sub.add_argument("--threshold", type=float, default=0.28)
            sub.add_argument("--tolerance-frames", type=float, default=2)
        if name in {"review", "check-bundle"}:
            sub.add_argument("bundle", type=Path)
    args = parser.parse_args(argv)
    try:
        context = load_plan(args.plan)
        status = 0
        if args.command == "validate":
            result = {
                "status": "plan_valid",
                "duration": context["duration"],
                "shots": len(context["plan"]["shots"]),
                "scene_inspection": "pending",
            }
        elif args.command in {"inspect", "render"}:
            if not args.blender.is_file():
                raise ValueError(f"未找到Blender：{args.blender}")
            paths = new_run(context, args.version, render=args.command == "render")
            path, bundle = execute_blender(
                context, paths, args.blender, render=args.command == "render"
            )
            result = {"bundle": str(path), "status": bundle["status"], "dynamic_review": "pending"}
            status = int(bundle["status"] != "checks_passed")
        elif args.command == "verify-cuts":
            output = inside(Path(context["project"]), str(args.output), exists=False)
            if output.exists():
                raise FileExistsError("检查记录已存在，请另存版本")
            result = verify_cuts(
                context,
                args.video,
                threshold=args.threshold,
                tolerance_frames=args.tolerance_frames,
            )
            write_new(output, result)
            status = int(result["status"] != "detected_match")
        elif args.command == "review":
            result = {
                "session": str(prepare_review(context, args.bundle.resolve())),
                "next": "使用审片.py serve 启动网页；通过浏览器审片",
            }
        else:
            result = {
                "status": "evidence_current",
                "checks": validate_bundle(context, args.bundle.resolve())["status"],
            }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return status
    except (ValueError, OSError, KeyError, AutoDLError) as exc:
        print(f"白模工具：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
