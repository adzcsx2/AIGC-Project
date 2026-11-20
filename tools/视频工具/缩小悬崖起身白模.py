"""Derive a half-size dragon guide while preserving the girl, camera and clock."""
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import save_checked
from whitebox_saved import write_json_new

P = Path(__file__).resolve().parents[2] / 'projects/悬崖上的小气球'
source = Path(bpy.data.filepath)
assert hashlib.sha256(source.read_bytes()).hexdigest() == 'b446bbcc7cb25bec17036c2eaf0446d14a5010b9d6721e10d713d366a4019e38'
s = bpy.context.scene
parts = [o for o in s.objects if o.name.startswith('GULU-') and o.type == 'MESH']
pivot = Vector((0.52, 0, 0))
poses = {}
for frame in range(1, 121):
    s.frame_set(frame)
    poses[frame] = {o.name: (o.location.copy(), o.rotation_quaternion.copy()) for o in parts}
for o in parts:
    assert o.parent.name == 'GULU-ROOT' and max(abs(a - 1) for a in o.scale) < 1e-6
    o.animation_data_clear()
    for v in o.data.vertices:
        v.co *= 0.5
for frame in range(1, 121):
    for o in parts:
        location, rotation = poses[frame][o.name]
        o.location = pivot + (location - pivot) * 0.5
        o.keyframe_insert('location', frame=frame)
        if o.rotation_mode == 'QUATERNION':
            o.rotation_quaternion = rotation
            o.keyframe_insert('rotation_quaternion', frame=frame)
for o in parts:
    for layer in o.animation_data.action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:
                        key.interpolation = 'LINEAR'
s.objects['GULU-20cm-body-ball'].name = 'GULU-10cm-body-ball'
s.timeline_markers[0].name = 'POSE-CONTROL13'
s.frame_set(1)
dest = P / '03-制作/三维工程/姿态高度对照13-十至二十厘米01.blend'
def validate():
    assert len(bpy.data.images) == 0
    assert s.render.fps == 24 and s.frame_start == 1 and s.frame_end == 120
digest = save_checked(bpy, dest, P, validate)
write_json_new(P / '05-检查与验收/姿态高度对照13-白模构建01.json', {
    'source_blend': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'blend': dest.relative_to(P).as_posix(), 'sha256': digest,
    'dragon_linear_scale_relative_to_previous': 0.5,
    'crouched_height_m': 0.1, 'standing_height_m': 0.2, 'body_sphere_diameter_m': 0.1,
    'rise_seconds': [1.2, 1.8], 'girl_and_camera_unchanged': True,
    'method': 'Scale dragon mesh coordinates and baked location paths around its planted base; object scales remain one; no time resampling.'
}, P)
print('Saved new 10-to-20 cm dragon guide; original project preserved.')
