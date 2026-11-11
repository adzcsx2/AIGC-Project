"""Editable articulated clay blocking, driven by a project-local pose table.

Run with Blender --background --factory-startup --python this_file -- --project ...
The source movie is never edited. This is authored blocking, not motion capture.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from whitebox_saved import (  # noqa: E402
    project_path,
    render_still_new,
    save_new,
    sha,
    write_json_new,
)


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--mode', choices=('stills', 'animation'), default='stills')
    parser.add_argument('--version', default='01')
    return parser.parse_args(sys.argv[sys.argv.index('--') + 1:])


def output_paths(project, version):
    """Validate the whole output version before creating files or changing the scene."""
    if not version or any(not (char.isalnum() or char in '-_') for char in version):
        raise ValueError('版本只能包含文字、数字、连字符或下划线，不能包含路径')
    project = Path(project).resolve()
    destinations = (
        project / f'03-制作/三维工程/龙宝宝喝奶-动作白模-版本{version}.blend',
        project / f'03-制作/中间数据/白模帧序列-版本{version}',
        project / f'05-检查与验收/白模关键帧-版本{version}',
        project / f'05-检查与验收/白模采样-版本{version}.json',
    )
    paths = tuple(project_path(project, path) for path in destinations)
    occupied = next((path for path in destinations if path.exists() or path.is_symlink()), None)
    if occupied is not None:
        raise FileExistsError(f'版本 {version} 已有产物：{occupied}；请换未使用版本')
    return paths


def material(name, value, roughness=0.7):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (value, value, value, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (value, value, value, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    return mat


def sphere(name, scale, mat, parent=None, location=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.location = location
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = True
    if parent:
        obj.parent = parent
    return obj


def empty(name, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.empty_display_type = 'SPHERE'
    obj.empty_display_size = 0.07
    obj.parent = parent
    obj.rotation_mode = 'QUATERNION'
    return obj


def cube(name, location, scale, mat, bevel=0.04):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new('软化边缘', 'BEVEL')
        mod.width, mod.segments = bevel, 3
        obj.modifiers.new('加权法线', 'WEIGHTED_NORMAL')
    return obj


def tube(name, points, radius, mat, parent=None):
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.resolution_u = 10
    curve.bevel_depth = radius
    curve.bevel_resolution = 3
    spline = curve.splines.new('BEZIER')
    spline.bezier_points.add(len(points) - 1)
    for point, coord in zip(spline.bezier_points, points, strict=True):
        point.co = coord
        point.handle_left_type = point.handle_right_type = 'AUTO'
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    curve.materials.append(mat)
    obj.parent = parent
    return obj


def pose(obj, location, rotation=None, scale=None, frame=None):
    obj.location = location
    if rotation is not None:
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = rotation
    if scale is not None:
        obj.scale = scale
    if frame is not None:
        obj.keyframe_insert('location', frame=frame)
        if rotation is not None:
            obj.keyframe_insert('rotation_quaternion', frame=frame)
        if scale is not None:
            obj.keyframe_insert('scale', frame=frame)


def basis(forward, up):
    forward = Vector(forward).normalized()
    right = (-forward).cross(Vector(up)).normalized()
    corrected_up = right.cross(-forward).normalized()
    # A proper right-handed rotation; local model faces -Y.
    return Matrix((right, -forward, corrected_up)).transposed().to_quaternion()


def segment(obj, a, b, width, depth, frame):
    a, b = Vector(a), Vector(b)
    delta = b - a
    pose(obj, (a + b) / 2, delta.to_track_quat('Z', 'Y'),
         (width, depth, max(delta.length / 2 + width * 0.22, 0.02)), frame)


def interpolate(keys, time):
    if time <= keys[0]['t']:
        return dict(keys[0])
    for left, right in zip(keys, keys[1:], strict=False):
        if time <= right['t']:
            ratio = (time - left['t']) / (right['t'] - left['t'])
            # Dense sampled transforms are baked below. Smooth within each authored beat.
            ratio = ratio * ratio * (3 - 2 * ratio)
            output = {'t': time}
            for key in left:
                if key == 't':
                    continue
                if isinstance(left[key], list):
                    output[key] = [
                        a + (b - a) * ratio
                        for a, b in zip(left[key], right[key], strict=True)
                    ]
                else:
                    output[key] = left[key] + (right[key] - left[key]) * ratio
            return output
    return dict(keys[-1])


def make_bowl(mat, milk_mat):
    root = empty('控制-奶碗')
    profile = [(0.0, 0.015), (0.22, 0.015), (0.31, 0.04), (0.37, 0.15),
               (0.38, 0.19), (0.35, 0.20), (0.33, 0.15), (0.27, 0.055), (0.0, 0.055)]
    verts, faces = [], []
    count = 64
    for radius, z in profile:
        verts.extend([(radius * math.cos(i * 2 * math.pi / count),
                       radius * math.sin(i * 2 * math.pi / count), z) for i in range(count)])
    for row in range(len(profile) - 1):
        for i in range(count):
            a, b = row * count + i, row * count + (i + 1) % count
            faces.append((a, b, b + count, a + count))
    mesh = bpy.data.meshes.new('陶碗截面网格')
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    bowl = bpy.data.objects.new('道具-浅奶碗', mesh)
    bpy.context.collection.objects.link(bowl)
    bowl.parent = root
    mesh.materials.append(mat)
    for p in mesh.polygons:
        p.use_smooth = True
    milk = sphere('奶面', (.332, .332, .014), milk_mat, root, (0, 0, .153))
    return root, milk


def build(args):
    project = Path(args.project).resolve()
    engine_path, render_dir, still_dir, sample_path = output_paths(project, args.version)
    config_path = project_path(project, '03-制作/制作计划/白模动作配置.json', exists=True)
    config_hash = sha(config_path)
    config = json.loads(config_path.read_text('utf-8'))
    engine_path.parent.mkdir(parents=True, exist_ok=True)
    for directory in (render_dir, still_dir):
        directory.mkdir(parents=True, exist_ok=False)

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 16
    scene.cycles.use_denoising = True
    try:
        preferences = bpy.context.preferences.addons['cycles'].preferences
        preferences.compute_device_type = 'OPTIX'
        preferences.get_devices()
        for device in preferences.devices:
            device.use = device.type == 'OPTIX'
        if any(d.use for d in preferences.devices):
            scene.cycles.device = 'GPU'
            scene.cycles.denoiser = 'OPTIX'
    except Exception as error:
        print('GPU fallback:', error, flush=True)
    scene.render.resolution_x, scene.render.resolution_y = config['width'], config['height']
    scene.render.resolution_percentage = 100
    scene.render.fps = config['fps']
    scene.frame_start, scene.frame_end = 1, config['frames']
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.use_overwrite = False
    scene.render.film_transparent = False
    scene.world.color = (.30, .30, .30)
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (.72, .72, .72, 1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .5
    scene.view_settings.view_transform = 'AgX'

    clay = material('幼龙-灰白黏土', .62)
    bellymat = material('腹甲-浅灰', .72)
    detail = material('眼睛鼻孔-深灰', .12, .4)
    wingmat = material('翼膜-灰', .45)
    envmat = material('木凳-中灰', .36)
    cushionmat = material('布垫-浅灰', .49)
    floormat = material('地板-灰', .29)
    bowlmat = material('陶碗-灰白', .61, .4)
    milkmat = material('牛奶-亮白', .86, .25)

    cube('地面', (0, 0, -.07), (12, 12, .12), floormat, 0)
    for index in range(-6, 7):
        cube(f'地板接缝-{index}', (index * .38, 0, -.006), (.008, 10, .005), envmat, 0)
    cube('木凳-座面', (-.96, .35, 1.48), (1.30, 1.50, .14), envmat)
    cube('木凳-布垫', (-.96, .35, 1.59), (1.32, 1.52, .12), cushionmat, .055)
    cube('木凳-右侧围板', (-.36, .35, 1.13), (.12, 1.40, .57), envmat)
    for x in (-1.47, -.45):
        for y in (-.20, .90):
            cube(f'木凳腿-{x}-{y}', (x, y, .73), (.14, .14, 1.46), envmat, .025)
    cube('木凳-横撑', (-.97, -.20, .35), (1.15, .09, .10), envmat, .015)
    bowl, milk = make_bowl(bowlmat, milkmat)

    torso = sphere('幼龙-躯干', (.24, .25, .4), clay)
    hips = sphere('幼龙-后腰', (.28, .28, .28), clay)
    shoulder_ball = sphere('幼龙-胸腔', (.23, .23, .26), clay)
    neck = sphere('幼龙-颈部', (.14, .14, .2), clay)
    headroot = empty('控制-头部')
    sphere('幼龙-大头', (.285, .245, .23), clay, headroot)
    sphere('幼龙-短吻', (.22, .16, .12), clay, headroot, (0, -.23, -.055))
    sphere('幼龙-下颌', (.18, .12, .055), bellymat, headroot, (0, -.22, -.135))
    for side in (-1, 1):
        sphere(f'眼眶-{side}', (.105, .075, .12), bellymat, headroot, (side * .18, -.16, .055))
        sphere(f'眼球-{side}', (.072, .054, .086), detail, headroot, (side * .18, -.206, .055))
        sphere(f'眼高光-{side}', (.017, .012, .020), bellymat, headroot, (side * .167, -.255, .087))
        sphere(f'鼻孔-{side}', (.025, .014, .017), detail, headroot, (side * .095, -.371, -.03))
        fin = sphere(f'耳鳍-{side}', (.07, .10, .19), clay, headroot, (side * .26, .045, .14))
        fin.rotation_euler[1] = side * .45
        tube(f'眉弧-{side}', [(side * .08, -.16, .16), (side * .17, -.19, .18),
                              (side * .24, -.12, .16)], .024, clay, headroot)
    for index in range(3):
        sphere(f'头顶矮脊-{index}', (.045, .065, .045), clay, headroot,
               (0, .02 + index * .065, .211 - index * .02))
    tube('嘴缝', [(-.16, -.322, -.102), (0, -.369, -.113), (.16, -.322, -.102)],
         .008, detail, headroot)
    tongue = sphere('舔奶舌头', (.045, .085, .014), bellymat, headroot, (0, -.38, -.12))
    bodyroot = empty('控制-躯干坐标')
    for index in range(5):
        sphere(f'腹甲-{index + 1}', (.19 - .012 * abs(index - 2), .09, .022), bellymat,
               bodyroot, (0, -.25 + index * .115, -.225))

    limbs = {}
    for kind in ('前', '后'):
        for side in (-1, 1):
            label = f'{kind}肢-{side}'
            upper = sphere(label + '-上段', (.1, .1, .2), clay)
            lower = sphere(label + '-下段', (.075, .075, .18), clay)
            joint = sphere(label + '-关节', (.105, .105, .105), clay)
            footroot = empty('控制-' + label + '-爪')
            sphere(label + '-掌', (.12, .14, .075), clay, footroot)
            for digit in (-1, 0, 1):
                sphere(label + f'-趾{digit}', (.034, .07, .034), bellymat, footroot,
                       (digit * .065, -.12, -.02))
            limbs[kind, side] = upper, lower, joint, footroot

    wings = []
    for side in (-1, 1):
        root = empty(f'控制-折翼-{side}')
        points = [(0, 0, 0), (side * .25, .10, .23), (side * .28, .48, .17),
                  (side * .17, .40, .015), (side * .10, .55, -.035), (side * .025, .34, -.04)]
        mesh = bpy.data.meshes.new(f'折翼网格-{side}')
        mesh.from_pydata(points, [], [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 5)])
        mesh.update()
        obj = bpy.data.objects.new(f'翼膜-{side}', mesh)
        bpy.context.collection.objects.link(obj)
        obj.parent = root
        mesh.materials.append(wingmat)
        solid = obj.modifiers.new('薄翼膜', 'SOLIDIFY')
        solid.thickness = .012
        tube(f'翼前缘-{side}', points[:3], .022, clay, root)
        for index in (3, 4, 5):
            tube(f'翼指-{side}-{index}', [points[1], points[index]], .013, clay, root)
        wings.append((side, root))
    tailcurve = bpy.data.curves.new('尾巴连续曲线', 'CURVE')
    tailcurve.dimensions = '3D'
    tailcurve.resolution_u = 8
    tailcurve.bevel_depth = .145
    tailcurve.bevel_resolution = 4
    tailspline = tailcurve.splines.new('NURBS')
    tailspline.points.add(10)
    tailspline.order_u = 4
    tailspline.use_endpoint_u = True
    tail = list(tailspline.points)
    for i, point in enumerate(tail):
        point.radius = (1 - i / (len(tail) - 1)) ** .9 + .055
    tailobj = bpy.data.objects.new('幼龙-连续渐细尾巴', tailcurve)
    bpy.context.collection.objects.link(tailobj)
    tailcurve.materials.append(clay)

    spillroot = empty('控制-地面奶渍')
    for index in range(9):
        angle = index * 2.4
        radius = .06 + .026 * index
        sphere(f'奶渍-{index}', (.16 + index * .004, .10, .006), milkmat, spillroot,
               (math.cos(angle) * radius, math.sin(angle) * radius, 0))
    droplets = [sphere(f'溅奶-{i}', (.024, .024, .03), milkmat) for i in range(12)]

    bpy.ops.object.camera_add(location=(3.25, -6.8, 3.05))
    camera = bpy.context.object
    camera.name = '摄影机-原片动作观察'
    camera.data.type = 'PERSP'
    camera.data.lens = 57
    scene.camera = camera
    for name, loc, power, size in [('主光', (1, -3, 5), 650, 4), ('补光', (-3, -1, 3), 250, 3),
                                   ('轮廓光', (1, 3, 4), 400, 3)]:
        bpy.ops.object.light_add(type='AREA', location=loc)
        light = bpy.context.object
        light.name = name
        light.data.energy, light.data.shape, light.data.size = power, 'DISK', size
        light.rotation_euler = (
            (Vector((0, 0, .8)) - light.location).to_track_quat('-Z', 'Y').to_euler()
        )

    samples = []
    for frame in range(1, scene.frame_end + 1):
        time = (frame - 1) / scene.render.fps
        p = interpolate(config['poses'], time)
        pelvis, chest, head = Vector(p['pelvis']), Vector(p['chest']), Vector(p['head'])
        forward = (chest - pelvis).normalized()
        up = Vector(p['up']).normalized()
        qbody = basis(forward, up)
        right = qbody @ Vector((1, 0, 0))
        bodyup = qbody @ Vector((0, 0, 1))
        qhead = basis(p['face'], p['head_up'])
        sipping = time < 4.95 or time > 7.15
        if sipping:
            head += Vector((0, 0, .006 * math.sin(time * 2 * math.pi * 3.8)))
        pose(hips, pelvis, qbody, (.265, .29, .25), frame)
        segment(torso, pelvis, chest, .23, .245, frame)
        pose(shoulder_ball, chest, qbody, (.225, .26, .235), frame)
        segment(neck, chest + forward * .12, head - Vector(p['face']).normalized() * .12,
                .135, .14, frame)
        pose(headroot, head, qhead, frame=frame)
        pose(bodyroot, (pelvis + chest) / 2, qbody, frame=frame)
        lick = max(0, math.sin(time * math.pi * 2 * 3.8)) if sipping else 0
        pose(tongue, (0, -.34 - .065 * lick, -.12),
             scale=(.045, .025 + .06 * lick, .014), frame=frame)
        for kind in ('前', '后'):
            for side in (-1, 1):
                upper, lower, joint, footroot = limbs[kind, side]
                anchor = (
                    (chest if kind == '前' else pelvis)
                    + right * side * (.20 if kind == '前' else .22)
                )
                target = Vector(
                    p[('fore_' if kind == '前' else 'hind_') + ('a' if side == -1 else 'b')]
                )
                outward = right * side * (.08 if kind == '前' else .13)
                elbow = (anchor + target) / 2 + outward + Vector(p['elbow_bias'])
                segment(upper, anchor, elbow, .105 if kind == '前' else .14,
                        .10 if kind == '前' else .13, frame)
                segment(lower, elbow, target, .073 if kind == '前' else .09, .075, frame)
                pose(joint, elbow, frame=frame)
                footq = basis(p['paw_face'], p['paw_up'])
                pose(footroot, target, footq, frame=frame)
        for side, wing in wings:
            pose(wing, chest - forward * .12 + right * side * .18 + bodyup * .13,
                 qbody, frame=frame)

        tailstart = pelvis - forward * .12
        control = Vector(p['tail_mid'])
        tailend = Vector(p['tail_end'])
        points = []
        for i in range(len(tail)):
            u = i / (len(tail) - 1)
            point = (1-u)**2 * tailstart + 2*(1-u)*u * control + u*u * tailend
            point.y += .025 * math.sin(time * 3.1 - u * 3) * u
            points.append(point)
        for point, location in zip(tail, points, strict=True):
            point.co = (*location, 1)
            point.keyframe_insert('co', frame=frame)

        bowlq = Matrix.Rotation(p['bowl_tilt'], 4, 'Y').to_quaternion()
        pose(bowl, p['bowl'], bowlq, frame=frame)
        progress = min(1, max(0, (time - 5.38) / .70))
        pose(spillroot, (.25, -.58, .009),
             scale=(max(.001, progress), max(.001, progress), 1), frame=frame)
        for i, obj in enumerate(droplets):
            flight = time - 5.32 - i * .016
            visible = 0 < flight < .55
            angle = i * 2.399
            location = Vector((.16, -.18, .20))
            if visible:
                location += Vector((math.cos(angle) * .7 * flight,
                                    math.sin(angle) * .7 * flight,
                                    1.0 * flight - 2.8 * flight**2))
            radius = .014 + (i % 3) * .005 if visible else .00001
            pose(obj, location, scale=(radius, radius, radius * 1.3), frame=frame)
        target = Vector(p['camera_target'])
        camloc = Vector(p['camera'])
        pose(camera, camloc, (target - camloc).to_track_quat('-Z', 'Y'), frame=frame)
        samples.append({'frame': frame, 'time': time, 'head': list(head), 'pelvis': list(pelvis),
                        'fore_a': p['fore_a'], 'fore_b': p['fore_b']})

    # Bake sampled animation with linear interpolation so re-timing does not overshoot contacts.
    for action in bpy.data.actions:
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:
                            key.interpolation = 'LINEAR'
    for name, seconds in [('倒挂舔奶', 0), ('开始滑落', 4.95), ('脸入奶碗', 5.25),
                          ('翻落与洒奶', 5.55), ('重新撑起', 6.3), ('继续喝奶', 7.3)]:
        scene.timeline_markers.new(name, frame=round(seconds * scene.render.fps) + 1)
    scene['制作说明'] = (
        '按原片事件与可见姿态人工编排的简化白模。'
        '非动捕；隐藏关节和翼尾为目标幼龙结构适配。'
    )
    scene['源帧数'] = config['frames']
    scene['来源动作配置'] = str(config_path)
    scene['来源动作配置SHA256'] = config_hash
    scene.frame_set(1)
    scene.render.filepath = str(render_dir / '帧-')
    if sha(project_path(project, config_path, exists=True)) != config_hash:
        raise ValueError('制作期间动作配置已变化，不保存派生工程')
    save_new(bpy, engine_path, project)
    write_json_new(sample_path, samples, project)
    if args.mode == 'stills':
        for frame in (1, 115, 126, 134, 148, 166, 190, 281):
            scene.frame_set(frame)
            render_still_new(bpy, still_dir / f'关键帧-{frame:04}.png', project)
    else:
        for frame in range(scene.frame_start, scene.frame_end + 1):
            scene.frame_set(frame)
            render_still_new(bpy, render_dir / f'帧-{frame:04}.png', project)
    print(json.dumps(
        {'blend': str(engine_path), 'frames': str(render_dir), 'stills': str(still_dir)},
        ensure_ascii=False,
    ), flush=True)


if __name__ == '__main__':
    build(arguments())
