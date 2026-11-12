"""Deterministic reference-canvas layout and a separate model-only motion guide."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import require_hash, save_checked

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("mode", choices=["canvas", "build", "inspect", "render"])
parser.add_argument("config")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
cfg_path = Path(args.config).resolve(strict=True)
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
root = Path(cfg["project"]).resolve(strict=True)
assert cfg_path.is_relative_to(root)


def path(key):
    p = (root / cfg[key]).resolve()
    assert p.is_relative_to(root)
    return p


def validate():
    for item in cfg["source_pins"]:
        require_hash(root / item["path"], item["sha256"])


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def dump(key, data):
    p = path(key)
    p.parent.mkdir(exist_ok=True, parents=True)
    with p.open("x", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def scene_empty():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.view_settings.view_transform = "Standard"
    s.view_settings.look = "None"
    s.render.dither_intensity = 0
    s.render.image_settings.file_format = "PNG"
    return s


def material(obj, color):
    mat = bpy.data.materials.new(obj.name + "-label")
    mat.diffuse_color = (*color, 1)
    obj.data.materials.append(mat)


def join(parts, name):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    return obj


def ramp(t, start, duration):
    u = max(0, min(1, (t - start) / duration))
    return u * u * (3 - 2 * u)


validate()
if args.mode == "canvas":
    scene = scene_empty()
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 8
    scene.cycles.use_denoising = False
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.resolution_x, scene.render.resolution_y = 1024, 1536
    scene.render.resolution_percentage = 100
    cam = bpy.data.objects.new("Canvas-camera", bpy.data.cameras.new("Canvas-camera"))
    scene.collection.objects.link(cam)
    cam.location = (512, 768, 10)
    cam.data.type, cam.data.sensor_fit, cam.data.ortho_scale = "ORTHO", "HORIZONTAL", 1024
    scene.camera = cam
    for key in ("girl", "dragon"):
        item = cfg[key]
        w, h = item["size"]
        left, top, right, bottom = item["bbox"]
        factor = item["factor"]
        x0 = item["target_center_x"] - (left + right) * factor / 2
        y0 = item["target_bottom"] - bottom * factor
        bpy.ops.mesh.primitive_plane_add(size=2)
        obj = bpy.context.object
        obj.name = key + "-reference-plane-NOT-GUIDE"
        obj.location = (x0 + w * factor / 2, 1536 - y0 - h * factor / 2, 0)
        obj.scale = (w * factor / 2, h * factor / 2, 1)
        mat = bpy.data.materials.new(key + "-alpha")
        mat.use_nodes = True
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        nodes.clear()
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(str(root / item["path"]))
        tex.interpolation = "Linear"
        emit = nodes.new("ShaderNodeEmission")
        transparent = nodes.new("ShaderNodeBsdfTransparent")
        threshold = nodes.new("ShaderNodeMath")
        threshold.operation = "GREATER_THAN"
        threshold.inputs[1].default_value = 249.5 / 255
        mix, out = nodes.new("ShaderNodeMixShader"), nodes.new("ShaderNodeOutputMaterial")
        links.new(tex.outputs["Color"], emit.inputs["Color"])
        links.new(tex.outputs["Alpha"], threshold.inputs[0])
        links.new(threshold.outputs[0], mix.inputs[0])
        links.new(transparent.outputs[0], mix.inputs[1])
        links.new(emit.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], out.inputs["Surface"])
        obj.data.materials.append(mat)
        for other in scene.objects:
            if other.type == "MESH":
                other.hide_render = other != obj
        scene.render.filepath = str(path(key + "_canvas"))
        path(key + "_canvas").parent.mkdir(exist_ok=True, parents=True)
        assert not path(key + "_canvas").exists()
        bpy.ops.render.render(write_still=True)
    bpy.ops.file.pack_all()
    layout_sha = save_checked(bpy, path("canvas_blend"), root, validate)
    dump(
        "canvas_record",
        {
            "layout_blend_sha256": layout_sha,
            "scope": "Reference layout only; image planes never enter ref_video",
            "inputs": cfg["girl"],
            "dragon": cfg["dragon"],
            "canvas": [1024, 1536],
            "alpha_policy": "core alpha>=250; removes source translucent halo",
        },
    )
elif args.mode == "build":
    require_hash(path("source_blend"), cfg["source_blend_sha256"])
    bpy.ops.wm.open_mainfile(filepath=str(path("source_blend")))
    scene = bpy.context.scene
    assert len(bpy.data.images) == 0
    girl_old = bpy.data.objects["MIA-reclining-length-envelope"]
    bpy.data.objects.remove(girl_old, do_unlink=True)
    figure = bpy.data.objects["GULU-geometric-figure"]
    figure.data.shape_keys.animation_data_clear()
    anchor = Vector(cfg["old_anchor"])
    target = Vector(cfg["dragon_anchor"])
    factor = cfg["dragon_height_m"] / 0.4
    for key in figure.data.shape_keys.key_blocks:
        for vert in key.data:
            vert.co = target + (vert.co - anchor) * factor
    # Basis and mesh coordinates are kept consistent in the saved editable file.
    for vert, base in zip(
        figure.data.vertices, figure.data.shape_keys.key_blocks[0].data, strict=True
    ):
        vert.co = base.co
    resting = figure.data.shape_keys.key_blocks["Resting-supported"]
    for frame in range(1, 121):
        resting.value = 1 - ramp((frame - 1) / 24, 1.2, 0.6)
        resting.keyframe_insert("value", frame=frame)
    # Human: one horizontal body cylinder plus a simple head direction marker.
    gx, gy = cfg["girl_center"]
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32, radius=0.15, depth=1.15, location=(gx - 0.075, gy, 0.15)
    )
    body = bpy.context.object
    body.name = "MIA-body-cylinder"
    body.rotation_euler.y = math.pi / 2
    material(body, (0.12, 0.30, 0.64))
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=24, ring_count=12, radius=0.09, location=(gx + 0.56, gy, 0.24)
    )
    head = bpy.context.object
    head.name = "MIA-head-direction-envelope"
    material(head, (0.12, 0.30, 0.64))
    for obj in (body, head):
        group = obj.vertex_groups.new(name=obj.name)
        group.add(list(range(len(obj.data.vertices))), 1, "REPLACE")
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    girl = join([body, head], "MIA-geometric-figure")
    girl.shape_key_add(name="Reclining-supported")
    lift = girl.shape_key_add(name="Head-response")
    head_group = girl.vertex_groups["MIA-head-direction-envelope"].index
    for vert in girl.data.vertices:
        if any(g.group == head_group for g in vert.groups):
            lift.data[vert.index].co.z += 0.015
    for frame in range(1, 121):
        lift.value = ramp((frame - 1) / 24, 1.35, 0.45)
        lift.keyframe_insert("value", frame=frame)
    scene.frame_set(1)
    scene.render.filepath = str(path("frames") / "帧-")
    scene.render.resolution_x, scene.render.resolution_y = 960, 540
    scene.render.fps = 24
    scene.frame_start, scene.frame_end = 1, 120
    sha = save_checked(bpy, path("blend"), root, validate)
    dump(
        "build_record",
        {
            "blend_sha256": sha,
            "config_sha256": digest(cfg_path),
            "dragon_height_m": cfg["dragon_height_m"],
            "standing_to_rest_ratio": 0.33 / 0.4,
            "order": ["MIA LEFT", "GULU RIGHT"],
            "no_images": len(bpy.data.images) == 0,
        },
    )
else:
    build = json.loads(path("build_record").read_text(encoding="utf-8"))
    require_hash(path("blend"), build["blend_sha256"])
    bpy.ops.wm.open_mainfile(filepath=str(path("blend")))
    scene = bpy.context.scene
    if args.mode == "render":
        path("frames").mkdir(exist_ok=False, parents=True)
        bpy.ops.render.render(animation=True)
    else:
        assert len(bpy.data.images) == 0
        meshes = [o for o in scene.objects if o.type == "MESH" and not o.hide_render]
        assert len(meshes) == 2
        base_parts, rows = {}, []
        cam_matrix = [list(row) for row in scene.camera.matrix_world]
        for frame in range(1, 121):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            assert cam_matrix == [list(row) for row in scene.camera.matrix_world]
            sample = {"frame": frame, "pts": (frame - 1) / 24}
            for obj in meshes:
                assert all(abs(s - 1) < 1e-6 for s in obj.scale)
                evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
                mesh = evaluated.to_mesh()
                pts = [obj.matrix_world @ v.co for v in mesh.vertices]
                parts = {}
                for group in obj.vertex_groups:
                    indices = [
                        v.index
                        for v in obj.data.vertices
                        if any(g.group == group.index for g in v.groups)
                    ]
                    subset = [pts[i] for i in indices]
                    size = [max(v[i] for v in subset) - min(v[i] for v in subset) for i in range(3)]
                    if group.name not in base_parts:
                        base_parts[group.name] = size
                    assert (
                        max(abs(a - b) for a, b in zip(size, base_parts[group.name], strict=True))
                        < 1e-5
                    )
                    parts[group.name] = {
                        "extent_m": size,
                        "center_m": [sum(v[i] for v in subset) / len(subset) for i in range(3)],
                    }
                uv = [world_to_camera_view(scene, scene.camera, v) for v in pts]
                bbox = [
                    min(v.x for v in uv),
                    1 - max(v.y for v in uv),
                    max(v.x for v in uv),
                    1 - min(v.y for v in uv),
                ]
                assert 0 < bbox[0] < bbox[2] < 1 and 0 < bbox[1] < bbox[3] < 1
                assert abs(min(v.z for v in pts)) < 1e-5
                sample[obj.name] = {
                    "parts": parts,
                    "bbox": bbox,
                    "z_min": min(v.z for v in pts),
                    "z_max": max(v.z for v in pts),
                }
                evaluated.to_mesh_clear()
            assert (
                sample["MIA-geometric-figure"]["bbox"][2]
                < sample["GULU-geometric-figure"]["bbox"][0]
            )
            rows.append(sample)
        assert abs(rows[44]["GULU-geometric-figure"]["z_max"] - cfg["dragon_height_m"]) < 1e-5
        assert (
            abs(rows[0]["GULU-geometric-figure"]["z_max"] - cfg["dragon_height_m"] * 0.825) < 1e-5
        )
        dump(
            "inspection",
            {
                "blend_sha256": build["blend_sha256"],
                "constant_part_dimensions": base_parts,
                "camera_fixed": True,
                "image_datablocks": 0,
                "order_verified_all_120_frames": ["MIA LEFT", "GULU RIGHT"],
                "same_depth": True,
                "normal_speed_rise_s": 0.6,
                "dragon_body_travel_m": cfg["dragon_height_m"] * 0.175,
                "max_body_speed_m_s": cfg["dragon_height_m"] * 0.175 * 2.5,
                "samples": rows,
            },
        )
        print(
            "PASS:120 evaluated frames; constant parts; ground support; "
            "MIA LEFT/GULU RIGHT; fixed camera; no image datablocks"
        )
