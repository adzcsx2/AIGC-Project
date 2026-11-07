"""Validate the server's dynamic input_rules rather than a hand-written model list."""

from __future__ import annotations

import base64
import binascii
import math
import mimetypes
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

from .errors import AutoDLError

MEDIA_TYPES = {"image", "audio", "video"}
MAX_MEDIA_BYTES = 100 * 1024 * 1024


def _media(value: str, rule: dict, base_dir: Path, *, encode: bool) -> str:
    accept = rule.get("accept_types", [])
    if value.startswith(("http://", "https://")):
        parsed = urlsplit(value)
        if not parsed.hostname or parsed.username or parsed.password:
            raise AutoDLError("Media URL must have a host and no embedded credentials")
        return value
    if value.startswith("data:"):
        header, separator, payload = value.partition(",")
        mime = header[5:].removesuffix(";base64")
        if not separator or not header.endswith(";base64") or (accept and mime not in accept):
            raise AutoDLError("Media must be a supported base64 data URL")
        if len(payload) > (MAX_MEDIA_BYTES * 4 // 3 + 8):
            raise AutoDLError("Media exceeds the 100 MiB client limit")
        try:
            decoded = base64.b64decode(payload, validate=True)
        except (ValueError, binascii.Error):
            raise AutoDLError("Invalid base64 media") from None
        if not decoded or len(decoded) > MAX_MEDIA_BYTES:
            raise AutoDLError("Empty or oversized media")
        return value if encode else f"<base64 {mime}, {len(decoded)} bytes>"
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    if not path.is_file():
        raise AutoDLError(f"Media file does not exist: {path}")
    mime = mimetypes.guess_type(path.name)[0]
    mime = {"audio/x-wav": "audio/wav", "audio/vnd.wave": "audio/wav"}.get(mime, mime)
    if not mime or (accept and mime not in accept):
        raise AutoDLError(f"Unsupported media format for {path.name}; allowed: {accept}")
    size = path.stat().st_size
    if size < 1 or size > MAX_MEDIA_BYTES:
        raise AutoDLError("Media must be nonempty and at most 100 MiB")
    if not encode:
        return f"<local file {path.name}, {mime}, {size} bytes>"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def validate_inputs(
    inputs: dict, rules: dict, *, base_dir: Path, encode_media: bool = True
) -> dict:
    if not isinstance(inputs, dict) or any(not isinstance(k, str) for k in inputs):
        raise AutoDLError("inputs must be a mapping with string keys")
    unknown = inputs.keys() - rules.keys()
    if unknown:
        raise AutoDLError(f"Unknown input parameter(s): {', '.join(sorted(unknown))}")
    prepared = {}
    for name, rule in rules.items():
        # Required media must be supplied even if the server lists a blank-image default.
        if name not in inputs:
            if rule.get("required"):
                raise AutoDLError(f"Missing required input: {name}")
            continue  # Let the service supply its optional defaults.
        value = inputs[name]
        kind = rule.get("type")
        if value is None:
            raise AutoDLError(f"{name}: null is not a valid value; omit optional parameters")
        if kind in {"integer", "number"}:
            expected = (int,) if kind == "integer" else (int, float)
            if isinstance(value, bool) or not isinstance(value, expected):
                raise AutoDLError(f"{name}: expected {kind}")
            if isinstance(value, float) and not math.isfinite(value):
                raise AutoDLError(f"{name}: number must be finite")
            if "min" in rule and value < rule["min"]:
                raise AutoDLError(f"{name}: must be >= {rule['min']}")
            if "max" in rule and value > rule["max"]:
                raise AutoDLError(f"{name}: must be <= {rule['max']}")
        elif kind == "boolean":
            if not isinstance(value, bool):
                raise AutoDLError(f"{name}: expected a boolean")
        elif kind == "enum":
            choices = [v["label"] if isinstance(v, dict) else v for v in rule.get("options", [])]
            if not isinstance(value, str) or value not in choices:
                raise AutoDLError(f"{name}: choose one of {choices}")
        elif kind in {"string", "prompt", *MEDIA_TYPES}:
            if not isinstance(value, str) or not value.strip():
                raise AutoDLError(f"{name}: expected a nonempty string")
            if len(value) < rule.get("min_length", 0):
                raise AutoDLError(f"{name}: text is too short")
            if "max_length" in rule and len(value) > rule["max_length"]:
                raise AutoDLError(f"{name}: text exceeds {rule['max_length']} characters")
            if kind in MEDIA_TYPES:
                value = _media(value, rule, base_dir, encode=encode_media)
        else:
            raise AutoDLError(f"{name}: unsupported server parameter type {kind!r}")
        prepared[name] = value
    return prepared


def estimate_cost(workflow: dict, inputs: dict) -> Decimal | None:
    """Conservative peak/off-peak maximum in CNY, for duration-based H3 workflows only."""
    if workflow.get("price_type") != "minimax_h3":
        return None
    rules = workflow["input_rules"]
    duration = inputs.get("duration", rules.get("duration", {}).get("default"))
    resolution = inputs.get("resolution", rules.get("resolution", {}).get("default", ""))
    if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
        return None
    for row in workflow.get("billing_config", {}).get("minimax_h3", []):
        if str(resolution).startswith(str(row.get("resolution", "NO_MATCH"))):
            try:
                peak = Decimal(str(row["price"]))
                off_peak = Decimal(str(row.get("off_peak_price", row["price"])))
            except (KeyError, InvalidOperation):
                return None
            if not peak.is_finite() or not off_peak.is_finite() or min(peak, off_peak) < 0:
                return None
            return max(peak, off_peak) * duration / Decimal(1000)
    return None
