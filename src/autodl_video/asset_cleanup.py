"""Conservative image cleanup: reviewed plans, reference protection and verified unlink."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
from collections import defaultdict
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import unquote

import yaml

from .asset_bindings import digest_file
from .config import atomic_json
from .errors import AutoDLError
from .locking import resource_lock

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
TEXT_SUFFIXES = {".yaml", ".yml", ".json", ".md", ".txt", ".py", ".html", ".toml"}


def unlink_verified(
    path: Path, *, boundary: Path, expected: str, keeper: Path | None = None
) -> None:
    path, boundary = path.absolute(), boundary.resolve()
    if path.is_symlink() or not path.resolve().is_relative_to(boundary):
        raise AutoDLError("Deletion target escapes the approved asset directory")
    if os.name != "nt":
        raise AutoDLError("Verified media deletion currently requires Windows handles")
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    dispose = kernel.SetFileInformationByHandle
    dispose.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    dispose.restype = wintypes.BOOL
    # GENERIC_READ|DELETE, FILE_SHARE_READ only. Other writers/replacements are
    # denied while the exact opened file is hashed and its link is disposed.
    handle = create(str(path), 0x80010000, 1, None, 3, 0x00200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        close(handle)
        raise
    with os.fdopen(descriptor, "rb") as stream, ExitStack() as retained:
        if (
            not os.path.samestat(os.fstat(stream.fileno()), path.stat())
            or hashlib.file_digest(stream, "sha256").hexdigest() != expected
        ):
            raise AutoDLError("Deletion target changed; nothing was deleted")
        if keeper is not None:
            keeper = keeper.absolute()
            if (
                keeper == path
                or keeper.is_symlink()
                or not keeper.resolve().is_relative_to(boundary)
            ):
                raise AutoDLError("Duplicate keeper must be a separate approved local path")
            same_file = os.path.samestat(os.fstat(stream.fileno()), keeper.stat())
            # For hard links, the target's still-open restrictive handle already
            # denies writes/replacement through ALL aliases. The keeper's share
            # DELETE permits our target handle's own DELETE access only; it does
            # not relax the target's restriction for other writers.
            keep_handle = create(
                str(keeper), 0x80000000, 5 if same_file else 1, None, 3, 0x00200000, None
            )
            if keep_handle == ctypes.c_void_p(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                keep_fd = msvcrt.open_osfhandle(keep_handle, os.O_RDONLY | os.O_BINARY)
            except BaseException:
                close(keep_handle)
                raise
            keep_stream = retained.enter_context(os.fdopen(keep_fd, "rb"))
            if (
                not os.path.samestat(os.fstat(keep_fd), keeper.stat())
                or hashlib.file_digest(keep_stream, "sha256").hexdigest() != expected
            ):
                raise AutoDLError("Duplicate keeper changed; target was retained")
        flags = wintypes.DWORD(0x13)
        if not dispose(handle, 21, ctypes.byref(flags), ctypes.sizeof(flags)):
            raise ctypes.WinError(ctypes.get_last_error())


def reference_texts(root: Path, excluded: tuple[Path, ...] = ()) -> list[str]:
    """Include all historical branches, task receipts and docs; never just uses()."""
    texts = []
    for folder in (
        "projects",
        "docs",
        "tools",
        "src",
        "templates",
        "examples",
        ".autodl/tasks",
        ".autodl/attempts",
    ):
        for path in (root / folder).rglob("*"):
            if (
                path.is_file()
                and path.resolve() not in excluded
                and path.suffix.lower() in TEXT_SUFFIXES
            ):
                # Large receipts may contain inline media, but path names still matter.
                raw = path.read_text("utf-8-sig", errors="replace")
                values = [raw]
                if path.suffix.lower() in {".json", ".yaml", ".yml"}:
                    try:
                        parsed = (
                            json.loads(raw)
                            if path.suffix.lower() == ".json"
                            else yaml.safe_load(raw)
                        )
                        pending = [parsed]
                    except (ValueError, yaml.YAMLError):
                        # Unknown structured references cannot justify deletion.
                        texts.append("__unparsed_reference__:" + str(path))
                        pending = []
                    seen = set()
                    while pending:
                        value = pending.pop()
                        if isinstance(value, str):
                            values.append(value)
                        elif isinstance(value, dict) and id(value) not in seen:
                            seen.add(id(value))
                            pending.extend(value.keys())
                            pending.extend(value.values())
                        elif isinstance(value, list) and id(value) not in seen:
                            seen.add(id(value))
                            pending.extend(value)
                texts.extend(unquote(value).replace(chr(92), "/").casefold() for value in values)
    return texts


def cleanup_plan(root: Path, excluded: tuple[Path, ...] = ()) -> dict:
    """Only remove unreferenced, byte-identical extras. Unique or indexed frames stay."""
    root = root.resolve()
    texts = reference_texts(root, excluded)
    by_size = defaultdict(list)
    images = []
    for work in (root / "projects").iterdir():
        if not work.is_dir():
            continue
        for folder in ("02-素材", "03-制作/中间数据"):
            for path in (work / folder).rglob("*"):
                if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                    images.append(path)
                    if not re.search(r"\d{4,}$", path.stem):
                        by_size[path.stat().st_size].append(path)
    by_hash = defaultdict(list)
    for paths in by_size.values():
        if len(paths) > 1:
            for path in paths:
                by_hash[digest_file(path)].append(path)
    deletions = []
    uncertain = [
        text.removeprefix("__unparsed_reference__:")
        for text in texts
        if text.startswith("__unparsed_reference__:")
    ]
    for digest, paths in by_hash.items():
        if len(paths) < 2 or uncertain:
            continue
        protected, extras = [], []
        for path in paths:
            # Sequence directories and original-input references remain valid inputs
            # even when an individual numbered filename is not spelled out.
            tokens = (
                path.name.casefold(),
                path.parent.relative_to(root).as_posix().casefold(),
                str(path.parent).casefold(),
            )
            referenced = path.stem.isdecimal() or any(
                token and any(token in text for text in texts) for token in tokens
            )
            (protected if referenced else extras).append(path)
        if not protected:
            protected = [extras.pop(0)]
        for path in extras:
            deletions.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": digest,
                    "keeper": protected[0].relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "reason": "unreferenced_exact_duplicate",
                }
            )
    return {
        "schema_version": 1,
        "root": str(root),
        "scanned_images": len(images),
        "delete": deletions,
        "reference_scope": "current+historical+tasks+docs+tools",
        "protected": "unique images, all referenced files/directories and numbered sequences",
        "unparsed_references": uncertain,
    }


def apply_cleanup(plan: dict, *, root: Path, journal: Path) -> dict:
    root = root.resolve()
    if plan.get("root") != str(root) or not journal.resolve().is_relative_to(root):
        raise AutoDLError("Cleanup root/journal does not match this workspace")
    if journal.exists() or journal.suffix.lower() != ".json":
        raise AutoDLError(
            "Cleanup requires a new JSON journal; existing files are never overwritten"
        )
    # Rebuild protection immediately before deletion; a stale plan is not authority.
    with ExitStack() as locks:
        locks.enter_context(resource_lock(root / "projects", root=root))
        for project in sorted((root / "projects").glob("*/project.yaml")):
            locks.enter_context(resource_lock(project, root=root))
        # The same project-first order is used by normal asset writers. Lock
        # manifests as well for CLI producers that only update an existing list.
        for manifest in sorted((root / "projects").rglob("*.yaml")):
            if manifest.name != "project.yaml":
                locks.enter_context(resource_lock(manifest, root=root))
        plan_file = Path(plan["plan_file"]).resolve()
        if not plan_file.is_relative_to(root):
            raise AutoDLError("Cleanup plan must be inside this workspace")
        if json.loads(plan_file.read_text("utf-8")) != plan:
            raise AutoDLError("Cleanup plan file changed")
        current = cleanup_plan(root, excluded=(plan_file, journal.resolve()))
        allowed = {(row["path"], row["sha256"], row["keeper"]) for row in current["delete"]}
        for row in plan["delete"]:
            if (row["path"], row["sha256"], row["keeper"]) not in allowed:
                raise AutoDLError("Cleanup dependencies changed; rebuild the plan")
        result = {"deleted": [], "bytes_removed_logical": 0}
        atomic_json(journal, result)
        for row in plan["delete"]:
            path, keeper = root / row["path"], root / row["keeper"]
            if not keeper.resolve().is_relative_to(root / "projects"):
                raise AutoDLError("Duplicate keeper escapes projects")
            if digest_file(keeper) != row["sha256"]:
                raise AutoDLError("Duplicate keeper changed")
            # Preserve intent before the irreversible directory-entry deletion.
            result["pending"] = row
            atomic_json(journal, result)
            unlink_verified(path, boundary=root / "projects", expected=row["sha256"], keeper=keeper)
            result["deleted"].append(row)
            result["bytes_removed_logical"] += row["bytes"]
            result.pop("pending")
            atomic_json(journal, result)
        return result


def write_plan(root: Path, output: Path) -> dict:
    if not output.resolve().is_relative_to(root.resolve()) or output.suffix.lower() != ".json":
        raise AutoDLError("Cleanup plan must be a new JSON file inside the workspace")
    result = cleanup_plan(root)
    if output.exists():
        raise AutoDLError("Choose a new cleanup-plan filename")
    result["plan_file"] = str(output.resolve())
    atomic_json(output, result)
    return {
        "scanned_images": result["scanned_images"],
        "duplicates": len(result["delete"]),
        "plan": str(output),
    }
