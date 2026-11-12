"""Render the existing diagnostic cylinders over transparency, in a new saved copy."""

import hashlib
import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "projects/悬崖上的小气球"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import save_checked

source = WORK / "03-制作/三维工程/一致性五秒测试-圆柱白模-版本02.blend"
assert hashlib.sha256(source.read_bytes()).hexdigest() == "749a3b0f20236bfa7a59327f4afb1b2f4dbc56289180da36e8e2e8964577d236"
bpy.ops.wm.open_mainfile(filepath=str(source))
scene = bpy.context.scene
actors = {"占位-女孩", "占位-幼龙", "占位-幼龙-尾向"}
for obj in scene.objects:
    if obj.type == "MESH":
        obj.hide_render = obj.name not in actors
scene.render.film_transparent = True
scene.render.resolution_percentage = 50
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.image_settings.color_depth = "8"
scene.display.shading.show_shadows = False
scene.display.shading.show_cavity = True
output = WORK / "03-制作/中间数据/一致性测试-titim01/圆柱透明层"
output.mkdir(parents=True, exist_ok=False)
scene.render.filepath = str(output / "帧-")
copy = WORK / "03-制作/三维工程/一致性五秒测试-透明圆柱层-版本01.blend"
digest = save_checked(bpy, copy, WORK, lambda: None)
bpy.ops.render.render(animation=True)
proof = {
    "source": str(source.relative_to(WORK)),
    "copy": str(copy.relative_to(WORK)),
    "copy_sha256": digest,
    "changed": "Render visibility, transparency and resolution only; camera, actor geometry and all animation unchanged.",
    "frames": len(list(output.glob("帧-*.png"))),
    "fps": scene.render.fps,
    "dimensions": [960, 540],
    "actors": sorted(actors),
}
record = WORK / "05-检查与验收/一致性测试-titim01-透明层构建.json"
with record.open("x", encoding="utf-8") as stream:
    json.dump(proof, stream, ensure_ascii=False, indent=2)
print(json.dumps(proof, ensure_ascii=True))
