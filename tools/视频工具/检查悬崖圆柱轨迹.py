"""Measure saved cliff-blocking transforms in an independent Blender process."""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from whitebox_saved import load_saved, project_path, write_json_new


def reference_rotation(forward):
    up = Vector((0, 0, 1))
    if abs(forward.dot(up)) > 0.98:
        up = Vector((0, 1, 0))
    right = up.cross(forward).normalized()
    return Matrix((right, forward.cross(right).normalized(), forward)).transposed()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--build-record", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    project = Path(args.project).resolve()
    record_path = project_path(project, args.build_record, exists=True)
    record = json.loads(record_path.read_text("utf-8"))
    blend = project_path(project, record["blend"], exists=True)
    scene = load_saved(bpy, str(blend), record["blend_sha256"])
    girl, dragon = bpy.data.objects["占位-女孩"], bpy.data.objects["占位-幼龙"]
    tail = bpy.data.objects["占位-幼龙-方向尾杆"]
    lift, landing, circle, angles = [], [], [], []
    scale_error = 0.0
    for index in range(3600):
        scene.frame_set(index + 1)
        bpy.context.view_layer.update()
        for obj in (girl, dragon):
            scale_error = max(scale_error, *(abs(v - 1) for v in obj.scale))
        if 38 * 24 <= index <= 46 * 24:
            lift.append(
                min(
                    (obj.matrix_world @ Vector(v)).z
                    for obj in (dragon, tail)
                    for v in obj.bound_box
                )
            )
        if 138 * 24 <= index:
            landing.append(min((girl.matrix_world @ Vector(v)).z for v in girl.bound_box))
        if 113.5 * 24 <= index < 121 * 24:
            circle.append(math.hypot(dragon.location.x, dragon.location.y + 6))
        if 121.5 * 24 <= index <= 124.5 * 24:
            actual = dragon.matrix_world.to_3x3().normalized()
            forward = (actual @ Vector((0, 0, 1))).normalized()
            relative = reference_rotation(forward).transposed() @ actual
            angles.append(math.atan2(relative[1][0], relative[0][0]))
    rotation = sum(
        (b - a + math.pi) % math.tau - math.pi for a, b in zip(angles, angles[1:], strict=False)
    )
    errors = []
    if scale_error > 1e-6:
        errors.append("主体尺寸有动画缩放")
    if not 0.049 <= max(lift) <= 0.051 or min(lift) < -1e-5:
        errors.append("第二次起飞的最低包络高度或地面接触不符")
    if min(landing) < -1e-5 or not 0.13 <= max(landing) <= 0.15:
        errors.append("女孩跳起/落足包络不符")
    if max(abs(radius - 3) for radius in circle) > 1e-4:
        errors.append("盘旋半径偏离")
    if abs(rotation - math.tau) > 0.02:
        errors.append("完整翻滚旋转量不符")
    result = {
        "blend": record["blend"],
        "blend_sha256": record["blend_sha256"],
        "scope": "Saved cylinder transforms only; no articulated anatomy or dynamic approval.",
        "sampled_frames": 3600,
        "scale_max_error": scale_error,
        "short_takeoff_minimum_world_z": [min(lift), max(lift)],
        "girl_hop_minimum_world_z": [min(landing), max(landing)],
        "circle_radius_range": [min(circle), max(circle)],
        "continuous_forward_roll_radians": rotation,
        "camera_count": len([o for o in scene.objects if o.type == "CAMERA"]),
        "errors": errors,
        "status": "passed" if not errors else "failed",
    }
    write_json_new(project_path(project, args.output), result, project)
    print(json.dumps(result, ensure_ascii=False))
    if errors:
        raise ValueError("; ".join(errors))


if __name__ == "__main__":
    main()
