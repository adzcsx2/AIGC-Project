"""Author an editable two-character blocking scene from a project-owned timeline.

Run in factory-startup background Blender. This is authored reconstruction,
not automatic motion capture. Output versions are never overwritten.
"""

import argparse
import bisect
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import read_json_bound, require_hash, save_checked
from whitebox_saved import (
    project_path,
    render_still_new,
    require_self_contained,
    sha,
    write_json_new,
)

Z = Vector((0, 0, 1))


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def sample(keys, t, cubic=True):
    if t <= keys[0][0]:
        return Vector(keys[0][1:])
    if t >= keys[-1][0]:
        return Vector(keys[-1][1:])
    k = bisect.bisect_right([x[0] for x in keys], t) - 1
    a, b = keys[k], keys[k + 1]
    u = (t - a[0]) / (b[0] - a[0])
    if not cubic:
        return Vector(a[1:]).lerp(Vector(b[1:]), smooth(u))
    before, after = keys[max(k - 1, 0)], keys[min(k + 2, len(keys) - 1)]
    dt = b[0] - a[0]
    m0 = (Vector(b[1:]) - Vector(before[1:])) / max(b[0] - before[0], 1e-6) * dt
    m1 = (Vector(after[1:]) - Vector(a[1:])) / max(after[0] - a[0], 1e-6) * dt
    return (
        (2 * u**3 - 3 * u * u + 1) * Vector(a[1:])
        + (u**3 - 2 * u * u + u) * m0
        + (-2 * u**3 + 3 * u * u) * Vector(b[1:])
        + (u**3 - u * u) * m1
    )


def basis(forward, up=Z):
    f = Vector(forward).normalized()
    r = f.cross(Vector(up)).normalized()
    return Matrix((r, f, r.cross(f))).transposed().to_quaternion()


def empty(name, parent=None):
    o = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(o)
    o.parent = parent
    o.rotation_mode = "QUATERNION"
    return o


def material(name, color):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    node = m.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value = (*color, 1)
    node.inputs["Roughness"].default_value = 0.85
    return m


def sphere(name, scale, mat, parent=None, location=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10)
    o = bpy.context.object
    o.name, o.parent = name, parent
    o.location, o.scale = location, scale
    o.data.materials.append(mat)
    o.color = mat.diffuse_color
    for p in o.data.polygons:
        p.use_smooth = True
    o.rotation_mode = "QUATERNION"
    return o


def mesh(name, verts, faces, mat, parent=None):
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts, [], faces)
    data.update()
    o = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(o)
    o.parent = parent
    data.materials.append(mat)
    o.color = mat.diffuse_color
    return o


def tube(name, pts, radii, mat, parent=None):
    c = bpy.data.curves.new(name, "CURVE")
    c.dimensions, c.resolution_u, c.bevel_resolution = "3D", 4, 2
    c.bevel_depth = 1
    s = c.splines.new("BEZIER")
    s.bezier_points.add(len(pts) - 1)
    for p, v, r in zip(s.bezier_points, pts, radii, strict=True):
        p.co, p.radius = v, r
        p.handle_left_type = p.handle_right_type = "AUTO"
    o = bpy.data.objects.new(name, c)
    bpy.context.collection.objects.link(o)
    o.parent = parent
    c.materials.append(mat)
    o.color = mat.diffuse_color
    return o, s


def pose(o, loc, q=None, scale=None, frame=None):
    o.location = loc
    if q is not None:
        o.rotation_mode = "QUATERNION"
        o.rotation_quaternion = q
    if scale is not None:
        o.scale = scale
    if frame is not None:
        o.keyframe_insert("location", frame=frame)
        if q is not None:
            o.keyframe_insert("rotation_quaternion", frame=frame)
        if scale is not None:
            o.keyframe_insert("scale", frame=frame)


def segment(o, a, b, radius, frame):
    a, b = Vector(a), Vector(b)
    d = b - a
    pose(
        o,
        (a + b) / 2,
        d.to_track_quat("Z", "Y"),
        (radius, radius, d.length / 2 + radius * 0.3),
        frame,
    )


def joint(a, b, bend, length):
    d = Vector(b) - Vector(a)
    axis = d.normalized()
    bend = Vector(bend) - axis * Vector(bend).dot(axis)
    if bend.length < 1e-5:
        bend = axis.cross(Vector((1, 0, 0)))
    h = math.sqrt(max(0.0001, length**2 - (d.length / 2) ** 2))
    return (Vector(a) + Vector(b)) / 2 + bend.normalized() * h


def build_set(c):
    env = material("场景-石膏灰", (0.53, 0.53, 0.53))
    bark = material("树干-灰", (0.34, 0.34, 0.34))
    leaf = material("树冠-浅灰", (0.48, 0.48, 0.48))
    bpy.ops.mesh.primitive_plane_add(size=32)
    bpy.context.object.name = "地面"
    bpy.context.object.data.materials.append(env)
    bpy.context.object.color = env.diffuse_color
    radius = c["tree_radius"]
    verts, faces, n = [], [], 32
    rings = [
        (0, radius * 1.09, 0, 0),
        (0.25, radius * 1.02, 0, 0),
        (1.2, radius, 0.03, 0),
        (2.3, radius * 0.88, 0.1, 0.06),
        (3.8, radius * 0.64, 0.24, 0.1),
        (5.6, 0.20, 0.35, 0.12),
    ]
    for z, r, x, y in rings:
        for i in range(n):
            a = i * 2 * math.pi / n
            rr = r * (1 + 0.025 * math.sin(5 * a + z) + 0.018 * math.sin(11 * a - z))
            verts.append((x + rr * math.cos(a), y + rr * math.sin(a), z))
    for j in range(len(rings) - 1):
        for i in range(n):
            a = j * n + i
            b = j * n + (i + 1) % n
            faces.append((a, b, b + n, a + n))
    trunk = mesh("巨树-主干", verts, faces, bark)
    for p in trunk.data.polygons:
        p.use_smooth = True
    random.seed(17)
    for i in range(6):
        a = i * 1.08 + 0.25
        start = Vector((0.1, 0.05, 2.5 + (i % 3) * 0.55))
        d = Vector((math.cos(a), math.sin(a), 0.65))
        tube(
            f"巨树-枝{i}",
            [start, start + d * 1.3, start + d * 2.4 + Z * 0.8],
            [0.20, 0.13, 0.045],
            bark,
        )
        sphere(f"巨树-冠{i}", (1.3, 1.1, 0.6), leaf, location=start + d * 2.8 + Z * 0.8)
    for i, a in enumerate((0.6, 1.1, 1.7, 2.3)):
        tube(
            f"巨树-侧后根{i}",
            [
                (radius * 0.8 * math.cos(a), radius * 0.8 * math.sin(a), 0.1),
                (1.0 * math.cos(a), 1.0 * math.sin(a), 0.04),
                (1.3 * math.cos(a), 1.3 * math.sin(a), -0.04),
            ],
            [0.09, 0.05, 0.01],
            bark,
        )
    for i, (x, y, w, h) in enumerate(((-4.5, 3.8, 1.5, 1.6), (-2.5, 5.5, 1.6, 1.7))):
        vs = [
            (x + sx * w / 2, y + sy * w / 2, z) for z in (0, h) for sy in (-1, 1) for sx in (-1, 1)
        ]
        mesh(
            f"村屋{i}-墙",
            vs,
            [(0, 1, 3, 2), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3), (4, 6, 7, 5)],
            env,
        )
        mesh(
            f"村屋{i}-屋顶",
            [
                (x - w * 0.58, y - w * 0.58, h),
                (x + w * 0.58, y - w * 0.58, h),
                (x, y - w * 0.58, h + 0.75),
                (x - w * 0.58, y + w * 0.58, h),
                (x + w * 0.58, y + w * 0.58, h),
                (x, y + w * 0.58, h + 0.75),
            ],
            [(0, 1, 2), (3, 5, 4), (0, 2, 5, 3), (2, 1, 4, 5)],
            bark,
        )
    for i in range(8):
        x = -5 + i * 1.5
        y = 5 + (i % 3)
        tube(
            f"远林树{i}",
            [(x, y, 0), (x + 0.1, y, 2.3), (x + 0.25, y, 4.5)],
            [0.12, 0.09, 0.035],
            bark,
        )
    return trunk


def build_girl():
    root = empty("女孩-主体")
    clay = material("女孩-白模", (0.72, 0.72, 0.72))
    cloth = material("披风-白模", (0.42, 0.42, 0.42))
    dark = material("面部细节", (0.13, 0.13, 0.13))
    hair = material("发辫-白模", (0.30, 0.30, 0.30))
    g = {"root": root}
    for name, sc in [
        ("pelvis", (0.14, 0.10, 0.13)),
        ("torso", (0.155, 0.105, 0.21)),
        ("neck", (0.045, 0.045, 0.06)),
    ]:
        g[name] = sphere("女孩-" + name, sc, clay, root)
    g["head"] = empty("女孩-头部控制", root)
    sphere("女孩-头", (0.115, 0.103, 0.145), clay, g["head"])
    sphere("女孩-鼻", (0.022, 0.025, 0.029), clay, g["head"], (0, 0.101, 0.005))
    sphere("女孩-头发", (0.119, 0.106, 0.095), hair, g["head"], (0, -0.012, 0.085))
    for side in (-1, 1):
        sphere(
            f"女孩-眼{side}", (0.016, 0.009, 0.013), dark, g["head"], (side * 0.043, 0.096, 0.035)
        )
        sphere(f"女孩-耳{side}", (0.02, 0.018, 0.035), clay, g["head"], (side * 0.115, 0, 0.005))
    tube(
        "女孩-微笑",
        [(-0.031, 0.100, -0.047), (0, 0.111, -0.053), (0.031, 0.100, -0.047)],
        [0.004] * 3,
        dark,
        g["head"],
    )
    for i in range(7):
        sphere(
            f"女孩-发辫{i}",
            (0.027 - i * 0.002, 0.025 - i * 0.0015, 0.030),
            hair,
            g["head"],
            (0.008 * math.sin(i * 2), -0.108 - i * 0.006, -0.035 - i * 0.035),
        )
    g["cloak"] = empty("女孩-披风控制", root)
    vs = []
    fs = []
    count = 16
    for row in range(4):
        z = -row * 0.20
        rx = 0.17 + row * 0.045
        ry = 0.105 + row * 0.04
        for i in range(count):
            a = math.radians(60) + math.radians(240) * i / (count - 1)
            vs.append((rx * math.sin(a), ry * math.cos(a), z))
    for row in range(3):
        for i in range(count - 1):
            a = row * count + i
            fs.append((a, a + 1, a + count + 1, a + count))
    cloak = mesh("女孩-披风", vs, fs, cloth, g["cloak"])
    solid = cloak.modifiers.new("披风厚度", "SOLIDIFY")
    solid.thickness = 0.009
    for side in (-1, 1):
        for name, r in [("thigh", 0.065), ("shin", 0.048), ("upper", 0.046), ("lower", 0.038)]:
            g[name, side] = sphere(f"女孩-{name}-{side}", (r, r, 0.15), clay, root)
        g["foot", side] = empty(f"女孩-脚控制-{side}", root)
        sphere(f"女孩-靴-{side}", (0.059, 0.105, 0.045), cloth, g["foot", side], (0, 0.025, 0))
        g["hand", side] = empty(f"女孩-手控制-{side}", root)
        sphere(f"女孩-手掌-{side}", (0.037, 0.049, 0.024), clay, g["hand", side])
        g["ground", side] = empty(f"地面-脚落点-{side}")
    g["bag"] = sphere("女孩-挎包", (0.065, 0.04, 0.095), cloth, root)
    return g


def build_dragon():
    root = empty("幼龙-主体")
    clay = material("幼龙-白模", (0.78, 0.78, 0.78))
    membrane = material("幼龙-翼膜", (0.55, 0.55, 0.55))
    dark = material("幼龙-眼", (0.1, 0.1, 0.1))
    sphere("幼龙-身体", (0.08, 0.13, 0.072), clay, root)
    sphere("幼龙-后躯", (0.085, 0.077, 0.07), clay, root, (0, -0.08, 0))
    head = empty("幼龙-头部", root)
    head.location = (0, 0.145, 0.038)
    sphere("幼龙-头", (0.095, 0.078, 0.073), clay, head)
    sphere("幼龙-短吻", (0.065, 0.043, 0.039), clay, head, (0, 0.07, -0.02))
    for side in (-1, 1):
        sphere(f"幼龙-眼眶{side}", (0.027, 0.018, 0.029), clay, head, (side * 0.060, 0.051, 0.024))
        sphere(f"幼龙-眼球{side}", (0.018, 0.012, 0.022), dark, head, (side * 0.061, 0.065, 0.024))
        fin = sphere(
            f"幼龙-耳鳍{side}", (0.017, 0.035, 0.05), clay, head, (side * 0.088, -0.02, 0.046)
        )
        fin.rotation_quaternion = Quaternion((0, 1, 0), side * 0.45)
    for i in range(3):
        sphere(f"幼龙-短头脊{i}", (0.014, 0.017, 0.013), clay, head, (0, -0.03 + i * 0.025, 0.07))
    d = {"root": root, "head": head}
    for side in (-1, 1):
        wing = empty(f"幼龙-翼控制{side}", root)
        wing.location = (side * 0.055, 0.025, 0.055)
        pts = [
            (0, 0, 0),
            (side * 0.055, -0.005, 0.075),
            (side * 0.105, -0.11, 0.043),
            (side * 0.06, -0.10, 0.008),
            (side * 0.06, -0.16, -0.006),
            (0, -0.11, -0.015),
        ]
        obj = mesh(
            f"幼龙-翼膜{side}", pts, [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 5)], membrane, wing
        )
        sol = obj.modifiers.new("翼膜厚度", "SOLIDIFY")
        sol.thickness = 0.003
        tube(f"幼龙-翼前缘{side}", pts[:3], [0.007, 0.005, 0.003], clay, wing)
        for j in (3, 4, 5):
            tube(f"幼龙-翼骨{side}-{j}", [pts[1], pts[j]], [0.004, 0.002], clay, wing)
        d["wing", side] = wing
        for end in ("fore", "hind"):
            for part, r in [("upper", 0.026), ("lower", 0.019)]:
                d[end, part, side] = sphere(f"幼龙-{end}-{part}{side}", (r, r, 0.04), clay, root)
            foot = empty(f"幼龙-{end}-爪{side}", root)
            sphere(f"幼龙-{end}-掌{side}", (0.025, 0.031, 0.016), clay, foot)
            for toe in (-1, 0, 1):
                sphere(
                    f"幼龙-{end}-{side}-趾{toe}",
                    (0.007, 0.016, 0.007),
                    clay,
                    foot,
                    (toe * 0.014, 0.025, -0.004),
                )
            d[end, "foot", side] = foot
    pts = [(0, -0.12, 0), (0, -0.19, -0.015), (0.025, -0.25, -0.04), (0.045, -0.31, -0.055)]
    _, d["tail"] = tube("幼龙-连续尾巴", pts, [0.035, 0.025, 0.014, 0.004], clay, root)
    return d


def timeline(c):
    count, rate = c["frames"], c["fps"]
    positions = []
    angles = []
    dragon_angles = []
    previous = 0
    for i in range(count):
        t = i / rate
        v = sample(c["girl_path"], t)
        if t < 16.25 and v.length < 1.04:
            v.normalize()
            v *= 1.04
        positions.append(Vector((v.x, v.y, 0)))
        a = math.atan2(v.x, -v.y)
        if i:
            while a - previous > math.pi:
                a -= 2 * math.pi
            while a - previous < -math.pi:
                a += 2 * math.pi
        previous = a
        dragon_angles.append(a + math.radians(140))
    boundary = min(count - 1, round(c["source_boundary"] * rate))
    target = -math.radians(35)
    start = dragon_angles[boundary]
    while target - start > math.pi:
        target -= 2 * math.pi
    while target - start < -math.pi:
        target += 2 * math.pi
    for i in range(boundary, count):
        t = i / rate
        dragon_angles[i] = start + (target - start) * smooth(
            (t - c["source_boundary"]) / (c["jump_start"] - c["source_boundary"])
        )
    yawbase = math.atan2(0.5, 0.85)
    for i, p in enumerate(positions):
        t = i / rate
        speed = positions[min(i + 2, count - 1)] - positions[max(0, i - 2)]
        if t < 15.8:
            a = dragon_angles[i]
            targetpos = Vector((0.80 * math.sin(a), -0.80 * math.cos(a), 0))
            toward = (targetpos - p).normalized()
            if speed.length > 0.025:
                direction = speed.normalized() * 0.65 + toward * 0.35
            else:
                direction = toward
            yaw = math.atan2(direction.y, direction.x)
        elif t < 19.2:
            yaw = yawbase
        else:
            u = smooth((t - 19.2) / 4)
            yaw = yawbase + 2 * math.pi * u
            positions[i] += Vector(
                (0.04 * math.sin(2 * math.pi * u), 0.035 * (1 - math.cos(2 * math.pi * u)), 0)
            )
        if i:
            while yaw - angles[-1] > math.pi:
                yaw -= 2 * math.pi
            while yaw - angles[-1] < -math.pi:
                yaw += 2 * math.pi
        if 15 < t < 15.8 and angles:
            yaw = angles[-1] + max(-0.12, min(0.12, yaw - angles[-1]))
        angles.append(yaw)
    # Smooth only orientation, while retaining the authored root trajectory.
    smooth_angles = []
    for i in range(count):
        if i < round(15.8 * rate):
            nearby = angles[max(0, i - 3) : min(count, i + 4)]
            smooth_angles.append(sum(nearby) / len(nearby))
        else:
            smooth_angles.append(angles[i])
    angles = smooth_angles
    phases = [0.0]
    for i in range(1, count):
        distance = (positions[i] - positions[i - 1]).length
        turn = abs(angles[i] - angles[i - 1])
        phases.append(
            phases[-1]
            + distance / 0.64
            + (turn / (2 * math.pi / 3) if i / rate >= 19.2 else turn * 0.035)
        )
    feet = {}
    grounded = {}
    for side in (-1, 1):
        offset = 0 if side == -1 else 0.5
        feet[side] = []
        grounded[side] = []

        def landing(k, side=side):
            q = Quaternion(Z, angles[k] - math.pi / 2)
            return positions[k] + q @ Vector((side * 0.085, 0.075, 0)) + Z * 0.045

        plant = landing(0)
        plantq = Quaternion(Z, angles[0] - math.pi / 2)
        lastcycle = math.floor(phases[0] + offset)
        for i, phase in enumerate(phases):
            cycle = math.floor(phase + offset)
            u = (phase + offset) % 1
            if cycle != lastcycle:
                plant = landing(i)
                plantq = Quaternion(Z, angles[i] - math.pi / 2)
                lastcycle = cycle
            moving = i > 0 and phase - phases[i - 1] > 0.0001
            if u < 0.55 or not moving:
                foot, rot = plant.copy(), plantq.copy()
                standing = True
            else:
                targetphase = cycle + 1 - offset
                k = min(count - 1, bisect.bisect_left(phases, targetphase))
                v = (u - 0.55) / 0.45
                foot = plant.lerp(landing(k), smooth(v))
                foot.z += 0.12 * math.sin(math.pi * v)
                rot = plantq.slerp(Quaternion(Z, angles[k] - math.pi / 2), smooth(v))
                standing = False
            feet[side].append((foot, rot))
            grounded[side].append(standing)
    return positions, angles, dragon_angles, phases, feet, grounded


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--version", default="01")
    ap.add_argument("--config", default="03-制作/制作计划/巨树互动动作配置-版本01.json")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    if not args.version or not all(c.isalnum() or c in "-_" for c in args.version):
        raise ValueError("版本格式无效")
    project = Path(args.project).resolve()
    cp = project_path(project, args.config, exists=True)
    c, config_hash = read_json_bound(cp)
    blend = project_path(project, f"03-制作/三维工程/巨树互动白模-版本{args.version}.blend")
    stills = project_path(project, f"05-检查与验收/白模关键帧-版本{args.version}")
    report = project_path(project, f"05-检查与验收/白模动作采样-版本{args.version}.json")
    for p in (blend, stills, report):
        if p.exists() or p.is_symlink():
            raise FileExistsError(p)
    blend.parent.mkdir(parents=True, exist_ok=True)
    stills.mkdir(parents=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # Factory-startup 5.3 carries unused asset-brush file references. This mesh-only
    # scene uses no brushes; remove them in this isolated process, not user prefs.
    for brush in list(bpy.data.brushes):
        bpy.data.brushes.remove(brush)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = c["width"]
    scene.render.resolution_y = c["height"]
    scene.render.resolution_percentage = 100
    scene.render.fps = c["fps"]
    scene.frame_start = 1
    scene.frame_end = c["frames"]
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.use_overwrite = False
    scene.world = bpy.data.worlds.new("白模世界")
    scene.world.color = (0.7, 0.7, 0.7)
    scene.view_settings.view_transform = "Standard"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.show_object_outline = False
    build_set(c)
    g = build_girl()
    d = build_dragon()
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    cam.name = "摄影机-连续观察"
    cam.data.lens = c["camera_lens"]
    cam.data.clip_end = 100
    scene.camera = cam
    pos, yaws, da, phases, feet, grounded = timeline(c)
    samples = []
    rate = c["fps"]
    lastq = None
    grip_phase = [0.0]
    for k in range(1, c["frames"]):
        grip_phase.append(grip_phase[-1] + abs(da[k] - da[k - 1]) * 0.65 / 0.11)
    grip_states = {}
    for i in range(c["frames"]):
        t = i / rate
        frame = i + 1
        root = pos[i]
        yaw = yaws[i]
        q = Quaternion(Z, yaw - math.pi / 2)
        forward = q @ Vector((0, 1, 0))
        right = q @ Vector((1, 0, 0))
        crouch = 0.055 * smooth((t - 15.8) / 1.0) * (1 - smooth((t - 18.4) / 0.8))
        absorb = 0.065 * math.exp(-(((t - 18.55) / 0.20) ** 2))
        moving = (pos[min(i + 1, c["frames"] - 1)] - pos[max(0, i - 1)]).length > 0.008
        bob = 0.013 * math.sin(phases[i] * 4 * math.pi) if moving else 0.002 * math.sin(t * 3)
        pelvis = root + Z * (0.64 - crouch - absorb + bob)
        # Keep both leg links at their authored length while the feet plant.
        # The pelvis lowers at wider steps rather than stretching the legs.
        for side in (-1, 1):
            ankle = feet[side][i][0]
            offset = pelvis + right * side * 0.084 - ankle
            horizontal = offset.x * offset.x + offset.y * offset.y
            if horizontal >= 0.626**2:
                raise ValueError(f"步幅超出腿部可达范围: frame {frame}")
            pelvis.z = min(pelvis.z, ankle.z + math.sqrt(0.626**2 - horizontal))
        torso = pelvis + Z * 0.235 + forward * 0.014
        head = pelvis + Z * 0.535 + forward * 0.018
        a = da[i]
        normal = Vector((math.sin(a), -math.cos(a), 0))
        tangent = Vector((math.cos(a), math.sin(a), 0))
        preload = (
            0.035 * math.sin(math.pi * min(1, max(0, (t - 17) / 0.65))) if 17 < t < 17.65 else 0
        )
        climbpos = normal * 0.80 + Z * (0.72 + 0.025 * math.sin(t * 3.2) - preload)
        climbq = basis(Z + tangent * 0.15, normal)
        heldpos = pelvis + forward * 0.27 + Z * 0.29
        heldq = basis(-right, Z)
        if t < c["jump_start"]:
            dp, dq = climbpos, climbq
        elif t < c["jump_end"]:
            u = (t - c["jump_start"]) / (c["jump_end"] - c["jump_start"])
            # Takeoff is tied to the actual tree position at the first jump frame.
            aa = da[round(c["jump_start"] * rate)]
            origin = Vector((math.sin(aa), -math.cos(aa), 0)) * 0.80 + Z * (
                0.72 + 0.025 * math.sin(c["jump_start"] * 3.2)
            )
            dp = origin.lerp(heldpos, u) + Z * (0.34 * 4 * u * (1 - u))
            dq = climbq.slerp(heldq, smooth(u))
        else:
            dp, dq = heldpos, heldq
        if lastq is not None and dq.dot(lastq) < 0:
            dq.negate()
        lastq = dq.copy()
        pose(d["root"], dp, dq, frame=frame)
        # Body and actual limbs remain editable as keyed objects, not a flat card.
        for side in (-1, 1):
            for end, yy in (("fore", 0.065), ("hind", -0.085)):
                anchor = Vector((side * 0.063, yy, 0))
                if t < c["jump_start"]:
                    offset = (0 if end == "fore" else 0.5) + (side + 1) * 0.25
                    phase = grip_phase[i] + offset
                    cycle = math.floor(phase)
                    phase -= cycle
                    key = (end, side)

                    def grip_surface(k, side=side, yy=yy):
                        angle = da[k] + side * 0.10
                        return Vector(
                            (
                                0.654 * math.sin(angle),
                                -0.654 * math.cos(angle),
                                0.72 + 0.025 * math.sin(k / rate * 3.2) + yy,
                            )
                        )

                    if key not in grip_states or grip_states[key][0] != cycle:
                        grip_states[key] = (cycle, grip_surface(i))
                    plant = grip_states[key][1]
                    if phase < 0.45:
                        world_grip = plant
                    else:
                        k = min(c["frames"] - 1, bisect.bisect_left(grip_phase, cycle + 1 - offset))
                        k = min(k, round(c["jump_start"] * rate))
                        swing = (phase - 0.45) / 0.55
                        world_grip = plant.lerp(grip_surface(k), smooth(swing)) + normal * (
                            0.018 * math.sin(math.pi * swing)
                        )
                    grip = dq.inverted() @ (world_grip - dp)
                elif t < c["jump_end"]:
                    u = (t - c["jump_start"]) / (c["jump_end"] - c["jump_start"])
                    grip = Vector(
                        (
                            side * 0.075,
                            yy + (0.035 if end == "fore" else -0.025),
                            -0.095 - 0.035 * math.sin(u * math.pi),
                        )
                    )
                else:
                    grip = Vector((side * 0.067, yy + (0.015 if end == "fore" else 0), -0.085))
                elbow = joint(anchor, grip, Vector((side, 0, 0.15)), 0.095)
                segment(d[end, "upper", side], anchor, elbow, 0.025, frame)
                segment(d[end, "lower", side], elbow, grip, 0.017, frame)
                pose(d[end, "foot", side], grip, Quaternion((1, 0, 0), -0.35), frame=frame)
            wingq = Quaternion((0, 1, 0), side * 0.07 * math.sin(t * 2))
            pose(d["wing", side], (side * 0.055, 0.025, 0.055), wingq, frame=frame)
        for k, p in enumerate(d["tail"].bezier_points):
            u = k / 3
            co = Vector((0.045 * u * u, -0.12 - 0.19 * u, -0.055 * u))
            co.x += 0.025 * math.sin(t * 3.0 - u * 2) * u
            p.co = co
            p.keyframe_insert("co", frame=frame)
        headq = Quaternion((1, 0, 0), 0.06 * math.sin(t * 2.2))
        pose(d["head"], (0, 0.145, 0.038), headq, frame=frame)
        pose(g["pelvis"], pelvis, q, frame=frame)
        pose(g["torso"], torso, q, frame=frame)
        pose(g["neck"], head - Z * 0.135, q, frame=frame)
        look = (dp - head).normalized()
        lookyaw = math.atan2(look.y, look.x)
        while lookyaw - yaw > math.pi:
            lookyaw -= 2 * math.pi
        while lookyaw - yaw < -math.pi:
            lookyaw += 2 * math.pi
        lookyaw = yaw + max(-1.15, min(1.15, lookyaw - yaw))
        hforward = Vector((math.cos(lookyaw), math.sin(lookyaw), max(-0.75, min(0.1, look.z))))
        pose(g["head"], head, basis(hforward), frame=frame)
        cloakq = q @ Quaternion((1, 0, 0), 0.04 * math.sin(phases[i] * 2 * math.pi))
        pose(g["cloak"], torso + Z * 0.11 - forward * 0.015, cloakq, frame=frame)
        pose(g["bag"], pelvis + right * 0.18 - forward * 0.025 - Z * 0.025, q, frame=frame)
        hand_dists = []
        for side in (-1, 1):
            foot, fq = feet[side][i]
            hip = pelvis + right * side * 0.084
            knee = joint(hip, foot, forward, 0.315)
            segment(g["thigh", side], hip, knee, 0.059, frame)
            segment(g["shin", side], knee, foot, 0.045, frame)
            pose(g["foot", side], foot, fq, frame=frame)
            ground = foot + fq @ Vector((0, 0.025, 0))
            ground.z = 0
            pose(g["ground", side], ground, frame=frame)
            shoulder = torso + Z * 0.12 + right * side * 0.148
            if t < 15.8:
                swing = 0.10 * math.sin(phases[i] * 2 * math.pi + side * math.pi / 2)
                hand = (
                    pelvis
                    + right * side * 0.21
                    + forward * (0.15 + swing)
                    + Z * (0.13 - 0.04 * math.cos(phases[i] * 2 * math.pi))
                )
            else:
                openhand = pelvis + right * side * 0.20 + forward * 0.35 + Z * 0.28
                belly = dp + dq @ Vector((0, -0.065 if side == 1 else 0.065, -0.071))
                targethand = belly - Z * 0.024
                blend_in = smooth((t - 17.8) / 0.4)
                hand = openhand.lerp(targethand, blend_in)
                hand_dists.append((hand + Z * 0.024 - belly).length)
            elbow = joint(shoulder, hand, right * side - forward * 0.15, 0.235)
            segment(g["upper", side], shoulder, elbow, 0.045, frame)
            segment(g["lower", side], elbow, hand, 0.034, frame)
            pose(g["hand", side], hand, q, frame=frame)
        camera_params = sample(c["camera_keys"], t, cubic=False)
        cl = Vector(camera_params[:3])
        target = Vector(camera_params[3:])
        pose(cam, cl, (target - cl).to_track_quat("-Z", "Y"), frame=frame)
        samples.append(
            {
                "frame": frame,
                "time": t,
                "girl_root": list(root),
                "girl_yaw": yaw,
                "dragon_root": list(dp),
                "left_planted": grounded[-1][i],
                "right_planted": grounded[1][i],
                "support_errors": hand_dists,
            }
        )
    for action in bpy.data.actions:
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for fc in bag.fcurves:
                        for key in fc.keyframe_points:
                            key.interpolation = "LINEAR"
    for name, sec in [
        ("原片动作", 0),
        ("新增承接", 14.875),
        ("蹬跳蓄力", 17),
        ("离树扑抱", c["jump_start"]),
        ("双臂接住", c["jump_end"]),
        ("抱稳转圈", 19.2),
        ("停稳对视", 23.2),
    ]:
        scene.timeline_markers.new(name, frame=round(sec * rate) + 1)
    scene["制作说明"] = "按可见参考重建并补拍；树后轨迹为估计；可编辑关节对象与关键帧，非动捕。"
    scene["场景基准"] = c["scene_image"]
    scene["来源动作配置SHA256"] = config_hash
    scene.frame_set(1)
    if sha(cp) != config_hash:
        raise ValueError("配置制作期间改变")
    require_self_contained(bpy)
    save_checked(bpy, blend, project, lambda: require_hash(cp, config_hash))
    write_json_new(
        report,
        {"config_sha256": config_hash, "samples": samples, "dynamic_review": "pending"},
        project,
    )
    scene.render.resolution_percentage = 50
    for sec in c["still_times"]:
        frame = min(c["frames"], round(sec * rate) + 1)
        scene.frame_set(frame)
        render_still_new(bpy, stills / f"关键帧-{frame:04d}.png", project)
    print(
        json.dumps(
            {
                "blend": str(blend),
                "sha256": sha(blend),
                "stills": str(stills),
                "samples": str(report),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
