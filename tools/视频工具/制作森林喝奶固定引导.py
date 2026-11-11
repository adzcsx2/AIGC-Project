"""Dress the existing drink blocking for a fixed-camera forest plate.

Run in Blender; preserve source animation and save new versioned artifacts.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from whitebox_saved import (  # noqa: E402
    launch_saved,
    load_saved,
    project_path,
    render_still_new,
    save_new,
    sha,
    write_json_new,
)

KEY_FRAMES = (1, 126, 148, 190, 281)


def preflight(project, stage, version, plate=None):
    """Resolve every input/output before touching scene state or creating files."""
    project = Path(project).resolve()
    if not isinstance(version, str) or not version.isalnum():
        raise ValueError("非法版本号")
    if stage == "prepare":
        source = "03-制作/三维工程/龙宝宝喝奶-动作白模-版本03.blend"
        destination = f"03-制作/三维工程/龙宝宝喝奶-森林固定机位-版本{version}.blend"
        stills = f"05-检查与验收/森林固定机位-布局{version}"
        names = [f"固定机位-{frame:04}.png" for frame in KEY_FRAMES]
        names.append("森林底图-几何布局.png")
    elif stage == "finish":
        source = f"03-制作/三维工程/龙宝宝喝奶-森林固定机位-版本{version}.blend"
        destination = f"03-制作/三维工程/龙宝宝喝奶-森林固定机位-送模{version}.blend"
        stills = f"05-检查与验收/森林固定机位-合成{version}"
        names = [f"合成-{frame:04}.png" for frame in KEY_FRAMES]
    else:
        raise ValueError("未知制作阶段")
    paths = {
        "project": project,
        "source": project_path(project, source, exists=True),
        "destination": project_path(project, destination),
        "stills": project_path(project, stills),
        "record": project_path(project, Path(stills) / "制作测量.json"),
        "images": [project_path(project, Path(stills) / name) for name in names],
    }
    outputs = [paths["destination"], paths["stills"], paths["record"], *paths["images"]]
    if stage == "finish":
        if plate is None:
            raise ValueError("合成阶段需要本作品底图")
        paths["plate"] = project_path(project, plate, exists=True)
        paths["frames"] = project_path(project, f"03-制作/中间数据/森林固定机位-送模帧{version}")
        outputs.append(paths["frames"])
    if any(path.exists() or path.is_symlink() for path in outputs):
        raise FileExistsError("新版本路径已存在，拒绝覆盖")
    return paths


def check_inputs(paths, source_hash, plate_hash=None):
    if sha(paths["source"]) != source_hash:
        raise ValueError("源工程发生变化")
    if "plate" in paths and sha(paths["plate"]) != plate_hash:
        raise ValueError("森林底图发生变化")


def dispatch(project, stage, version, plate=None):
    paths = preflight(project, stage, version, plate)
    if not bpy.data.filepath or bpy.data.is_dirty:
        raise ValueError("请先保存来源工程；不会丢弃调用方的未保存修改")
    if Path(bpy.data.filepath).resolve() != paths["source"]:
        raise ValueError("必须加载当前作品所选来源工程")
    args = [
        "--project",
        Path(project).resolve(),
        "--stage",
        stage,
        "--version",
        version,
        "--saved-source",
        paths["source"],
        "--source-sha256",
        sha(paths["source"]),
    ]
    if stage == "finish":
        args += ["--plate", paths["plate"], "--plate-sha256", sha(paths["plate"])]
    print(launch_saved(bpy.app.binary_path, Path(__file__), args), flush=True)
    return paths["destination"]


def prepare(project, version):
    return dispatch(project, "prepare", version)


def finish(project, plate, version):
    return dispatch(project, "finish", version, plate)


def write_record(path, record, project):
    write_json_new(path, record, project)


def material(name, color, roughness=0.8):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    s = m.node_tree.nodes.get("Principled BSDF")
    s.inputs["Base Color"].default_value = (*color, 1)
    s.inputs["Roughness"].default_value = roughness
    return m


def assign(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def points_for(objects, deps):
    for obj in objects:
        ev = obj.evaluated_get(deps)
        corners = ev.bound_box
        if obj.type == "CURVE":
            mesh = ev.to_mesh()
            lo = [min(v.co[k] for v in mesh.vertices) for k in range(3)]
            hi = [max(v.co[k] for v in mesh.vertices) for k in range(3)]
            corners = [
                (x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])
            ]
            ev.to_mesh_clear()
        for co in corners:
            yield ev.matrix_world @ Vector(co)


def setup_render(scene):
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    pref = bpy.context.preferences.addons["cycles"].preferences
    pref.compute_device_type = "OPTIX"
    pref.get_devices()
    for dev in pref.devices:
        dev.use = dev.type == "OPTIX"
    scene.cycles.device = "GPU"
    scene.cycles.denoiser = "OPTIX"
    scene.render.resolution_x, scene.render.resolution_y = 1024, 576
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.use_overwrite = False
    scene.view_settings.view_transform = "AgX"


def prepare_saved(paths, source_hash):
    src, dest, stilldir = (paths[key] for key in ("source", "destination", "stills"))
    scene = bpy.context.scene
    if (
        scene.frame_start != 1
        or scene.frame_end != 281
        or scene.render.fps / scene.render.fps_base != 24
    ):
        raise ValueError("来源时间轴异常")
    scene.frame_set(1)
    setup_render(scene)
    cam = scene.camera
    old_positions = []
    for frame in range(1, 282):
        scene.frame_set(frame)
        old_positions.append(list(cam.matrix_world.translation))
    scene.frame_set(1)
    cam.animation_data_clear()
    cam.data.animation_data_clear()
    cam.parent = None
    for con in list(cam.constraints):
        cam.constraints.remove(con)
    cam.rotation_mode = "QUATERNION"
    cam.data.dof.use_dof = False
    cam.data.sensor_fit = "HORIZONTAL"

    env = []
    for obj in list(scene.objects):
        if obj.name.startswith(("木凳", "地板接缝")):
            bpy.data.objects.remove(obj, do_unlink=True)
    ground = bpy.data.objects["地面"]
    assign(ground, material("森林地面代理", (0.23, 0.23, 0.23)))
    env.append(ground)
    # A single weathered stump replaces the support without moving the paws.
    verts = []
    faces = []
    rings = [(0, 0.90), (0.15, 0.78), (1.5, 0.71), (1.64, 0.71)]
    n = 64
    for z, r in rings:
        for i in range(n):
            a = i * 2 * math.pi / n
            ripple = 1 + 0.012 * math.sin(7 * a) + 0.009 * math.sin(13 * a)
            verts.append(
                (-0.96 + r * ripple * math.cos(a), 0.24 + r * 1.08 * ripple * math.sin(a), z - 0.01)
            )
    for j in range(len(rings) - 1):
        for i in range(n):
            faces.append(
                (j * n + i, j * n + (i + 1) % n, (j + 1) * n + (i + 1) % n, (j + 1) * n + i)
            )
    faces.append(tuple(range((len(rings) - 1) * n, len(rings) * n)))
    mesh = bpy.data.meshes.new("单木桩网格")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    stump = bpy.data.objects.new("森林-唯一旧木桩", mesh)
    scene.collection.objects.link(stump)
    assign(stump, material("木桩轮廓代理", (0.40, 0.40, 0.40)))
    bevel = stump.modifiers.new("边沿轻微磨损", "BEVEL")
    bevel.width = 0.012
    bevel.segments = 2
    env.append(stump)

    dragon = []
    other = []
    neutral = material("统一灰白幼龙", (0.55, 0.55, 0.55))
    eyes = material("眼部中灰", (0.16, 0.16, 0.16), 0.5)
    milk = material("自然牛奶", (0.88, 0.86, 0.79), 0.25)
    bowl = material("粗陶碗", (0.28, 0.13, 0.05), 0.72)
    for obj in scene.objects:
        if obj.type not in {"MESH", "CURVE"} or obj in env:
            continue
        if obj.name == "道具-浅奶碗":
            assign(obj, bowl)
            other.append(obj)
        elif obj.name == "奶面" or obj.name.startswith(("奶渍-", "溅奶-")):
            assign(obj, milk)
            other.append(obj)
        else:
            assign(obj, eyes if obj.name.startswith(("眼球", "鼻孔", "嘴缝")) else neutral)
            dragon.append(obj)

    # Use the entire action envelope once; the camera never follows the actor.
    envelope = []
    for frame in range(1, 282):
        scene.frame_set(frame)
        envelope.extend(
            points_for(
                dragon + [bpy.data.objects["道具-浅奶碗"]], bpy.context.evaluated_depsgraph_get()
            )
        )
    low = Vector(tuple(min(p[k] for p in envelope) for k in range(3)))
    high = Vector(tuple(max(p[k] for p in envelope) for k in range(3)))
    center = (low + high) / 2
    cam.location = center + Vector((2.5, -5.7, 2.0))
    cam.rotation_quaternion = (center - cam.location).to_track_quat("-Z", "Y")
    cam.data.lens = 50
    scene.frame_set(1)
    bpy.context.view_layer.update()
    while True:
        coords = [world_to_camera_view(scene, cam, p) for p in envelope]
        bounds = [
            min(c.x for c in coords),
            max(c.x for c in coords),
            min(c.y for c in coords),
            max(c.y for c in coords),
        ]
        if bounds[0] >= 0.065 and bounds[1] <= 0.935 and bounds[2] >= 0.065 and bounds[3] <= 0.935:
            break
        cam.data.lens -= 0.5
        if cam.data.lens < 20:
            raise ValueError("无法在合理焦距内容纳全部动作")

    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.66, 0.72, 0.78, 1)
    bg.inputs["Strength"].default_value = 0.35
    for light in [o for o in scene.objects if o.type == "LIGHT"]:
        if light.name == "主光":
            light.location = (-3, -4, 6)
            light.data.energy = 550
            light.data.size = 5
            light.data.color = (1, 0.96, 0.90)
        elif light.name == "补光":
            light.data.energy = 80
            light.data.color = (0.76, 0.86, 1)
        else:
            light.data.energy = 65
            light.data.color = (0.85, 0.94, 0.83)
        light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
    # Continue only the pre-existing lick through the service-only fractional tail.
    scene.frame_set(281)
    head = bpy.data.objects["控制-头部"]
    base = head.location.copy()
    tongue = bpy.data.objects["舔奶舌头"]
    t0 = 280 / 24
    for frame in range(282, 289):
        t = (frame - 1) / 24
        head.location = base + Vector(
            (0, 0, 0.006 * (math.sin(t * 2 * math.pi * 3.8) - math.sin(t0 * 2 * math.pi * 3.8)))
        )
        head.keyframe_insert("location", frame=frame)
        lick = max(0, math.sin(t * 2 * math.pi * 3.8))
        tongue.location = (0, -0.34 - 0.065 * lick, -0.12)
        tongue.scale = (0.045, 0.025 + 0.06 * lick, 0.014)
        tongue.keyframe_insert("location", frame=frame)
        tongue.keyframe_insert("scale", frame=frame)
    scene.frame_end = 288
    scene.frame_set(1)
    scene["来源工程SHA256"] = source_hash
    scene["摄影机策略"] = "用户要求固定机位；无摄影机/镜头动画、约束、父级；主体动作保留。"
    scene["角色对象"] = json.dumps([o.name for o in dragon], ensure_ascii=False)
    scene["环境代理"] = json.dumps([o.name for o in env], ensure_ascii=False)
    stilldir.mkdir(parents=True, exist_ok=False)
    check_inputs(paths, source_hash)
    save_new(bpy, dest, paths["project"])
    for frame in KEY_FRAMES:
        scene.frame_set(frame)
        render_still_new(bpy, stilldir / f"固定机位-{frame:04}.png", paths["project"])
    scene.frame_set(1)
    for o in dragon + other:
        o.hide_render = True
    render_still_new(bpy, stilldir / "森林底图-几何布局.png", paths["project"])
    report = {
        "source": str(src),
        "source_sha256": source_hash,
        "blend": str(dest),
        "blend_sha256": sha(dest),
        "camera": cam.name,
        "camera_location": list(cam.location),
        "lens": cam.data.lens,
        "action_envelope_bounds": bounds,
        "original_camera_vertical_range": [
            min(p[2] for p in old_positions),
            max(p[2] for p in old_positions),
        ],
        "dragon_objects": [o.name for o in dragon],
        "frame_count": 288,
        "fps": 24,
        "source_action_frames": 281,
    }
    check_inputs(paths, source_hash)
    write_record(paths["record"], report, paths["project"])


def finish_saved(paths, source_hash, plate_hash):
    src, dest, frames, stills, plate = (
        paths[key] for key in ("source", "destination", "frames", "stills", "plate")
    )
    scene = bpy.context.scene
    if (
        scene.frame_start != 1
        or scene.frame_end != 288
        or scene.render.fps / scene.render.fps_base != 24
    ):
        raise ValueError("来源时间轴异常")
    for name in json.loads(scene["环境代理"]):
        bpy.data.objects[name].is_shadow_catcher = True
    scene.render.film_transparent = True
    scene.use_nodes = True
    # Blender 5 supports compositor node groups through compositing_node_group.
    tree = getattr(scene, "compositing_node_group", None)
    if tree is None:
        tree = bpy.data.node_groups.new("森林底图合成", "CompositorNodeTree")
        scene.compositing_node_group = tree
    tree.nodes.clear()
    tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    render = tree.nodes.new("CompositorNodeRLayers")
    plate_node = tree.nodes.new("CompositorNodeImage")
    plate_node.image = bpy.data.images.load(str(plate), check_existing=True)
    plate_node.image.pack()
    scale = tree.nodes.new("CompositorNodeScale")
    scale.inputs["Type"].default_value = "Relative"
    scale.inputs["X"].default_value = scene.render.resolution_x / plate_node.image.size[0]
    scale.inputs["Y"].default_value = scene.render.resolution_y / plate_node.image.size[1]
    over = tree.nodes.new("CompositorNodeAlphaOver")
    over.inputs["Factor"].default_value = 1
    out = tree.nodes.new("NodeGroupOutput")
    tree.links.new(plate_node.outputs["Image"], scale.inputs["Image"])
    tree.links.new(scale.outputs["Image"], over.inputs["Background"])
    tree.links.new(render.outputs["Image"], over.inputs["Foreground"])
    tree.links.new(over.outputs["Image"], out.inputs[0])
    # The photograph is already display referred; avoid a second AgX tone curve.
    scene.view_settings.view_transform = "Standard"
    scene["森林底图"] = str(plate)
    scene["森林底图SHA256"] = plate_hash
    scene["合成来源工程"] = str(src)
    scene["合成来源工程SHA256"] = source_hash
    frames.mkdir(parents=True, exist_ok=False)
    stills.mkdir(parents=True, exist_ok=False)
    scene.render.filepath = str(frames / "帧-")
    scene.frame_set(1)
    check_inputs(paths, source_hash, plate_hash)
    save_new(bpy, dest, paths["project"])
    for frame in KEY_FRAMES:
        scene.frame_set(frame)
        render_still_new(bpy, stills / f"合成-{frame:04}.png", paths["project"])
    check_inputs(paths, source_hash, plate_hash)
    write_record(
        paths["record"],
        {
            "source": str(src),
            "source_sha256": source_hash,
            "plate": str(plate),
            "plate_sha256": plate_hash,
            "blend": str(dest),
            "blend_sha256": sha(dest),
            "frame_count": 288,
            "fps": 24,
        },
        paths["project"],
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--stage", choices=["prepare", "finish"], required=True)
    p.add_argument("--plate")
    p.add_argument("--version", default="02")
    p.add_argument("--saved-source", type=Path)
    p.add_argument("--source-sha256")
    p.add_argument("--plate-sha256")
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    project = Path(args.project).resolve()
    plate = Path(args.plate) if args.plate is not None else None
    if args.saved_source is not None:
        paths = preflight(project, args.stage, args.version, plate)
        if args.saved_source.resolve() != paths["source"]:
            raise ValueError("实际来源与当前作品所选工程不一致")
        check_inputs(paths, args.source_sha256, args.plate_sha256)
        load_saved(bpy, paths["source"], args.source_sha256)
        if args.stage == "prepare":
            prepare_saved(paths, args.source_sha256)
        else:
            finish_saved(paths, args.source_sha256, args.plate_sha256)
    else:
        dispatch(project, args.stage, args.version, plate)


if __name__ == "__main__":
    main()
