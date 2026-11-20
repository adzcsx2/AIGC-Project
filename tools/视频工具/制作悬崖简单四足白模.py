"""Build a primitive quadruped silhouette in the previous guide's unchanged shot."""
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import save_checked
from whitebox_saved import write_json_new

P = Path(__file__).resolve().parents[2] / 'projects/悬崖上的小气球'
source = Path(bpy.data.filepath)
assert hashlib.sha256(source.read_bytes()).hexdigest() == 'ee46f566c8c9aade92cfdfbb708e2d81ca3eca289b873797b16be7938d153025'
s = bpy.context.scene
parent = s.objects['GULU-ROOT']
for o in list(s.objects):
    if o.type == 'MESH' and o.name.startswith('GULU-'):
        bpy.data.objects.remove(o, do_unlink=True)

def make(name, kind, size):
    if kind == 'sphere':
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12)
    elif kind == 'cylinder':
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=1, depth=2)
    elif kind == 'cone':
        bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=1, radius2=0.08, depth=2)
    else:
        bpy.ops.mesh.primitive_cube_add(size=2)
    o = bpy.context.object
    o.name = name
    o.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.parent = parent
    o.color = (0.92, 0.52, 0.12, 1)
    return o

def position(o, value, frame):
    o.location = value
    o.keyframe_insert('location', frame=frame)

def link(o, a, b, frame):
    a, b = Vector(a), Vector(b)
    position(o, (a + b) / 2, frame)
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = (b - a).to_track_quat('Z', 'Y')
    o.keyframe_insert('rotation_quaternion', frame=frame)

base = 0.52
body = make('GULU-horizontal-torso', 'sphere', (0.14, 0.075, 0.07))
head = make('GULU-head-envelope', 'sphere', (0.06, 0.06, 0.06))
neck = make('GULU-short-neck', 'sphere', (0.045, 0.05, 0.045))
muzzle = make('GULU-right-facing-muzzle', 'cube', (0.04, 0.04, 0.024))
tail = make('GULU-left-pointing-tail', 'cone', (0.026, 0.026, 0.12))
tail.rotation_mode = 'QUATERNION'
tail.rotation_quaternion = Vector((-1, 0, -0.06)).to_track_quat('Z', 'Y')
legs = []
for index, (dx, dy) in enumerate([(-0.06, -0.0325), (-0.05, 0.0325), (0.06, -0.0325), (0.05, 0.0325)]):
    foot = Vector((base + dx, dy, 0.01))
    paw = make(f'GULU-paw-{index}', 'cube', (0.028, 0.02, 0.01))
    paw.location = (foot.x, foot.y, 0.005)
    upper = make(f'GULU-leg-{index}-upper', 'cylinder', (0.012, 0.012, 0.063))
    lower = make(f'GULU-leg-{index}-lower', 'cylinder', (0.012, 0.012, 0.063))
    legs.append((dx, dy, foot, upper, lower))
for frame in range(1, 121):
    t = (frame - 1) / 24
    u = max(0, min(1, (t - 1.2) / 0.6))
    q = u * u * (3 - 2 * u)
    z = 0.04 + 0.10 * q
    position(body, (base, 0, z), frame)
    position(head, (base + 0.095, 0, z + 0.03), frame)
    position(neck, (base + 0.065, 0, z + 0.018), frame)
    position(muzzle, (base + 0.13, 0, z + 0.018), frame)
    position(tail, (base - 0.12, 0, z - 0.002), frame)
    for dx, dy, foot, upper, lower in legs:
        hip = Vector((base + dx, dy, z - 0.014))
        midpoint = (hip + foot) / 2
        bend = math.sqrt(0.063 ** 2 - ((hip - foot).length / 2) ** 2)
        knee = midpoint + Vector((bend if dx > 0 else -bend, 0, 0))
        link(upper, hip, knee, frame)
        link(lower, knee, foot, frame)
for o in s.objects:
    if o.name.startswith('GULU-') and o.animation_data and o.animation_data.action:
        for layer in o.animation_data.action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:
                            key.interpolation = 'LINEAR'
s.timeline_markers[0].name = 'POSE-CONTROL14'
s.frame_set(1)
dest = P / '03-制作/三维工程/姿态高度对照14-简单四足十至二十厘米01.blend'
def validate():
    assert len(bpy.data.images) == 0
    assert s.render.fps == 24 and s.frame_start == 1 and s.frame_end == 120
digest = save_checked(bpy, dest, P, validate)
write_json_new(P / '05-检查与验收/姿态高度对照14-白模构建01.json', {
    'source_blend': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'blend': dest.relative_to(P).as_posix(), 'sha256': digest,
    'geometry': 'horizontal ellipsoid torso, sphere head envelope, short ellipsoid neck, box muzzle, four two-cylinder legs with box paws, cone tail',
    'torso_dimensions_m': [0.14, 0.075, 0.07], 'head_diameter_m': 0.06,
    'crouched_height_m': 0.1, 'standing_height_m': 0.2,
    'rise_seconds': [1.2, 1.8], 'girl_camera_and_clock_unchanged': True,
    'changed_variable': 'quadruped proxy geometry and its supported articulation, plus necessary prompt mapping words only',
    'mechanism': 'horizontal back, head/muzzle to screen-right, tail left; four planted paws; constant geometry and no root travel'
}, P)
print('Saved primitive quadruped guide; original girl, camera and clock retained.')
