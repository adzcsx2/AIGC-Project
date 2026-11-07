from pathlib import Path

import pytest
import yaml


@pytest.fixture
def detail():
    return {
        "uuid": "demo",
        "name": "演示模型",
        "description": "A test workflow",
        "input_rules": {
            "prompt": {"type": "prompt", "required": True, "min_length": 1, "max_length": 100},
            "duration": {"type": "integer", "min": 1, "max": 15, "default": 5},
            "resolution": {
                "type": "enum",
                "default": "480p横",
                "options": [{"label": "480p横"}, {"label": "768p竖"}],
            },
        },
        "price_type": "minimax_h3",
        "billing_config": {
            "minimax_h3": [
                {"resolution": "480p", "price": 40, "off_peak_price": 30},
                {"resolution": "768p", "price": 50, "off_peak_price": 40},
            ]
        },
    }


@pytest.fixture
def project(tmp_path, detail, monkeypatch):
    from autodl_video.catalog import entry_from_detail

    monkeypatch.delenv("AUTODL_API_KEY", raising=False)
    monkeypatch.delenv("AUTODL_TOKEN", raising=False)
    (tmp_path / "catalog").mkdir()
    (tmp_path / "catalog/workflows.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "workflows": {"demo": entry_from_detail(detail)},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("fake-test-token", encoding="utf-8")
    return tmp_path


@pytest.fixture
def config(project):
    path = Path(project) / "sample.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "workflow_id": "demo",
                "inputs": {"prompt": "测试镜头", "duration": 1, "resolution": "480p横"},
                "max_cost_cny": 0.10,
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return path
