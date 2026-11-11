"""Run only in an isolated Blender process against a saved, hash-bound scene."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from array import array
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from whitebox_saved import (  # noqa: E402
    load_saved,
    property_value_matches,
    render_still_new,
    require_viewport_evaluation,
    save_render_new,
    set_unanimated_property,
)

GEOMETRY_TYPES = {"MESH", "CURVE", "SURFACE", "FONT", "META"}


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def verify(job):
    for item in job["dependencies"] + job["implementation"]:
        if sha(item["path"]) != item["sha256"]:
            raise ValueError(f"输入在处理期间变化：{item['path']}")


def load_scene(job):
    verify(job)
    source = next(item for item in job["dependencies"] if item["path"] == job["blend"])
    scene = load_saved(bpy, job["blend"], source["sha256"])
    plan = job["plan"]
    rate = plan["fps"]["num"] / plan["fps"]["den"]
    if abs(scene.render.fps / scene.render.fps_base - rate) > 1e-6:
        raise ValueError("工程实际帧率与白模计划不一致")
    start = plan.get("frame_start", 1)
    if scene.frame_start != start or scene.frame_end != start + plan["frame_count"] - 1:
        raise ValueError("工程实际帧范围与白模计划不一致")
    if any(o.instance_type != "NONE" for o in scene.objects):
        raise ValueError("当前检查器不支持实例对象，请在副本中转为实际对象后检查")
    if scene.render.use_border or scene.render.use_simplify:
        raise ValueError("请在工程副本中关闭渲染区域裁切和Simplify后检查")
    return scene


def visible_meshes(scene):
    """Render visibility, including nested collections; never skip objects by name."""
    visible = set()

    def visit(layer):
        if layer.exclude or layer.collection.hide_render:
            return
        for obj in layer.collection.objects:
            if not obj.hide_render:
                if obj.type in {"VOLUME", "GREASEPENCIL", "POINTCLOUD"}:
                    raise ValueError(f"暂不支持此类可渲染对象：{obj.name} ({obj.type})")
                if obj.type in GEOMETRY_TYPES:
                    visible.add(obj.name)
        for child in layer.children:
            visit(child)

    visit(bpy.context.view_layer.layer_collection)
    return [o for o in scene.objects if o.name in visible]


def subject_objects(plan):
    subjects = {}
    owners = {}
    for sid, spec in plan["subjects"].items():
        names = set()
        for name in spec["objects"]:
            obj = bpy.data.objects.get(name)
            if obj is None:
                raise ValueError(f"检查主体对象不存在：{name}")
            names.update(o.name for o in (obj, *obj.children_recursive) if o.type in GEOMETRY_TYPES)
        if not names:
            raise ValueError(f"主体没有网格：{sid}")
        for name in names:
            if name in owners:
                raise ValueError(f"网格属于多个主体：{name}")
            owners[name] = sid
        subjects[sid] = names
    return subjects


def geometry(scene, graph, with_bvh=True):
    meshes, signature = {}, []
    for instance in graph.object_instances:
        if instance.is_instance:
            # Blender 5.3 exposes a curve's own tessellated surface as a same-name
            # mesh instance; to_mesh() below already includes that geometry.
            if (
                instance.parent is not None
                and instance.parent.original.type in {"CURVE", "SURFACE", "FONT", "META"}
                and instance.object.type == "MESH"
                and instance.object.name == instance.parent.name
            ):
                continue
            raise ValueError(
                "求值场景含实例，请先在工程副本中实体化后检查："
                f"{instance.object.name} ({instance.object.type}), "
                f"parent={instance.parent.name if instance.parent else None}"
            )
    for obj in sorted(visible_meshes(scene), key=lambda o: o.name):
        if obj.type in {"CURVE", "SURFACE", "FONT"}:
            for axis in ("u", "v"):
                render_resolution = getattr(obj.data, f"render_resolution_{axis}", 0)
                if render_resolution not in (0, getattr(obj.data, f"resolution_{axis}", 0)):
                    raise ValueError(f"曲线视口与渲染细分不一致，请在副本中统一：{obj.name}")
        if obj.type == "META" and obj.data.resolution != obj.data.render_resolution:
            raise ValueError(f"融球视口与渲染细分不一致，请在副本中统一：{obj.name}")
        if obj.particle_systems:
            raise ValueError(f"暂不支持粒子系统：{obj.name}")
        for modifier in obj.modifiers:
            if modifier.show_viewport != modifier.show_render or (
                modifier.type in {"SUBSURF", "MULTIRES"}
                and modifier.show_render
                and modifier.levels != modifier.render_levels
            ):
                raise ValueError(f"视口与渲染修改器不一致，请在工程副本中统一：{obj.name}")
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        try:
            if mesh is None or not mesh.vertices or not mesh.polygons:
                continue
            # Hash full evaluated coordinates/topology in compact binary form. Bounds-only
            # checks do not need expensive world-space vertex copies or ray-casting trees.
            coordinates = array("f", [0]) * (len(mesh.vertices) * 3)
            loops = array("i", [0]) * len(mesh.loops)
            sizes = array("i", [0]) * len(mesh.polygons)
            mesh.vertices.foreach_get("co", coordinates)
            mesh.loops.foreach_get("vertex_index", loops)
            mesh.polygons.foreach_get("loop_total", sizes)
            mesh_hash = hashlib.sha256()
            for values in (coordinates, loops, sizes):
                mesh_hash.update(len(values).to_bytes(8, "little"))
                mesh_hash.update(values.tobytes())
            signature.append(
                (obj.name, [list(row) for row in evaluated.matrix_world], mesh_hash.hexdigest())
            )
            vertices, tree = [], None
            if with_bvh:
                vertices = [evaluated.matrix_world @ v.co for v in mesh.vertices]
                tree = BVHTree.FromPolygons(vertices, [list(p.vertices) for p in mesh.polygons])
            # Blender 5.3 can expose a stale unit bound_box for evaluated bevelled
            # curves. Use the actual converted mesh, which is already read above.
            lo = [min(coordinates[k::3]) for k in range(3)]
            hi = [max(coordinates[k::3]) for k in range(3)]
            bounds = [
                evaluated.matrix_world @ Vector((x, y, z))
                for x in (lo[0], hi[0])
                for y in (lo[1], hi[1])
                for z in (lo[2], hi[2])
            ]
            meshes[obj.name] = {"vertices": vertices, "bounds": bounds, "tree": tree}
        finally:
            evaluated.to_mesh_clear()
    return meshes, signature


def occlusion(camera, own, meshes):
    camera_origin = camera.matrix_world.translation
    forward = (camera.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
    points = []
    for name in sorted(own):
        verts = meshes[name]["vertices"]
        # Bounded surface sampling. This is a diagnostic, not a pixel visibility proof.
        points += verts[:: max(1, math.ceil(len(verts) / 24))]
    hits, clipped = {}, 0
    for point in points:
        # Orthographic rays are parallel, not rays from the camera's central point.
        depth = (point - camera_origin).dot(forward)
        if not camera.data.clip_start <= depth <= camera.data.clip_end:
            clipped += 1
            continue
        origin = point - forward * depth if camera.data.type == "ORTHO" else camera_origin
        direction = point - origin
        distance = direction.length
        if distance < 1e-6:
            continue
        direction.normalize()
        # Nothing before the near plane can appear in the camera image.
        near_distance = camera.data.clip_start / direction.dot(forward)
        origin = origin + direction * near_distance
        distance -= near_distance
        if distance <= 1e-4:
            continue
        nearest, blocker = distance - 1e-4, None
        for name, mesh in meshes.items():
            if name in own:
                continue
            loc, _normal, _face, dist = mesh["tree"].ray_cast(origin, direction, nearest)
            if loc is not None and dist < nearest:
                nearest, blocker = dist, name
        if blocker:
            hits[blocker] = hits.get(blocker, 0) + 1
    return {
        "sample_count": len(points),
        "clipped_samples": clipped,
        "blocked_fraction": sum(hits.values()) / max(1, len(points) - clipped),
        "blockers": hits,
    }


def anchor_point(anchor, graph):
    obj = bpy.data.objects.get(anchor["object"])
    if obj is None:
        raise ValueError(f"接触锚点不存在：{anchor['object']}")
    return obj.evaluated_get(graph).matrix_world @ Vector(anchor.get("point", [0, 0, 0]))


def inspect(scene, plan, *, exporting=False):
    subjects = subject_objects(plan)
    failures, samples = [], []
    digest = hashlib.sha256()
    for shot in plan["shots"]:
        camera_states = []
        for index in range(shot["start_frame"], shot["end_frame"]):
            frame = index + plan.get("frame_start", 1)
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            require_viewport_evaluation(bpy, scene)
            if exporting and any(obj.type == "FONT" for obj in visible_meshes(scene)):
                raise ValueError(
                    f"第{index}帧含可见文字对象，请在送模工程副本中移除标注或转为必要的实体几何"
                )
            graph = bpy.context.evaluated_depsgraph_get()
            camera = scene.camera
            if camera is None or camera.name != shot["camera"]:
                raise ValueError(f"第{index}帧实际相机与镜头{shot['id']}不一致")
            camera = camera.evaluated_get(graph)
            if camera.data.type not in {"PERSP", "ORTHO"}:
                raise ValueError("当前构图检查仅支持透视和正交相机")
            # Normalized dimensions make preview downscaling irrelevant, while
            # retaining the actual display aspect, sensor fit, lens and clipping.
            aspect = (
                scene.render.resolution_x
                * scene.render.pixel_aspect_x
                / (scene.render.resolution_y * scene.render.pixel_aspect_y)
            )
            projection = camera.calc_matrix_camera(graph, x=1000, y=1000, scale_x=aspect, scale_y=1)
            camera_state = [v for row in camera.matrix_world for v in row] + [
                v for row in projection for v in row
            ]
            camera_states.append(camera_state)
            needs_rays = any("max_occlusion" in v for v in shot.get("framing", {}).values())
            meshes, signature = geometry(scene, graph, with_bvh=needs_rays)
            digest.update(
                json.dumps(
                    (index, camera_state, signature), ensure_ascii=False, allow_nan=False
                ).encode("utf-8")
            )
            sample = {
                "frame": index,
                "blender_frame": frame,
                "shot_id": shot["id"],
                "camera": shot["camera"],
                "subjects": {},
                "contacts": [],
            }
            for sid in shot["subjects"]:
                own = subjects[sid] & meshes.keys()
                if not own:
                    failures.append({"frame": index, "kind": "invisible_subject", "subject": sid})
                    continue
                points = [p for name in sorted(own) for p in meshes[name]["bounds"]]
                uv = [world_to_camera_view(scene, camera, p) for p in points]
                x0, x1 = min(p.x for p in uv), max(p.x for p in uv)
                y0, y1 = min(p.y for p in uv), max(p.y for p in uv)
                limits = shot.get("framing", {}).get(sid, {})
                margin = limits.get("margin", 0)
                in_frame = (
                    all(camera.data.clip_start <= p.z <= camera.data.clip_end for p in uv)
                    and margin <= x0 <= x1 <= 1 - margin
                    and margin <= y0 <= y1 <= 1 - margin
                )
                fact = {
                    "bounds": [x0, y0, x1, y1],
                    "height": y1 - y0,
                    "inside": in_frame,
                    "camera_depth_range": [min(p.z for p in uv), max(p.z for p in uv)],
                    "camera_clip_range": [camera.data.clip_start, camera.data.clip_end],
                    "minimum_world_z": min(p.z for p in points),
                    "visible_objects": sorted(own),
                }
                if limits.get("inside") and not in_frame:
                    failures.append({"frame": index, "kind": "cropped", "subject": sid})
                if not limits.get("min_height", 0) <= y1 - y0 <= limits.get("max_height", 100):
                    failures.append({"frame": index, "kind": "height", "subject": sid})
                if "max_occlusion" in limits:
                    fact["occlusion"] = occlusion(camera, own, meshes)
                    if fact["occlusion"]["blocked_fraction"] > limits["max_occlusion"]:
                        failures.append(
                            {
                                "frame": index,
                                "kind": "occlusion",
                                "subject": sid,
                                "blockers": fact["occlusion"]["blockers"],
                            }
                        )
                sample["subjects"][sid] = fact
            for contact in shot.get("contacts", []):
                if (
                    contact.get("start_frame", shot["start_frame"])
                    <= index
                    < contact.get("end_frame", shot["end_frame"])
                ):
                    distance = (
                        anchor_point(contact["a"], graph) - anchor_point(contact["b"], graph)
                    ).length
                    sample["contacts"].append({"id": contact["id"], "distance": distance})
                    if distance > contact["max_distance"]:
                        failures.append(
                            {
                                "frame": index,
                                "kind": "contact",
                                "id": contact["id"],
                                "distance": distance,
                            }
                        )
            samples.append(sample)
        moving = any(
            any(abs(a - b) > 1e-6 for a, b in zip(camera_states[0], state, strict=True))
            for state in camera_states[1:]
        )
        wanted = shot.get("camera_motion", "any")
        if (wanted == "fixed" and moving) or (wanted == "moving" and not moving):
            failures.append(
                {
                    "shot": shot["id"],
                    "kind": "camera_motion",
                    "wanted": wanted,
                    "actual": "moving" if moving else "fixed",
                }
            )
    return {
        "schema_version": 1,
        "blender_version": bpy.app.version_string,
        "geometry_camera_sha256": digest.hexdigest(),
        "sampled_frames": len(samples),
        "failures": failures,
        "samples": samples,
        "render_format": {
            "width": scene.render.resolution_x,
            "height": scene.render.resolution_y,
            "percentage": scene.render.resolution_percentage,
            "pixel_aspect_x": scene.render.pixel_aspect_x,
            "pixel_aspect_y": scene.render.pixel_aspect_y,
        },
        "limitations": [
            "包围盒投影及有限表面射线是诊断数据，不是完整碰撞/逐像素可见性证明。",
            "仅检查声明的主体、相机和接触锚点；动态自然度、声音、模型可读性和用户认可仍待审。",
        ],
    }


def blur_switches(scene):
    """The supported engine-wide switches and every possible shot camera."""
    motion = [
        (scene, f"{name}.use_motion_blur")
        for name in ("render", "eevee")
        if hasattr(getattr(scene, name, None), "use_motion_blur")
    ]
    if not motion:
        raise ValueError("当前Blender未提供支持的运动模糊开关，拒绝导出")
    # A camera assigned directly or through a timeline marker need not be
    # linked to a scene collection. Its data still controls the rendered view.
    cameras = {obj.data for obj in scene.objects if obj.type == "CAMERA"}
    cameras.update(
        camera.data for camera in [scene.camera, *(m.camera for m in scene.timeline_markers)]
        if camera is not None
    )
    return motion + [
        (data, "dof.use_dof") for data in sorted(cameras, key=lambda data: data.name)
    ]


def require_blur_disabled(scene):
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    for owner, path in blur_switches(scene):
        if owner.path_resolve(path) or owner.evaluated_get(graph).path_resolve(path):
            raise ValueError(f"求值后模糊开关重新启用，拒绝导出：{owner.name}.{path}")


def fix_pass_property(contract, owner, path, value):
    set_unanimated_property(owner, path, value)
    contract[owner, path] = value


def require_pass_settings(scene, contract):
    """Check the declared display contract, including render-time reevaluation."""
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    for (owner, path), expected in contract.items():
        for state in (owner, owner.evaluated_get(graph)):
            if not property_value_matches(state.path_resolve(path), expected):
                raise ValueError(f"求值后显示属性改变，拒绝导出：{owner.name}.{path}")


def configure_pass(scene, plan, name):
    contract = {}

    def fixed(path, value, owner=scene):
        fix_pass_property(contract, owner, path, value)

    subjects = subject_objects(plan)
    owners = {name: sid for sid, names in subjects.items() for name in names}
    if any(obj.type == "FONT" for obj in visible_meshes(scene)):
        raise ValueError("工程含可见文字对象，请在送模工程副本中移除标注或转为必要的实体几何")
    for owner, path in blur_switches(scene):
        fixed(path, False, owner)
    # These properties define the preview, rather than the source's artistic
    # grading/output setup. Clear only their animation channels in this copy.
    for path, value in (
        ("display_settings.display_device", "sRGB"),
        ("view_settings.view_transform", "Standard"),
        ("view_settings.look", "None"),
        ("view_settings.exposure", 0.0),
        ("view_settings.gamma", 1.0),
        ("view_settings.use_curve_mapping", False),
        ("render.use_stamp", name == "审片版"),
        ("render.stamp_note_text", ""),
        ("render.film_transparent", False),
        ("render.use_compositing", False),
        ("render.use_sequencer", False),
        ("render.use_multiview", False),
        ("render.dither_intensity", 0.0),
        ("render.image_settings.file_format", "PNG"),
        ("render.image_settings.color_mode", "RGB"),
        ("render.image_settings.color_depth", "8"),
        ("render.image_settings.color_management", "FOLLOW_SCENE"),
    ):
        fixed(path, value)
    # A feature absent from this Blender API cannot be enabled in its scene.
    for target, attribute, value in (
        (scene.view_settings, "use_white_balance", False),
        (scene.display_settings, "emulation", "OFF"),
        (scene.render, "use_freestyle", False),
    ):
        if hasattr(target, attribute):
            fixed(target.path_from_id(attribute), value)
    if hasattr(scene.view_settings, "is_hdr"):
        contract[scene, "view_settings.is_hdr"] = False  # Read-only derived capability.
    for prop in scene.render.bl_rna.properties:
        if prop.identifier.startswith("use_stamp_"):
            fixed(f"render.{prop.identifier}", False)
    if name == "审片版":
        fixed("render.engine", "BLENDER_WORKBENCH")
        for attribute, value in (
            ("light", "STUDIO"), ("color_type", "OBJECT"), ("show_object_outline", True),
            ("show_cavity", True), ("show_shadows", False),
        ):
            fixed(f"display.shading.{attribute}", value)
        colors = [(1.0, 0.4, 0.1, 1), (0.15, 0.45, 0.9, 1), (0.8, 0.2, 0.4, 1), (0.4, 0.8, 0.3, 1)]
        for obj in scene.objects:
            if obj.type not in GEOMETRY_TYPES:
                continue
            sid = owners.get(obj.name)
            color = (
                colors[list(subjects).index(sid) % len(colors)] if sid else (0.65, 0.65, 0.65, 1)
            )
            fixed("color", color, obj)
        fixed("render.use_stamp_note", True)
    else:
        fixed("render.engine", "BLENDER_EEVEE")
        # This isolated pass renders the current layer. Its source override
        # would replace every object slot, defeating the subject gray mapping.
        fixed(bpy.context.view_layer.path_from_id("material_override"), None)
        fixed("world", bpy.data.worlds.new("白模送模背景"))
        scene.world.use_nodes = True
        scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.8, 0.8, 0.8, 1)
        mats = {}
        for obj in scene.objects:
            if obj.type not in GEOMETRY_TYPES:
                continue
            sid = owners.get(obj.name)
            gray = plan["subjects"][sid].get("model_gray", 0.35) if sid else 0.7
            if gray not in mats:
                mat = bpy.data.materials.new(f"白模灰度{gray}")
                mat.use_nodes = True
                nodes = mat.node_tree.nodes
                nodes.clear()
                emission = nodes.new("ShaderNodeEmission")
                emission.inputs["Color"].default_value = (gray, gray, gray, 1)
                out = nodes.new("ShaderNodeOutputMaterial")
                mat.node_tree.links.new(emission.outputs[0], out.inputs["Surface"])
                mats[gray] = mat
            # OBJECT slots avoid altering another object's shared mesh material choices.
            if not obj.data.materials:
                obj.data.materials.append(mats[gray])
            for slot in obj.material_slots:
                slot.link = "OBJECT"
                slot.material = mats[gray]
    scale = plan.get("preview_scale", 25) / 100
    factor = scene.render.resolution_percentage / 100 * scale
    w, h = scene.render.resolution_x * factor, scene.render.resolution_y * factor
    if w != int(w) or h != int(h) or int(w) % 2 or int(h) % 2 or min(w, h) < 16:
        raise ValueError("预览缩放后尺寸须为不小于16的偶数；调整preview_scale，不改变画幅")
    fixed("render.resolution_x", int(w))
    fixed("render.resolution_y", int(h))
    fixed("render.resolution_percentage", 100)
    require_pass_settings(scene, contract)
    return contract


def render_pass(job, original, name):
    scene = load_scene(job)
    contract = configure_pass(scene, job["plan"], name)
    # Check the actual configured scene; material/display changes must preserve motion.
    candidate = inspect(scene, job["plan"], exporting=True)
    if candidate["geometry_camera_sha256"] != original["geometry_camera_sha256"]:
        raise ValueError(f"{name}改变了实际几何或相机，拒绝导出")
    frames = Path(job["paths"]["work"]) / name
    frames.mkdir()
    evidence = Path(job["paths"]["evidence"])
    shots = job["plan"]["shots"]
    for index in range(job["plan"]["frame_count"]):
        scene.frame_set(index + job["plan"].get("frame_start", 1))
        shot = next(s for s in shots if s["start_frame"] <= index < s["end_frame"])
        if name == "审片版":
            fix_pass_property(
                contract, scene, "render.stamp_note_text", f"{shot['id']} | frame {index}"
            )
        require_viewport_evaluation(bpy, scene)
        require_pass_settings(scene, contract)
        render_still_new(
            bpy, frames / f"帧-{index:06d}.png", job["project"],
            validate_render=lambda: require_pass_settings(scene, contract),
            layer=bpy.context.view_layer.name,
        )
        if index in {shot["start_frame"], shot["end_frame"] - 1}:
            tag = "入点" if index == shot["start_frame"] else "出点"
            # Saved render result, no second render or contrast manipulation.
            save_render_new(
                bpy.data.images["Render Result"],
                evidence / f"{name}-镜头{shots.index(shot) + 1:02d}-{tag}.png",
                job["project"],
            )
    verify(job)


def render_plan(job):
    scene = load_scene(job)
    contract = configure_pass(scene, job["plan"], "审片版")
    scene.frame_set(job["plan"].get("frame_start", 1))
    for name in job["plan"].get("plan_hide", []):
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise ValueError(f"平面图隐藏对象不存在：{name}")
        obj.hide_render = True
        for child in obj.children_recursive:
            child.hide_render = True
    graph = bpy.context.evaluated_depsgraph_get()
    points = [
        evaluated.matrix_world @ Vector(v)
        for obj in visible_meshes(scene)
        for evaluated in [obj.evaluated_get(graph)]
        for v in evaluated.bound_box
    ]
    # This auxiliary view is explicitly a first-frame plan, not animated camera-path evidence.
    used_cameras = {shot["camera"] for shot in job["plan"]["shots"]}
    for camera in [o for o in scene.objects if o.name in used_cameras]:
        corners = camera.data.view_frame(scene=scene)
        origin = camera.matrix_world.translation
        rays = [origin + (camera.matrix_world.to_3x3() @ v).normalized() * 2 for v in corners]
        points.extend([origin, *rays])
        curve = bpy.data.curves.new("机位视锥", "CURVE")
        curve.dimensions, curve.bevel_depth = "3D", 0.02
        for point in rays:
            spline = curve.splines.new("POLY")
            spline.points.add(1)
            spline.points[0].co = (*origin, 1)
            spline.points[1].co = (*point, 1)
        marker = bpy.data.objects.new("机位视锥", curve)
        marker.color = (1, 0.1, 0.1, 1)
        scene.collection.objects.link(marker)
    x0, x1 = min(p.x for p in points), max(p.x for p in points)
    y0, y1 = min(p.y for p in points), max(p.y for p in points)
    z1 = max(p.z for p in points)
    data = bpy.data.cameras.new("检查用俯视")
    data.type, data.ortho_scale = "ORTHO", max(x1 - x0, y1 - y0, 1) * 1.2
    obj = bpy.data.objects.new("检查用俯视", data)
    scene.collection.objects.link(obj)
    obj.location = ((x0 + x1) / 2, (y0 + y1) / 2, z1 + 10)
    # Rendering reevaluates timeline camera markers. Remove their bindings only
    # in this disposable auxiliary scene, or they silently replace the plan camera.
    for marker in scene.timeline_markers:
        marker.camera = None
    scene.camera = obj
    fix_pass_property(contract, scene, "render.resolution_x", 512)
    fix_pass_property(contract, scene, "render.resolution_y", 512)
    fix_pass_property(
        contract, scene, "render.stamp_note_text",
        "First-frame plan | red: cameras | declared plan_hide applied",
    )
    require_viewport_evaluation(bpy, scene)
    require_pass_settings(scene, contract)
    render_still_new(
        bpy, Path(job["paths"]["evidence"]) / "首帧空间与机位图.png", job["project"],
        validate_render=lambda: require_pass_settings(scene, contract),
        layer=bpy.context.view_layer.name,
    )
    if scene.camera != obj:
        raise ValueError("首帧空间图实际相机被替换，拒绝发布检查包")


def main():
    job_path = Path(sys.argv[sys.argv.index("--") + 1])
    job_hash = sha(job_path)
    job = json.loads(job_path.read_text("utf-8"))
    scene = load_scene(job)
    report = inspect(scene, job["plan"], exporting=job["render"])
    report["dependencies"] = job["dependencies"]
    verify(job)
    write_new(Path(job["paths"]["evidence"]) / "场景检查.json", report)
    if job["render"] and not report["failures"]:
        render_pass(job, report, "审片版")
        render_pass(job, report, "送模版")
        render_plan(job)
    verify(job)
    if sha(job_path) != job_hash:
        raise ValueError("执行输入在处理期间变化")


if __name__ == "__main__":
    main()
