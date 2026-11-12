"""Archive reviewed R04 image assets and bind the three authorized u30 requests."""

# ruff: noqa: E501 -- Exact audited prompt text and Chinese artifact paths.
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "projects/悬崖上的小气球"
TAG = "局部重制04"
GEN = Path("C:/Users/long/.codex/generated_images/01a1c83f-3fe5-7412-b65c-29237be12733")
SOURCES = [
    "exec-45beb18d-0ecd-4e19-95eb-1d9eba1c28d4.png",
    "exec-0d8c6e80-233e-4ce5-b5f9-3c34e710eb09.png",
    "exec-646368d7-fcc3-4fb4-99dc-9f922dd8d824.png",
    "exec-386a2d9f-449d-48fb-b473-d36d2c68ea5a.png",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")


def main() -> None:
    plan_dir = PROJECT / "03-制作/制作计划" / TAG
    pack = json.loads((plan_dir / "制作包01.json").read_text("utf-8"))
    manifest_path = PROJECT / "素材清单-三视图更新01-资产归位01.yaml"
    manifest = yaml.safe_load(manifest_path.read_text("utf-8"))
    review = "05-检查与验收/局部重制04-实际素材与生成前总审计02.md"
    image_record = []
    for item, source in zip(pack["images"], SOURCES, strict=True):
        target = PROJECT / item["path"]
        if item["id"] == "R04-05-GIRL":
            target = target.with_name("片段05-女孩第二次笑-中景02.png")
            item["path"] = target.relative_to(PROJECT).as_posix()
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and sha(target) != sha(GEN / source):
            raise RuntimeError(f"Refusing to overwrite different bytes: {target}")
        shutil.copyfile(GEN / source, target)
        with Image.open(target) as im:
            dimensions = list(im.size)
        entry = {
            "id": item["id"],
            "path": target.relative_to(PROJECT).as_posix(),
            "source": str(GEN / source),
            "sha256": sha(target),
            "dimensions": dimensions,
            "prompt": item["prompt"],
            "review_record": review,
            "generation_mode": "built_in_imagegen",
        }
        if item["id"] == "R04-05-GIRL":
            initial = target.with_name("片段05-女孩第二次笑-宽景候选01.png")
            shutil.copyfile(GEN / "exec-232dbd97-77be-4054-9695-4e5df69aaa2d.png", initial)
            entry["initial_candidate"] = initial.relative_to(PROJECT).as_posix()
            entry["targeted_edit_prompt"] = (
                "Reframe Reference1 ONLY into a low 50mm MEDIUM REACTION SHOT. Preserve the same girl identity, "
                "open laughing expression, right hand on belly, loaded LEFT elbow on grass, low reclining torso, "
                "clothing, scene, upper-left daylight and medieval photoreal live-action materials. Frame from a "
                "little above her hair to her waist/hip and the full supporting elbow/forearm. Her head should occupy "
                "roughly one third of the image height, with clear headroom and the elbow fully inside the bottom edge. "
                "Her boots and lower legs must be outside the frame. No sitting, standing, new pose, dragon, text, collage "
                "or new backdrop. Keep the two timber/plaster cottages and right tree as softly defocused world anchors "
                "at the same camera axis. Do not widen back to a full-body composition."
            )
        image_record.append(entry)
        manifest["assets"][item["id"]] = {
            "kind": "keyframe",
            "path": entry["path"],
            "sha256": entry["sha256"],
            "state": "ready",
            "required": True,
            "purpose": "later_dragon_angry_expression"
            if "ANGER" in item["id"]
            else "initial_shot_pose_scale_environment",
            "review_record": review,
            "assistant_review": "Actual returned image inspected; stage-specific framing/pose/expression reference, not a hard geometry guarantee.",
            "user_review": "User explicitly authorized audit, preparation, redo and merge; no individual image acceptance inferred.",
        }
    landing = pack["shared_landing"]
    manifest["assets"][landing["id"]] = {
        "kind": "keyframe",
        "path": Path(landing["path"]).as_posix(),
        "sha256": landing["sha256"],
        "state": "ready",
        "required": True,
        "purpose": "shared_end02_later03_grass_landing_state",
        "review_record": review,
    }
    common = [
        "CHAR-GIRL-THREEVIEW",
        "CHAR-DRAGON-THREEVIEW",
        "HEIGHT-CHART-R04",
        "U30-R07-STANDING-PAIR",
        "HEIGHT-EMPTY-SCENE-R04",
    ]
    authorization = "06-记录/用户确认/局部重制04-审计重做合并授权-20261112.json"
    config_dir = PROJECT / "03-制作/生成配置" / TAG
    config_dir.mkdir(parents=True, exist_ok=True)
    for unit in pack["units"]:
        prompt = unit["prompt"]
        for i in range(1, 8):
            prompt = prompt.replace(f"Image{i}", f"Image {i}").replace(f"Images{i}", f"Images {i}")
        prompt = re.sub(r"(?<=\d)(cm|mm|seconds|seconds|s)(?=\b)", r" \1", prompt)
        prompt = (
            prompt.replace("second16:9", "second 16:9")
            .replace("about0", "about 0")
            .replace("about6", "about 6")
            .replace("low50", "low 50")
            .replace("lateral35", "lateral 35")
            .replace("stable70", "stable 70")
            .replace("low70", "low 70")
        )
        unit["prompt"] = prompt
        ids = common + [unit["main_id"], unit["aux_id"]]
        bindings = {f"ref_image_{i}": asset_id for i, asset_id in enumerate(ids)}
        if unit["n"] in (3, 5):
            bindings["ref_audio_0"] = "VOICE-GIRL"
        unit["shot_id"] = f"CLIFF-{unit['n']:02d}-U30-R04"
        manifest["shots"][unit["shot_id"]] = {
            "speakers": ["CHAR-GIRL"] if unit["n"] in (3, 5) else [],
            "voice_bindings": {"ref_audio_0": "CHAR-GIRL"} if unit["n"] in (3, 5) else {},
            "required_assets": list(bindings.values()),
            "reference_bindings": bindings,
            "purpose": unit["name"],
            "authorization_ref": authorization,
        }
        inputs = {"prompt": prompt}
        for field, asset_id in bindings.items():
            inputs[field] = str((PROJECT / manifest["assets"][asset_id]["path"]).resolve())
        inputs.update(duration=unit["duration"], resolution="768p横")
        config = {
            "workflow_id": "minimax_h3_zm_u30",
            "materials_manifest": "../../../素材清单-三视图更新01-资产归位01.yaml",
            "shot_id": unit["shot_id"],
            "inputs": inputs,
            "output_dir": str(PROJECT / "04-输出/原始片段" / TAG / f"片段{unit['n']:02d}"),
            "timeout": 3600,
            "poll_interval": 15,
        }
        config_path = config_dir / f"片段{unit['n']:02d}-{unit['name']}-执行02.yaml"
        config_path.write_text(
            yaml.safe_dump(config, allow_unicode=True, sort_keys=False, width=100), "utf-8"
        )
        unit["config_path"] = config_path.relative_to(PROJECT).as_posix()
        unit["config_sha256"] = sha(config_path)
        unit["reference_bindings"] = bindings
        unit["actual_asset_pins"] = {
            field: {"id": asset_id, "sha256": sha(Path(inputs[field]))}
            for field, asset_id in bindings.items()
        }
    manifest_path.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False, width=100), "utf-8"
    )
    pack["review_record"] = review
    pack["image_generation_record"] = "06-记录/图片生成/局部重制04-归档结果01.json"
    write_json(PROJECT / pack["image_generation_record"], image_record)
    write_json(plan_dir / "制作包02-实际输入.json", pack)
    prompt_doc = PROJECT / "01-文档/提示词/局部重制04-英文执行稿02-实际输入.md"
    text = "# 局部重制04：实际英文执行稿02\n\n模型：u30；无白模。每段7张图，03/05绑定米娅已确认英文声音。\n\n"
    for unit in pack["units"]:
        text += f"## 片段{unit['n']:02d}：{unit['name']}（{unit['duration']}秒）\n\n```text\n{unit['prompt']}\n```\n\n"
    text += "## 图片实际正文\n\n"
    for item in image_record:
        text += f"### {item['id']}\n\n```text\n{item['prompt']}\n```\n\n"
        if "targeted_edit_prompt" in item:
            text += f"局部重构图：\n\n```text\n{item['targeted_edit_prompt']}\n```\n\n"
    prompt_doc.write_text(text, "utf-8")
    project_path = PROJECT / "project.yaml"
    project = yaml.safe_load(project_path.read_text("utf-8"))
    project["current"].update(
        stage="formal_first5_u30_R04_pre_submission",
        version=TAG,
        next_step="新素材已制作；完成真实输入校验与总审计后按本轮授权提交02/03/05各一次。",
    )
    project["documents"].update(
        local_R04_plan="03-制作/制作计划/局部重制04/制作包02-实际输入.json",
        local_R04_prompts=prompt_doc.relative_to(PROJECT).as_posix(),
        local_R04_pre_audit=review,
    )
    project_path.write_text(
        yaml.safe_dump(project, allow_unicode=True, sort_keys=False, width=100), "utf-8"
    )
    print(
        json.dumps(
            {
                "configs": [u["config_path"] for u in pack["units"]],
                "image_count": len(image_record),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
