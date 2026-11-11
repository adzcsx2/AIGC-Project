"""Real Blender probes for render visibility, curve geometry and fixed-camera checks."""

import importlib.util
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

root = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "whitebox_probe_worker", root / "tools/视频工具/whitebox_blender.py"
)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def cube(name, where, scale):
    bpy.ops.mesh.primitive_cube_add(size=1, location=where)
    obj = bpy.context.object
    obj.name, obj.scale = name, scale
    return obj


target = cube("主体", (0, 0, 1), (1, 1, 1))
wall = cube("墙_遮挡", (0, -3, 1), (10, 0.2, 10))
data = bpy.data.cameras.new("相机")
camera = bpy.data.objects.new("相机", data)
scene.collection.objects.link(camera)
camera.location = (0, -7, 1)
camera.rotation_euler = (Vector((0, 0, 1)) - camera.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = camera


def blocked():
    bpy.context.view_layer.update()
    meshes, _ = worker.geometry(scene, bpy.context.evaluated_depsgraph_get())
    return worker.occlusion(camera, {target.name}, meshes)["blocked_fraction"]


assert blocked() == 1
wall.hide_render = True
assert blocked() == 0

wall.hide_render = False
collection = bpy.data.collections.new("隐藏集合")
scene.collection.children.link(collection)
for old in list(wall.users_collection):
    old.objects.unlink(wall)
collection.objects.link(wall)
collection.hide_render = True
assert blocked() == 0

# A narrow blocker on the perspective rays must not block parallel rays
# to the offset subject in an orthographic view.
collection.hide_render = False
wall.scale = (0.25, 0.2, 10)
wall.location = (0.8, -3.5, 1)
target.location.x = 2
assert blocked() > 0
camera.data.type = "ORTHO"
assert blocked() == 0
camera.data.type = "PERSP"
target.location.x = 0
collection.hide_render = True

curve = bpy.data.curves.new("蛇尾曲线", "CURVE")
curve.dimensions, curve.bevel_depth = "3D", 0.1
spline = curve.splines.new("POLY")
spline.points.add(1)
spline.points[0].co, spline.points[1].co = (0, 0, 0, 1), (2, 0, 0, 1)
tail = bpy.data.objects.new("蛇尾", curve)
scene.collection.objects.link(tail)
bpy.context.view_layer.update()
meshes, _ = worker.geometry(scene, bpy.context.evaluated_depsgraph_get())
assert "蛇尾" in meshes and len(meshes["蛇尾"]["vertices"]) > 2

scene.frame_start, scene.frame_end = 1, 2
camera.location.x = 0
camera.keyframe_insert("location", frame=1)
camera.location.x = 0.2
camera.keyframe_insert("location", frame=2)
plan = {
    "frame_count": 2,
    "subjects": {"A": {"objects": ["主体"]}},
    "shots": [
        {
            "id": "C1",
            "start_frame": 0,
            "end_frame": 2,
            "camera": "相机",
            "camera_motion": "fixed",
            "subjects": ["A"],
            "contacts": [
                {
                    "id": "握持",
                    "a": {"object": "主体"},
                    "b": {"object": "蛇尾"},
                    "max_distance": 0.01,
                }
            ],
        }
    ],
}
result = worker.inspect(scene, plan)
assert any(f["kind"] == "camera_motion" for f in result["failures"])
assert sum(f["kind"] == "contact" for f in result["failures"]) == 2

# RNA changes in a live session must never replace the saved engineering input.
saved = Path(sys.argv[sys.argv.index("--") + 1])
scene.render.fps = 24
bpy.ops.wm.save_as_mainfile(filepath=str(saved))
before = worker.sha(saved)
target.location.x = 100
reloaded = worker.load_scene(
    {
        "blend": str(saved),
        "dependencies": [{"path": str(saved), "sha256": before}],
        "implementation": [],
        "plan": {"fps": {"num": 24, "den": 1}, "frame_count": 2},
    }
)
assert bpy.data.objects["主体"].location.x == 0
assert worker.sha(saved) == before
print(
    "WHITEBOX_PROBES="
    + json.dumps(
        {
            "wall_detected": True,
            "hidden_object_ignored": True,
            "hidden_collection_ignored": True,
            "orthographic_parallel_rays": True,
            "curve_sampled": True,
            "fixed_camera_conflict_detected": True,
            "contact_failure_detected": True,
            "saved_scene_reload": True,
        }
    )
)
