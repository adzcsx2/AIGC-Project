"""Character speech language, independent of the conversation/prompt language."""

from __future__ import annotations

import re

from .errors import AutoDLError


def language_code(value: object = "en") -> str:
    """Accept a language tag (en, zh, en-US, zh-Hans); missing means English."""
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", value
    ):
        raise AutoDLError("language需要语言代码，例如en、zh、en-US；默认en")
    parts = value.split("-")
    return "-".join(
        [parts[0].lower()]
        + [
            part.upper() if len(part) == 2 else part.title() if len(part) == 4 else part
            for part in parts[1:]
        ]
    )
