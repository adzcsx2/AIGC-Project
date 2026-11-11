"""Independent project-specific geometry evidence, not a creative pass."""

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import require_hash, validate_sample_timeline, write_json_checked
from whitebox_saved import load_saved, project_path, sha

p = argparse.ArgumentParser()
p.add_argument("--project", required=True)
p.add_argument("--source", required=True)
p.add_argument("--output", required=True)
a = p.parse_args(sys.argv[sys.argv.index("--") + 1 :])
project = Path(a.project).resolve()
source = project_path(project, a.source, exists=True)
out = project_path(project, a.output)
if out.exists():
    raise FileExistsError(out)
source_hash = sha(source)
scene = load_saved(bpy, source, source_hash)
validate_sample_timeline(scene, [1, 768])
samples = []
for f in [
    1,
    30,
    90,
    150,
    220,
    261,
    267,
    271,
    279,
    284,
    342,
    357,
    365,
    374,
    397,
    413,
    440,
    463,
    503,
    511,
    518,
    590,
    629,
    665,
    695,
    719,
    754,
    768,
]:
    scene.frame_set(f)
    graph = bpy.context.evaluated_depsgraph_get()
    objects = {}
    for name in [
        "幼龙-躯干",
        "幼龙-后腰",
        "幼龙-胸腔",
        "幼龙-圆肚子",
        "幼龙-大头",
        "幼龙-耳鳍-1",
        "幼龙-耳鳍1",
        "幼龙-翼膜-1",
        "幼龙-翼膜1",
        "幼龙-可卷舌网格",
    ]:
        o = bpy.data.objects[name].evaluated_get(graph)
        m = o.to_mesh()
        pts = [o.matrix_world @ v.co for v in m.vertices]
        o.to_mesh_clear()
        objects[name] = {"min_z": min(v.z for v in pts), "max_z": max(v.z for v in pts)}
        if name == "幼龙-可卷舌网格":
            milk = bpy.data.objects["奶面"]
            center = milk.matrix_world.translation
            near = [
                v for v in pts if (Vector((v.x, v.y)) - Vector((center.x, center.y))).length < 0.32
            ]
            objects[name]["lowest_over_milk"] = min((v.z - center.z for v in near), default=None)
    samples.append(
        {
            "frame": f,
            "time": (f - scene.frame_start) * scene.render.fps_base / scene.render.fps,
            "objects": objects,
            "head": list(bpy.data.objects["控制-头部"].location),
            "eye_closed": bpy.data.objects["幼龙-上眼睑-1"]
            .data.shape_keys.key_blocks["闭眼"]
            .value,
        }
    )
require_hash(source, source_hash)
write_json_checked(
    out,
    {
        "source": a.source,
        "sha256": source_hash,
        "samples": samples,
        "interpretation": (
            "Actual evaluated vertices at selected frames. "
            "Not full collision, dynamic or listening acceptance."
        ),
    },
    project,
    lambda: require_hash(source, source_hash),
)
print(json.dumps({"output": str(out), "samples": len(samples)}, ensure_ascii=False))
