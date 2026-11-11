"""Real Blender actions, NLA and drivers must not restore preview blur."""

import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/视频工具"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import whitebox_blender as worker  # noqa: E402
from whitebox_scene import create  # noqa: E402

destination = Path(sys.argv[sys.argv.index("--") + 1])
case = sys.argv[sys.argv.index("--") + 2]
create(destination)
scene = bpy.context.scene
scene.render.use_motion_blur = True
scene.render.motion_blur_shutter = 0.2
scene.render.keyframe_insert("motion_blur_shutter", frame=1)
scene.render.motion_blur_shutter = 1.0
scene.render.keyframe_insert("motion_blur_shutter", frame=8)
for camera in (obj for obj in scene.objects if obj.type == "CAMERA"):
    data = camera.data
    data.dof.use_dof = True
    data.dof.focus_distance = 0.1
    data.dof.aperture_fstop = 0.1
    data.lens = 32
    data.keyframe_insert("lens", frame=1)
    data.lens = 36
    data.keyframe_insert("lens", frame=8)
    if case == "driver":
        data.driver_add("dof.use_dof").driver.expression = "True"
    else:
        data.dof.keyframe_insert("use_dof", frame=1)
        data.dof.keyframe_insert("use_dof", frame=8)
        if case == "nla":
            animation = data.animation_data
            action, slot = animation.action, animation.action_slot
            animation.action = None
            strip = animation.nla_tracks.new().strips.new("模糊与镜头动画", 1, action)
            strip.action_slot = slot
    camera.keyframe_insert("location", frame=1)
    camera.location.x += 0.25
    camera.keyframe_insert("location", frame=8)
subject = bpy.data.objects["主体甲"]
subject.keyframe_insert("location", frame=1)
subject.location.x += 0.5
subject.keyframe_insert("location", frame=8)
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(destination))
source_hash = worker.sha(destination)
plan = {
    "frame_count": 8, "preview_scale": 50,
    "subjects": {"A": {"objects": ["主体甲"]}, "B": {"objects": ["主体乙"]}},
    "shots": [
        {"id": "C1", "start_frame": 0, "end_frame": 4, "camera": "机位甲",
         "camera_motion": "moving", "subjects": ["A", "B"]},
        {"id": "C2", "start_frame": 4, "end_frame": 8, "camera": "机位乙",
         "camera_motion": "moving", "subjects": ["A", "B"]},
    ],
}


def saved_state():
    rows = []
    for frame in range(1, 9):
        scene.frame_set(frame)
        rows.append([
            scene.camera.name, scene.camera.data.lens,
            list(scene.camera.location), list(bpy.data.objects["主体甲"].location),
            scene.render.motion_blur_shutter,
        ])
        assert scene.camera.data.dof.use_dof
        assert scene.render.use_motion_blur
    return rows


original_state = saved_state()
original = worker.inspect(scene, plan)
assert not original["failures"]


def pixels(path):
    # Blender 5.3's Render Result may expose an empty pixels collection in
    # background mode; read the real rendered artifact instead.
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        result = list(image.pixels)
        assert len(result) == 160 * 90 * 4
        return result
    finally:
        bpy.data.images.remove(image)


for pass_name in ("审片版", "送模版"):
    scene = worker.load_saved(bpy, destination, source_hash)
    worker.configure_pass(scene, plan, pass_name)
    candidate = worker.inspect(scene, plan, exporting=True)
    assert not candidate["failures"]
    assert candidate["geometry_camera_sha256"] == original["geometry_camera_sha256"]
    for frame in range(1, 9):
        scene.frame_set(frame)
        worker.require_blur_disabled(scene)
        assert scene.render.motion_blur_shutter == original_state[frame - 1][-1]
    # The render operator evaluates the dependency graph again, independently
    # of frame_set(). Compare actual pixels with an animation-free blur control.
    if pass_name == "送模版":
        scene.eevee.taa_render_samples = 1
        for frame in (1, 8):
            scene.frame_set(frame)
            rendered = destination.parent / f"{case}-送模-{frame}.png"
            worker.render_still_new(
                bpy, rendered,
                validate_render=lambda scene=scene: worker.require_blur_disabled(scene),
                layer=bpy.context.view_layer.name,
            )
            actual = pixels(rendered)
            # A second render with no camera-data animation is an independent
            # control at this frame, preserving the evaluated lens/DOF values.
            data = scene.camera.data
            animation = data.animation_data
            action = animation.action
            slot = animation.action_slot
            use_nla = animation.use_nla
            lens = data.lens
            animation.action = None
            animation.use_nla = False
            data.lens = lens
            data.dof.use_dof = False
            control = destination.parent / f"{case}-清晰基准-{frame}.png"
            worker.render_still_new(bpy, control, layer=bpy.context.view_layer.name)
            expected = pixels(control)
            assert actual == expected, (case, frame, "render restored blur")
            assert max(actual[::4]) - min(actual[::4]) > 0.2  # The scene is visible.
            animation.action = action
            if action is not None:
                animation.action_slot = slot
            animation.use_nla = use_nla

assert worker.sha(destination) == source_hash
scene = worker.load_saved(bpy, destination, source_hash)
assert saved_state() == original_state
assert worker.inspect(scene, plan)["geometry_camera_sha256"] == original["geometry_camera_sha256"]
print("ANIMATED_BLUR_DISABLED_OK=" + json.dumps({
    "case": case, "blender": bpy.app.version_string, "source_sha256": source_hash,
    "geometry_camera_sha256": original["geometry_camera_sha256"],
    "source_animation_preserved": True, "actual_pixels_match_clear_control": True,
}))
