"""Independently reload the saved ending and measure circle, camera and projections."""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import read_json_bound, require_hash
from whitebox_saved import load_saved, project_path, write_json_new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True)
    ap.add_argument('--config', required=True)
    a = ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    p = Path(a.project).resolve()
    cp = project_path(p, a.config, exists=True)
    c, ch = read_json_bound(cp)
    produced = json.loads(project_path(p, c['report'], exists=True).read_text('utf-8'))
    blend = project_path(p, c['output_blend'], exists=True)
    scene = load_saved(bpy, str(blend), produced['blend_sha256'])
    adult = bpy.data.objects['圆柱-成年巨龙占位']
    iris = bpy.data.objects['龙眼-虹膜圆片']
    pupil = bpy.data.objects['龙眼-瞳孔标记']
    girl = bpy.data.objects['圆柱-女孩占位']
    objects = [adult, girl, bpy.data.objects['圆柱-幼龙占位']]
    scale0 = [tuple(x.scale) for x in objects]
    vertices, polygons = [], []
    for obj in scene.objects:
        if obj.name.startswith('巨树-') and obj.type == 'MESH':
            offset = len(vertices)
            vertices.extend(obj.matrix_world @ v.co for v in obj.data.vertices)
            polygons.extend([offset+i for i in poly.vertices] for poly in obj.data.polygons)
    tree = BVHTree.FromPolygons(vertices, polygons)
    samples, blocked = [], []
    for i in range(scene.frame_end):
        scene.frame_set(i+1)
        graph = bpy.context.evaluated_depsgraph_get()
        camera = scene.camera.evaluated_get(graph)
        def bounds(obj):
            obj = obj.evaluated_get(graph)
            uv = [world_to_camera_view(scene, camera, obj.matrix_world @ Vector(v)) for v in obj.bound_box]
            return [min(v.x for v in uv), min(v.y for v in uv), max(v.x for v in uv), max(v.y for v in uv)]
        env = [bpy.data.objects[f'巨龙-展开边界{j:02d}'].evaluated_get(graph).matrix_world.translation for j in range(8)]
        uv = [world_to_camera_view(scene, camera, v) for v in env]
        env_bounds = [min(v.x for v in uv), min(v.y for v in uv), max(v.x for v in uv), max(v.y for v in uv)]
        if i >= 432 and (min(env_bounds[:2]) < .015 or max(env_bounds[2:]) > .985):
            raise ValueError(f'Flight extent cropped at {i}: {env_bounds}')
        for obj, original in zip(objects, scale0):
            if max(abs(x-y) for x, y in zip(obj.scale, original)) > 1e-6:
                raise ValueError('An actor changes physical size')
        if i < 240:
            point = bpy.data.objects['女孩-面颊参照'].matrix_world.translation
            origin = camera.matrix_world.translation
            delta = point-origin
            hit = tree.ray_cast(origin, delta.normalized(), delta.length-.015)[0]
            if hit is not None:
                blocked.append(i)
        samples.append({'frame': i, 'seconds': i/24,
                        'camera': list(camera.matrix_world.translation),
                        'camera_quaternion': list(camera.matrix_world.to_quaternion()),
                        'adult_root': list(adult.matrix_world.translation),
                        'adult_forward': list(adult.matrix_world.to_quaternion() @ Vector((0, 0, 1))),
                        'iris_bounds': bounds(iris), 'pupil_bounds': bounds(pupil),
                        'girl_bounds': bounds(girl) if i < 240 else None,
                        'flight_envelope_bounds': env_bounds})
    circle_end = 432+round(c['flight']['circle_seconds']*24)
    circle = samples[432:circle_end+1]
    center = Vector(circle[0]['adult_root'])+Vector((0, c['flight']['radius'], 0))
    phases = [math.atan2(r['adult_root'][1]-center.y, r['adult_root'][0]-center.x) for r in circle]
    angle = sum((b-a+math.pi) % (2*math.pi)-math.pi for a, b in zip(phases, phases[1:]))
    if abs(angle-2*math.pi) > 1e-5:
        raise ValueError(f'The adult does not fly one complete circuit: {angle}')
    radial_error = max(abs((Vector(r['adult_root'])-center).length-c['flight']['radius']) for r in circle)
    if radial_error > 1e-4:
        raise ValueError('Flight path leaves its authored circle')
    if blocked:
        raise ValueError(f'Trunk/crown blocks the cheek target in frames: {blocked[:20]}')
    last_girl = samples[239]['girl_bounds']
    if last_girl[3]-last_girl[1] > .006:
        raise ValueError('The aerial endpoint does not reduce the girl to a speck')
    final_env = samples[-1]['flight_envelope_bounds']
    if final_env[2]-final_env[0] > .12:
        raise ValueError('The adult is still too large at the departure endpoint')
    camera_cuts = []
    if c.get('camera', {}).get('explicit_wide_cut'):
        cut_frame = round(c['times']['reveal_end']*24)
        displacement = (Vector(samples[cut_frame]['camera'])-Vector(samples[cut_frame-1]['camera'])).length
        if displacement < 20:
            raise ValueError('The authored head-to-wide camera cut is not visible in saved transforms')
        camera_cuts.append({'frame': cut_frame, 'seconds': cut_frame/24,
                            'camera_jump_metres': displacement, 'intent': 'head_closeup_to_rear_wide'})
        if c['camera'].get('departure_shot_cut'):
            cut_frame = round((c['times']['reveal_end']+c['flight']['circle_seconds'])*24)
            displacement = (Vector(samples[cut_frame]['camera'])-Vector(samples[cut_frame-1]['camera'])).length
            if displacement < 20:
                raise ValueError('The authored post-circuit long-shot cut is not present')
            camera_cuts.append({'frame': cut_frame, 'seconds': cut_frame/24,
                                'camera_jump_metres': displacement, 'intent': 'completed_circle_to_departure_longshot'})
    require_hash(cp, ch)
    require_hash(blend, produced['blend_sha256'])
    result = {'status': 'passed_for_spatial_camera_proxies_only', 'blend_sha256': produced['blend_sha256'],
              'camera_cuts': camera_cuts,
              'circle_radians': angle, 'circle_radial_max_error': radial_error,
              'trunk_crown_occluded_frames': blocked,
              'girl_aerial_projected_height': last_girl[3]-last_girl[1],
              'adult_final_envelope_width': final_env[2]-final_env[0],
              'samples': samples,
              'limitations': ['No real face, arm, paw or wing articulation.',
                              'Tree ray test concerns the conceptual cheek target, not all anatomy or every set object.',
                              'Optical contraction must be checked in the separately derived preview.']}
    output = project_path(p, c['independent_report'])
    write_json_new(output, result, p)
    print(json.dumps({k: v for k, v in result.items() if k not in {'samples', 'limitations'}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
