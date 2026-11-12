"""Build or independently inspect one size-calibrated cylinder for the cliff test."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import save_checked


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def projected(scene, actor):
    vertices = [actor.matrix_world @ v.co for v in actor.data.vertices]
    uv = [world_to_camera_view(scene, scene.camera, p) for p in vertices]
    return [min(p.x for p in uv), 1 - max(p.y for p in uv),
            max(p.x for p in uv), 1 - min(p.y for p in uv)]


def measure(scene, actor):
    box = projected(scene, actor)
    return Vector(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2, box[3] - box[1]))


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("mode", choices=("build", "inspect", "render"))
parser.add_argument("config")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
config_path = Path(args.config).resolve(strict=True)
cfg = json.loads(config_path.read_text(encoding="utf-8"))
work = Path(cfg["project"]).resolve(strict=True)
assert (work / "project.yaml").is_file() and config_path.is_relative_to(work)


def owned(key):
    path = (work / cfg[key]).resolve()
    assert path.is_relative_to(work)
    parent = path.parent
    while parent != work:
        assert not (parent / "project.yaml").is_file(), "Nested project output refused"
        parent = parent.parent
    return path


if args.mode == "build":
    source = owned("source")
    assert digest(source) == cfg["source_sha256"]
    target = owned("blend")
    assert not target.exists()
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    scene.frame_set(1)
    actor = bpy.data.objects[cfg["actor"]]
    actor.animation_data_clear()
    for obj in scene.objects:
        if obj.type == "MESH":
            obj.hide_render = obj != actor
    scene.render.resolution_x, scene.render.resolution_y = cfg["resolution"]
    scene.render.resolution_percentage = 100
    scene.render.fps = cfg["fps"]
    scene.frame_start, scene.frame_end = 1, cfg["frames"]
    bpy.context.view_layer.update()
    refw, refh = cfg["reference_size"]
    left, top, right, bottom = cfg["target_body_bbox"]
    goal = Vector(((left + right) / 2 / refw, (top + bottom) / 2 / refh, (bottom - top) / refh))
    def fit_translation():
        # Fit only rigid placement; physical cylinder dimensions stay fixed.
        for _ in range(16):
            before = measure(scene, actor)
            error = goal - before
            if error.length < 1e-7:
                break
            columns = []
            for axis in range(3):
                actor.location[axis] += 0.0005
                bpy.context.view_layer.update()
                columns.append((measure(scene, actor) - before) / 0.0005)
                actor.location[axis] -= 0.0005
                bpy.context.view_layer.update()
            jacobian = Matrix([[columns[c][r] for c in range(3)] for r in range(3)])
            delta = jacobian.inverted() @ error
            assert delta.length < 2.0
            actor.location += delta
            bpy.context.view_layer.update()

    if cfg.get("fit_projected_width"):
        width_goal = (right - left) / refw
        best = None
        # An off-axis cylinder has perspective width beyond its axis length.
        # Fit a static yaw, not an animated scale change.
        angles = [math.radians(degrees) for degrees in range(-90, 91, 3)]
        for refinement in range(3):
            for angle in angles:
                actor.rotation_euler.z = angle
                bpy.context.view_layer.update()
                fit_translation()
                box = projected(scene, actor)
                error = abs((box[2] - box[0]) - width_goal)
                if best is None or error < best[0]:
                    best = (error, angle, actor.location.copy())
            step = math.radians(3) / (5 ** (refinement + 1))
            angles = [best[1] + offset * step for offset in range(-5, 6)]
        actor.rotation_euler.z, actor.location = best[1], best[2]
        bpy.context.view_layer.update()
        assert best[0] < 0.001
    else:
        fit_translation()
    assert (measure(scene, actor) - goal).length < 1e-5
    points = [actor.matrix_world @ v.co for v in actor.data.vertices]
    ground = min(p.z for p in points)
    actor.location.z -= ground
    scene.camera.location.z -= ground
    bpy.context.view_layer.update()
    base = actor.location.copy()
    for key in cfg["lift_keys"]:
        actor.location = base + Vector((0, 0, key["height_m"]))
        actor.keyframe_insert(data_path="location", frame=key["frame"])
    if actor.animation_data and actor.animation_data.action:
        action = actor.animation_data.action
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:
                            key.interpolation = "BEZIER"
                            key.handle_left_type = key.handle_right_type = "AUTO_CLAMPED"
    scene.frame_set(1)
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.display.shading.show_shadows = False
    frame_dir = owned("frames_dir")
    assert not frame_dir.exists()
    frame_dir.mkdir(parents=True)
    scene.render.filepath = str(frame_dir / "帧-")
    blend_hash = save_checked(bpy, target, work, lambda: None)
    write_new(owned("build_record"), {
        "source": cfg["source"], "source_sha256": cfg["source_sha256"],
        "blend": cfg["blend"], "sha256": blend_hash,
        "reference": cfg["reference"], "reference_sha256": cfg["reference_sha256"],
        "body_projection_normalized": projected(scene, actor),
        "target_body_bbox": cfg["target_body_bbox"],
        "scope": "One rigid cylinder, fixed perspective camera; no detailed character or rig. Full reference retained separately.",
    })
    print("Saved calibrated guide source", blend_hash)
else:
    record = json.loads(owned("build_record").read_text(encoding="utf-8"))
    target = owned("blend")
    assert digest(target) == record["sha256"]
    bpy.ops.wm.open_mainfile(filepath=str(target))
    scene = bpy.context.scene
    actor = bpy.data.objects[cfg["actor"]]
    if args.mode == "render":
        assert len(list(owned("frames_dir").glob("*.png"))) == 0
        bpy.ops.render.render(animation=True)
        print("Rendered", len(list(owned("frames_dir").glob("*.png"))), "transparent frames")
    else:
        samples = []
        for frame in range(1, cfg["frames"] + 1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            points = [actor.matrix_world @ v.co for v in actor.data.vertices]
            dimensions = [max(p[i] for p in points) - min(p[i] for p in points) for i in range(3)]
            visible = [o.name for o in scene.objects if o.type == "MESH" and not o.hide_render]
            assert visible == [actor.name]
            samples.append({"frame": frame, "bottom_m": min(p.z for p in points),
                            "dimensions_m": dimensions, "projection": projected(scene, actor),
                            "camera_matrix": [list(row) for row in scene.camera.matrix_world],
                            "lens_mm": scene.camera.data.lens})
        assert all(s["camera_matrix"] == samples[0]["camera_matrix"] for s in samples)
        assert all(abs(s["lens_mm"] - 50) < 1e-6 for s in samples)
        assert min(s["bottom_m"] for s in samples) > -1e-6
        assert abs(max(s["bottom_m"] for s in samples) - 0.05) < 1e-6
        for axis in range(3):
            assert max(s["dimensions_m"][axis] for s in samples) - min(s["dimensions_m"][axis] for s in samples) < 1e-6
        local_length = max(v.co.z for v in actor.data.vertices) - min(v.co.z for v in actor.data.vertices)
        assert abs(local_length - 0.35) < 1e-6
        assert abs(samples[0]["dimensions_m"][2] - 0.30) < 1e-6
        write_new(owned("inspection"), {"status": "passed", "blend_sha256": record["sha256"],
                  "sampled_frames": len(samples), "samples": samples,
                  "scope": "Rigid proxy geometry and actual camera only; no claim of generated size control."})
        print("Independent disk-loaded geometry check passed; maximum lift 0.05m")
