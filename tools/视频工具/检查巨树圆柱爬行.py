"""Read-only verification of the saved climbing proxy and preserved tracks."""
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


def matrix_values(obj):
    return [value for row in obj.matrix_world for value in row]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--config', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    project = Path(args.project).resolve()
    cp = project_path(project, args.config, exists=True)
    config, config_hash = read_json_bound(cp)
    report = json.loads(project_path(project, config['report'], exists=True).read_text('utf-8'))
    source = project_path(project, config['source_blend'], exists=True)
    load_saved(bpy, str(source), config['source_sha256'])
    tracks = []
    for frame in range(1, config['frames'] + 1):
        bpy.context.scene.frame_set(frame)
        tracks.append((matrix_values(bpy.data.objects['圆柱-女孩占位']),
                       matrix_values(bpy.context.scene.camera), bpy.context.scene.camera.data.lens))
    saved = project_path(project, config['output_blend'], exists=True)
    load_saved(bpy, str(saved), report['blend_sha256'])
    rows = []
    for index, (girl, camera, lens) in enumerate(tracks):
        scene = bpy.context.scene
        scene.frame_set(index + 1)
        marker = bpy.data.objects['圆柱-幼龙占位']
        tree = bpy.data.objects['巨树-主干']
        evaluated = tree.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        bvh = BVHTree.FromPolygons([evaluated.matrix_world @ v.co for v in mesh.vertices],
                                  [list(p.vertices) for p in mesh.polygons])
        evaluated.to_mesh_clear()
        world_vertices = [marker.matrix_world @ v.co for v in marker.data.vertices]
        world_vertices.extend(marker.matrix_world @ ((marker.data.vertices[e.vertices[0]].co + marker.data.vertices[e.vertices[1]].co) / 2) for e in marker.data.edges)
        nearest = min(bvh.find_nearest(v)[3] for v in world_vertices)
        world_height = max(v.z for v in world_vertices) - min(v.z for v in world_vertices)
        pursuit = config.get('pursuit')
        girl_obj = bpy.data.objects['圆柱-女孩占位']
        preserved = True if pursuit else max(abs(a-b) for a,b in zip(girl, matrix_values(girl_obj))) < 1e-6
        preserved &= max(abs(a-b) for a,b in zip(camera, matrix_values(scene.camera))) < 1e-6
        preserved &= abs(lens - scene.camera.data.lens) < 1e-6
        expected_height = config.get('world_body_height', .30)
        if not preserved or not 0 <= nearest <= .012 or abs(world_height - expected_height) > 1e-6:
            raise ValueError(f'Saved-scene proxy verification failed at {index + 1}: distance={nearest}, height={world_height}')
        rows.append(dict(frame=index+1, center_z=marker.matrix_world.translation.z,
                         marker_height=world_height, surface_distance=nearest,
                         camera_unchanged=bool(preserved), girl_center=list(girl_obj.matrix_world.translation),
                         dragon_center=list(marker.matrix_world.translation),
                         forward_axis=list(marker.matrix_world.to_quaternion() @ Vector((0, 0, 1)))))
    vertical = rows[-1]['center_z'] - rows[0]['center_z']
    expected_vertical = config['center_z_end'] - config['center_z_start']
    if abs(vertical - expected_vertical) > 1e-6:
        raise ValueError('Vertical motion differs from the configured path')
    if expected_vertical == 0:
        if max(r['center_z'] for r in rows) - min(r['center_z'] for r in rows) > 1e-6:
            raise ValueError('Horizontal orbit must stay at the same height')
    elif any(b['center_z'] <= a['center_z'] for a,b in zip(rows, rows[1:])):
        raise ValueError('Vertical climb must rise continuously')
    require_hash(cp, config_hash)
    require_hash(saved, report['blend_sha256'])
    output = project_path(project, config.get('inspection_report', '05-检查与验收/圆柱贴树爬行02-独立工程检查.json'))
    pursuit_measurement = None
    if config.get('pursuit'):
        speeds = []
        for a, b in zip(rows, rows[1:]):
            girl_speed = (Vector(b['girl_center']) - Vector(a['girl_center'])).length * 24
            dragon_speed = (Vector(b['dragon_center']) - Vector(a['dragon_center'])).length * 24
            if dragon_speed <= girl_speed:
                raise ValueError('Dragon must travel faster than the girl throughout the test')
            speeds.append((girl_speed, dragon_speed))
        def phase_track(key):
            values = [math.atan2(r[key][1], r[key][0]) for r in rows]
            result = [values[0]]
            for a, b in zip(values, values[1:]):
                result.append(result[-1] + ((b - a + math.pi) % (2 * math.pi) - math.pi))
            return result
        girl_phase = phase_track('girl_center')
        dragon_phase = phase_track('dragon_center')
        leads = [b-a for a,b in zip(girl_phase, dragon_phase)]
        if any(b <= a for a,b in zip(girl_phase, girl_phase[1:])) or any(b <= a for a,b in zip(dragon_phase, dragon_phase[1:])):
            raise ValueError('Both actors must orbit counterclockwise when viewed from above')
        if config.get('orientation') == 'horizontal_tangent':
            for row in rows:
                x, y, z = row['dragon_center']
                theta = math.atan2(y, x)
                tangent = Vector((-math.sin(theta), math.cos(theta), 0))
                if Vector(row['forward_axis']).dot(tangent) < .99999:
                    raise ValueError('Dragon proxy must point tangentially along its orbit')
            front_angle = math.atan2(scene.camera.matrix_world.translation.y, scene.camera.matrix_world.translation.x)
            front_tangent = Vector((-math.sin(front_angle), math.cos(front_angle), 0))
            camera_right = scene.camera.matrix_world.to_quaternion() @ Vector((1, 0, 0))
            if front_tangent.dot(camera_right) <= 0:
                raise ValueError('Near-side counterclockwise travel must move screen-right')
        distances = [(Vector(r['girl_center'])-Vector(r['dragon_center'])).length for r in rows]
        if min(leads) <= 0 or max(leads) >= 6.283185307179586:
            raise ValueError('Dragon must lead without lapping or passing the girl')
        pursuit_measurement = dict(girl_speed_min=min(s[0] for s in speeds), girl_speed_max=max(s[0] for s in speeds),
                                   dragon_speed_min=min(s[1] for s in speeds), dragon_speed_max=max(s[1] for s in speeds),
                                   lead_radians_start=leads[0], lead_radians_end=leads[-1],
                                   girl_revolutions=(girl_phase[-1]-girl_phase[0])/(2*math.pi),
                                   dragon_revolutions=(dragon_phase[-1]-dragon_phase[0])/(2*math.pi),
                                   direction='counterclockwise_from_above_front_side_screen_right',
                                   minimum_center_separation=min(distances))
    result = dict(status='passed_for_proxy_geometry_only', blend_sha256=report['blend_sha256'],
                  vertical_travel=vertical, girl_height=bpy.data.objects['圆柱-女孩占位'].dimensions.z,
                  minimum_surface_distance=min(r['surface_distance'] for r in rows),
                  maximum_surface_distance=max(r['surface_distance'] for r in rows), pursuit=pursuit_measurement, rows=rows,
                  limitation='No claws or articulated motion in proxy; generated anatomy and climbing must be reviewed separately.')
    write_json_new(output, result, project)
    print(json.dumps({k:v for k,v in result.items() if k != 'rows'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
