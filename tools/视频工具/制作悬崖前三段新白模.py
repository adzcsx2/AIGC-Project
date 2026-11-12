"""Build and inspect the three authorized cliff previews at their real playback speed.

The photographed backdrop is a 2.5D plate. Lens/shift changes are real Blender
camera controls; this tool does not claim reconstructed scenery or articulated rigs.
"""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import save_checked


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def key_value(keys, t):
    for a, b in zip(keys, keys[1:], strict=False):
        if a[0] <= t < b[0]:
            u = (t - a[0]) / (b[0] - a[0])
            return [x + (y - x) * u for x, y in zip(a[1:], b[1:], strict=True)]
    return keys[0][1:] if t < keys[0][0] else keys[-1][1:]


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("mode", choices=("build", "inspect", "render"))
parser.add_argument("config")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
cfg_path = Path(args.config).resolve(strict=True)
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
root = Path(cfg["project"]).resolve(strict=True)
assert (root / "project.yaml").is_file() and cfg_path.is_relative_to(root)


def owned(path):
    result = (root / path).resolve()
    assert result.is_relative_to(root)
    return result


if args.mode == "build":
    source = owned(cfg["source"])
    assert sha(source) == cfg["source_sha256"]
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    scene.frame_set(1)
    dragon = bpy.data.objects["占位-幼龙"]
    base_q = dragon.matrix_world.to_quaternion()
    dragon.animation_data_clear()
    dragon.rotation_mode = "QUATERNION"
    dragon.rotation_quaternion = base_q
    dragon.color = (0.68, 0.68, 0.68, 1)
    base = dragon.location.copy()
    camera = scene.camera
    camera.animation_data_clear()
    camera.data.animation_data_clear()
    camera.data.lens = 50
    camera.data.shift_x = camera.data.shift_y = 0
    for obj in list(scene.objects):
        if obj not in (dragon, camera):
            bpy.data.objects.remove(obj, do_unlink=True)
    # One rigid cylinder for the girl, never a detailed humanoid/limb rig.
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.15, depth=1.30)
    girl = bpy.context.object
    girl.name = "占位-女孩"
    for vertex in girl.data.vertices:
        vertex.co.x *= 0.73
    girl.rotation_mode = "QUATERNION"
    girl.rotation_quaternion = Quaternion((0, 1, 0), math.pi / 2)
    girl.color = (0.25, 0.34, 0.48, 1)
    girl.location = base + Vector((1.18, 0, 0))
    # Same ground plane as the dragon. The cylinder is the body envelope,
    # not a claim that a reclining girl's elbows/face have been modeled.
    bpy.context.view_layer.update()
    girl.location.z -= min((girl.matrix_world @ v.co).z for v in girl.data.vertices)
    girl_base = girl.location.copy()
    if cfg.get("plate"):
        plate = owned(cfg["plate"])
        assert sha(plate) == cfg["plate_sha256"]
        bpy.ops.mesh.primitive_plane_add(size=2)
        card = bpy.context.object
        card.name = "环境-摄影底板-非三维地形"
        card.parent = camera
        card.location = (0, 0, -50)
        card.rotation_euler = (0, 0, 0)
        card.scale = (18, 18 * 9 / 16, 1)
        mat = bpy.data.materials.new("原图环境")
        mat.use_nodes = True
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(str(plate))
        mat.node_tree.nodes.active = tex
        card.data.materials.append(mat)
    else:
        bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 12, -0.002))
        bpy.context.object.name = "场景-地面"
        bpy.context.object.color = (0.30, 0.37, 0.25, 1)
        for name, loc, dims, color in [
            ("场景-村屋近", (-3, 15, 1.5), (2.4, 2.6, 3), (0.53, 0.47, 0.36, 1)),
            ("场景-村屋远", (-0.8, 18, 1.3), (2, 2.3, 2.6), (0.53, 0.47, 0.36, 1)),
            ("场景-岩沿", (0, 3.8, -0.3), (12, 0.3, 0.6), (0.4, 0.4, 0.4, 1)),
        ]:
            bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
            obj = bpy.context.object
            obj.name, obj.dimensions, obj.color = name, dims, color
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.4, depth=6, location=(4, 15, 3))
        bpy.context.object.name = "场景-巨树"
        bpy.context.object.color = (0.32, 0.27, 0.20, 1)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.025)
        fruit = bpy.context.object
        fruit.name = "道具-固定浆果"
        fruit.color = (0.65, 0.10, 0.08, 1)
        fruit.location = base + Vector((-0.35, 0, 0.75))
        fruit.location.z = 0.9
        # Solve the ground location with height fixed; match the actual fruit ray.
        for _ in range(10):
            uv = world_to_camera_view(scene, camera, fruit.location)
            error = Vector((0.165 - uv.x, 0.858 - uv.y))
            if error.length < 1e-7:
                break
            cols = []
            for axis in (0, 1):
                pos = fruit.location.copy()
                pos[axis] += 0.001
                shifted = world_to_camera_view(scene, camera, pos)
                cols.append(Vector(((shifted.x - uv.x) / 0.001, (shifted.y - uv.y) / 0.001)))
            determinant = cols[0].x * cols[1].y - cols[1].x * cols[0].y
            dx = (error.x * cols[1].y - error.y * cols[1].x) / determinant
            dy = (cols[0].x * error.y - cols[0].y * error.x) / determinant
            fruit.location.x += dx
            fruit.location.y += dy
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=12,
            radius=0.012,
            depth=0.9,
            location=(fruit.location.x + 0.08, fruit.location.y + 0.05, 0.45),
        )
        bpy.context.object.name = "道具-浆果灌木"
        bpy.context.object.color = (0.32, 0.26, 0.16, 1)
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "FLAT"
    scene.display.shading.color_type = "TEXTURE" if cfg.get("plate") else "OBJECT"
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = True
    scene.display.shading.background_type = "WORLD"
    scene.world.color = (0.19, 0.19, 0.19)
    scene.render.film_transparent = False
    scene.render.resolution_x, scene.render.resolution_y = 960, 540
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.frame_start, scene.frame_end = 1, cfg["duration"] * 24
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "Standard"
    girl.hide_render = not cfg.get("girl_proxy", False)
    # Bake one sample per actual frame. Linear channels avoid an implicit
    # Bezier/apex hold or deceleration invented by the interpolation system.
    for frame in range(1, scene.frame_end + 1):
        t = (frame - 1) / 24
        dx, dy, roll = key_value(cfg["dragon_keys"], t)
        dragon.location = base + Vector((dx, dy, 0))
        dragon.rotation_quaternion = Quaternion((0, 1, 0), roll) @ base_q
        bpy.context.view_layer.update()
        dragon.location.z -= min((dragon.matrix_world @ v.co).z for v in dragon.data.vertices)
        # All this unit's motion is grounded slipping/rolling. No artificial lift.
        dragon.keyframe_insert("location", frame=frame)
        dragon.keyframe_insert("rotation_quaternion", frame=frame)
        girl.location = girl_base.copy()
        g_roll = key_value(cfg["girl_roll_keys"], t)[0]
        girl.rotation_quaternion = Quaternion((1, 0, 0), g_roll) @ Quaternion(
            (0, 1, 0), math.pi / 2
        )
        bpy.context.view_layer.update()
        girl.location.z -= min((girl.matrix_world @ v.co).z for v in girl.data.vertices)
        girl.keyframe_insert("location", frame=frame)
        girl.keyframe_insert("rotation_quaternion", frame=frame)
        lens, fx, fy = key_value(cfg["camera_keys"], t)
        camera.data.lens = lens
        camera.data.shift_x = camera.data.shift_y = 0
        # Desired plate center is specified in original normalized image coords.
        # Find lens shifts from an actual projected world point on the plate plane.
        p = camera.matrix_world @ Vector(((fx - 0.5) * 36, (0.5 - fy) * 20.25, -50))
        uv = world_to_camera_view(scene, camera, p)
        camera.data.shift_x = uv.x - 0.5
        camera.data.shift_y = (uv.y - 0.5) * 9 / 16
        for field in ("lens", "shift_x", "shift_y"):
            camera.data.keyframe_insert(field, frame=frame)
    for owner in (dragon, girl, camera.data):
        for fc in (
            owner.animation_data.action.fcurves
            if hasattr(owner.animation_data.action, "fcurves")
            else []
        ):
            for point in fc.keyframe_points:
                point.interpolation = "LINEAR"
    scene["scope"] = (
        "Rigid simple proxies; plate-based lens crops; "
        "no reconstructed environment or natural gait."
    )
    scene.render.filepath = str(owned(cfg["frames"]) / "帧-")
    destination = owned(cfg["blend"])
    assert not destination.exists()
    digest = save_checked(bpy, destination, root, lambda: None)
    dump(
        owned(cfg["build_record"]),
        {"blend_sha256": digest, "config_sha256": sha(cfg_path), "source_sha256": sha(source)},
    )
else:
    record = json.loads(owned(cfg["build_record"]).read_text(encoding="utf-8"))
    assert sha(owned(cfg["blend"])) == record["blend_sha256"]
    bpy.ops.wm.open_mainfile(filepath=str(owned(cfg["blend"])))
    scene = bpy.context.scene
    if args.mode == "render":
        frames = owned(cfg["frames"])
        frames.mkdir(parents=True, exist_ok=False)
        bpy.ops.render.render(animation=True)
    else:
        samples = []
        for frame in range(1, scene.frame_end + 1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            sample = {
                "frame": frame,
                "t": (frame - 1) / 24,
                "subjects": {},
                "camera": {
                    "lens": scene.camera.data.lens,
                    "shift": [scene.camera.data.shift_x, scene.camera.data.shift_y],
                },
            }
            for name in ("占位-幼龙", "占位-女孩"):
                obj = bpy.data.objects[name]
                points = [obj.matrix_world @ v.co for v in obj.data.vertices]
                uv = [world_to_camera_view(scene, scene.camera, p) for p in points]
                assert abs(min(p.z for p in points)) < 1e-5
                assert all(abs(v - 1) < 1e-6 for v in obj.scale)
                sample["subjects"][name] = {
                    "center": list(obj.location),
                    "bottom": min(p.z for p in points),
                    "bbox": [
                        min(p.x for p in uv),
                        1 - max(p.y for p in uv),
                        max(p.x for p in uv),
                        1 - min(p.y for p in uv),
                    ],
                }
            samples.append(sample)
        speeds = []
        for a, b in zip(samples, samples[1:], strict=False):
            pa, pb = (Vector(s["subjects"]["占位-幼龙"]["center"]) for s in (a, b))
            speeds.append(
                {
                    "t": a["t"],
                    "horizontal_m_s": math.hypot(pb.x - pa.x, pb.y - pa.y) * 24,
                    "vertical_m_s": (pb.z - pa.z) * 24,
                }
            )
        dump(
            owned(cfg["inspection"]),
            {
                "blend_sha256": record["blend_sha256"],
                "samples": samples,
                "speeds": speeds,
                "scope": (
                    "Disk-loaded rigid geometry and actual camera only; "
                    "dynamic 1x review required separately."
                ),
            },
        )
        print(
            "Checked",
            len(samples),
            "frames; maximum horizontal speed",
            max(v["horizontal_m_s"] for v in speeds),
        )
