"""Project a photographed forest onto an independently loaded saved whitebox.

All shots share one optical center; fixed-angle/lens cuts use the same projective
texture without moving the scene. The source blend is never modified.
"""

import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import (
    read_json_bound,
    require_hash,
    require_sequence_binding,
    save_checked,
    sequence_binding,
)
from whitebox_saved import load_saved, project_path, render_still_new, sha, write_json_new


def projection_material(name, image, camera, width, height, diffuse=0.0, vscale=1.0, voffset=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    n = mat.node_tree.nodes
    links = mat.node_tree.links
    n.clear()
    tc = n.new("ShaderNodeTexCoord")
    tc.object = camera
    xyz = n.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], xyz.inputs[0])

    def calc(operation, first, second):
        o = n.new("ShaderNodeMath")
        o.operation = operation
        if hasattr(first, "bl_rna"):
            links.new(first, o.inputs[0])
        else:
            o.inputs[0].default_value = first
        if hasattr(second, "bl_rna"):
            links.new(second, o.inputs[1])
        else:
            o.inputs[1].default_value = second
        return o.outputs[0]

    f = camera.data.lens / camera.data.sensor_width
    u = calc("ADD", calc("MULTIPLY", calc("DIVIDE", xyz.outputs["X"], xyz.outputs["Z"]), -f), 0.5)
    v = calc(
        "ADD",
        calc("MULTIPLY", calc("DIVIDE", xyz.outputs["Y"], xyz.outputs["Z"]), -f * width / height),
        0.5,
    )
    if vscale != 1 or voffset != 0:
        v = calc("ADD", calc("MULTIPLY", v, vscale), voffset)
    comb = n.new("ShaderNodeCombineXYZ")
    links.new(u, comb.inputs["X"])
    links.new(v, comb.inputs["Y"])
    tex = n.new("ShaderNodeTexImage")
    tex.image = image
    tex.extension = "EXTEND"
    tex.interpolation = "Linear"
    links.new(comb.outputs[0], tex.inputs["Vector"])
    em = n.new("ShaderNodeEmission")
    links.new(tex.outputs["Color"], em.inputs["Color"])
    out = n.new("ShaderNodeOutputMaterial")
    if diffuse:
        d = n.new("ShaderNodeBsdfDiffuse")
        d.inputs["Roughness"].default_value = 0.8
        links.new(tex.outputs["Color"], d.inputs["Color"])
        mix = n.new("ShaderNodeMixShader")
        mix.inputs[0].default_value = diffuse
        links.new(em.outputs[0], mix.inputs[1])
        links.new(d.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], out.inputs["Surface"])
    else:
        links.new(em.outputs[0], out.inputs["Surface"])
    return mat


def configure_gpu(scene):
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 8
    scene.cycles.use_denoising = True
    scene.render.use_persistent_data = True
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "OPTIX"
    scene.cycles.device = "GPU" if any(d.use for d in prefs.devices) else "CPU"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--plate", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=768)
    ap.add_argument("--engine", choices=["CYCLES", "BLENDER_EEVEE"], default="CYCLES")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    p = Path(args.project).resolve()
    source = project_path(p, args.source, exists=True)
    plate = project_path(p, args.plate, exists=True)
    out = project_path(p, f"03-制作/三维工程/龙宝宝-睡醒舔奶-森林引导{args.version}.blend")
    record = project_path(p, f"05-检查与验收/睡醒舔奶-森林引导{args.version}.json")
    stilldir = project_path(p, f"05-检查与验收/睡醒舔奶-森林布局{args.version}")
    frames = project_path(p, f"03-制作/中间数据/睡醒舔奶-森林序列{args.version}")
    if not args.render:
        for q in (out, record, stilldir, frames):
            if q.exists():
                raise FileExistsError(str(q))
        before = sha(source)
        platehash = sha(plate)
        scene = load_saved(bpy, source, before)
        image = bpy.data.images.load(str(plate), check_existing=False)
        image.pack()
        camera = bpy.data.objects["摄影机-A全身固定"]
        ground = projection_material("森林地面投影", image, camera, 1024, 576, 0.55)
        bark = projection_material("旧桩树皮投影", image, camera, 1024, 576, 0.20, 0.9167, 0.015)
        top = projection_material("旧桩顶投影校准", image, camera, 1024, 576, 0.22, 0.8125, 0.05875)
        background = projection_material("森林背景投影", image, camera, 1024, 576, 0)
        for o in scene.objects:
            if not o.name.startswith("环境-") or not hasattr(o.data, "materials"):
                continue
            o.data.materials.clear()
            o.data.materials.append(
                ground
                if o.name == "环境-地面"
                else bark
                if o.name == "环境-矮宽旧木桩"
                else background
            )
            if o.name == "环境-矮宽旧木桩":
                o.data.materials.append(top)
                for poly in o.data.polygons:
                    if poly.normal.z > 0.8:
                        poly.material_index = 1
        # A distant plane fills openings between projected trunks; it is static.
        q = camera.rotation_euler.to_quaternion()
        forward = q @ Vector((0, 0, -1))
        bpy.ops.mesh.primitive_plane_add(size=2, location=camera.location + forward * 30)
        bg = bpy.context.object
        bg.name = "环境-森林远景底片"
        bg.rotation_euler = camera.rotation_euler
        bg.scale = (30 * 36 / 43 * 0.70, 30 * 36 / 43 * 576 / 1024 * 0.70, 1)
        bg.data.materials.append(background)
        bg.is_shadow_catcher = False
        bg.is_holdout = False
        for prop in ("visible_shadow", "visible_glossy", "visible_diffuse"):
            if hasattr(bg, prop):
                setattr(bg, prop, False)
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        for o in scene.objects:
            if o.type == "LIGHT":
                o.data.energy *= 0.30
        scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.30
        for name in ("龙宝宝灰模", "腹部浅灰", "翼膜中灰", "舌体灰"):
            mat = bpy.data.materials.get(name)
            if mat:
                bs = mat.node_tree.nodes.get("Principled BSDF")
                col = bs.inputs["Base Color"].default_value
                bs.inputs["Base Color"].default_value = tuple(v * 0.65 for v in col[:3]) + (1,)
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = False
        configure_gpu(scene)
        scene.render.engine = args.engine
        if args.engine == "BLENDER_EEVEE" and hasattr(
            getattr(scene, "eevee", None), "taa_render_samples"
        ):
            scene.eevee.taa_render_samples = 32
        out.parent.mkdir(parents=True, exist_ok=True)
        stilldir.mkdir(parents=True)
        frames.mkdir(parents=True)

        def validate_inputs():
            require_hash(source, before)
            require_hash(plate, platehash)

        output_hash = save_checked(bpy, out, p, validate_inputs)
        binding = sequence_binding(scene, out, output_hash, frames, p)
        write_json_new(
            record,
            {
                "source": str(source.relative_to(p)),
                "source_sha256": before,
                "plate": str(plate.relative_to(p)),
                "plate_sha256": platehash,
                "blend": str(out.relative_to(p)),
                "sha256": output_hash,
                "sequence": binding,
                "mapping": (
                    "Same optical center. Projected textures; stump top and bark vertical UV "
                    "calibrated to the fixed gray geometry. Geometry and animation preserved."
                ),
                "dynamic_review": "pending",
            },
            p,
        )
        write_json_new(frames / "序列绑定.json", binding, p)
        for f in [1, 150, 279, 365, 413, 503, 695, 754]:
            scene.frame_set(f)
            render_still_new(bpy, stilldir / f"帧{f:04d}.png", p)
    else:
        evidence, record_hash = read_json_bound(project_path(p, record, exists=True))
        if evidence.get("blend") != str(out.relative_to(p)):
            raise ValueError("记录不属于当前工程")
        output_hash = evidence["sha256"]
        scene = load_saved(bpy, out, output_hash)
        configure_gpu(scene)
        scene.render.engine = args.engine
        if args.engine == "BLENDER_EEVEE" and hasattr(
            getattr(scene, "eevee", None), "taa_render_samples"
        ):
            scene.eevee.taa_render_samples = 32
        binding = sequence_binding(scene, out, output_hash, frames, p)
        require_sequence_binding(evidence, binding)
        sequence_record = project_path(p, frames / "序列绑定.json", exists=True)
        sequence, sequence_hash = read_json_bound(sequence_record)
        if sequence != binding:
            raise ValueError("现有序列不属于当前工程和渲染规格")
        if not scene.frame_start <= args.start <= args.end <= scene.frame_end:
            raise ValueError("渲染范围超出已绑定时间轴")

        def validate_frame():
            require_hash(out, output_hash)
            require_hash(record, record_hash)
            require_hash(sequence_record, sequence_hash)
            if sequence_binding(scene, out, output_hash, frames, p) != binding:
                raise ValueError("渲染规格在处理期间变化")

        for f in range(args.start, args.end + 1):
            dest = project_path(p, frames / f"帧{f:04d}.png")
            if dest.exists():
                raise FileExistsError(str(dest))
            validate_frame()
            scene.frame_set(f)
            render_still_new(bpy, dest, p, validate_render=validate_frame)
    print("forest guide stage complete")


if __name__ == "__main__":
    main()
