"""Revise only the small spatial marker into a bark-contact climbing path."""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import read_json_bound, require_hash, save_checked
from whitebox_saved import load_saved, project_path, render_still_new, write_json_new


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--config', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    project = Path(args.project).resolve()
    config_path = project_path(project, args.config, exists=True)
    config, config_hash = read_json_bound(config_path)
    source = project_path(project, config['source_blend'], exists=True)
    destination = project_path(project, config['output_blend'])
    report = project_path(project, config['report'])
    stills = project_path(project, config['stills'])
    for target in (destination, report, stills):
        if target.exists():
            raise FileExistsError(target)
    load_saved(bpy, str(source), config['source_sha256'])
    scene = bpy.context.scene
    scene.frame_set(1)
    marker = bpy.data.objects['圆柱-幼龙占位']
    marker.animation_data_clear()
    girl = bpy.data.objects['圆柱-女孩占位']
    pursuit = config.get('pursuit')
    if pursuit:
        girl.animation_data_clear()
    marker.dimensions = (2 * config['radius'], 2 * config['radius'], config['height'])
    bpy.context.view_layer.update()
    tree = bpy.data.objects['巨树-主干']
    evaluated = tree.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    vertices = [evaluated.matrix_world @ v.co for v in mesh.vertices]
    bvh = BVHTree.FromPolygons(vertices, [list(p.vertices) for p in mesh.polygons])
    evaluated.to_mesh_clear()
    rows = []
    horizontal = config.get('orientation') == 'horizontal_tangent'
    for index in range(config['frames']):
        frame = index + 1
        scene.frame_set(frame)
        u = index / (config['frames'] - 1)
        # Equal endpoints produce a horizontal band; unequal endpoints allow a climb.
        progress = u + 0.018 * math.sin(8 * math.pi * u)
        angle = math.radians(config['angle_start'] + (config['angle_end'] - config['angle_start']) * u)
        radial = Vector((math.cos(angle), math.sin(angle), 0))
        center_z = config['center_z_start'] + (config['center_z_end'] - config['center_z_start']) * progress
        supports = []
        # The trunk tapers. Use its actual evaluated surface, not nominal radius.
        vertical_half = config['radius'] if horizontal else config['height'] / 2
        for offset in (-vertical_half, 0, vertical_half):
            z = center_z + offset
            hit, normal, face, distance = bvh.ray_cast(radial * 3 + Vector((0, 0, z)), -radial, 5)
            if hit is None:
                raise ValueError('No trunk surface at climbing marker height')
            supports.append((hit.dot(radial), offset, list(hit)))
        surface_radius, support_offset, hit = max(supports)
        marker.location = radial * (surface_radius + config['radius'] + config['surface_clearance']) + Vector((0, 0, center_z))
        if horizontal:
            tangent = Vector((-math.sin(angle), math.cos(angle), 0))
            marker.rotation_mode = 'QUATERNION'
            marker.rotation_quaternion = Matrix((radial, Vector((0, 0, -1)), tangent)).transposed().to_quaternion()
        else:
            marker.rotation_mode = 'XYZ'
            marker.rotation_euler = (0, 0, angle)
        marker.keyframe_insert('location', frame=frame)
        marker.keyframe_insert('rotation_quaternion' if horizontal else 'rotation_euler', frame=frame)
        if pursuit:
            girl_angle = math.radians(pursuit['angle_start']) + pursuit['angular_travel'] * u
            girl.location = (pursuit['radius'] * math.cos(girl_angle),
                             pursuit['radius'] * math.sin(girl_angle), .65)
            girl.keyframe_insert('location', frame=frame)
        bpy.context.view_layer.update()
        nearest = []
        contact_samples = [v.co.copy() for v in marker.data.vertices]
        contact_samples.extend((marker.data.vertices[e.vertices[0]].co + marker.data.vertices[e.vertices[1]].co) / 2 for e in marker.data.edges)
        for local in contact_samples:
            world = marker.matrix_world @ local
            contact, normal, polygon, distance = bvh.find_nearest(world)
            nearest.append((distance, list(world), list(contact)))
        actual_distance, marker_contact, trunk_contact = min(nearest)
        rows.append(dict(frame=frame, seconds=index / 24, center=list(marker.location),
                         angle_degrees=math.degrees(angle), trunk_contact=trunk_contact,
                         marker_contact=marker_contact, sampled_surface_distance=actual_distance,
                         support_clearance=config['surface_clearance'],
                         girl_center=list(girl.location),
                         angular_lead=(angle - girl_angle) if pursuit else None))
    for action in bpy.data.actions:
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:
                            key.interpolation = 'LINEAR'
    scene['圆柱测试用途'] = config.get('description', '女孩路径和相机沿用测试01；幼龙小圆柱保持30厘米高，贴实际树干表面从低处斜向爬高。圆柱不提供步态或爪部骨骼。')
    scene.frame_set(1)

    def validate():
        require_hash(config_path, config_hash)
        require_hash(source, config['source_sha256'])

    destination.parent.mkdir(parents=True, exist_ok=True)
    stills.mkdir(parents=True)
    digest = save_checked(bpy, destination, project, validate)
    write_json_new(report, dict(source_sha256=config['source_sha256'], config_sha256=config_hash,
                               blend_sha256=digest, radius=config['radius'], height=config['height'],
                               vertical_travel=config['center_z_end'] - config['center_z_start'], rows=rows), project)
    scene.render.resolution_percentage = 50
    for frame in (1, 25, 49, 73, 97, 120):
        scene.frame_set(frame)
        render_still_new(bpy, stills / f'贴树爬行-帧{frame:03d}.png', project)
    validate()
    print(json.dumps(dict(blend=str(destination), sha256=digest, vertical_travel=config['center_z_end'] - config['center_z_start']), ensure_ascii=False))


if __name__ == '__main__':
    main()
