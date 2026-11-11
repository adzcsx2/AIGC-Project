"""Adapt path references from the verified snapshot, retaining original payloads."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".autodl/reorganization/20261110"


def remap_reference(value, old, new, *, root, paths, dirs, key="", rebase_unmoved=False):
    """Rebase known local targets, including targets that were not themselves moved."""
    if not isinstance(value, str) or not value or "\n" in value or len(value) > 1500:
        return value
    if value.startswith(("http:", "https:", "data:", "mailto:", "#")):
        return value
    raw, separator, fragment = value.replace("\\", "/").partition("#")
    suffix = separator + fragment
    possibilities = [(old.parent / raw).resolve(), (root / raw).resolve()]
    if Path(raw).is_absolute():
        possibilities.insert(0, Path(raw).resolve())
    for path in possibilities:
        if not path.is_relative_to(root):
            continue
        rel = path.relative_to(root).as_posix()
        mapped = paths.get(rel, dirs.get(rel))
        # Moving the document changes relative links even when their targets stay put.
        if mapped is None and rebase_unmoved and path.exists():
            mapped = rel
        if mapped is None:
            continue
        if key == "output_dir" or raw.startswith(
            ("projects/", "assets/", "outputs/", "输入/", "docs/", ".agents/")
        ):
            return mapped + suffix
        if Path(raw).is_absolute():
            return str(root / mapped) + suffix
        return os.path.relpath(root / mapped, new.parent).replace("\\", "/") + suffix
    return value


def main():
    plan = json.loads((STATE / "manifest.json").read_text("utf-8"))
    if plan["status"] != "moved":
        raise ValueError("Migration must be complete first")
    paths = {
        r["old"]: r.get("canonical", r["new"]) if r.get("dedup") == "alias" else r["new"]
        for r in plan["rows"]
    }
    dirs = {}
    for row in plan["rows"]:
        if row["old"].startswith("outputs/"):
            olddir = str(Path(row["old"]).parent).replace("\\", "/")
            # Downloads resume at the existing canonical location, not old outputs.
            dirs.setdefault(olddir, str(Path(paths[row["old"]]).parent).replace("\\", "/"))
    (ROOT / ".autodl/path-map.json").write_text(
        json.dumps({"files": paths, "directories": dirs}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    originals = json.loads((STATE / "snapshot.json").read_text("utf-8"))
    protected = set()
    for entry in originals:
        if entry["path"].endswith((".yaml", ".yml")):
            try:
                data = yaml.safe_load((STATE / "objects" / entry["sha256"]).read_text("utf-8-sig"))
                if isinstance(data, dict) and isinstance(data.get("documents"), dict):
                    script = data["documents"].get("script", {}).get("path")
                    if script:
                        protected.add(str((ROOT / entry["path"]).parent.joinpath(script).resolve()))
            except (ValueError, yaml.YAMLError, UnicodeError, AttributeError):
                pass

    def scalar(value, old, new, key="", *, rebase_unmoved=False):
        return remap_reference(
            value, old, new, root=ROOT, paths=paths, dirs=dirs, key=key,
            rebase_unmoved=rebase_unmoved,
        )

    def walk(data, old, new, key=""):
        if isinstance(data, dict):
            return {k: walk(v, old, new, str(k)) for k, v in data.items()}
        if isinstance(data, list):
            return [walk(v, old, new, key) for v in data]
        return scalar(data, old, new, key)

    changes = []
    for entry in originals:
        old = ROOT / entry["path"]
        new = ROOT / paths.get(entry["path"], entry["path"])
        if not new.exists() or new.suffix.lower() not in {".md", ".yaml", ".yml", ".json", ".html"}:
            continue
        if "99-历史" in new.parts or str(old) in protected:
            continue
        # Re-read latest working bytes: do not replace another chat's updates with snapshot.
        text = new.read_text("utf-8-sig")
        out = text
        try:
            if new.suffix in {".yaml", ".yml", ".json"}:
                data = json.loads(text) if new.suffix == ".json" else yaml.safe_load(text)
                updated = walk(data, old, new)
                if updated != data:
                    out = (
                        json.dumps(updated, ensure_ascii=False, indent=2) + "\n"
                        if new.suffix == ".json"
                        else yaml.safe_dump(updated, allow_unicode=True, sort_keys=False, width=120)
                    )
            else:
                # Markdown/HTML path tokens only, not prose or immutable creative scripts.
                out = re.sub(
                    r"(?<=\]\()([^\n)]+)(?=\))",
                    lambda m, old=old, new=new: scalar(m[0], old, new, rebase_unmoved=True),
                    out,
                )
                out = re.sub(
                    r"`([^`\n]+)`",
                    lambda m, old=old, new=new: "`"
                    + scalar(m[1], old, new, rebase_unmoved=True) + "`",
                    out,
                )
                for source, dest in sorted(paths.items(), key=lambda x: len(x[0]), reverse=True):
                    if source.startswith("docs/") or source.endswith("中世纪写实风格规范.md"):
                        out = out.replace(source, dest)
        except (ValueError, yaml.YAMLError, UnicodeError):
            continue
        if out != text:
            # Updated files also have pre-edit hashes, original bytes in the snapshot.
            changes.append(
                {
                    "path": new.relative_to(ROOT).as_posix(),
                    "before": hashlib.sha256(new.read_bytes()).hexdigest(),
                }
            )
            new.write_text(out, encoding="utf-8")
    (STATE / "reference-updates.json").write_text(
        json.dumps(changes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"updated_files": len(changes), "protected_creative_files": len(protected)}))


if __name__ == "__main__":
    main()
