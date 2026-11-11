"""Resolve explicitly recorded legacy paths without recreating old asset trees."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .errors import AutoDLError


def resolve_media_path(path: Path, root: Path | None = None) -> Path:
    if root is not None:
        root = root.resolve()
    path = path.resolve()
    if root is None:
        root = next((p for p in path.parents if (p / "pyproject.toml").exists()), None)
    if root is None:
        return path
    registry = root / ".autodl/path-map.json"
    if not registry.exists() or not path.is_relative_to(root):
        return path
    mapping = json.loads(registry.read_text("utf-8"))
    rel = path.relative_to(root).as_posix()
    # Legacy paths retain the host filesystem's case semantics after migration.
    # On Windows, a now-missing alias can no longer be canonicalized by resolve().
    key = os.path.normcase(rel)
    for old, new in mapping["files"].items():
        if key == os.path.normcase(old):
            return (root / new).resolve()
    for old, new in sorted(
        mapping.get("directories", {}).items(), key=lambda item: len(item[0]), reverse=True
    ):
        if key == os.path.normcase(old) or key.startswith(os.path.normcase(old + "/")):
            return (root / new / rel[len(old) :].lstrip("/")).resolve()
    return path


def project_owner(path: Path, *, root: Path | None = None) -> Path | None:
    """Find the work owning a current or migrated path, including a new output path.

    ``root`` selects the repository migration registry, not a new relative-path base.
    """
    path = resolve_media_path(path, root)
    return next(
        (parent for parent in (path, *path.parents) if (parent / "project.yaml").is_file()),
        None,
    )


def ensure_project_output(
    destination: Path, *sources: Path, root: Path | None = None
) -> Path:
    """Keep outputs with their known work; standalone external tools remain usable."""
    destination = resolve_media_path(destination, root)
    owners = {owner for source in sources if (owner := project_owner(source, root=root))}
    if len(owners) > 1:
        raise AutoDLError("输入属于不同作品；请先将本作品输入归档到同一作品内")
    if owners:
        owner = owners.pop()
        output_owner = project_owner(destination, root=root)
        if not destination.is_relative_to(owner) or output_owner not in (None, owner):
            raise AutoDLError(f"输出必须保存在当前作品内：{owner}")
    return destination
