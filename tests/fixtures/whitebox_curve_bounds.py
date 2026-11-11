"""Blender regression: curve framing must use the rendered evaluated geometry."""

import importlib.util
from pathlib import Path

import bpy
from mathutils import Vector

root = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "curve_bounds_worker", root / "tools/视频工具/whitebox_blender.py"
)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
bpy.ops.wm.read_factory_settings(use_empty=True)
curve = bpy.data.curves.new("short_bevelled_mouth", "CURVE")
curve.dimensions = "3D"
curve.bevel_depth = 0.008
spline = curve.splines.new("BEZIER")
spline.bezier_points.add(2)
for point, co in zip(
    spline.bezier_points,
    [(-0.16, -0.322, -0.102), (0, -0.369, -0.113), (0.16, -0.322, -0.102)],
    strict=True,
):
    point.co = co
    point.handle_left_type = point.handle_right_type = "AUTO"
obj = bpy.data.objects.new("mouth", curve)
bpy.context.scene.collection.objects.link(obj)
obj.rotation_euler = (0.9, 0.4, 0.2)
obj.location = (0.2, -0.1, 0.5)
for frame, offset in [(1, 0), (2, 0.6)]:
    spline.bezier_points[1].co.z = -0.113 + offset
    spline.bezier_points[1].keyframe_insert("co", frame=frame)
for frame in (1, 2):
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    meshes, _ = worker.geometry(bpy.context.scene, graph, with_bvh=False)
    ev = obj.evaluated_get(graph)
    mesh = ev.to_mesh()
    lo = [min(v.co[k] for v in mesh.vertices) for k in range(3)]
    hi = [max(v.co[k] for v in mesh.vertices) for k in range(3)]
    expected = [
        ev.matrix_world @ Vector((x, y, z))
        for x in (lo[0], hi[0])
        for y in (lo[1], hi[1])
        for z in (lo[2], hi[2])
    ]
    ev.to_mesh_clear()
    assert (
        max((a - b).length for a, b in zip(meshes["mouth"]["bounds"], expected, strict=True)) < 1e-6
    )
print("ANIMATED_CURVE_BOUNDS_OK")
