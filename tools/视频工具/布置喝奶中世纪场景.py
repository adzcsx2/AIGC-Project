"""Dress the selected blocking scene without replacing its authored movement."""

import argparse
import hashlib
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from whitebox_saved import (  # noqa: E402
    launch_saved,
    load_saved,
    project_path,
    render_still_new,
    save_new,
)


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def preflight(project, version):
    """Validate the selected source and every destination before scene edits."""
    project = Path(project).resolve()
    if not version.isalnum():
        raise ValueError("版本号必须由字母数字组成")
    destinations = (
        project / f"03-制作/三维工程/龙宝宝喝奶-中世纪引导-版本{version}.blend",
        project / f"05-检查与验收/中世纪引导关键帧-版本{version}",
        project / f"03-制作/中间数据/中世纪引导帧-版本{version}",
    )
    paths = tuple(project_path(project, path) for path in destinations)
    if any(path.exists() or path.is_symlink() for path in destinations):
        raise FileExistsError("已有该版本产物，不覆盖；请换未使用版本")
    if not bpy.data.filepath or bpy.data.is_dirty:
        raise ValueError("请加载已保存且没有未保存修改的白模版本03工程")
    source = project_path(project, bpy.data.filepath, exists=True)
    selected = project_path(project, "03-制作/三维工程/龙宝宝喝奶-动作白模-版本03.blend")
    if source != selected:
        raise ValueError("来源必须是当前作品选定的白模版本03工程")
    scene = bpy.context.scene
    if (
        scene.frame_start != 1
        or scene.frame_end != 281
        or scene.render.fps / scene.render.fps_base != 24
    ):
        raise ValueError("白模版本03必须为24fps、1至281帧，不能套用七帧扩展")
    return source, sha256(source), paths


def mat(name, dark, light, scale=(4, 4, 4), roughness=0.75, strength=0.12):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*light, 1)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.inputs["Roughness"].default_value = roughness
    tex = nodes.new("ShaderNodeTexCoord")
    vector = nodes.new("ShaderNodeVectorMath")
    vector.operation = "MULTIPLY"
    vector.inputs[1].default_value = scale
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 5
    noise.inputs["Detail"].default_value = 4
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.22
    ramp.color_ramp.elements[0].color = (*dark, 1)
    ramp.color_ramp.elements[1].position = 0.78
    ramp.color_ramp.elements[1].color = (*light, 1)
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = 0.025
    links = material.node_tree.links
    for a, b in [
        (tex.outputs["Object"], vector.inputs[0]),
        (vector.outputs[0], noise.inputs["Vector"]),
        (noise.outputs["Fac"], ramp.inputs[0]),
        (ramp.outputs[0], shader.inputs["Base Color"]),
        (noise.outputs["Fac"], bump.inputs["Height"]),
        (bump.outputs[0], shader.inputs["Normal"]),
        (shader.outputs[0], output.inputs["Surface"]),
    ]:
        links.new(a, b)
    return material


def assign(obj, material):
    obj.data.materials.clear()
    obj.data.materials.append(material)


def cube(name, location, size, material, bevel=0.025):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign(obj, material)
    if bevel:
        mod = obj.modifiers.new("磨损圆角", "BEVEL")
        mod.width, mod.segments = bevel, 3
        obj.modifiers.new("平滑法线", "WEIGHTED_NORMAL")
    return obj


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--version", default="01")
    parser.add_argument("--saved-source", type=Path)
    parser.add_argument("--source-sha256")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    project = Path(args.project).resolve()
    if args.saved_source is not None:
        source = project_path(project, args.saved_source, exists=True)
        selected = project_path(project, "03-制作/三维工程/龙宝宝喝奶-动作白模-版本03.blend")
        if source != selected:
            raise ValueError("来源必须是当前作品选定的白模版本03工程")
        load_saved(bpy, source, args.source_sha256)
    source, source_hash, (blend, stills, frames) = preflight(project, args.version)
    if args.saved_source is None:
        print(
            launch_saved(
                bpy.app.binary_path,
                Path(__file__),
                [
                    "--project",
                    project,
                    "--version",
                    args.version,
                    "--saved-source",
                    source,
                    "--source-sha256",
                    source_hash,
                ],
            ),
            flush=True,
        )
        return
    if source != args.saved_source.resolve() or source_hash != args.source_sha256:
        raise ValueError("实际加载工程与请求来源不一致")
    stills.mkdir(parents=True)
    try:
        frames.mkdir(parents=True)
    except OSError:
        stills.rmdir()
        raise
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.samples = 32
    s.cycles.use_denoising = True
    pref = bpy.context.preferences.addons["cycles"].preferences
    pref.compute_device_type = "OPTIX"
    pref.get_devices()
    for device in pref.devices:
        device.use = device.type == "OPTIX"
    s.cycles.device = "GPU"
    s.cycles.denoiser = "OPTIX"
    s.render.resolution_x, s.render.resolution_y = 1024, 576
    s.render.resolution_percentage = 100
    # Widen the selected portrait composition, retaining readable face/bowl contacts.
    s.camera.data.sensor_fit = "HORIZONTAL"
    s.camera.data.lens = 40.5
    s.camera.data.dof.use_dof = False
    s.view_settings.view_transform = "AgX"
    s.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.63, 0.72, 1)
    s.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.22

    wood = mat("旧橡木", (0.035, 0.017, 0.007), (0.17, 0.085, 0.032), (11, 0.3, 8), 0.8, 0.22)
    beam = mat("深色结构木梁", (0.019, 0.009, 0.004), (0.065, 0.028, 0.01), (6, 6, 0.2))
    plaster = mat("石灰抹墙", (0.27, 0.24, 0.19), (0.46, 0.42, 0.34), (2, 2, 2), 0.92, 0.18)
    cloth = mat("亚麻坐垫", (0.17, 0.135, 0.085), (0.28, 0.23, 0.155), (12, 12, 12), 0.95, 0.2)
    pottery = mat(
        "蜂蜜色粗陶碗", (0.16, 0.065, 0.018), (0.31, 0.17, 0.07), (10, 10, 10), 0.38, 0.06
    )
    milk = mat("牛奶材质", (0.78, 0.77, 0.69), (0.9, 0.88, 0.8), (3, 3, 3), 0.22, 0)
    gray = mat("中性灰白幼龙占位", (0.42, 0.42, 0.42), (0.42, 0.42, 0.42), strength=0)
    eyes = mat("深灰眼睛", (0.035, 0.035, 0.035), (0.035, 0.035, 0.035), roughness=0.3, strength=0)
    for obj in list(s.objects):
        if obj.type not in {"MESH", "CURVE"}:
            continue
        name = obj.name
        if name == "地面" or name.startswith("木凳"):
            assign(obj, cloth if name == "木凳-布垫" else wood)
        elif name.startswith("地板接缝"):
            assign(obj, beam)
        elif name == "道具-浅奶碗":
            assign(obj, pottery)
        elif name == "奶面" or name.startswith(("奶渍-", "溅奶-")):
            assign(obj, milk)
        else:
            assign(obj, eyes if name.startswith(("眼球", "鼻孔", "嘴缝")) else gray)

    # One modest timber-framed room; no modern fixtures or additional characters.
    cube("背景-石灰墙", (0, 2.8, 1.8), (10, 0.18, 3.6), plaster)
    cube("左侧-石灰墙", (-3.8, 0, 1.8), (0.18, 5.6, 3.6), plaster)
    for x in (-3.7, -1.8, 0.2, 2.2, 4.2):
        cube(f"背景-立木梁-{x}", (x, 2.66, 1.8), (0.14, 0.18, 3.6), beam)
    for z in (0.25, 1.95, 3.45):
        cube(f"背景-横木梁-{z}", (0, 2.62, z), (8, 0.18, 0.14), beam)
    cube("左侧-踢脚木梁", (-3.67, 0.1, 0.24), (0.17, 5.3, 0.20), beam)
    # A shallow recessed shutter behind the bench provides period-specific detail.
    cube("窗框-暗底", (-2.6, 2.49, 2.30), (1.3, 0.12, 1.1), beam)
    for i in range(6):
        cube(f"木百叶-{i}", (-3.125 + i * 0.21, 2.40, 2.30), (0.19, 0.08, 1.0), wood, 0.008)
    cube("百叶横挡", (-2.6, 2.32, 2.3), (1.24, 0.07, 0.10), beam, 0.01)
    for light in [o for o in s.objects if o.type == "LIGHT"]:
        if light.name == "主光":
            light.location = (-1.8, -3, 4.6)
            light.data.energy, light.data.size = 450, 3.8
            light.data.color = (1, 0.90, 0.75)
        elif light.name == "补光":
            light.data.energy = 85
            light.data.color = (0.72, 0.82, 1)
        else:
            light.data.energy = 100
            light.data.color = (1, 0.87, 0.68)
        light.rotation_euler = (
            (Vector((0, 0, 0.8)) - light.location).to_track_quat("-Z", "Y").to_euler()
        )
    # The API takes integer seconds. Continue the existing lick for seven frames,
    # then remove this service-only tail from the finished result.
    s.frame_set(281)
    head = bpy.data.objects["控制-头部"]
    head_base = head.location.copy()
    t0 = 280 / 24
    tongue = bpy.data.objects["舔奶舌头"]
    for frame in range(282, 289):
        t = (frame - 1) / 24
        head.location = head_base + Vector(
            (
                0,
                0,
                0.006 * (math.sin(t * 2 * math.pi * 3.8) - math.sin(t0 * 2 * math.pi * 3.8)),
            )
        )
        head.keyframe_insert("location", frame=frame)
        lick = max(0, math.sin(t * 2 * math.pi * 3.8))
        tongue.location = (0, -0.34 - 0.065 * lick, -0.12)
        tongue.scale = (0.045, 0.025 + 0.06 * lick, 0.014)
        tongue.keyframe_insert("location", frame=frame)
        tongue.keyframe_insert("scale", frame=frame)
    s.frame_end = 288
    s.frame_set(1)
    s["用途"] = "保持白模版本03动作，添加中世纪置景；新增末7帧只供整秒接口，成片去除。"
    s["来源工程"] = str(source)
    s["来源工程SHA256"] = source_hash
    s["来源帧率"] = 24
    s["来源帧范围"] = [1, 281]
    s.render.filepath = str(frames / "帧-")
    s.render.use_overwrite = False
    if sha256(source) != source_hash:
        raise ValueError("制作期间源工程已变化，不保存派生工程")
    save_new(bpy, blend, project)
    for frame in (1, 126, 148, 190, 281):
        s.frame_set(frame)
        render_still_new(bpy, stills / f"关键帧-{frame:04}.png", project)


if __name__ == "__main__":
    main()
