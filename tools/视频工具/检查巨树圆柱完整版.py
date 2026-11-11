"""Inspect the saved full-story proxies; do not infer articulated performance."""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import read_json_bound, require_hash
from whitebox_saved import load_saved, project_path, write_json_new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True)
    ap.add_argument('--config', required=True)
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
    p = Path(a.project).resolve()
    cp = project_path(p, a.config, exists=True)
    c, ch = read_json_bound(cp)
    rep = json.loads(project_path(p, c['report'], exists=True).read_text('utf-8'))
    blend = project_path(p, c['output_blend'], exists=True)
    load_saved(bpy, str(blend), rep['blend_sha256'])
    scene = bpy.context.scene
    girl = bpy.data.objects['圆柱-女孩占位']
    dragon = bpy.data.objects['圆柱-幼龙占位']
    tree = bpy.data.objects['巨树-主干']
    bvh = BVHTree.FromPolygons([tree.matrix_world @ v.co for v in tree.data.vertices],
                              [list(x.vertices) for x in tree.data.polygons])
    rows = []
    for i in range(600):
        scene.frame_set(i + 1)
        dg = bpy.context.evaluated_depsgraph_get()
        g = girl.evaluated_get(dg)
        d = dragon.evaluated_get(dg)
        root = g.matrix_world.translation - g.matrix_world.to_quaternion() @ Vector((0, 0, .65))
        verts = [d.matrix_world @ v.co for v in d.data.vertices]
        gap = min(bvh.find_nearest(v)[3] for v in verts)
        cheek = (bpy.data.objects['女孩-面颊参照'].matrix_world.translation -
                 bpy.data.objects['幼龙-面颊参照'].matrix_world.translation).length
        rows.append({'seconds': i / 24, 'girl_root': list(root),
                     'dragon': list(d.matrix_world.translation), 'gap': gap,
                     'cheek_distance': cheek, 'girl_scale': list(g.scale),
                     'dragon_scale': list(d.scale)})
    wait = rows[156:320]
    drift = max((Vector(r['girl_root']) - Vector(wait[0]['girl_root'])).length for r in wait)
    if drift > 1e-5:
        raise ValueError(f'Girl moves during wait/laugh: {drift}')
    tree_rows = rows[:320]
    if max(r['dragon'][2] for r in tree_rows) - min(r['dragon'][2] for r in tree_rows) > 1e-5:
        raise ValueError('Dragon climbs vertically before flight')
    phases = [math.atan2(r['dragon'][1], r['dragon'][0]) for r in rows[156:253]]
    turn = sum((b-a+math.pi) % (2*math.pi)-math.pi for a, b in zip(phases, phases[1:]))
    if abs(turn - 2*math.pi) > 1e-5:
        raise ValueError(f'Additional lap is incomplete: {turn}')
    base_scale = rows[0]['girl_scale'] + rows[0]['dragon_scale']
    for r in rows:
        if max(abs(x-y) for x, y in zip(r['girl_scale'] + r['dragon_scale'], base_scale)) > 1e-5:
            raise ValueError('Proxy scales change')
    if max(r['cheek_distance'] for r in rows[512:]) > 1e-5:
        raise ValueError('Conceptual cheek targets do not meet')
    # The held baby travels around the same fixed root; unwrap its polar offset.
    spin_rows = rows[389:462]
    phases = [math.atan2(r['dragon'][1]-r['girl_root'][1], r['dragon'][0]-r['girl_root'][0]) for r in spin_rows]
    spin = sum((b-a+math.pi) % (2*math.pi)-math.pi for a, b in zip(phases, phases[1:]))
    if abs(spin-2*math.pi) > .01:
        raise ValueError(f'Shared spin differs from one turn: {spin}')
    require_hash(cp, ch)
    require_hash(blend, rep['blend_sha256'])
    result = {'status': 'passed_proxy_spatial_timing_only', 'blend_sha256': rep['blend_sha256'],
              'wait_root_drift': drift, 'extra_circuit_radians': turn,
              'hug_spin_radians': spin, 'tree_center_height': rows[0]['dragon'][2],
              'tree_surface_gap_range': [min(r['gap'] for r in tree_rows), max(r['gap'] for r in tree_rows)],
              'limitation': 'No anatomical paws, wings, arms or faces. Cheek empties are conceptual targets, not actual facial contact.',
              'rows': rows}
    write_json_new(project_path(p, '05-检查与验收/完整06-独立轨迹检查.json'), result, p)
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
