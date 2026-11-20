"""Independently reload and compare the old and new shot, then measure all frames."""
import hashlib
import json
from pathlib import Path

import bpy
from mathutils import Vector

P = Path(__file__).resolve().parents[2] / 'projects/悬崖上的小气球'
target = Path(bpy.data.filepath)
source = P / '03-制作/三维工程/姿态高度对照13-十至二十厘米01.blend'

def retained_state(scene):
    result = []
    for name in ['MIA-ROOT', 'MIA-body-cylinder', 'MIA-head-end-marker', 'Camera-fixed']:
        o = scene.objects[name]
        result.append([name, [v for row in o.matrix_world for v in row], list(o.scale)])
        if o.type == 'MESH':
            result.append([tuple(v.co) for v in o.data.vertices])
    c = scene.camera.data
    result.append([c.type, c.ortho_scale, c.lens, c.clip_start, c.clip_end])
    result.append([scene.render.fps, scene.render.fps_base, scene.frame_start, scene.frame_end,
                   scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage])
    return hashlib.sha256(json.dumps(result).encode()).hexdigest()

bpy.ops.wm.open_mainfile(filepath=str(source))
baseline = {}
for frame in range(1, 121):
    bpy.context.scene.frame_set(frame)
    baseline[frame] = retained_state(bpy.context.scene)
bpy.ops.wm.open_mainfile(filepath=str(target))
s = bpy.context.scene
rows = []
reference = None
feet = None
for frame in range(1, 121):
    s.frame_set(frame)
    assert retained_state(s) == baseline[frame], 'Girl, camera or clock changed'
    parts = [o for o in s.objects if o.name.startswith('GULU-') and o.type == 'MESH']
    graph = bpy.context.evaluated_depsgraph_get()
    signatures = []
    points = []
    paws = []
    for o in parts:
        e = o.evaluated_get(graph)
        mesh = e.to_mesh()
        signatures.append((o.name, hashlib.sha256(json.dumps([tuple(v.co) for v in mesh.vertices]).encode()).hexdigest()))
        points.extend(e.matrix_world @ v.co for v in mesh.vertices)
        e.to_mesh_clear()
        assert max(abs(a - 1) for a in o.scale) < 1e-6
        if o.name.startswith('GULU-paw-'):
            paws.append((o.name, tuple(o.location)))
            assert abs(o.location.z - 0.005) < 1e-6
        if o.name.startswith('GULU-leg-'):
            length = (e.matrix_world @ Vector((0, 0, 0.0315)) - e.matrix_world @ Vector((0, 0, -0.0315))).length
            assert abs(length - 0.063) < 1e-6
    if reference is None:
        reference = signatures
        feet = paws
    assert signatures == reference and paws == feet and len(paws) == 4
    body = s.objects['GULU-horizontal-torso']
    head = s.objects['GULU-head-envelope']
    muzzle = s.objects['GULU-right-facing-muzzle']
    tail = s.objects['GULU-left-pointing-tail']
    assert abs(body.location.x - 0.52) < 1e-6 and abs(body.location.y) < 1e-6
    assert max(abs(a) for a in body.rotation_euler) < 1e-6
    assert muzzle.location.x > head.location.x > body.location.x > tail.location.x
    assert abs((head.location - body.location).length - Vector((0.095, 0, 0.03)).length) < 1e-6
    low, high = min(v.z for v in points), max(v.z for v in points)
    t = (frame - 1) / 24
    u = max(0, min(1, (t - 1.2) / 0.6))
    expected = 0.1 + 0.1 * u * u * (3 - 2 * u)
    assert abs(low) < 1e-6 and abs((high - low) - expected) < 1e-6
    rows.append({'frame': frame, 'seconds': t, 'whole_height_m': high - low,
                 'body_center_z': body.location.z, 'head_center_z': head.location.z, 'lowest_paw_z': low})
assert len(bpy.data.images) == 0
result = {'source_blend': str(target), 'source_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
          'baseline_blend': str(source), 'baseline_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'checks_passed': True, 'frames_measured': 120, 'rest_height_m': rows[0]['whole_height_m'],
          'stand_height_m': rows[-1]['whole_height_m'], 'constant_primitive_geometry_and_scale': True,
          'constant_leg_segments_m': 0.063, 'fixed_four_paws': True, 'horizontal_back': True,
          'head_muzzle_screen_right_tail_left': True, 'girl_camera_and_clock_identical_to13': True,
          'images_count': 0, 'rise_seconds': [1.2, 1.8],
          'max_body_vertical_speed_mps': max(abs(b['body_center_z'] - a['body_center_z']) * 24 for a, b in zip(rows, rows[1:])),
          'mechanism': 'supported leg unfolding with a horizontal torso, no jump or scaling', 'samples': rows}
out = P / '05-检查与验收/姿态高度对照14-独立几何与速度01.json'
assert not out.exists()
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'samples'}, ensure_ascii=False))
