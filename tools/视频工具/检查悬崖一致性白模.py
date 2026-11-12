import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from whitebox_saved import load_saved, write_json_new

work = Path(__file__).resolve().parents[2] / "projects/悬崖上的小气球"
record = json.loads(
    (work / "05-检查与验收/一致性五秒测试01-白模构建02.json").read_text(encoding="utf-8")
)
scene = load_saved(bpy, record["blend"], record["sha256"])
names = ["占位-女孩", "摄影机-一致性测试", "场景-目标浆果"]
scene.frame_set(1)
matrices = {name: bpy.data.objects[name].matrix_world.copy() for name in names}
maximum_static_error = 0.0
bottoms, heights, lengths = [], [], []
for frame in range(1, 121):
    scene.frame_set(frame)
    for name in names:
        current = bpy.data.objects[name].matrix_world
        maximum_static_error = max(
            maximum_static_error,
            max(abs(current[i][j] - matrices[name][i][j]) for i in range(4) for j in range(4)),
        )
    dragon = bpy.data.objects["占位-幼龙"]
    points = [dragon.matrix_world @ Vector(v) for v in dragon.bound_box]
    low, high = min(v.z for v in points), max(v.z for v in points)
    bottoms.append(low)
    heights.append(high - low)
    lengths.append(max(v.x for v in points) - min(v.x for v in points))
result = {
    "blend_sha256": record["sha256"],
    "sampled_frames": 120,
    "girl_camera_berry_max_matrix_error": maximum_static_error,
    "dragon_bottom_z_min_max": [min(bottoms), max(bottoms)],
    "dragon_proxy_height_range": [min(heights), max(heights)],
    "dragon_proxy_body_length_range": [min(lengths), max(lengths)],
    "berry_center_z": bpy.data.objects["场景-目标浆果"].matrix_world.translation.z,
    "scope": "Actual saved cylinder transforms, not rendered creature control or user approval",
}
assert maximum_static_error < 1e-8
assert abs(max(bottoms) - 0.05) < 1e-6
assert min(bottoms) > -1e-6
assert max(heights) - min(heights) < 1e-6
assert max(lengths) - min(lengths) < 1e-6
result["status"] = "passed"
write_json_new(work / "05-检查与验收/一致性五秒测试01-独立几何测量.json", result, work)
print(json.dumps(result, ensure_ascii=False))
