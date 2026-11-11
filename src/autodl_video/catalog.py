"""Refresh the public workflow catalog without transmitting a Token."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from .client import AutoDLClient
from .config import atomic_text, load_yaml
from .errors import AutoDLError


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def category(workflow_id: str) -> str:
    if "indextts" in workflow_id:
        return "text-to-speech"
    if "retargeting" in workflow_id or "_titi" in workflow_id:
        return "motion-transfer"
    if workflow_id in {"minimax_h3_lightx2v_no_pic", "minimax_h3_b99_001", "minimax_h3_z0901"}:
        return "text-to-video"
    if workflow_id in {"minimax_h3_lightx2v", "minimax_h3_b99_002"}:
        return "first-last-frame"
    if workflow_id == "minimax_h3_image_audio_to_video":
        return "lip-sync"
    return "reference-to-video"


def entry_from_detail(detail: dict) -> dict:
    workflow_id = detail["uuid"]
    return {
        "name": detail.get("name", workflow_id),
        "description": detail.get("description", ""),
        "category": category(workflow_id),
        "source_url": f"https://autodl.art/large-model/comfyui/{workflow_id}",
        "metadata_url": f"https://autodl.art/api/v1/comfyui/workflows/{workflow_id}",
        "version": detail.get("version"),
        "updated_at": detail.get("updated_at"),
        "input_rules": detail["input_rules"],
        "input_example": detail.get("input_example", ""),
        "output_example": detail.get("output_example", ""),
        "price_type": detail.get("price_type"),
        "billing_config": detail.get("billing_config", {}),
        "endpoint_info": detail.get("endpoint_info", {}),
        "instructions": detail.get("content", ""),
    }


def load_catalog(root: Path) -> dict:
    path = root / "catalog" / "workflows.yaml"
    if not path.exists():
        raise AutoDLError("Catalog not found; run: autodl models sync")
    catalog = load_yaml(path)
    if catalog.get("schema_version") != 1 or not isinstance(catalog.get("workflows"), dict):
        raise AutoDLError("Unsupported catalog format; run: autodl models sync")
    return catalog


def get_workflow(root: Path, workflow_id: str) -> dict:
    workflows = load_catalog(root)["workflows"]
    if workflow_id not in workflows:
        raise AutoDLError(f"Unknown workflow: {workflow_id}; run autodl models list")
    return workflows[workflow_id]


def sync_catalog(root: Path, client: AutoDLClient, *, check: bool = False) -> dict:
    # Complete every page and detail read before replacing any local file.
    listing = client.workflows()
    entries = {}
    for item in sorted(listing, key=lambda item: item["uuid"]):
        entries[item["uuid"]] = entry_from_detail(client.workflow(item["uuid"]))
    if not entries:
        raise AutoDLError("Refusing to replace the catalog with an empty result")
    path = root / "catalog" / "workflows.yaml"
    old = load_catalog(root)["workflows"] if path.exists() else {}
    changes = {
        "added": sorted(entries.keys() - old.keys()),
        "removed": sorted(old.keys() - entries.keys()),
        "changed": sorted(key for key in entries.keys() & old.keys() if entries[key] != old[key]),
    }
    if not check:
        document = {
            "schema_version": 1,
            "provider": "autodl",
            "source_url": "https://autodl.art/large-model/comfyui",
            "synced_at": utc_now(),
            "workflows": entries,
        }
        atomic_text(path, yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=100))
        atomic_text(root / "docs" / "工具与接口" / "models.md", catalog_markdown(document))
    return {"total": len(entries), "check_only": check, **changes}


def catalog_markdown(document: dict) -> str:
    lines = [
        "# AutoDL 工作流目录",
        "",
        f"同步时间：{document['synced_at']}",
        "",
        "由 `autodl models sync` 生成。参数以 `catalog/workflows.yaml` 的 input_rules 为准。",
        "价格和目录接口属于网页使用的接口，平台调整时可能需要更新适配。",
        "",
        "| 工作流 ID | 名称 | 分类 | 必填项 |",
        "|---|---|---|---|",
    ]
    for workflow_id, item in document["workflows"].items():
        required = ", ".join(k for k, v in item["input_rules"].items() if v.get("required"))
        name = item["name"].replace("|", "\\|")
        lines.append(f"| `{workflow_id}` | {name} | {item['category']} | {required} |")
    lines += [
        "",
        "查看单个工作流的参数、选项和使用说明：",
        "",
        "```powershell",
        "autodl models show minimax_h3_lightx2v_no_pic",
        "```",
        "",
    ]
    return "\n".join(lines)
