"""Bind reviewed R05 stills to real u30 inputs without submitting a task."""

# ruff: noqa: E501 -- Exact Chinese artifact paths.
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "projects/悬崖上的小气球"
TAG = "空间重制05"
REVIEW = "05-检查与验收/空间重制05-实际素材与生成前总审计02.md"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")


def main() -> None:
    folder = P / "03-制作/制作计划" / TAG
    pack = json.loads((folder / "制作包02-实际图片待绑定.json").read_text("utf-8"))
    manifest_path = P / "素材清单-三视图更新01-资产归位01.yaml"
    manifest = yaml.safe_load(manifest_path.read_text("utf-8"))
    image_record_path = P / "06-记录/图片生成/空间重制05-归档结果01.json"
    images = json.loads(image_record_path.read_text("utf-8"))
    for item in pack["images"]:
        path = P / item["path"]
        assert path.is_file()
        with Image.open(path) as im:
            size = list(im.size)
        meta = next(x for x in images if x["id"] == item["id"])
        meta.update(
            path=item["path"],
            sha256=sha(path),
            dimensions=size,
            review_record=REVIEW,
            generation_mode="built_in_imagegen",
        )
        manifest["assets"][item["id"]] = {
            "kind": "keyframe",
            "path": item["path"],
            "sha256": sha(path),
            "state": "ready",
            "required": True,
            "purpose": "facial_expression_and_eyeline_only"
            if "ANGER" in item["id"]
            else "stage_specific_world_pose_scale_composition",
            "review_record": REVIEW,
            "assistant_review": "Actual returned image inspected; stage-specific soft reference. Does not certify hard3D dimensions or future motion.",
            "user_review": "Spatial plan accepted; assistant preparation/review authorized. No individual image acceptance inferred.",
        }
    save(image_record_path, images)
    auth = "06-记录/用户确认/空间重制05-四段方案接受与重做合并授权接续-20261112.json"
    config_dir = P / "03-制作/生成配置" / TAG
    config_dir.mkdir(parents=True, exist_ok=True)
    for unit in pack["units"]:
        ids = pack["common_asset_ids"] + [unit["main_id"]] + unit["aux_ids"]
        bindings = {f"ref_image_{i}": aid for i, aid in enumerate(ids)}
        if "dialogue" in unit:
            bindings["ref_audio_0"] = "VOICE-GIRL"
        shot_id = f"CLIFF-{unit['n']:02d}-U30-R05"
        manifest["shots"][shot_id] = {
            "speakers": ["CHAR-GIRL"] if "dialogue" in unit else [],
            "voice_bindings": {"ref_audio_0": "CHAR-GIRL"} if "dialogue" in unit else {},
            "required_assets": list(bindings.values()),
            "reference_bindings": bindings,
            "purpose": unit["name"],
            "authorization_ref": auth,
        }
        inputs = {"prompt": unit["prompt"]}
        for field, aid in bindings.items():
            inputs[field] = str((P / manifest["assets"][aid]["path"]).resolve())
        inputs.update(duration=unit["duration"], resolution="768p横")
        cfg = {
            "workflow_id": pack["workflow"],
            "materials_manifest": "../../../素材清单-三视图更新01-资产归位01.yaml",
            "shot_id": shot_id,
            "inputs": inputs,
            "output_dir": str(P / "04-输出/原始片段" / TAG / f"片段{unit['n']:02d}"),
            "timeout": 3600,
            "poll_interval": 15,
        }
        cfg_path = config_dir / f"片段{unit['n']:02d}-{unit['name']}-执行02.yaml"
        assert not cfg_path.exists(), "Do not overwrite a potentially submitted configuration."
        cfg_path.write_text(
            yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False, width=100), "utf-8"
        )
        unit.update(
            shot_id=shot_id,
            config_path=cfg_path.relative_to(P).as_posix(),
            config_sha256=sha(cfg_path),
            reference_bindings=bindings,
            actual_asset_pins={
                field: {"id": aid, "sha256": sha(Path(inputs[field]))}
                for field, aid in bindings.items()
            },
        )
    manifest_path.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False, width=100), "utf-8"
    )
    style_path = P / yaml.safe_load((P / "project.yaml").read_text("utf-8"))["documents"]["style"]
    pack.update(
        state="actual_inputs_bound_pending_total_audit_and_validation",
        style={"path": style_path.relative_to(P).as_posix(), "sha256": sha(style_path)},
        review_record=REVIEW,
    )
    save(folder / "制作包03-实际输入.json", pack)
    text = "# 空间重制05：实际英文执行稿02\n\n用户已接受四段空间方案；本文件正文与真实执行配置逐字相同。是否提交仍按总审计/实际校验门槛。\n\n"
    for unit in pack["units"]:
        text += f"## 视频{unit['n']:02d}：{unit['name']}（{unit['duration']}秒）\n\n```text\n{unit['prompt']}\n```\n\n"
    text += "## 实际图片生成正文及局部修正\n\n"
    for item in images:
        text += f"### {item['id']}\n\n```text\n{item['prompt']}\n```\n\n"
        if item.get("targeted_edit_prompt"):
            text += f"局部修正：\n\n```text\n{item['targeted_edit_prompt']}\n```\n\n"
    doc = P / "01-文档/提示词/空间重制05-实际英文执行稿02.md"
    doc.write_text(text, "utf-8")
    pp = P / "project.yaml"
    project = yaml.safe_load(pp.read_text("utf-8"))
    project["documents"].update(
        spatial_R05_actual_inputs="03-制作/制作计划/空间重制05/制作包03-实际输入.json",
        spatial_R05_actual_prompts=doc.relative_to(P).as_posix(),
        spatial_R05_pre_audit=REVIEW,
    )
    project["current"].update(
        stage="formal_first5_u30_R05_pre_submission",
        next_step="7张新图已制作并审看；真实配置已绑定，待总审计与材料/接口校验通过后按接受的四段方案提交各一次。",
    )
    pp.write_text(yaml.safe_dump(project, allow_unicode=True, sort_keys=False, width=100), "utf-8")
    print(
        json.dumps(
            {"configs": [u["config_path"] for u in pack["units"]], "images": len(images)},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
