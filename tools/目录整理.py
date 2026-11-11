"""One-time, journaled local migration. Plan first; never overwrite a destination.

The snapshot is content-addressed, so identical payloads are backed up once.
Only paths beneath the explicit workspace may be mutated. No secrets are read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path

TEXT = {".md", ".yaml", ".yml", ".json", ".py", ".html", ".txt", ".log", ".vpy", ".ps1"}
MEDIA = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".mkv", ".wav", ".mp3", ".flac"}
VIDEO = {".mp4", ".mov", ".mkv", ".webm"}
AUDIO = {".wav", ".mp3", ".flac", ".m4a", ".aac"}
ALIASES = {
    "elf-duel": "双精灵对决",
    "怪物三视图检查": "双怪物对决",
    "补帧技能验证": "工具验证",
    "demo": "工具验证",
    "midjourney": "双精灵对决",
}
# Verified ref_video inputs; a filename containing "原片" does not establish its role.
REFERENCE_ORIGINALS = {
    "assets/云宫挥杆/视频/原片-高尔夫白模.mp4":
        "projects/云宫挥杆/02-素材/参考原片/原片-高尔夫白模.mp4",
}
DOCS = {
    **{
        x: "工作流"
        for x in (
            "director-workflow",
            "short-drama-workflow",
            "multi-segment-video",
            "fight-scenes",
            "video-retargeting",
            "music-postproduction",
        )
    },
    **{
        x: "工具与接口"
        for x in ("api", "models", "midjourney-local", "blender-integration", "acheng-integration")
    },
    "verification": "验证记录",
    "short-drama-skills-analysis": "维护记录",
}


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def inside(root, path):
    result = path.resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError(f"Path outside workspace: {result}")
    return result


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def category(p, area):
    name, text, ext = p.name, p.as_posix(), p.suffix.lower()
    if ext in {".py", ".ps1", ".vpy"}:
        return "@scripts"
    if name == "当前制作状态.json":
        return "99-历史/旧版状态"
    if any(x in text for x in ("修订前", "历史版本", "归档")):
        return "99-历史/旧版文档与配置"
    if "materials" in name or "素材清单" in name and ext in {".yaml", ".yml"}:
        return "03-制作/制作计划"
    if any(x in text for x in ("遮罩", "掩码", "mask", "源帧", "逐帧", "前景帧")):
        return "03-制作/中间数据"
    if any(x in text for x in ("检查", "审片", "验收", "审计", "校验", "复审", "预览帧")):
        return "05-检查与验收/素材与成片检查"
    if ext in VIDEO:
        if any(x in text for x in ("成片", "合成", "补帧", "预览", "60帧", "版本04")):
            return "04-输出/成片"
        if area == "输入":
            return "02-素材/参考原片"
        return "04-输出/原始片段"
    if ext in AUDIO:
        return "02-素材/音频"
    if ext in {".png", ".jpg", ".jpeg", ".webp"}:
        if any(x in text for x in ("衔接", "首帧", "尾帧")):
            return "02-素材/衔接图"
        if any(x in text for x in ("场景", "背景", "风格")):
            return "02-素材/场景"
        if any(x in text for x in ("人物", "角色", "参考板")):
            return "02-素材/人物"
        if area in {"outputs", "projects", "输入"}:
            return "05-检查与验收/检查帧与预览"
        return "02-素材/参考图"
    if ext == ".blend":
        return "03-制作/三维工程"
    if ext in {".yaml", ".yml"}:
        return "03-制作/生成配置"
    if ext in {".json", ".log"}:
        if "计划" in name:
            return "03-制作/制作计划"
        if "确认" in name:
            return "06-记录/用户确认"
        if "来源" in name:
            return "06-记录/素材来源"
        return "06-记录/制作记录"
    if ext == ".md":
        if any(x in name for x in ("确认", "来源", "执行记录", "交付")):
            return "06-记录/制作记录"
        if "提示词" in name:
            return "01-文档/提示词"
        if any(x in name for x in ("分镜", "运镜")):
            return "01-文档/分镜与运镜"
        if any(x in name for x in ("视觉", "人物", "场景", "风格", "参考")):
            return "01-文档/视觉设定"
        return "01-文档/需求与剧本"
    return "06-记录/其他资料"


def target(rel):
    if rel.as_posix() in REFERENCE_ORIGINALS:
        return Path(REFERENCE_ORIGINALS[rel.as_posix()])
    parts = rel.parts
    if parts[0] == "docs":
        if len(parts) > 2 and parts[1] == "plan":
            return Path("projects/双精灵对决/99-历史/制作计划", *parts[2:])
        group = DOCS.get(rel.stem, "维护记录")
        return Path("docs", group, rel.name)
    if parts[0] == "examples":
        return Path("projects/双精灵对决/03-制作/生成配置", rel.name)
    if parts[0] == "输入":
        work = {
            "扶柱滑倒白模": "扶柱滑倒",
            "白模高尔夫": "云宫挥杆",
            "高尔夫稳定示例": "云宫挥杆",
            "幻影动势打斗": "双怪物对决",
        }[parts[2]]
        tail = Path(*parts[2:])
    else:
        work = ALIASES.get(parts[1], parts[1])
        tail = Path(*parts[2:])
    cat = category(tail, parts[0])
    if cat == "@scripts":
        return Path("tools/视频工具/历史脚本", work, parts[0], tail)
    if work == "接口验证":
        return Path("docs/验证记录/接口验证", tail)
    if rel.as_posix() == "projects/一小片屋檐/中世纪写实风格规范.md":
        return Path("docs/视觉规范/中世纪写实风格规范.md")
    if parts[0] == "projects" and tail.name == "materials.yaml" and len(tail.parts) == 1:
        return Path("projects", work, tail)
    return Path("projects", work, cat, tail)


def candidates(root):
    for base in ("projects", "assets", "outputs", "输入"):
        yield from (
            p for p in (root / base).rglob("*") if p.is_file() and "__pycache__" not in p.parts
        )
    for p in (root / "docs").glob("*.md"):
        if p.name not in {"README.md", "CODEX-NAVIGATION-GUIDE.md", "skill-routing.md"}:
            yield p
    yield from (root / "docs/plan/双精灵仙侠打斗-2026-11-07").rglob("*.*")
    p = root / "examples/双精灵-法师生图.yaml"
    if p.exists():
        yield p


def make_plan(root, state):
    rows, occupied, unreadable = [], set(), []
    for p in sorted(set(candidates(root))):
        rel = p.relative_to(root)
        dest = target(rel)
        if dest.as_posix() in occupied:
            dest = dest.with_name(f"{dest.stem}-来源{rel.parts[0]}{dest.suffix}")
        if dest.as_posix() in occupied:
            raise ValueError(f"Collision: {dest}")
        occupied.add(dest.as_posix())
        try:
            sha = digest(p)
        except PermissionError:
            unreadable.append(rel.as_posix())
            continue
        rows.append(
            {"old": rel.as_posix(), "new": dest.as_posix(), "sha256": sha, "size": p.stat().st_size}
        )
    groups = defaultdict(list)
    for row in rows:
        if Path(row["old"]).suffix.lower() in MEDIA and row["size"]:
            groups[row["sha256"]].append(row)
    for group in groups.values():
        if len(group) < 2:
            continue

        # Prefer the semantic named source, never a review copy or UUID task output.
        def score(row):
            return (
                row["old"].startswith("outputs/"),
                "05-检查" in row["new"],
                len(row["new"]),
                row["new"],
            )

        canonical = min(group, key=score)
        for row in group:
            if row is canonical:
                continue
            # Repeated indexed frames are logical entries; share bytes via hardlinks.
            indexed = bool(re.search(r"(?:\d{4,}|帧\d+|mask|遮罩)", row["old"]))
            if Path(row["new"]).parts[:2] != Path(canonical["new"]).parts[:2]:
                indexed = True
            row["dedup"] = (
                "hardlink" if indexed and Path(row["old"]).suffix.lower() not in VIDEO else "alias"
            )
            row["canonical"] = canonical["new"]
    data = {"root": str(root), "rows": rows, "status": "planned", "unreadable": unreadable}
    save(state / "manifest.json", data)
    return data


def snapshot(root, state, plan):
    # All active project/rule files that may be updated are backed up once.
    paths = {r["old"] for r in plan["rows"]}
    for base in ("docs", "templates", ".agents/skills", "src", "tests", ".autodl/tasks"):
        paths.update(
            p.relative_to(root).as_posix()
            for p in (root / base).rglob("*")
            if p.is_file()
            and p.suffix in TEXT
            and "__pycache__" not in p.parts
            and ".agents/resources" not in p.as_posix()
            and "docs/archive" not in p.as_posix()
        )
    paths.update({"AGENTS.md", "README.md", ".gitignore", "pyproject.toml"})
    entries = []
    for name in sorted(paths):
        p = inside(root, root / name)
        sha = digest(p)
        obj = state / "objects" / sha
        if not obj.exists():
            obj.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, obj)
        if digest(obj) != sha:
            raise ValueError(f"Backup verification failed: {name}")
        entries.append({"path": name, "sha256": sha})
    save(state / "snapshot.json", entries)


def apply(root, state, plan):
    if plan["status"] != "planned":
        raise ValueError("Migration already started; inspect journal before continuing")
    snapshot(root, state, plan)
    for row in plan["rows"]:
        old, new = inside(root, root / row["old"]), inside(root, root / row["new"])
        if digest(old) != row["sha256"]:
            raise ValueError(f"Concurrent change: {old}")
        if new.exists() and new != old:
            raise ValueError(f"Existing destination: {new}")
    plan["status"] = "moving"
    save(state / "manifest.json", plan)
    # Canonical files first, then references and logical sequence links.
    for row in sorted(plan["rows"], key=lambda r: bool(r.get("dedup"))):
        old, new = inside(root, root / row["old"]), inside(root, root / row["new"])
        if row.get("dedup"):
            canonical = inside(root, root / row["canonical"])
            if digest(canonical) != row["sha256"]:
                raise ValueError("Canonical content changed")
            if row["dedup"] == "hardlink":
                new.parent.mkdir(parents=True, exist_ok=True)
                os.link(canonical, new)
            old.unlink()
        elif old != new:
            new.parent.mkdir(parents=True, exist_ok=True)
            old.rename(new)
        row["done"] = True
        with (state / "journal.jsonl").open("a", encoding="utf-8") as log:
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
    plan["status"] = "moved"
    save(state / "manifest.json", plan)
    # Empty folders only; never recursively delete unenumerated files.
    for base in ("projects", "assets", "outputs", "输入"):
        for p in sorted((root / base).rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if p.is_dir() and not any(p.iterdir()):
                inside(root, p).rmdir()
        if (root / base).exists() and not any((root / base).iterdir()):
            inside(root, root / base).rmdir()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["plan", "apply"])
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = ap.parse_args()
    root = args.root.resolve()
    state = root / ".autodl/reorganization/20261110"
    if args.action == "plan":
        if (state / "manifest.json").exists():
            raise ValueError("Existing migration manifest; do not overwrite")
        plan = make_plan(root, state)
    else:
        plan = json.loads((state / "manifest.json").read_text("utf-8"))
        apply(root, state, plan)
    print(
        json.dumps(
            {
                "status": plan["status"],
                "files": len(plan["rows"]),
                "aliases": sum(r.get("dedup") == "alias" for r in plan["rows"]),
                "sequence_links": sum(r.get("dedup") == "hardlink" for r in plan["rows"]),
            }
        )
    )


if __name__ == "__main__":
    main()
