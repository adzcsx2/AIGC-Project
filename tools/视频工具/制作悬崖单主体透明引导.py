"""Local single-cylinder proposal; no API submission and no detailed modeling."""

import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "projects/悬崖上的小气球"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import save_checked

source = WORK / "03-制作/三维工程/一致性五秒测试-圆柱白模-版本02.blend"
assert hashlib.sha256(source.read_bytes()).hexdigest() == "749a3b0f20236bfa7a59327f4afb1b2f4dbc56289180da36e8e2e8964577d236"
bpy.ops.wm.open_mainfile(filepath=str(source))
scene = bpy.context.scene
for obj in scene.objects:
    if obj.type == "MESH":
        obj.hide_render = obj.name != "占位-幼龙"
scene.render.film_transparent = True
scene.render.resolution_percentage = 50
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.display.shading.show_shadows = False
directory = WORK / "03-制作/中间数据/一致性测试-titim03/单圆柱透明层"
directory.mkdir(parents=True, exist_ok=False)
scene.render.filepath = str(directory / "帧-")
copy = WORK / "03-制作/三维工程/一致性五秒测试-单圆柱候选03.blend"
digest = save_checked(bpy, copy, WORK, lambda: None)
bpy.ops.render.render(animation=True)
with (WORK / "05-检查与验收/一致性测试-titim03-本地构建记录.json").open("x", encoding="utf-8") as f:
    json.dump(
        {
            "source": str(source.relative_to(WORK)),
            "copy": str(copy.relative_to(WORK)),
            "sha256": digest,
            "visible_mesh_count": 1,
            "changed": "Hide girl and tail-rod proxies in the render only. Actual girl comes from the photo plate. Original source, cylinder geometry, camera and Z animation unchanged.",
            "frames": 120,
            "fps": 24,
            "status": "local_proposal_not_generated",
        }, f, ensure_ascii=False, indent=2,
    )
print("Single-cylinder transparent proposal rendered; original sources preserved.")
