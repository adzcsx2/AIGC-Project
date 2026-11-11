"""Real forest front end/child reload, with tiny renders instead of production previews."""

import importlib.util
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "forest_tool", ROOT / "tools/视频工具/制作森林喝奶固定引导.py"
)
forest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(forest)
arguments = sys.argv[sys.argv.index("--") + 1 :]


def small_render(scene):
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 1
    scene.render.resolution_x = 128
    scene.render.resolution_y = 72
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.use_overwrite = False


if arguments[0] == "child":
    # Exercise the real CLI, filesystem preflight and load_saved in a fresh process.
    # Only preview resolution/render settings are reduced for this fixture.
    forest.setup_render = small_render
    sys.argv = [sys.argv[0], "--", *arguments[1:]]
    forest.main()
else:
    project, stage = Path(arguments[0]), arguments[1]
    project.mkdir(parents=True)
    (project / "project.yaml").write_text("name: 森林工具验证\n", encoding="utf-8")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 24
    scene.frame_start, scene.frame_end = 1, 281 if stage == "prepare" else 288
    small_render(scene)
    scene.world = bpy.data.worlds.new("世界")
    scene.world.use_nodes = True
    for name, location in [
        ("地面", (0, 0, -0.1)),
        ("幼龙-短吻", (0, 0, 0.5)),
        ("道具-浅奶碗", (0.5, 0, 0.2)),
        ("舔奶舌头", (0, -0.2, 0.5)),
    ]:
        bpy.ops.mesh.primitive_cube_add(size=0.2, location=location)
        bpy.context.object.name = name
    head = bpy.data.objects.new("控制-头部", None)
    scene.collection.objects.link(head)
    data = bpy.data.cameras.new("摄影机")
    camera = bpy.data.objects.new("摄影机", data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.location = (3, -6, 3)
    camera.rotation_euler = (
        (Vector((0, 0, 0.5)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    )
    scene["环境代理"] = json.dumps(["地面"], ensure_ascii=False)
    source_name = (
        "龙宝宝喝奶-动作白模-版本03.blend"
        if stage == "prepare"
        else "龙宝宝喝奶-森林固定机位-版本测试.blend"
    )
    source = project / "03-制作/三维工程" / source_name
    source.parent.mkdir(parents=True)
    plate = project / "底图.png"
    image = bpy.data.images.new("测试底图", width=128, height=72)
    image.filepath_raw, image.file_format = str(plate), "PNG"
    image.save()
    bpy.data.images.remove(image)
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    source_hash = forest.sha(source)
    plate_hash = forest.sha(plate)
    subject = bpy.data.objects["幼龙-短吻"]
    saved_z = subject.location.z
    subject.location.z += 0.35
    live_z = subject.location.z
    assert not bpy.data.is_dirty  # Direct RNA edits can evade is_dirty.
    original_launcher = forest.launch_saved

    def launch_fixture(blender, _script, args):
        return original_launcher(blender, Path(__file__), ["child", *args])

    forest.launch_saved = launch_fixture
    if stage == "prepare":
        destination = forest.prepare(project, "测试")
    else:
        destination = forest.finish(project, plate, "测试")
    assert subject.location.z == live_z  # Caller memory has not been discarded.
    assert Path(bpy.data.filepath).resolve() == source.resolve()
    assert forest.sha(source) == source_hash
    assert forest.sha(plate) == plate_hash
    bpy.ops.wm.open_mainfile(filepath=str(destination), load_ui=False, use_scripts=False)
    assert bpy.data.objects["幼龙-短吻"].location.z == saved_z
    if stage == "prepare":
        assert bpy.context.scene["来源工程SHA256"] == source_hash
    else:
        assert bpy.context.scene["合成来源工程SHA256"] == source_hash
        assert bpy.context.scene["森林底图SHA256"] == plate_hash
    print("FOREST_RELOAD_OK=" + stage)
