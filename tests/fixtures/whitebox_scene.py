"""Small deterministic Blender fixture: two subjects, held prop and two camera cuts."""

import sys
from pathlib import Path

import bpy
from mathutils import Vector


def create(destination):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 24
    scene.frame_start, scene.frame_end = 1, 8
    scene.render.resolution_x, scene.render.resolution_y = 320, 180
    scene.render.resolution_percentage = 100

    def cube(name, location, size):
        bpy.ops.mesh.primitive_cube_add(size=1, location=location)
        obj = bpy.context.object
        obj.name = name
        obj.scale = size
        return obj

    lead = cube("主体甲", (-1, 0, 0.8), (0.6, 0.5, 1.6))
    cube("主体乙", (1, 0, 0.8), (0.6, 0.5, 1.6))
    prop = cube("握持道具", (-0.5, 0, 1), (0.4, 0.2, 0.2))
    prop.parent = lead
    prop.matrix_parent_inverse = lead.matrix_world.inverted()
    cube("地面", (0, 0, -0.1), (6, 6, 0.2))
    hidden = cube("隐藏旧人物", (0, -3, 1), (5, 1, 5))
    hidden.hide_render = True
    for name, location, frame in [("机位甲", (0, -7, 3), 1), ("机位乙", (0, 7, 3), 5)]:
        data = bpy.data.cameras.new(name)
        data.lens = 32
        camera = bpy.data.objects.new(name, data)
        scene.collection.objects.link(camera)
        camera.location = location
        camera.rotation_euler = (
            (Vector((0, 0, 0.8)) - camera.location).to_track_quat("-Z", "Y").to_euler()
        )
        scene.timeline_markers.new(name, frame=frame).camera = camera
    scene.frame_set(1)
    scene.camera = bpy.data.objects["机位甲"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(destination))


if __name__ == "__main__":
    create(Path(sys.argv[sys.argv.index("--") + 1]))
