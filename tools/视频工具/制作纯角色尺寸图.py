"""Render only the two existing character planes from an audited scale-chart blend."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("project")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
root = Path(args.project).resolve(strict=True)
source = root / "03-制作/三维工程/身高参考四图测试04-尺寸图布局01.blend"
target = root / "03-制作/三维工程/u30六图同框测试07-纯角色比例布局01.blend"
image = root / "02-素材/尺寸参考/u30六图同框测试07/米娅左-咕噜右-纯站立比例-定稿03.png"
record = root / "06-记录/图片生成/u30六图同框测试07-纯站立比例渲染03.json"
assert (root / "project.yaml").is_file()
for path in (source, target, image, record):
    assert path.resolve().is_relative_to(root)
for path in (target, image, record):
    assert not path.exists(), str(path)
    path.parent.mkdir(parents=True, exist_ok=True)

source_sha = sha(source)
bpy.ops.wm.open_mainfile(filepath=str(source))
keep = {"MIA-cutout", "GULU-cutout", "Chart-background", "Chart-camera"}
assert keep <= set(bpy.data.objects.keys())
hidden = []
for obj in bpy.data.objects:
    if obj.name not in keep:
        obj.hide_render = True
        hidden.append(obj.name)
scene = bpy.context.scene
scene.render.filepath = str(image)
assert scene.camera.name == "Chart-camera" and scene.camera.data.type == "ORTHO"
assert (scene.render.resolution_x, scene.render.resolution_y) == (1800, 1000)
placements = {
    name: {
        "location": list(bpy.data.objects[name].location),
        "scale": list(bpy.data.objects[name].scale),
    }
    for name in ("MIA-cutout", "GULU-cutout")
}
bpy.ops.wm.save_as_mainfile(filepath=str(target), check_existing=False)
bpy.ops.render.render(write_still=True)
assert sha(source) == source_sha
record.write_text(json.dumps({
    "source": str(source.relative_to(root)), "source_sha256": source_sha,
    "blend": str(target.relative_to(root)), "blend_sha256": sha(target),
    "image": str(image.relative_to(root)), "image_sha256": sha(image),
    "rendered_objects": sorted(keep), "hidden_objects": hidden,
    "placements_unchanged": placements, "standing_cm": {"MIA": 130, "GULU": 40},
    "source_chart_measurement": {"MIA_pixels": 727, "GULU_pixels": 222, "baseline_y": 830},
    "scope": "Native layout edit only; no new geometry, identity generation or guide video."
}, ensure_ascii=False, indent=2), encoding="utf-8")
print("COMPLETED", str(image))
