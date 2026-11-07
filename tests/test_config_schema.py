import base64
from decimal import Decimal
from pathlib import Path

import pytest

from autodl_video.config import load_token, load_yaml, project_root
from autodl_video.errors import AutoDLError
from autodl_video.runner import budget_decimal
from autodl_video.schema import estimate_cost, validate_inputs


@pytest.mark.parametrize(
    "body",
    [
        "raw-test-token",
        "# comment\nraw-test-token\n",
        "AUTODL_API_KEY=test-key",
        "AUTODL_TOKEN='test-key'",
        "autodl_apikey:test-key",
        "autodl_apikey: test-key",
        "autodl_apikey=test-key",
        'AUTODL_API_KEY: "test-key"',
        "# settings\nautodl_apikey:test-key\nOTHER_SETTING=unchanged",
    ],
)
def test_env_formats(tmp_path, monkeypatch, body):
    monkeypatch.delenv("AUTODL_API_KEY", raising=False)
    monkeypatch.delenv("AUTODL_TOKEN", raising=False)
    (tmp_path / ".env").write_text(body, encoding="utf-8-sig")
    expected = "raw-test-token" if "raw-test" in body else "test-key"
    assert load_token(tmp_path) == expected
    assert (tmp_path / ".env").read_text("utf-8-sig") == body


def test_env_priority_and_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTODL_API_KEY", "environment-token")
    assert load_token(tmp_path) == "environment-token"
    monkeypatch.delenv("AUTODL_API_KEY")
    monkeypatch.delenv("AUTODL_TOKEN", raising=False)
    with pytest.raises(AutoDLError, match="Set AUTODL_API_KEY"):
        load_token(tmp_path)


@pytest.mark.parametrize("token", ["two words", "Bearer-something"])
def test_bad_token_is_never_echoed(tmp_path, monkeypatch, token):
    monkeypatch.setenv("AUTODL_API_KEY", token)
    with pytest.raises(AutoDLError) as error:
        load_token(tmp_path)
    assert token not in str(error.value)


@pytest.mark.parametrize("body", ["inputs: 1\ninputs: 2", "- list", "x: !!python/object:bad {}"])
def test_yaml_rejects_duplicate_unsafe_or_nonmapping(tmp_path, body):
    path = tmp_path / "config.yaml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(AutoDLError):
        load_yaml(path)


def test_project_resolution(project, monkeypatch):
    subdir = project / "nested"
    subdir.mkdir()
    monkeypatch.chdir(subdir)
    assert project_root() == project
    assert project_root(str(project)) == project


@pytest.mark.parametrize(
    "inputs,match",
    [
        ({}, "Missing required"),
        ({"prompt": "ok", "typo": 1}, "Unknown input"),
        ({"prompt": "ok", "duration": True}, "expected integer"),
        ({"prompt": "ok", "duration": 1.1}, "expected integer"),
        ({"prompt": "ok", "duration": 0}, "must be >="),
        ({"prompt": "ok", "duration": 16}, "must be <="),
        ({"prompt": "ok", "resolution": "1080p"}, "choose one"),
        ({"prompt": " "}, "nonempty"),
        ({"prompt": None}, "null"),
        ({"prompt": "x" * 101}, "exceeds"),
    ],
)
def test_schema_boundaries(detail, inputs, match):
    with pytest.raises(AutoDLError, match=match):
        validate_inputs(inputs, detail["input_rules"], base_dir=Path("."))


def test_schema_optional_defaults_are_not_injected(detail):
    assert validate_inputs({"prompt": "ok"}, detail["input_rules"], base_dir=Path(".")) == {
        "prompt": "ok"
    }


@pytest.mark.parametrize(
    "kind,value,valid",
    [
        ("boolean", True, True),
        ("boolean", 1, False),
        ("number", 0.5, True),
        ("number", True, False),
        ("number", float("nan"), False),
        ("number", float("inf"), False),
        ("string", 1, False),
        ("future-type", "x", False),
    ],
)
def test_rule_types(kind, value, valid):
    rules = {"x": {"type": kind}}
    if valid:
        assert validate_inputs({"x": value}, rules, base_dir=Path("."))["x"] == value
    else:
        with pytest.raises(AutoDLError):
            validate_inputs({"x": value}, rules, base_dir=Path("."))


def test_media_local_base64_and_url(tmp_path):
    path = tmp_path / "reference.png"
    path.write_bytes(b"fake-image-data")
    rules = {"image": {"type": "image", "required": True, "accept_types": ["image/png"]}}
    inputs = {"image": "reference.png"}
    actual = validate_inputs(inputs, rules, base_dir=tmp_path)["image"]
    assert actual == "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()
    assert (
        "<local file"
        in validate_inputs(inputs, rules, base_dir=tmp_path, encode_media=False)["image"]
    )
    assert validate_inputs({"image": actual}, rules, base_dir=tmp_path)["image"] == actual
    assert (
        "<base64"
        in validate_inputs({"image": actual}, rules, base_dir=tmp_path, encode_media=False)["image"]
    )
    url = "https://example.org/image.png"
    assert validate_inputs({"image": url}, rules, base_dir=tmp_path)["image"] == url


@pytest.mark.parametrize(
    "value",
    [
        "missing.png",
        "data:image/png;base64,???",
        "data:image/png;base64,",
        "https://user:pass@example.org/x",
        "data:video/mp4;base64,YQ==",
        "https:///bad",
    ],
)
def test_bad_media(tmp_path, value):
    with pytest.raises(AutoDLError):
        validate_inputs(
            {"x": value}, {"x": {"type": "image", "accept_types": ["image/png"]}}, base_dir=tmp_path
        )


def test_media_format_empty_and_missing_required(tmp_path):
    (tmp_path / "x.txt").write_text("bad")
    (tmp_path / "empty.png").touch()
    rules = {
        "x": {
            "type": "image",
            "required": True,
            "default": "default_local_path:blank",
            "accept_types": ["image/png"],
        }
    }
    for inputs in ({}, {"x": "x.txt"}, {"x": "empty.png"}):
        with pytest.raises(AutoDLError):
            validate_inputs(inputs, rules, base_dir=tmp_path)


def test_cost_and_budget(detail):
    assert estimate_cost(detail, {"duration": 1, "resolution": "480p横"}) == Decimal("0.04")
    assert estimate_cost(detail, {}) == Decimal("0.20")
    assert estimate_cost(detail, {"resolution": "unknown"}) is None
    assert estimate_cost({**detail, "price_type": "audio_sec_cost"}, {}) is None
    assert budget_decimal("0.10") == Decimal("0.10")
    assert budget_decimal(None) is None


@pytest.mark.parametrize("value", ["bad", "NaN", "Infinity", -1, True])
def test_invalid_budget(value):
    with pytest.raises(AutoDLError):
        budget_decimal(value)
