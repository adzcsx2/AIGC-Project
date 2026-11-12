"""Single-camera, simple-cylinder geometry for the user-requested control test."""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import save_checked
from whitebox_saved import render_still_new, write_json_new

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "projects/悬崖上的小气球"


def primitive(name, kind, dimensions, location, color):
    if kind == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=1, depth=2)
    elif kind == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8)
    else:
        bpy.ops.mesh.primitive_cube_add(size=2)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.location = location
    obj.color = color
    material = bpy.data.materials.new(name + "-身份标签")
    material.diffuse_color = color
    obj.data.materials.append(material)
    return obj


def altitude(t):
    if t <= 1.4 or t >= 3.2:
        return 0.0
    if t < 2.2:
        return 0.05 * (t - 1.4) / 0.8
    if t <= 2.6:
        return 0.05
    return 0.05 * (3.2 - t) / 0.6


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 120
    scene.render.fps, scene.render.fps_base = 24, 1
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    scene.render.resolution_percentage = 100
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.world = bpy.data.worlds.new("世界")
    scene.world.color = (0.35, 0.35, 0.35)
    primitive("场景-地面", "cube", (40, 40, 0.2), (0, 12, -0.1), (0.22, 0.3, 0.18, 1))
    primitive("场景-软泥区", "cube", (0.8, 0.65, 0.002), (-0.6, 8, 0.001), (0.2, 0.16, 0.12, 1))
    girl = primitive(
        "占位-女孩", "cylinder", (0.28, 0.28, 1.3), (0.7, 8, 0.14), (0.06, 0.25, 0.75, 1)
    )
    girl.rotation_euler[1] = math.pi / 2
    dragon = primitive(
        "占位-幼龙", "cylinder", (0.3, 0.3, 0.35), (-0.6, 8, 0.15), (0.9, 0.3, 0.04, 1)
    )
    dragon.rotation_euler[1] = math.pi / 2
    tail = primitive(
        "占位-幼龙-尾向", "cylinder", (0.07, 0.07, 0.2), (-0.325, 8, 0.15), (0.9, 0.3, 0.04, 1)
    )
    tail.rotation_euler[1] = math.pi / 2
    primitive(
        "场景-浆果树干", "cylinder", (0.045, 0.045, 1.0), (-1.1, 8, 0.5), (0.3, 0.24, 0.16, 1)
    )
    branch = primitive(
        "场景-侧枝", "cylinder", (0.012, 0.012, 0.17), (-1.025, 8, 0.97), (0.3, 0.24, 0.16, 1)
    )
    branch.rotation_euler[1] = math.pi / 2
    primitive(
        "场景-果柄", "cylinder", (0.007, 0.007, 0.05), (-0.95, 8, 0.9475), (0.3, 0.24, 0.16, 1)
    )
    berry = primitive(
        "场景-目标浆果", "sphere", (0.045, 0.045, 0.045), (-0.95, 8, 0.9), (0.8, 0.01, 0.01, 1)
    )
    primitive("场景-枝叶", "sphere", (0.24, 0.16, 0.16), (-1.12, 8.04, 1.02), (0.2, 0.42, 0.1, 1))
    primitive("场景-巨树干", "cylinder", (1.5, 1.5, 7), (2.6, 10, 3.5), (0.4, 0.35, 0.27, 1))
    for index, (x, y) in enumerate([(-7, 17), (-4, 21)], 1):
        primitive(f"场景-村屋{index}", "cube", (3, 3, 3), (x, y, 1.5), (0.6, 0.6, 0.56, 1))
    camera_data = bpy.data.cameras.new("固定比尺摄影机")
    camera = bpy.data.objects.new("摄影机-一致性测试", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0.25, 3.5, 0.8)
    target = Vector((0.25, 8, 0.45))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.lens, camera_data.sensor_width = 50, 36
    camera_data.clip_start, camera_data.clip_end = 0.01, 100
    scene.camera = camera
    marker = scene.timeline_markers.new("单机位五秒", frame=1)
    marker.camera = camera
    for frame in range(1, 121):
        t = (frame - 1) / 24
        for obj in (dragon, tail):
            obj.location.z = 0.15 + altitude(t)
            obj.keyframe_insert("location", frame=frame)
    scene.frame_set(1)
    destination = WORK / "03-制作/三维工程/一致性五秒测试-圆柱白模-版本02.blend"
    digest = save_checked(bpy, destination, WORK, lambda: None)
    proof = WORK / "05-检查与验收/一致性五秒测试01-白模构建02.json"
    write_json_new(
        proof,
        {
            "blend": str(destination),
            "sha256": digest,
            "frames": 120,
            "fps": 24,
            "girl_length": 1.3,
            "girl_pose": "horizontal cylinder, no transform animation",
            "dragon_body_length": 0.35,
            "dragon_full_length_including_tail": 0.55,
            "dragon_grounded_proxy_height": 0.3,
            "target_berry_z": berry.location.z,
            "max_body_lower_envelope_clearance": 0.05,
            "camera_location": list(camera.location),
            "camera_target": list(target),
            "lens_mm": 50,
            "scope": (
                "simple geometry, fixed camera and trajectory; "
                "not anatomy or appearance acceptance"
            ),
        },
        WORK,
    )
    scene.render.resolution_percentage = 50
    still = WORK / "05-检查与验收/一致性五秒测试01-白模空间首帧02.png"
    render_still_new(bpy, still, WORK)
    print(
        json.dumps(
            {"blend": str(destination), "sha256": digest, "still": str(still)}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
