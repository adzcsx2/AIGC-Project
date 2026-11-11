"""Build spatial/camera proxies for the nuzzle, eye reveal and aerial departure."""
import argparse
import json
import math
import random
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import read_json_bound, require_hash, save_checked
from whitebox_saved import load_saved, project_path, render_still_new, write_json_new


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x*x*(3-2*x)


def lerp(a, b, u):
    return a+(b-a)*u


def sphere(name, location, scale, color):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.color = (*color, 1)
    return obj


def cylinder(name, radius, length, color):
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=radius, depth=length)
    obj = bpy.context.object
    obj.name = name
    obj.color = (*color, 1)
    return obj


def empty(name):
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.empty_display_size = .025
    return obj


def key(obj, frame, location, rotation=None):
    obj.location = location
    obj.keyframe_insert('location', frame=frame)
    if rotation is not None:
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = rotation
        obj.keyframe_insert('rotation_quaternion', frame=frame)


def basis(forward, bank=0.0):
    x = Vector(forward).normalized()
    y = Vector((0, 0, 1)).cross(x).normalized()
    z = x.cross(y).normalized()
    return Quaternion(x, bank) @ Matrix((x, y, z)).transposed().to_quaternion()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True)
    ap.add_argument('--config', required=True)
    a = ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    p = Path(a.project).resolve()
    cp = project_path(p, a.config, exists=True)
    c, ch = read_json_bound(cp)
    source = project_path(p, c['source_blend'], exists=True)
    dest = project_path(p, c['output_blend'])
    report = project_path(p, c['report'])
    stills = project_path(p, c['stills'])
    for path in (dest, report, stills):
        if path.exists():
            raise FileExistsError(path)
    scene = load_saved(bpy, str(source), c['source_sha256'])
    scene.frame_set(600)
    girl = bpy.data.objects['圆柱-女孩占位']
    baby = bpy.data.objects['圆柱-幼龙占位']
    cam = scene.camera
    gpos, gq = girl.location.copy(), girl.rotation_quaternion.copy()
    bpos, bq = baby.location.copy(), baby.rotation_quaternion.copy()
    start_cam = cam.matrix_world.copy()
    for obj in list(scene.objects):
        obj.animation_data_clear()
    cam.data.animation_data_clear()
    for obj in list(scene.objects):
        if obj.name.startswith('巨树-冠') or obj.name.startswith('巨树-枝'):
            bpy.data.objects.remove(obj, do_unlink=True)
    # Preserve the already-used lower trunk and root geometry; extend only above it.
    trunk = bpy.data.objects['巨树-主干']
    for v in trunk.data.vertices:
        if v.co.z > 2:
            v.co.z = 2+(v.co.z-2)*5
    rng = random.Random(801)
    crowns = []
    for j in range(7):
        angle = 2*math.pi*j/7
        crowns.append(sphere(f'巨树-上冠占位{j:02d}',
                             (math.cos(angle)*3.5, math.sin(angle)*3.5, 19.5+j%3),
                             (5.0, 4.5, 3.5), (.26, .4, .25)))
    ground = bpy.data.objects['地面']
    ground.scale.x *= 150
    ground.scale.y *= 150
    for j in range(2):
        wall = bpy.data.objects[f'村屋{j}-墙']
        roof = bpy.data.objects[f'村屋{j}-屋顶']
        pts = [wall.matrix_world @ v.co for v in wall.data.vertices]
        center = sum(pts, Vector()) / len(pts)
        center.z = 0
        for obj in (wall, roof):
            inv = obj.matrix_world.inverted()
            for v in obj.data.vertices:
                world = obj.matrix_world @ v.co
                v.co = inv @ (center+(world-center)*1.7)
    # Few low-poly cones indicate distant foliage volumes; no detailed trees or terrain.
    for j in range(72):
        angle = 2*math.pi*j/72
        radius = rng.uniform(24, 70) if j < 32 else rng.uniform(85, 520)
        height = rng.uniform(8, 17)
        bpy.ops.mesh.primitive_cone_add(vertices=7, radius1=height*.38,
                                       depth=height, location=(math.cos(angle)*radius,
                                       math.sin(angle)*radius, height/2))
        obj = bpy.context.object
        obj.name = f'远林-占位{j:02d}'
        obj.color = (.27, .36, .25, 1)

    adult = cylinder('圆柱-成年巨龙占位', 1.0, 9.0, (.48, .18, .10))
    direction = cylinder('巨龙-朝向端标记', 1.03, .18, (.8, .6, .28))
    eye = sphere('龙眼-球体占位', (0, 0, 0), (.24, .13, .08), (.48, .18, .10))
    iris = sphere('龙眼-虹膜圆片', (0, 0, 0), (.20, .115, .012), (.65, .52, .18))
    pupil = sphere('龙眼-瞳孔标记', (0, 0, 0), (.022, .098, .005), (.06, .06, .06))
    cheek_g = bpy.data.objects.get('女孩-面颊参照') or empty('女孩-面颊参照')
    cheek_b = bpy.data.objects.get('幼龙-面颊参照') or empty('幼龙-面颊参照')
    envelope = [empty(f'巨龙-展开边界{k:02d}') for k in range(8)]
    local_envelope = [Vector((x, y, z)) for x in (-10, 5) for y in (-9, 9) for z in (-3, 3)]
    eye_normal = Vector((.25, -.96, .12)).normalized()
    eye_rot = eye_normal.to_track_quat('Z', 'Y')
    face = Vector((math.cos(math.radians(175)), math.sin(math.radians(175)), 0))
    side = Vector((-face.y, face.x, 0))
    fps = 24
    times = c['times']
    b_end, c_end, d_end, e_end = [times[k] for k in ['aerial_end', 'eye_end', 'reveal_end', 'end']]
    circle_seconds = c['flight']['circle_seconds']
    radius = c['flight']['radius']
    speed = 2*math.pi*radius/circle_seconds
    circle_root = Vector((speed*(d_end-b_end), 0, 45))
    circle_center = circle_root+Vector((0, radius, 0))
    bank = math.atan(speed*speed/(radius*9.81))
    target_close = gpos+Vector((0, 0, .4))
    target_far = Vector((gpos.x, gpos.y, 0))
    far_pos = target_far+face*450+Vector((0, 0, 240))
    close_pos = start_cam.translation
    close_q = start_cam.to_quaternion()
    start_target = close_pos+(close_q @ Vector((0, 0, -1)))*3.5
    near_eye_dist = .80
    reveal_dist = c.get('camera', {}).get('reveal_distance', 35.0)
    pull_k = math.log(reveal_dist/near_eye_dist)/(d_end-c_end)
    last_cam = None
    last_target = None
    last_velocity = None
    end_lens = 42.0
    rows = []
    scene.frame_start = 1
    scene.frame_end = round(e_end*fps)
    scene.render.fps = fps
    scene.render.fps_base = 1
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.use_compositing = False
    scene.render.use_sequencer = False
    cam.data.clip_start = .01
    cam.data.clip_end = 5000
    cam.rotation_mode = 'QUATERNION'
    for i in range(scene.frame_end):
        t = i/fps
        frame = i+1
        scene.frame_set(frame)
        active = max(0.0, t-b_end)
        if t < d_end:
            root = Vector((speed*active, 0, 45))
            heading = Vector((1, 0, 0))
            turn = 0.0
            roll = 0.0
        else:
            tau = t-d_end
            turn = 2*math.pi*min(1, tau/circle_seconds)
            angle = -math.pi/2+turn
            if tau <= circle_seconds:
                root = circle_center+Vector((radius*math.cos(angle), radius*math.sin(angle), 0))
                heading = Vector((-math.sin(angle), math.cos(angle), 0))
                roll = bank*smooth(tau/.75)*smooth((circle_seconds-tau)/.75)
            else:
                leave = tau-circle_seconds
                root = circle_root+Vector((speed*leave+3.2*leave*leave, 0, 2.2*leave*leave))
                heading = Vector((speed+6.4*leave, 0, 4.4*leave)).normalized()
                roll = 0.0
        qbody = basis(heading, roll)
        long_axis = qbody @ Quaternion((0, 1, 0), math.pi/2)
        key(adult, frame, root, long_axis)
        key(direction, frame, root+qbody @ Vector((4.48, 0, 0)), long_axis)
        eye_center = root+qbody @ Vector((3.6, -1.03, .32))
        n = qbody @ eye_normal
        qeye = qbody @ eye_rot
        for obj, offset in [(eye, 0), (iris, .081), (pupil, .096)]:
            key(obj, frame, eye_center+n*offset, qeye)
        for obj in (adult, direction, eye, iris, pupil):
            obj.hide_render = t < b_end
            obj.keyframe_insert('hide_render', frame=frame)
        for obj, local in zip(envelope, local_envelope):
            key(obj, frame, root+qbody @ local)

        # Cylinders carry only body-space intent; no modeled faces, arms or wings.
        nuzzle = math.sin(2*math.pi*t/1.35)*smooth(t/.2)*smooth((3.2-t)/.3) if t < 3.2 else 0
        key(girl, frame, gpos+side*.018*nuzzle,
            Quaternion(face, math.radians(1.5)*nuzzle) @ gq)
        key(baby, frame, bpos+side*.010*nuzzle+Vector((0, 0, .006*nuzzle)),
            Quaternion(face, math.radians(-2.0)*nuzzle) @ bq)
        contact = (gpos+bpos)/2+Vector((0, 0, .31))+side*.022*nuzzle
        key(cheek_g, frame, contact)
        key(cheek_b, frame, contact)

        if t < b_end:
            u = smooth((t-times['pull_start'])/(b_end-times['pull_start']))
            # Geometric growth gives a gentle start over a very large distance range.
            f = (math.exp(4*u)-1)/(math.exp(4)-1)
            camera_pos = close_pos.lerp(far_pos, f)
            camera_pos.z = lerp(close_pos.z, far_pos.z, f**.6)
            target = start_target.lerp(target_far, f)
            lens = lerp(c.get('camera', {}).get('nuzzle_close_lens', 50), 28, smooth(u))
            rotation = close_q if t <= times['pull_start'] else (target-camera_pos).to_track_quat('-Z', 'Y')
        elif t < c_end:
            if 'eye_macro_settle_time' in c.get('camera', {}):
                u = smooth((t-b_end)/(c['camera']['eye_macro_settle_time']-b_end))
            else:
                u = max(0, min(1, (t-(c_end-.6))/.6))
            distance = .58+.22*u*u
            target = eye_center+n*.081
            camera_pos = eye_center+n*distance
            lens = 50
            rotation = (target-camera_pos).to_track_quat('-Z', 'Y')
        elif t < d_end:
            u = (t-c_end)/(d_end-c_end)
            distance = near_eye_dist*math.exp(pull_k*(t-c_end))
            reveal_target = (root+qbody @ Vector((3.6, 0, .32))
                             if c.get('camera', {}).get('reveal_head_target')
                             else root+Vector((0, 0, .5)))
            target = (eye_center+n*.081).lerp(reveal_target, smooth(u))
            camera_pos = eye_center+n*distance-Vector((0, 0, c.get('camera', {}).get('reveal_drop', 8)*smooth(u)))
            lens = lerp(50, end_lens, smooth(u))
            rotation = (target-camera_pos).to_track_quat('-Z', 'Y')
            last_velocity = (camera_pos-last_cam)*fps if last_cam is not None else Vector((0, 0, 0))
            last_cam = camera_pos.copy()
            last_target = target.copy()
        elif not c.get('camera', {}).get('explicit_wide_cut', False):
            tau = t-d_end
            # Continue the outgoing camera velocity, then settle while the dragon banks.
            tau_cam = min(.9, tau+1/fps)
            camera_pos = last_cam+last_velocity*(tau_cam-tau_cam*tau_cam/(2*.9))
            target = last_target.lerp(circle_center+Vector((0, 0, 1)), smooth(tau/1.1))
            if circle_seconds-.9 < tau <= circle_seconds:
                target = target.lerp(root+Vector((0, 0, .5)), smooth((tau-circle_seconds+.9)/.9))
            if tau > circle_seconds:
                leave_blend = smooth((tau-circle_seconds)/(e_end-d_end-circle_seconds))
                retreat = Vector((-.62, -.78, .08)).normalized()
                camera_pos += retreat*c.get('camera', {}).get('departure_retreat', 0)*leave_blend
                right = Vector((circle_center.y-camera_pos.y, camera_pos.x-circle_center.x, 0)).normalized()
                target = root+Vector((0, 0, .5))-right*45*leave_blend-Vector((0, 0, 15*leave_blend))
            lens = lerp(end_lens, 30, smooth(tau/1.1))
            rotation = (target-camera_pos).to_track_quat('-Z', 'Y')
        else:
            # An editorial cut changes camera position/scale. No outgoing velocity
            # is carried across this explicitly separate shot.
            tau = t-d_end
            camera_pos = circle_root+Vector(c['camera']['wide_offset'])
            target = root+Vector((0, 0, .5))
            leave_blend = smooth((tau-circle_seconds)/(e_end-d_end-circle_seconds))
            long_shot_cut = tau >= circle_seconds and c['camera'].get('departure_shot_cut')
            if long_shot_cut:
                camera_pos = circle_root+Vector(c['camera']['departure_offset'])
            if tau > circle_seconds:
                camera_pos += Vector((-.62, -.78, .08)).normalized()*c['camera'].get('departure_retreat', 135)*leave_blend
                right = Vector((circle_center.y-camera_pos.y, camera_pos.x-circle_center.x, 0)).normalized()
                target -= right*45*leave_blend+Vector((0, 0, 15*leave_blend))
            lens = lerp(30 if long_shot_cut else c['camera'].get('wide_lens', 45), 30, leave_blend)
            rotation = (target-camera_pos).to_track_quat('-Z', 'Y')
        key(cam, frame, camera_pos, rotation)
        cam.data.lens = lens
        cam.data.keyframe_insert('lens', frame=frame)
        bpy.context.view_layer.update()
        uv = [world_to_camera_view(scene, cam, iris.matrix_world @ Vector(v))
              for v in [(-1, -1, 0), (-1, 1, 0), (1, -1, 0), (1, 1, 0)]]
        ir_bounds = [min(v.x for v in uv), min(v.y for v in uv), max(v.x for v in uv), max(v.y for v in uv)]
        e_uv = [world_to_camera_view(scene, cam, obj.matrix_world.translation) for obj in envelope]
        rows.append(dict(frame=i, seconds=t, camera=list(camera_pos), target=list(target), lens=lens,
                         adult_root=list(root), heading=list(heading), bank_radians=roll,
                         flight_angle=turn, iris_bounds=ir_bounds,
                         flight_envelope_bounds=[min(v.x for v in e_uv), min(v.y for v in e_uv),
                                                 max(v.x for v in e_uv), max(v.y for v in e_uv)],
                         nuzzle_displacement=nuzzle))
    for action in bpy.data.actions:
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for k in curve.keyframe_points:
                            k.interpolation = 'CONSTANT' if curve.data_path == 'hide_render' else 'LINEAR'
    scene.timeline_markers.clear()
    for name, t in times.items():
        scene.timeline_markers.new(name, frame=round(t*fps)+1)
    scene['本版用途'] = '简单几何摄影/轨迹预演；入眼汇聚由外部派生光学预览展示，不作精细角色或真实表情证明。'
    scene.frame_set(1)
    def validate():
        require_hash(cp, ch)
        require_hash(source, c['source_sha256'])
    digest = save_checked(bpy, dest, p, validate)
    write_json_new(report, dict(blend_sha256=digest, config_sha256=ch, source_sha256=c['source_sha256'],
                              fps=fps, frames=scene.frame_end, times=times,
                              flight=dict(radius=radius, speed=speed, circle_seconds=circle_seconds,
                                          bank_radians=bank), rows=rows,
                              limitation='No articulated anatomy or real facial surface. Iris and cheek markers are geometric intent only. Optical contraction is a separately bound derived preview.'), p)
    stills.mkdir(parents=True)
    scene.render.resolution_percentage = 50
    for t in [0, 1, 2, 3.5, 4.1, 6, 8, 9.958, 10, 11, 12, 13.958, 14, 15, 16, 17.958, 18, 20, 22, 24, 26.5, 28, 29.958]:
        frame = min(scene.frame_end, round(t*fps)+1)
        scene.frame_set(frame)
        render_still_new(bpy, stills/f'收尾白模-帧{frame:03d}.png', p)
    print(json.dumps({'blend': str(dest), 'sha256': digest, 'frames': scene.frame_end, 'seconds': e_end}, ensure_ascii=False))


if __name__ == '__main__':
    main()
