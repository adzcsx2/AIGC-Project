"""Project paths, strict YAML and backwards-compatible .env loading."""

from __future__ import annotations

import io
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values

from .errors import AutoDLError


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _mapping(loader: UniqueKeyLoader, node: Any, deep: bool = False) -> dict:
    pairs = loader.construct_pairs(node, deep=deep)
    result = {}
    for key, value in pairs:
        if not isinstance(key, (str, int, float, bool, type(None))):
            raise AutoDLError("YAML mapping keys must be scalar values")
        if key in result:
            raise AutoDLError(f"Duplicate YAML key: {key}")
        result[key] = value
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_yaml(path: Path) -> dict:
    try:
        if path.stat().st_size > 8 * 1024 * 1024:
            raise AutoDLError(f"YAML file is too large: {path}")
        value = yaml.load(path.read_text(encoding="utf-8-sig"), Loader=UniqueKeyLoader)
    except (OSError, yaml.YAMLError, RecursionError) as exc:
        raise AutoDLError(f"Cannot read YAML {path}: {type(exc).__name__}") from None
    if not isinstance(value, dict):
        raise AutoDLError(f"Expected a YAML mapping in {path}")
    return value


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        prefix=path.name + ".",
        suffix=".tmp",
        delete=False,
    ) as output:
        temporary = Path(output.name)
        try:
            output.write(text)
        except BaseException:
            output.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def project_root(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).resolve()
    for candidate in [Path.cwd(), *Path.cwd().parents, Path(__file__).resolve().parents[2]]:
        if (candidate / "catalog" / "workflows.yaml").exists():
            return candidate
        if (candidate / "pyproject.toml").exists():
            if 'name = "autodl-aigc"' in (candidate / "pyproject.toml").read_text("utf-8"):
                return candidate
    return Path.cwd()


def load_token(root: Path) -> str:
    names = ("AUTODL_API_KEY", "AUTODL_APIKEY", "AUTODL_TOKEN")
    token = next((os.environ[n].strip() for n in names if os.environ.get(n, "").strip()), "")
    path = root / ".env"
    if not token and path.exists():
        raw = path.read_text(encoding="utf-8-sig").strip()
        lines = [
            line.strip()
            for line in raw.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if len(lines) == 1 and not re.match(r"^(?:export\s+)?[A-Za-z_]\w*\s*[=:]", lines[0]):
            token = lines[0]
        else:
            normalized = []
            for line in raw.splitlines():
                match = re.match(r"^\s*(?:export\s+)?([A-Za-z_]\w*)\s*:\s*(.*)$", line)
                if match and match[1].upper() in names:
                    line = f"{match[1]}={match[2]}"
                normalized.append(line)
            parsed = dotenv_values(stream=io.StringIO("\n".join(normalized)))
            values = {name.upper(): value for name, value in parsed.items()}
            token = next((str(values[n]).strip() for n in names if values.get(n)), "")
    if not token:
        raise AutoDLError("Set AUTODL_API_KEY in .env (or keep a single bare Token line)")
    if any(character.isspace() for character in token):
        raise AutoDLError("The Token contains whitespace; use the raw ComfyUI Token")
    if token.lower().startswith("bearer"):
        raise AutoDLError("AutoDL expects the raw Token without a Bearer prefix")
    return token
