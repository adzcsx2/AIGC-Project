"""Build the approved cliff story using simple proxies and real animated cameras."""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import read_json_bound, require_hash, save_checked
from whitebox_saved import project_path, render_still_new, write_json_new


def lerp(a, b, u):
    return a + (b - a) * u


def interpolate(track, t):
    if t <= track[0][0]:
        return track[0][1:]
    for before, after in zip(track, track[1:], strict=False):
        if t <= after[0]:
            u = (t - before[0]) / (after[0] - before[0])
            return [lerp(a, b, u) for a, b in zip(before[1:], after[1:], strict=True)]
    return track[-1][1:]


def forward_pose(direction, roll=0):
    forward = Vector(direction).normalized()
    up = Vector((0, 0, 1))
    if abs(forward.dot(up)) > 0.98:
        up = Vector((0, 1, 0))
    right = up.cross(forward).normalized()
    up = forward.cross(right).normalized()
    basis = Matrix((right, up, forward)).transposed()
    return (basis @ Matrix.Rotation(roll, 3, "Z")).to_quaternion()


def mesh(name, kind, dimensions, location, color):
    if kind == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1, depth=2)
    elif kind == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1)
    else:
        bpy.ops.mesh.primitive_cube_add(size=2)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.location = location
    obj.color = color
    material = bpy.data.materials.new(name + "-纯色")
    material.diffuse_color = color
    obj.data.materials.append(material)
    return obj


def point_empty(name, location):
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    obj.empty_display_size = 0.025
    return obj


def insert_transform(obj, frame):
    obj.keyframe_insert("location", frame=frame)
    obj.keyframe_insert("rotation_quaternion", frame=frame)


def dragon_state(config, t):
    if 113.5 <= t < 121:
        u = (t - 113.5) / 7.5
        angle = math.pi / 2 + math.tau * u
        pos = Vector((3 * math.cos(angle), -6 + 3 * math.sin(angle), 4.5 + 0.3 * u))
        direction = (-math.sin(angle), math.cos(angle), 0.03)
        return pos, forward_pose(direction, math.radians(15))
    if t >= 138:
        angle = (t - 138) * 0.55
        pos = Vector((1.4 * math.sin(angle), -3.5 + 0.8 * math.cos(angle), 2.7))
        return pos, forward_pose((math.cos(angle), -0.57 * math.sin(angle), 0))
    x, y, z, yaw, pitch, roll, _ = interpolate(config["dragon_track"], t)
    direction = (math.sin(yaw) * math.cos(pitch), math.cos(yaw) * math.cos(pitch), math.sin(pitch))
    q = forward_pose(direction, roll)
    # Track Z denotes the lower support-envelope height, distinct from body scale.
    obj = bpy.data.objects["占位-幼龙"]
    points = [Vector(v) for v in obj.bound_box]
    tail = bpy.data.objects["占位-幼龙-方向尾杆"]
    points.extend(Vector(v) + tail.location for v in tail.bound_box)
    z -= min((q @ v).z for v in points)
    return Vector((x, y, z)), q


def girl_state(config, t):
    x, y, lift, tilt, yaw = interpolate(config["girl_track"], t)
    q = Quaternion((0, 0, 1), yaw) @ Quaternion((1, 0, 0), tilt)
    obj = bpy.data.objects["占位-女孩"]
    minimum = min((q @ Vector(v)).z for v in obj.bound_box)
    return Vector((x, y, lift - minimum)), q


def camera_target(cid, authored, girl, dragon):
    if cid in {"C04", "C07", "C11", "C12", "C20", "C21", "C23", "C24", "C25"}:
        return dragon.location.copy()
    if cid == "C14":
        return girl.location.copy() + Vector((0, -0.2, 0.12))
    # Close-ups aim at the authored conceptual face/contact position, not a modeled face.
    return Vector(authored)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--config", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    project = Path(args.project).resolve()
    config_path = project_path(project, args.config, exists=True)
    config, config_hash = read_json_bound(config_path)
    destination = project_path(project, config["output_blend"])
    report_path = project_path(project, config["report"])
    stills = project_path(project, config["stills"])
    for path in (destination, report_path, stills):
        if path.exists():
            raise FileExistsError(path)
    pins = [
        (project_path(project, item["path"], exists=True), item["sha256"])
        for item in config["source_documents"]
    ]

    def validate():
        require_hash(config_path, config_hash)
        for path, digest in pins:
            require_hash(path, digest)

    validate()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    # Factory startup may preload linked grease-pencil brushes. This new scene
    # uses no such assets; do not let installation-owned libraries enter the blend.
    for collection in (bpy.data.brushes, bpy.data.materials, bpy.data.textures):
        for item in list(collection):
            if item.library is not None or item.users == 0:
                collection.remove(item)
    for library in list(bpy.data.libraries):
        bpy.data.libraries.remove(library)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, config["frame_count"]
    scene.render.fps, scene.render.fps_base = 24, 1
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.film_transparent = False
    scene.use_nodes = False
    scene.view_settings.view_transform = "Standard"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("白模世界")
    scene.world.color = (0.18, 0.18, 0.18)
    if hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = 8
    bpy.context.view_layer.name = "白模唯一层"

    gray = (0.5, 0.5, 0.5, 1)
    mesh("场景-崖沿", "cube", (40, 40, 30), (0, 20, -15), gray)
    mesh("场景-巨树干", "cylinder", (1.5, 1.5, 7), (2.6, 10, 3.5), gray)
    for i, (x, y, z) in enumerate(((2.6, 10, 7), (0.5, 10, 6.8), (4.8, 10.5, 6.8))):
        mesh(f"场景-树冠-{i}", "sphere", (5.5, 5.0, 3), (x, y, z), gray)
    for i, (x, y) in enumerate(config.get("house_locations", ((-7, 17), (-10, 21)))):
        mesh(f"场景-村屋-{i}", "cube", (3.5, 4.5, 3), (x, y, 1.5), gray)
        for side in (-1, 1):
            roof = mesh(
                f"场景-屋顶-{i}-{side}", "cube", (2.2, 4.8, 0.18), (x + side * 0.85, y, 3.45), gray
            )
            roof.rotation_euler.y = side * math.radians(30)
    mesh("场景-浆果树干", "cylinder", (0.04, 0.04, 0.9), (-2.4, 8.7, 0.45), gray)
    mesh("场景-浆果", "sphere", (0.05, 0.05, 0.05), (-2.4, 8.7, 0.925), (0.8, 0.1, 0.1, 1))
    girl = mesh("占位-女孩", "cylinder", (0.28, 0.28, 1.3), (-1, 5.8, 0.14), (0.15, 0.45, 0.9, 1))
    dragon = mesh("占位-幼龙", "cylinder", (0.3, 0.3, 0.35), (-0.7, 6.8, 0.15), (1, 0.4, 0.1, 1))
    tail = mesh("占位-幼龙-方向尾杆", "cylinder", (0.035, 0.035, 0.2), (0, 0, -0.275), dragon.color)
    tail.parent = dragon
    for obj in (girl, dragon):
        obj.rotation_mode = "QUATERNION"
    projection = point_empty("锚点-幼龙-地面投影", (0, 0, 0))
    # Forearm/face details are deliberately absent; this is the torso support location.
    point_empty("锚点-女孩-胸前支撑", (-1, 0.5, 0))

    for index in range(config["frame_count"]):
        t, frame = index / 24, index + 1
        scene.frame_set(frame)
        dragon.location, dragon.rotation_quaternion = dragon_state(config, t)
        girl.location, girl.rotation_quaternion = girl_state(config, t)
        insert_transform(dragon, frame)
        insert_transform(girl, frame)
        projection.location = (dragon.location.x, dragon.location.y, 0)
        projection.keyframe_insert("location", frame=frame)
    scene["blocking_scope"] = (
        "Simple cylinders: space, timing, contact positions and actual cameras only. "
        "No articulated face, hands, legs or wings."
    )
    scene["asset_path_policy"] = (
        "Current work-local materials paths and immutable profile snapshots; "
        "no shared bytes modified."
    )

    camera_rows = []
    for shot in config["shots"]:
        cid = shot["id"]
        data = bpy.data.cameras.new(f"摄影机-{cid}")
        cam = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(cam)
        cam.rotation_mode = "QUATERNION"
        data.lens, data.sensor_width, data.sensor_fit = shot["lens"], 36, "HORIZONTAL"
        data.clip_start, data.clip_end = 0.02, 300
        data.dof.use_dof = False
        marker = scene.timeline_markers.new(cid, frame=shot["start_frame"] + 1)
        marker.camera = cam
        states = []
        for index in range(shot["start_frame"], shot["end_frame"]):
            scene.frame_set(index + 1)
            u = (index - shot["start_frame"]) / max(1, shot["end_frame"] - shot["start_frame"] - 1)
            start, end = Vector(shot["position_start"]), Vector(shot["position_end"])
            authored = Vector(shot["target_start"]).lerp(Vector(shot["target_end"]), u)
            target = camera_target(cid, authored, girl, dragon) if shot["moving"] else authored
            states.append((index, start.lerp(end, u), target))
        if cid == "C22":
            # A fixed spatial master must include the whole loop and the girl at the rim.
            target = Vector((-0.5, -3.0, 2.5))
            states = [(index, position, target) for index, position, _ in states]
        factor = shot.get("distance_factor", 1.0)
        for index, position, target in states:
            scene.frame_set(index + 1)
            cam.location = target + (position - target) * factor
            cam.rotation_quaternion = (target - cam.location).to_track_quat("-Z", "Y")
            if shot["moving"]:
                insert_transform(cam, index + 1)
        camera_rows.append(
            {
                "id": cid,
                "lens": data.lens,
                "moving": shot["moving"],
                "distance_factor": factor,
                "position_first": list(states[0][2] + (states[0][1] - states[0][2]) * factor),
                "position_last": list(states[-1][2] + (states[-1][1] - states[-1][2]) * factor),
                "target_first": list(states[0][2]),
                "target_last": list(states[-1][2]),
            }
        )

    scene.camera = bpy.data.objects["摄影机-C01"]
    scene.frame_set(1)
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = save_checked(bpy, destination, project, validate)
    write_json_new(
        report_path,
        {
            "blend": config["output_blend"],
            "blend_sha256": digest,
            "config_sha256": config_hash,
            "frame_count": 3600,
            "fps": 24,
            "cameras": camera_rows,
            "geometry_scope": "simple cylinders and primitive sets",
            "dynamic_review": "pending",
            "source_documents": config["source_documents"],
        },
        project,
    )
    stills.mkdir(parents=True)
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_shadows = False
    scene.render.resolution_percentage = 25
    for shot in config["shots"]:
        frame = 1 + (shot["start_frame"] + shot["end_frame"] - 1) // 2
        scene.frame_set(frame)
        scene.camera = bpy.data.objects[f"摄影机-{shot['id']}"]
        render_still_new(bpy, stills / f"{shot['id']}-中间帧.png", project)
    print(
        json.dumps(
            {"blend": str(destination), "sha256": digest, "frames": 3600, "cameras": 29},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
