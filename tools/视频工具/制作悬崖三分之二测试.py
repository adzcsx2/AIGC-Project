"""Deterministic reference layout and a measured two-cylinder jump test in Blender."""

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
from project_tool_safety import require_hash, save_checked


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("mode", choices=("reference", "build", "inspect", "render"))
parser.add_argument("config")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
config_path = Path(args.config).resolve(strict=True)
cfg = json.loads(config_path.read_text(encoding="utf-8"))
root = Path(cfg["project"]).resolve(strict=True)
assert (root / "project.yaml").is_file() and config_path.is_relative_to(root)


def owned(key):
    path = (root / cfg[key]).resolve()
    assert path.is_relative_to(root)
    return path


def validate_sources():
    keys = ("source", "plate", "girl_plate", "cutout") if args.mode == "reference" else ("source",)
    for key in keys:
        require_hash(owned(key), cfg[key + "_sha256"])


def image_plane(name, image, dimensions, location):
    bpy.ops.mesh.primitive_plane_add(size=2, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = (dimensions[0] / 2, dimensions[1] / 2, 1)
    mat = bpy.data.materials.new(name + "-image")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(image))
    emit = nodes.new("ShaderNodeEmission")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    output = nodes.new("ShaderNodeOutputMaterial")
    links = mat.node_tree.links
    links.new(tex.outputs["Color"], emit.inputs["Color"])
    links.new(tex.outputs["Alpha"], mix.inputs[0])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emit.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs["Surface"])
    mat.surface_render_method = "DITHERED"
    obj.data.materials.append(mat)
    return obj


def solid(obj, color):
    mat = bpy.data.materials.new(obj.name + "-label")
    mat.diffuse_color = color
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    obj.color = color


def supported(obj):
    bpy.context.view_layer.update()
    obj.location.z -= min((obj.matrix_world @ v.co).z for v in obj.data.vertices)


def lift_at(t):
    u = t - cfg["takeoff_s"]
    duration = cfg["flight_frames"] / 24
    if not 0 < u < duration:
        return 0.0
    return cfg["gravity"] * duration / 2 * u - cfg["gravity"] / 2 * u * u


if args.mode == "reference":
    validate_sources()
    assert not owned("reference").exists()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    width, height = cfg["reference_size"]
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.render.dither_intensity = 0
    cam_data = bpy.data.cameras.new("Reference-layout-camera")
    cam = bpy.data.objects.new("Reference-layout-camera", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (0, 0, 10)
    cam_data.type, cam_data.ortho_scale, cam_data.sensor_fit = "ORTHO", width, "HORIZONTAL"
    cam_data.clip_end = 100
    scene.camera = cam
    image_plane("Girl-and-scene-plate", owned("girl_plate"), (width, height), (0, 0, -0.02))
    iw, ih = cfg["cutout_size"]
    left, top, right, bottom = cfg["cutout_body_bbox"]
    tx, ty, target_height = cfg["target_body"]
    scale = target_height / (bottom - top)
    image_left, image_top = tx - left * scale, ty - top * scale
    center = (image_left + iw * scale / 2 - width / 2, height / 2 - image_top - ih * scale / 2, 0)
    image_plane(
        "Same-dragon-photographic-element", owned("cutout"), (iw * scale, ih * scale), center
    )
    bpy.ops.file.pack_all()
    owned("reference").parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(owned("reference"))
    digest = save_checked(bpy, owned("reference_blend"), root, validate_sources)
    bpy.ops.render.render(write_still=True)
    dump(
        owned("reference_record"),
        {
            "blend_sha256": digest,
            "reference_sha256": sha(owned("reference")),
            "body_target_bbox": [tx, ty, tx + (right - left) * scale, ty + target_height],
            "method": (
                "Imagegen cutout, deterministic Blender orthographic layout, original girl plate."
            ),
            "scope": "Reference bitmap only; not a detailed 3D creature or an animated cutout.",
        },
    )
elif args.mode == "build":
    validate_sources()
    assert not owned("blend").exists()
    bpy.ops.wm.open_mainfile(filepath=str(owned("source")))
    scene = bpy.context.scene
    scene.frame_set(1)
    dragon = bpy.data.objects["占位-幼龙"]
    orientation = dragon.matrix_world.to_quaternion()
    dragon.animation_data_clear()
    dragon.rotation_mode = "QUATERNION"
    dragon.rotation_quaternion = orientation
    dragon.data = dragon.data.copy()
    for vertex in dragon.data.vertices:
        vertex.co *= 2 / 3
    solid(dragon, (0.65, 0.40, 0.18, 1))
    supported(dragon)
    dragon_base = dragon.location.copy()
    cam = scene.camera
    cam.animation_data_clear()
    cam.data.animation_data_clear()
    cam.data.lens, cam.data.shift_x, cam.data.shift_y = 50, 0, 0
    for obj in list(scene.objects):
        if obj not in (dragon, cam):
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.15, depth=1.30)
    girl = bpy.context.object
    girl.name, girl.rotation_mode = "占位-女孩", "QUATERNION"
    solid(girl, (0.13, 0.32, 0.65, 1))
    girl.location = dragon_base + Vector((1.18, 0, 0))
    girl_base = girl.location.copy()
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light, scene.display.shading.color_type = "FLAT", "MATERIAL"
    scene.display.shading.background_type = "WORLD"
    scene.world.color = (0.18, 0.18, 0.18)
    scene.display.shading.show_shadows = False
    scene.render.resolution_x, scene.render.resolution_y = 960, 540
    scene.render.resolution_percentage, scene.render.fps = 100, 24
    scene.render.film_transparent = False
    scene.frame_start, scene.frame_end = 1, 120
    scene.render.image_settings.file_format, scene.render.image_settings.color_mode = "PNG", "RGB"
    scene.view_settings.view_transform = "Standard"
    opening = cfg.get("motion") == "opening_rest_and_notice"
    duration = cfg.get("flight_frames", 0) / 24
    for frame in range(1, 121):
        t = (frame - 1) / 24
        if opening:
            # A supported attention change, not an airborne whole-body lift.
            u = max(0, min(1, (t - 1.4) / 0.55))
            pitch = 0.10 * (u * u * (3 - 2 * u))
            dragon.location = dragon_base.copy()
            dragon.rotation_quaternion = Quaternion((0, 1, 0), pitch) @ orientation
            supported(dragon)
            dragon.keyframe_insert("rotation_quaternion", frame=frame)
        else:
            phase = max(0, min(1, (t - cfg["takeoff_s"]) / duration))
            dragon.location = dragon_base + Vector((-0.04 * phase, 0, lift_at(t)))
        dragon.keyframe_insert("location", frame=frame)
        if opening:
            u = max(0, min(1, (t - 2.0) / 0.55))
            angle = 0.02 * (u * u * (3 - 2 * u)) + 0.002 * math.sin(t * 2)
        elif t < 0.3:
            angle = 0
        elif t < 1.25:
            angle = (t - 0.3) / 0.95 * 0.0308
        elif t < 2.1:
            angle = 0.0308
        elif t < 2.65:
            angle = (2.65 - t) / 0.55 * 0.0308
        else:
            angle = 0.004 * math.sin((t - 2.65) * math.pi)
        girl.location = girl_base.copy()
        girl.rotation_quaternion = Quaternion((0, 1, 0), math.pi / 2 + angle)
        supported(girl)
        girl.keyframe_insert("location", frame=frame)
        girl.keyframe_insert("rotation_quaternion", frame=frame)
    scene.render.filepath = str(owned("frames") / "帧-")
    digest = save_checked(bpy, owned("blend"), root, validate_sources)
    dump(
        owned("build_record"),
        {
            "blend_sha256": digest,
            "config_sha256": sha(config_path),
            "ratio": "dragon diameter0.20m / girl diameter0.30m =2/3",
            "scale_changes_during_animation": False,
        },
    )
else:
    record = json.loads(owned("build_record").read_text(encoding="utf-8"))
    require_hash(owned("blend"), record["blend_sha256"])
    bpy.ops.wm.open_mainfile(filepath=str(owned("blend")))
    scene = bpy.context.scene
    if args.mode == "render":
        owned("frames").mkdir(parents=True, exist_ok=False)
        bpy.ops.render.render(animation=True)
    else:
        dragon, girl = (bpy.data.objects[n] for n in ("占位-幼龙", "占位-女孩"))
        assert dragon.rotation_mode == girl.rotation_mode == "QUATERNION"
        visible_meshes = {o.name for o in scene.objects if o.type == "MESH" and not o.hide_render}
        assert visible_meshes == {dragon.name, girl.name}, "Environment geometry in motion guide"

        def diameter(obj):
            return 2 * max(math.hypot(v.co.x, v.co.y) for v in obj.data.vertices)

        dd, gd = diameter(dragon), diameter(girl)
        assert abs(dd - 0.20) < 1e-6 and abs(gd - 0.30) < 1e-6
        assert abs(dd / gd - 2 / 3) < 1e-6
        samples = []
        camera_matrix = [list(row) for row in scene.camera.matrix_world]
        for frame in range(1, 121):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            pts = [dragon.matrix_world @ v.co for v in dragon.data.vertices]
            uv = [world_to_camera_view(scene, scene.camera, p) for p in pts]
            bottom = min(p.z for p in pts)
            expected_lift = (
                0 if cfg.get("motion") == "opening_rest_and_notice" else lift_at((frame - 1) / 24)
            )
            assert abs(bottom - expected_lift) < 1e-6
            assert all(abs(v - 1) < 1e-6 for o in (girl, dragon) for v in o.scale)
            assert [list(row) for row in scene.camera.matrix_world] == camera_matrix
            samples.append(
                {
                    "frame": frame,
                    "t": (frame - 1) / 24,
                    "bottom_m": bottom,
                    "center": list(dragon.location),
                    "girl_center": list(girl.location),
                    "dragon_rotation": list(dragon.matrix_world.to_quaternion()),
                    "girl_rotation": list(girl.rotation_quaternion),
                    "dragon_bbox": [
                        min(v.x for v in uv),
                        1 - max(v.y for v in uv),
                        max(v.x for v in uv),
                        1 - min(v.y for v in uv),
                    ],
                }
            )
        opening = cfg.get("motion") == "opening_rest_and_notice"
        expected_peak = 0 if opening else 0.1361111111
        assert abs(max(s["bottom_m"] for s in samples) - expected_peak) < 1e-6
        assert samples[0]["girl_rotation"] != samples[-1]["girl_rotation"]
        if opening:
            assert samples[0]["dragon_rotation"] != samples[-1]["dragon_rotation"]
        dump(
            owned("inspection"),
            {
                "blend_sha256": record["blend_sha256"],
                "diameters_m": {"dragon": dd, "girl": gd},
                "diameter_ratio": dd / gd,
                "flight_seconds": cfg.get("flight_frames", 0) / 24,
                "samples": samples,
                "visible_meshes": sorted(visible_meshes),
                "environment_in_guide": False,
                "scope": (
                    "Rigid dimensions/path/camera; "
                    "real generator motion and size remain separate checks."
                ),
            },
        )
        print("Verified exact2/3 diameters, constant scale, evaluated motion and model-only guide")
