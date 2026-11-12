"""Make a measured reference chart and a separate model-only Blender guide."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Quaternion

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import require_hash, save_checked


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("mode", choices=["chart", "chart-mask", "build", "inspect", "render"])
parser.add_argument("config")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
config_path = Path(args.config).resolve(strict=True)
cfg = json.loads(config_path.read_text(encoding="utf-8"))
root = Path(cfg["project"]).resolve(strict=True)
assert config_path.is_relative_to(root) and (root / "project.yaml").is_file()


def owned(key):
    result = (root / cfg[key]).resolve()
    assert result.is_relative_to(root)
    return result


def validate_sources():
    for item in cfg["source_pins"]:
        require_hash(root / item["path"], item["sha256"])


def empty_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.dither_intensity = 0
    return scene


def emission(name, color):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    emit = nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (*color, 1)
    output = nodes.new("ShaderNodeOutputMaterial")
    material.node_tree.links.new(emit.outputs[0], output.inputs["Surface"])
    return material


def rect(name, x, y, width, height, z, material):
    bpy.ops.mesh.primitive_plane_add(size=2, location=(x, y, z))
    obj = bpy.context.object
    obj.name = name
    obj.scale = (width / 2, height / 2, 1)
    obj.data.materials.append(material)
    return obj


def label(text, x, y, size, material, align="CENTER"):
    curve = bpy.data.curves.new(text, "FONT")
    curve.body = text
    curve.size = size
    curve.align_x, curve.align_y = align, "CENTER"
    curve.font = bpy.data.fonts.load(cfg["font"])
    obj = bpy.data.objects.new(text, curve)
    bpy.context.collection.objects.link(obj)
    obj.location = (x, y, 0.07)
    obj.data.materials.append(material)


def cutout(item, center_x, target_height, baseline):
    width, height = item["size"]
    left, top, right, bottom = item["bbox_250"]
    factor = target_height / (bottom - top)
    image_left = center_x - (right - left) * factor / 2 - left * factor
    image_top = baseline - target_height - top * factor
    obj = rect(
        item["name"],
        image_left + width * factor / 2,
        cfg["chart_height"] - image_top - height * factor / 2,
        width * factor,
        height * factor,
        0.04,
        emission(item["name"] + "-placeholder", (1, 1, 1)),
    )
    material = obj.data.materials[0]
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(root / item["path"]))
    tex.interpolation = "Linear"
    emit = nodes.new("ShaderNodeEmission")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    threshold = nodes.new("ShaderNodeMath")
    threshold.operation = "GREATER_THAN"
    threshold.inputs[1].default_value = 249.5 / 255
    mix, output = nodes.new("ShaderNodeMixShader"), nodes.new("ShaderNodeOutputMaterial")
    links.new(tex.outputs["Color"], emit.inputs["Color"])
    links.new(tex.outputs["Alpha"], threshold.inputs[0])
    links.new(threshold.outputs[0], mix.inputs[0])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emit.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs["Surface"])
    material.surface_render_method = "DITHERED"
    return {
        "name": item["name"],
        "target_height_pixels": target_height,
        "baseline_y_pixels": baseline,
        "target_top_y_pixels": baseline - target_height,
        "uniform_scale": factor,
    }


def solid(obj, color):
    material = bpy.data.materials.new(obj.name + "-label")
    material.diffuse_color = (*color, 1)
    obj.data.materials.append(material)


def supported(obj):
    bpy.context.view_layer.update()
    obj.location.z -= min((obj.matrix_world @ v.co).z for v in obj.data.vertices)


def ramp(t, start, duration):
    u = max(0, min(1, (t - start) / duration))
    return u * u * (3 - 2 * u)


validate_sources()
if args.mode == "chart":
    assert not owned("chart").exists()
    scene = empty_scene()
    width, height = cfg["chart_width"], cfg["chart_height"]
    baseline, ppcm = cfg["baseline_y"], cfg["pixels_per_cm"]
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 16
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    cam_data = bpy.data.cameras.new("Chart-camera")
    camera = bpy.data.objects.new("Chart-camera", cam_data)
    scene.collection.objects.link(camera)
    camera.location = (width / 2, height / 2, 10)
    cam_data.type, cam_data.ortho_scale = "ORTHO", width
    cam_data.sensor_fit, cam_data.clip_end = "HORIZONTAL", 100
    scene.camera = camera
    bg = emission("Warm-white", (0.95, 0.95, 0.93))
    grid = emission("Grid", (0.72, 0.74, 0.74))
    ink = emission("Ink", (0.025, 0.035, 0.045))
    blue = emission("Mia-line", (0.12, 0.28, 0.48))
    pink = emission("Gulu-line", (0.6, 0.16, 0.25))
    green = emission("Paper-line", (0.15, 0.36, 0.23))
    rect("Chart-background", width / 2, height / 2, width, height, 0, bg)
    for cm in range(0, 141, 10):
        y = height - baseline + cm * ppcm
        rect(f"Grid-{cm}cm", 975, y, 1550, 0.65, 0.01, grid)
        rect(f"Tick-{cm}cm", 180, y, 30, 1.2, 0.02, ink)
        label(f"{cm} cm", 150, y, 24, ink, "RIGHT")
    rect("Vertical-ruler", 170, height - baseline + 70 * ppcm, 2, 140 * ppcm, 0.02, ink)
    for cm in range(5, 140, 10):
        rect(f"Minor-{cm}", 177, height - baseline + cm * ppcm, 14, 0.8, 0.02, ink)
    rect("Common-ground-line", 960, height - baseline, 1580, 2, 0.025, ink)
    placements = []
    for key, x, cm, name, material in [
        ("girl", cfg.get("chart_centers", {}).get("girl", 540), 130, "MIA / 米娅", blue),
        ("dragon", cfg.get("chart_centers", {}).get("dragon", 1080), 40, "GULU / 咕噜", pink),
    ]:
        placements.append(cutout(cfg[key], x, cm * ppcm, baseline))
        y = height - baseline + cm * ppcm
        rect(name + "-height-line", 975, y, 1550, 1.1, 0.03, material)
        label(name, x, 111, 31, ink)
        label(f"{cm} cm", x, 65, 28, material)
    paper_x, paper_h, paper_w = 1530, 29.7 * ppcm, 21 * ppcm
    rect(
        "A4-border", paper_x, height - baseline + paper_h / 2, paper_w + 3, paper_h + 3, 0.035, ink
    )
    rect(
        "A4-sheet",
        paper_x,
        height - baseline + paper_h / 2,
        paper_w,
        paper_h,
        0.04,
        emission("Paper-white", (1, 1, 1)),
    )
    label("A4", paper_x, height - baseline + paper_h / 2, 30, ink)
    label("A4 PAPER / A4纸", paper_x, 111, 27, ink)
    label("29.7 cm", paper_x, 65, 28, green)
    label("HEIGHT & SCALE REFERENCE", 980, 974, 27, ink)
    label("Shared baseline · same scale · standing crown / horn-tip height", 950, 22, 20, ink)
    scene.render.filepath = str(owned("chart"))
    owned("chart").parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.file.pack_all()
    digest = save_checked(bpy, owned("chart_blend"), root, validate_sources)
    bpy.ops.render.render(write_still=True)
    dump(
        owned("chart_record"),
        {
            "blend_sha256": digest,
            "image_sha256": sha(owned("chart")),
            "pixels_per_cm": ppcm,
            "girl_cm": 130,
            "dragon_cm": 40,
            "a4_cm": [21, 29.7],
            "placements": placements,
            "scope": (
                "Measured orthographic reference only. "
                "Not the guide scene or an extra identity board."
            ),
        },
    )
elif args.mode == "chart-mask":
    record = json.loads(owned("chart_record").read_text(encoding="utf-8"))
    require_hash(owned("chart_blend"), record["blend_sha256"])
    bpy.ops.wm.open_mainfile(filepath=str(owned("chart_blend")))
    scene = bpy.context.scene
    for obj in scene.objects:
        if obj.type in ("MESH", "FONT"):
            obj.hide_render = obj.name not in (cfg["girl"]["name"], cfg["dragon"]["name"])
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = str(owned("chart_mask"))
    owned("chart_mask").parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)
elif args.mode == "build":
    assert not owned("blend").exists()
    scene = empty_scene()
    scene.unit_settings.system, scene.unit_settings.scale_length = "METRIC", 1
    scene.world = bpy.data.worlds.new("Neutral-encoding-canvas")
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light, scene.display.shading.color_type = "FLAT", "MATERIAL"
    scene.display.shading.background_type, scene.world.color = "WORLD", (0.18, 0.18, 0.18)
    scene.display.shading.show_shadows = False
    scene.render.resolution_x, scene.render.resolution_y = 960, 540
    scene.render.resolution_percentage, scene.render.fps = 100, 24
    scene.frame_start, scene.frame_end = 1, 120
    data = bpy.data.cameras.new("Camera-fixed")
    camera = bpy.data.objects.new("Camera-fixed", data)
    scene.collection.objects.link(camera)
    camera.matrix_world = Matrix(cfg["camera_matrix"])
    data.lens, data.sensor_width, data.sensor_fit = 50, 36, "AUTO"
    scene.camera = camera
    root_obj = bpy.data.objects.new("GULU-root", None)
    scene.collection.objects.link(root_obj)
    root_obj.location = cfg["dragon_position"]
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.07, depth=0.33)
    body = bpy.context.object
    body.name, body.parent = "GULU-torso-envelope", root_obj
    body.rotation_euler = (0, math.pi / 2, 0)
    body.location = (0, 0, 0.19)
    solid(body, (0.67, 0.38, 0.16))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=0.09)
    head = bpy.context.object
    head.name, head.parent = "GULU-head-and-horns-envelope", root_obj
    head.location = (-0.16, 0, 0.31)
    solid(head, (0.67, 0.38, 0.16))
    parts = [body, head]
    # Flat contact markers give a readable ground plane, without a limb or gait rig.
    for x in (-0.13, 0.13):
        for y in (-0.08, 0.08):
            anchor = bpy.data.objects.new(f"Paw-anchor-{x}-{y}", None)
            scene.collection.objects.link(anchor)
            anchor.location = (cfg["dragon_position"][0] + x, cfg["dragon_position"][1] + y, 0)
            bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.025, depth=0.024)
            paw = bpy.context.object
            paw.name = f"GULU-contact-{x}-{y}"
            paw.location = (anchor.location.x, anchor.location.y, 0.012)
            solid(paw, (0.67, 0.38, 0.16))
            parts.append(paw)
    bpy.context.view_layer.update()
    for obj in parts:
        world = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = world
        group = obj.vertex_groups.new(name=obj.name)
        group.add(list(range(len(obj.data.vertices))), 1, "REPLACE")
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    figure = bpy.context.object
    figure.name = "GULU-geometric-figure"
    bpy.data.objects.remove(root_obj, do_unlink=True)
    figure.shape_key_add(name="Standing")
    resting = figure.shape_key_add(name="Resting-supported")
    moving_groups = {
        figure.vertex_groups[name].index
        for name in ("GULU-torso-envelope", "GULU-head-and-horns-envelope")
    }
    for vertex in figure.data.vertices:
        if any(g.group in moving_groups for g in vertex.groups):
            resting.data[vertex.index].co.z -= 0.07
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.15, depth=1.30)
    girl = bpy.context.object
    girl.name, girl.rotation_mode = "MIA-reclining-length-envelope", "QUATERNION"
    girl.location = (cfg["dragon_position"][0] + 1.25, cfg["dragon_position"][1], 0.15)
    solid(girl, (0.12, 0.30, 0.64))
    for frame in range(1, 121):
        t = (frame - 1) / 24
        resting.value = 1 - ramp(t, 1.2, 0.6)
        resting.keyframe_insert("value", frame=frame)
        girl.rotation_quaternion = Quaternion((0, 1, 0), math.pi / 2 + 0.014 * ramp(t, 1.35, 0.45))
        girl.location.z = 0.15
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
            "visible_meshes": [figure.name, girl.name],
            "image_datablocks": len(bpy.data.images),
            "standing_highest_head_envelope_m": 0.4,
            "resting_highest_envelope_m": 0.33,
            "torso_diameter_m": 0.14,
            "torso_length_m": 0.33,
            "scope": (
                "Pure Blender primitives. "
                "Torso and head-range markers, not a detailed creature model."
            ),
        },
    )
else:
    build = json.loads(owned("build_record").read_text(encoding="utf-8"))
    require_hash(owned("blend"), build["blend_sha256"])
    bpy.ops.wm.open_mainfile(filepath=str(owned("blend")))
    scene = bpy.context.scene
    if args.mode == "render":
        owned("frames").mkdir(parents=True, exist_ok=False)
        bpy.ops.render.render(animation=True)
    else:
        assert len(bpy.data.images) == 0, "Images must not enter actual guide"
        visible = [o for o in scene.objects if o.type == "MESH" and not o.hide_render]
        assert len(visible) == 2

        def local_extents(obj):
            return [
                max(v.co[i] for v in obj.data.vertices) - min(v.co[i] for v in obj.data.vertices)
                for i in range(3)
            ]

        baseline = {o.name: local_extents(o) for o in visible}
        figure = bpy.data.objects["GULU-geometric-figure"]
        part_indices = {
            group.name: [
                v.index
                for v in figure.data.vertices
                if any(g.group == group.index for g in v.groups)
            ]
            for group in figure.vertex_groups
        }
        part_sizes = {}
        camera = [list(row) for row in scene.camera.matrix_world]
        samples = []
        for frame in range(1, 121):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            for obj in visible:
                assert all(abs(v - 1) < 1e-6 for v in obj.scale)
                assert (
                    max(
                        abs(a - b)
                        for a, b in zip(local_extents(obj), baseline[obj.name], strict=True)
                    )
                    < 1e-5
                )
            assert camera == [list(row) for row in scene.camera.matrix_world]
            evaluated = figure.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh = evaluated.to_mesh()
            pts = [figure.matrix_world @ v.co for v in mesh.vertices]
            for name, indices in part_indices.items():
                subset = [pts[i] for i in indices]
                extents = [max(v[i] for v in subset) - min(v[i] for v in subset) for i in range(3)]
                if name not in part_sizes:
                    part_sizes[name] = extents
                assert (
                    max(abs(a - b) for a, b in zip(extents, part_sizes[name], strict=True)) < 1e-6
                )
            assert abs(min(v.z for v in pts)) < 1e-6
            torso = [pts[i] for i in part_indices["GULU-torso-envelope"]]
            uv = [world_to_camera_view(scene, scene.camera, v) for v in pts]
            samples.append(
                {
                    "frame": frame,
                    "pts": (frame - 1) / 24,
                    "highest_head_envelope_m": max(v.z for v in pts),
                    "lowest_contact_m": min(v.z for v in pts),
                    "torso_center": [sum(v[i] for v in torso) / len(torso) for i in range(3)],
                    "bbox": [
                        min(v.x for v in uv),
                        1 - max(v.y for v in uv),
                        max(v.x for v in uv),
                        1 - min(v.y for v in uv),
                    ],
                }
            )
            evaluated.to_mesh_clear()
        assert abs(samples[0]["highest_head_envelope_m"] - 0.33) < 1e-6
        assert abs(samples[44]["highest_head_envelope_m"] - 0.40) < 1e-6
        dump(
            owned("inspection"),
            {
                "blend_sha256": build["blend_sha256"],
                "constant_mesh_dimensions": baseline,
                "constant_evaluated_part_extents": part_sizes,
                "visible_meshes": [o.name for o in visible],
                "image_datablocks": 0,
                "environment_in_guide": False,
                "camera_fixed": True,
                "samples": samples,
                "rise_seconds": 0.6,
                "vertical_torso_travel_m": 0.07,
                "max_rise_speed_m_s": 0.175,
                "scope": "Actual proxy control; no generated scale claim.",
            },
        )
        print(
            "Verified constant primitive sizes, pure guide, fixed camera and0.33→0.40m pose height"
        )
