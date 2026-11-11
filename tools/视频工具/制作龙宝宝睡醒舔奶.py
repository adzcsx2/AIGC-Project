"""Author a saved, editable dragon performance from a project-local pose plan.

Uses keyed transforms and mesh shape keys, with no handlers or simulation caches.
The neutral guide and the environment projection are separate saved versions.
"""

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import read_json_bound, require_hash, save_checked
from whitebox_saved import project_path, render_still_new, sha, write_json_new

spec = importlib.util.spec_from_file_location(
    "clay_helpers", Path(__file__).with_name("制作喝奶白模.py")
)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def smooth(a, b, t):
    v = max(0.0, min(1.0, (t - a) / (b - a)))
    return v * v * (3 - 2 * v)


def pulse(t, a, b):
    return math.sin(math.pi * (t - a) / (b - a)) if a < t < b else 0.0


def keyed(obj, prop, value, frame):
    setattr(obj, prop, value)
    obj.keyframe_insert(prop, frame=frame)


def color_material(name, rgb, rough=0.7):
    m = h.material(name, 0.5, rough)
    m.diffuse_color = (*rgb, 1)
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
    return m


def mesh_obj(name, verts, faces, mat, parent=None):
    mesh = bpy.data.meshes.new(name + "网格")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    mesh.materials.append(mat)
    for poly in mesh.polygons:
        poly.use_smooth = True
    return obj


def lid(name, parent, center, upper, mat):
    n, rings = 32, 10

    def vertices(closed):
        amax = math.radians((46 if upper else 38) * (1 - closed) + 90 * closed)
        verts = []
        for j in range(rings + 1):
            a = 0.002 + amax * j / rings
            for i in range(n):
                phi = 2 * math.pi * i / n
                verts.append(
                    (
                        0.113 * math.sin(a) * math.cos(phi),
                        0.135 * math.sin(a) * math.sin(phi),
                        (0.134 * math.cos(a)) * (1 if upper else -1),
                    )
                )
        return verts

    faces = []
    for j in range(rings):
        for i in range(n):
            k = j * n + i
            v = j * n + (i + 1) % n
            faces.append((k, v, v + n, k + n))
    obj = mesh_obj(name, vertices(0), faces, mat, parent)
    obj.location = center
    obj.shape_key_add(name="张眼")
    closed = obj.shape_key_add(name="闭眼")
    for v, co in zip(closed.data, vertices(1), strict=True):
        v.co = co
    return closed


def make_tongue(parent, mat):
    rows, sides = 24, 12

    def coords(mode):
        verts = []
        for j in range(rows + 1):
            u = j / rows
            if mode == "hidden":
                y, z = -0.29 - 0.028 * u, -0.132
            else:
                c = smooth(0.58, 1.0, u) if mode == "curl" else 0.0
                y = -0.325 - 0.155 * u + 0.122 * c
                z = -0.135 - 0.19 * u + 0.070 * c
            width = 0.047 * (1 - 0.55 * u * u)
            if j == rows:
                width = 0.012
            for i in range(sides):
                a = 2 * math.pi * i / sides
                verts.append((width * math.cos(a), y, z + 0.011 * math.sin(a)))
        return verts

    faces = []
    for j in range(rows):
        for i in range(sides):
            a = j * sides + i
            b = j * sides + (i + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    faces.extend([tuple(range(sides - 1, -1, -1)), tuple(range(rows * sides, (rows + 1) * sides))])
    obj = mesh_obj("幼龙-可卷舌网格", coords("hidden"), faces, mat, parent)
    obj.shape_key_add(name="收在口内")
    ex = obj.shape_key_add(name="伸舌")
    curl = obj.shape_key_add(name="卷尖")
    for v, co in zip(ex.data, coords("straight"), strict=True):
        v.co = co
    # Curl is a relative deformation on the extended form.
    curl.relative_key = ex
    for v, co in zip(curl.data, coords("curl"), strict=True):
        v.co = co
    return obj, ex, curl


def build(config):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.data.orphans_purge(do_recursive=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 16
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = config["resolution"]
    scene.render.resolution_percentage = 100
    scene.render.fps = config["fps"]
    scene.frame_start = 1
    scene.frame_end = config["frames"]
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.render.use_overwrite = False
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.65, 1)
    bg.inputs["Strength"].default_value = 0.45
    scene.view_settings.view_transform = "AgX"
    clay = color_material("龙宝宝灰模", (0.61, 0.64, 0.65))
    bellymat = color_material("腹部浅灰", (0.75, 0.76, 0.73))
    dark = color_material("眼瞳口缝深灰", (0.035, 0.045, 0.045), 0.36)
    iris = color_material("虹膜灰蓝", (0.18, 0.27, 0.29), 0.3)
    white = color_material("眼白与高光", (0.82, 0.84, 0.81), 0.35)
    wingmat = color_material("翼膜中灰", (0.39, 0.44, 0.45))
    tongue_mat = color_material("舌体灰", (0.34, 0.38, 0.40), 0.5)
    wood = color_material("木桩灰", (0.22, 0.24, 0.22))
    ground = color_material("地面灰", (0.28, 0.30, 0.27))
    bowlmat = color_material("粗陶碗灰", (0.38, 0.40, 0.37))
    milkmat = color_material("牛奶", (0.94, 0.95, 0.92), 0.28)
    h.cube("环境-地面", (0, 0, -0.055), (30, 30, 0.1), ground, 0)
    st = config["stump"]
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64, radius=st["radius"], depth=st["height"], location=st["center"]
    )
    stump = bpy.context.object
    stump.name = "环境-矮宽旧木桩"
    stump.data.materials.append(wood)
    bevel = stump.modifiers.new("桩沿磨损", "BEVEL")
    bevel.width = 0.035
    bevel.segments = 3
    for i in range(28):
        a = i * math.tau / 28
        r = st["radius"] + 0.003
        h.tube(
            f"环境-树皮沟纹{i:02d}",
            [
                (st["center"][0] + r * math.cos(a), st["center"][1] + r * math.sin(a), 0.06),
                (
                    st["center"][0] + r * math.cos(a + 0.016),
                    st["center"][1] + r * math.sin(a + 0.016),
                    st["height"] - 0.05,
                ),
            ],
            0.011,
            ground,
        )
    for i, (x, y, r, height) in enumerate(config["trees"]):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=16, radius=r, depth=height, location=(x, y, height / 2)
        )
        tree = bpy.context.object
        tree.name = f"环境-林木{i:02d}"
        tree.data.materials.append(wood)
    bowl, milk = h.make_bowl(bowlmat, milkmat)
    root = h.empty("龙宝宝主体")

    def sph(name, scale, mat=clay, parent=root, location=(0, 0, 0)):
        return h.sphere(name, scale, mat, parent, location)

    torso = sph("幼龙-躯干", (0.30, 0.33, 0.4))
    hips = sph("幼龙-后腰", (0.31, 0.33, 0.27))
    chest = sph("幼龙-胸腔", (0.27, 0.30, 0.27))
    neck = sph("幼龙-短颈", (0.145, 0.155, 0.2))
    belly = sph("幼龙-圆肚子", (0.29, 0.36, 0.25), bellymat)
    head = h.empty("控制-头部", root)
    sph("幼龙-大头", (0.31, 0.265, 0.255), parent=head)
    sph("幼龙-短吻", (0.225, 0.165, 0.115), parent=head, location=(0, -0.225, -0.075))
    jawroot = h.empty("控制-下颌", head)
    sph("幼龙-下颌", (0.185, 0.155, 0.052), bellymat, jawroot, (0, -0.215, -0.165))
    h.tube(
        "幼龙-嘴缝",
        [(-0.17, -0.32, -0.143), (0, -0.385, -0.15), (0.17, -0.32, -0.143)],
        0.009,
        dark,
        head,
    )
    lids = []
    eyes = []
    ears = []
    for s in (-1, 1):
        center = (s * 0.19, -0.17, 0.065)
        sph(f"幼龙-眼球{s}", (0.109, 0.089, 0.128), white, head, center)
        er = h.empty(f"控制-视线{s}", head)
        er.location = (s * 0.19, -0.259, 0.065)
        sph(f"幼龙-虹膜{s}", (0.060, 0.013, 0.078), iris, er)
        sph(f"幼龙-瞳孔{s}", (0.026, 0.009, 0.056), dark, er, (0, -0.015, 0))
        sph(f"幼龙-眼高光{s}", (0.013, 0.007, 0.016), white, er, (-0.014, -0.024, 0.027))
        eyes.append((s, er))
        lids.append(
            (
                s,
                lid(f"幼龙-上眼睑{s}", head, center, True, clay),
                lid(f"幼龙-下眼睑{s}", head, center, False, clay),
            )
        )
        ear = h.empty(f"控制-耳鳍{s}", head)
        ear.location = (s * 0.285, 0.035, 0.12)
        sph(f"幼龙-耳鳍{s}", (0.065, 0.095, 0.18), parent=ear, location=(s * 0.018, 0, 0.055))
        ears.append((s, ear))
        sph(f"幼龙-鼻孔{s}", (0.023, 0.013, 0.015), dark, head, (s * 0.09, -0.379, -0.06))
    for i in range(3):
        sph(
            f"幼龙-软短脊{i}",
            (0.041, 0.052, 0.035),
            parent=head,
            location=(0, 0.04 + i * 0.065, 0.242 - i * 0.018),
        )
    tongue, extension, curl = make_tongue(head, tongue_mat)
    limbs = {}
    for kind in ("fore", "hind"):
        for side in (-1, 1):
            tag = ("前" if kind == "fore" else "后") + ("近" if side == -1 else "远")
            upper = sph(tag + "肢-上段", (0.1, 0.1, 0.2))
            lower = sph(tag + "肢-下段", (0.08, 0.08, 0.18))
            joint = sph(tag + "肢-关节", (0.10, 0.10, 0.10))
            paw = h.empty("控制-" + tag + "爪", root)
            sph(tag + "爪掌", (0.115, 0.135, 0.066), parent=paw)
            for digit in (-1, 0, 1):
                sph(
                    tag + f"爪趾{digit}",
                    (0.032, 0.065, 0.03),
                    bellymat,
                    paw,
                    (digit * 0.06, -0.11, -0.02),
                )
            limbs[kind, side] = (upper, lower, joint, paw)
    wings = []
    for side in (-1, 1):
        wr = h.empty(f"控制-翼{side}", root)
        points = [
            (0, 0, 0),
            (side * 0.25, 0.10, 0.22),
            (side * 0.37, 0.47, 0.13),
            (side * 0.22, 0.36, -0.03),
            (side * 0.12, 0.51, -0.08),
            (side * 0.02, 0.30, -0.05),
        ]
        wm = mesh_obj(
            f"幼龙-翼膜{side}", points, [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 5)], wingmat, wr
        )
        mod = wm.modifiers.new("翼膜厚度", "SOLIDIFY")
        mod.thickness = 0.014
        h.tube(f"幼龙-翼前缘{side}", points[:3], 0.023, clay, wr)
        for i in (3, 4, 5):
            h.tube(f"幼龙-翼指{side}-{i}", [points[1], points[i]], 0.013, clay, wr)
        wings.append((side, wr))
    taildata = bpy.data.curves.new("连续尾巴曲线", "CURVE")
    taildata.dimensions = "3D"
    taildata.resolution_u = 8
    taildata.bevel_depth = 0.12
    taildata.bevel_resolution = 4
    spline = taildata.splines.new("NURBS")
    spline.points.add(10)
    spline.order_u = 4
    spline.use_endpoint_u = True
    tail = bpy.data.objects.new("幼龙-渐细尾巴", taildata)
    bpy.context.collection.objects.link(tail)
    tail.parent = root
    taildata.materials.append(clay)
    for i, pt in enumerate(spline.points):
        pt.radius = (1 - i / 10) ** 0.9 + 0.045
    stains = []
    spots = [
        (-0.09, -0.15, 0.20),
        (0.07, -0.16, 0.20),
        (0, -0.355, -0.01),
        (-0.26, -0.14, 0.015),
        (0.26, -0.14, 0.015),
        (-0.29, 0.02, 0.21),
        (0.29, 0.02, 0.21),
    ]
    for i, pt in enumerate(spots):
        ob = sph(f"幼龙-脸上奶渍{i:02d}", (0.052, 0.013, 0.063), milkmat, head, pt)
        if i in (0, 1, 3, 4):
            normal = Vector((pt[0] / 0.31**2, pt[1] / 0.265**2, pt[2] / 0.255**2)).normalized()
            ob.rotation_euler = normal.to_track_quat("Y", "Z").to_euler()
        if i >= 5:
            ob.parent = bpy.data.objects[f"控制-耳鳍{-1 if i == 5 else 1}"]
            ob.location = (0, -0.092, 0.07)
        stains.append(ob)
    nose_drop = sph("幼龙-鼻尖残奶", (0.022, 0.016, 0.035), milkmat, head, (0.02, -0.389, -0.07))
    flying = [h.sphere(f"牛奶-飞溅{i:02d}", (0.022, 0.022, 0.031), milkmat) for i in range(28)]
    spill = h.empty("地面奶渍组")
    for i in range(8):
        a = i * 2.4
        h.sphere(
            f"地面奶渍{i:02d}",
            (0.13 + 0.01 * i, 0.07, 0.004),
            milkmat,
            spill,
            (0.10 * math.cos(a), 0.17 * math.sin(a), 0),
        )
    cameras = {}
    for key, cfg in config["cameras"].items():
        bpy.ops.object.camera_add(location=cfg["location"])
        cam = bpy.context.object
        cam.name = cfg["name"]
        cam.data.lens = cfg["lens"]
        cam.rotation_euler = (
            (Vector(cfg["target"]) - cam.location).to_track_quat("-Z", "Y").to_euler()
        )
        cam.data.clip_start = 0.05
        cam.data.clip_end = 100
        cameras[key] = cam
    for shot in config["shots"]:
        marker = scene.timeline_markers.new(shot["id"], frame=shot["start_frame"] + 1)
        marker.camera = cameras[shot["camera"]]
    scene.camera = cameras[config["shots"][0]["camera"]]
    for name, loc, power, size in [
        ("左上柔光", (-3, -4, 6), 850, 5),
        ("柔补光", (4, -1, 3), 200, 4),
        ("林间轮廓光", (0, 4, 5), 500, 4),
    ]:
        bpy.ops.object.light_add(type="AREA", location=loc)
        light = bpy.context.object
        light.name = name
        light.data.energy = power
        light.data.shape = "DISK"
        light.data.size = size
        light.rotation_euler = (
            (Vector((0.3, 0, 0.7)) - light.location).to_track_quat("-Z", "Y").to_euler()
        )
    records = []
    for f in range(1, config["frames"] + 1):
        t = (f - 1) / config["fps"]
        p = h.interpolate(config["poses"], t)
        pelvis, ch, hd = map(Vector, (p["pelvis"], p["chest"], p["head"]))
        forward = (ch - pelvis).normalized()
        up = Vector(p["up"]).normalized()
        qb = h.basis(forward, up)
        right = qb @ Vector((1, 0, 0))
        bodyup = qb @ Vector((0, 0, 1))
        breath = 0.006 * math.sin(t * math.tau * 0.42)
        burp = 0.018 * pulse(t, 28.73, 29.04)
        fullness = 1 + 0.28 * smooth(20, 26, t)
        h.pose(hips, pelvis, qb, (0.30, 0.32, 0.26), f)
        h.segment(torso, pelvis, ch, 0.29, 0.31, f)
        h.pose(chest, ch + bodyup * burp, qb, (0.27, 0.30, 0.26), f)
        h.pose(
            belly,
            (pelvis + ch) / 2 - bodyup * 0.02,
            qb,
            (0.28 * fullness, 0.32, 0.20 * fullness + breath + burp),
            f,
        )
        shake = 0
        for a, b, amp in [(18.12, 18.77, 0.60), (19.00, 19.60, 0.43)]:
            if a < t < b:
                shake = (
                    amp
                    * math.sin(math.tau * (t - a) / (b - a))
                    * math.sin(math.pi * (t - a) / (b - a))
                )
        qh = h.basis(p["face"], p["head_up"]) @ Matrix.Rotation(shake, 4, "Z").to_quaternion()
        h.segment(
            neck, ch + forward * 0.11, hd - Vector(p["face"]).normalized() * 0.13, 0.145, 0.15, f
        )
        h.pose(head, hd, qh, frame=f)
        # Each lick has an extension, a distinct curled-contact phase, and a return.
        lick = 0.0
        lc = 0.0
        starts = config["lick_starts"]
        for start in starts:
            phase = (t - start) / 0.54
            if 0 <= phase <= 1:
                lick = smooth(0, 0.32, phase) * (1 - smooth(0.72, 1, phase))
                lc = smooth(0.20, 0.48, phase) * (1 - smooth(0.78, 1, phase))
                break
        keyed(extension, "value", lick, f)
        keyed(curl, "value", lc, f)
        gape = p["jaw"] + 0.026 * lick + 0.035 * pulse(t, 28.73, 29.04)
        h.pose(jawroot, (0, 0, -gape), frame=f)
        for side, top, bottom in lids:
            openness = p["eye"]
            if 16.6 < t < 17.6:
                openness = (
                    (0.12 + 0.52 * smooth(16.68, 17.05, t))
                    if side == -1
                    else (0.08 + 0.50 * smooth(17.10, 17.55, t))
                )
            blink = max([pulse(t, a, b) for a, b in config["blinks"]] + [0])
            if 18.08 < t < 19.64:
                blink = max(blink, 0.90)
            opened = max(0, min(1, openness * (1 - blink)))
            keyed(top, "value", 1 - opened, f)
            keyed(bottom, "value", 1 - opened, f)
        for side, er in eyes:
            h.pose(er, (side * 0.19 + p["gaze"][0], -0.259, p["gaze"][1] + 0.065), frame=f)
        for side, ear in ears:
            lag = 0.09 * math.sin((t - 0.06) * 25) if 18.1 < t < 19.9 else 0
            ear.rotation_mode = "XYZ"
            keyed(
                ear,
                "rotation_euler",
                (lag, side * (0.32 - 0.15 * p["eye"]), -0.06 * side * math.sin(t * 1.5)),
                f,
            )
        for (kind, side), (upper, lower, joint, paw) in limbs.items():
            anchor = (ch if kind == "fore" else pelvis) + right * side * (
                0.22 if kind == "fore" else 0.25
            )
            target = Vector(p[kind + ("_near" if side == -1 else "_far")])
            elbow = (anchor + target) / 2 + right * side * 0.065 + bodyup * 0.01
            h.segment(upper, anchor, elbow, 0.10 if kind == "fore" else 0.13, 0.10, f)
            h.segment(lower, elbow, target, 0.074 if kind == "fore" else 0.085, 0.072, f)
            h.pose(joint, elbow, frame=f)
            h.pose(paw, target, h.basis(p["paw_face"], p["paw_up"]), frame=f)
        for side, wr in wings:
            qw = qb @ Matrix.Rotation(side * p["wing"], 4, "Y").to_quaternion()
            h.pose(wr, ch - forward * 0.15 + right * side * 0.20 + bodyup * 0.16, qw, frame=f)
        ts = pelvis - forward * 0.15
        tm = Vector(p["tail_mid"])
        te = Vector(p["tail_end"])
        for i, point in enumerate(tail.data.splines[0].points):
            u = i / 10
            pos = (1 - u) ** 2 * ts + 2 * (1 - u) * u * tm + u * u * te
            pos.y += 0.018 * math.sin(t * 2.2 - u * 3) * u
            point.co = (*pos, 1)
            point.keyframe_insert("co", frame=f)
        bq = Matrix.Rotation(p["bowl_tilt"], 4, "Y").to_quaternion()
        h.pose(bowl, p["bowl"], bq, frame=f)
        milklevel = (
            0.153
            - 0.010 * smooth(10.5, 14, t)
            - 0.032 * smooth(15.0, 15.7, t)
            - 0.032 * smooth(20.5, 25.65, t)
        )
        milk.location.z = milklevel
        milk.keyframe_insert("location", frame=f)
        remaining = max(0.001, 1 - smooth(25.2, 25.75, t))
        milk.scale = (0.332 * remaining, 0.332 * remaining, 0.008)
        milk.keyframe_insert("scale", frame=f)
        for i, ob in enumerate(stains):
            show = smooth(15.20 + i * 0.008, 15.38 + i * 0.008, t)
            show *= 1 - 0.38 * smooth(18.15, 18.80, t) - 0.32 * smooth(19.05, 19.65, t)
            if i in (0, 1, 2):
                show = max(show, 0.45 * smooth(15.25, 15.4, t))
            ob.scale = (0.045 * show, 0.007 * show, 0.052 * show)
            ob.keyframe_insert("scale", frame=f)
        s = smooth(15.25, 15.45, t)
        nose_drop.scale = (0.022 * s, 0.016 * s, 0.035 * s)
        nose_drop.keyframe_insert("scale", frame=f)
        for i, ob in enumerate(flying):
            start = (
                15.02 + (i % 10) * 0.012
                if i < 16
                else (18.22 if i < 22 else 19.12) + (i % 6) * 0.012
            )
            dt = t - start
            visible = 0 < dt < 0.65
            if i < 16:
                origin = Vector(p["bowl"]) + Vector((0.15, 0, 0.17))
                vel = Vector((0.50 + (i % 4) * 0.10, (i % 5 - 2) * 0.15, 1.15 + (i % 3) * 0.12))
            else:
                origin = hd + Vector((0, 0, 0.08))
                vel = Vector(((i % 3 - 1) * 0.8, (-1 if i % 2 else 1) * 1.1, 0.35))
            pos = origin + vel * max(0, dt) + Vector((0, 0, -1.9 * max(0, dt) ** 2))
            h.pose(ob, pos, scale=(0.022, 0.022, 0.031) if visible else (0.00001,) * 3, frame=f)
        h.pose(spill, (1.0, -0.12, 0.006), scale=(s, s, 1), frame=f)
        if f in config["sample_frames"]:
            records.append(
                {
                    "frame": f,
                    "time": t,
                    "head": list(hd),
                    "tongue_extension": lick,
                    "tongue_curl": lc,
                    "eye_open": p["eye"],
                    "head_shake_radians": shake,
                    "milk_z": milklevel,
                    "belly_scale": fullness,
                }
            )
    scene.frame_set(1)
    for obj in scene.objects:
        obj.is_shadow_catcher = False
        obj.is_holdout = False
        # Linear interpolation preserves densely baked motion between exact samples.
        ad = obj.animation_data
        if ad and ad.action:
            try:
                for curve in ad.action.fcurves:
                    for key in curve.keyframe_points:
                        key.interpolation = "LINEAR"
            except AttributeError:
                pass
    return records


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--stills", action="store_true")
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    project = Path(args.project).resolve()
    cfgpath = project_path(project, args.config, exists=True)
    cfg, config_hash = read_json_bound(cfgpath)
    out = project_path(project, f"03-制作/三维工程/龙宝宝-睡醒舔奶-白模{args.version}.blend")
    rec = project_path(project, f"05-检查与验收/睡醒舔奶-制作采样{args.version}.json")
    stilldir = project_path(project, f"05-检查与验收/睡醒舔奶-布局{args.version}")
    for dest in (out, rec, stilldir):
        if dest.exists():
            raise FileExistsError(str(dest))
    out.parent.mkdir(parents=True, exist_ok=True)
    stilldir.mkdir(parents=True)
    records = build(cfg)
    save_checked(bpy, out, project, lambda: require_hash(cfgpath, config_hash))
    dragon_names = {o.name for o in bpy.data.objects["龙宝宝主体"].children_recursive}
    objects = [
        {
            "name": o.name,
            "type": o.type,
            "material": o.data.materials[0].name
            if hasattr(o.data, "materials") and o.data.materials
            else "",
            "dragon": o.name in dragon_names,
        }
        for o in bpy.context.scene.objects
    ]
    write_json_new(
        rec,
        {
            "blend": str(out.relative_to(project)),
            "sha256": sha(out),
            "config_sha256": config_hash,
            "samples": records,
            "objects": objects,
        },
        project,
    )
    if args.stills:
        scene = bpy.context.scene
        scene.render.engine = "BLENDER_EEVEE"
        scene.render.resolution_percentage = 75
        for f in cfg["sample_frames"]:
            scene.frame_set(f)
            render_still_new(bpy, stilldir / f"帧{f:04d}.png", project)
        for marker in scene.timeline_markers:
            marker.camera = None
        scene.camera = bpy.data.objects[cfg["cameras"]["A"]["name"]]
        scene.frame_set(1)
        for obj in scene.objects:
            if obj.type not in {"LIGHT", "CAMERA"} and not obj.name.startswith("环境-"):
                obj.hide_render = True
        scene.render.resolution_percentage = 100
        render_still_new(bpy, stilldir / "主机位-空场布局.png", project)
    print(json.dumps({"blend": str(out), "sha256": sha(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
