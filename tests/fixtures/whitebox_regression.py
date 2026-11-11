"""Real saved scenes for renderer/evidence regressions, isolated to pytest's project."""

import importlib.util
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from whitebox_scene import create  # noqa: E402

destination = Path(sys.argv[sys.argv.index("--") + 1])
case = sys.argv[sys.argv.index("--") + 2]
create(destination)
scene = bpy.context.scene
subject = bpy.data.objects["主体甲"]

if case.startswith("viewport_"):
    subject.keyframe_insert("location", frame=1)
    subject.location.x = 20
    subject.keyframe_insert("location", frame=8)
    if case == "viewport_object":
        subject.hide_viewport = True
    elif case == "viewport_eye":
        subject.hide_set(True)
    else:
        collection = bpy.data.collections.new("视口隐藏集合")
        scene.collection.children.link(collection)
        for old in list(subject.users_collection):
            old.objects.unlink(subject)
        collection.objects.link(subject)
        if case == "viewport_collection":
            collection.hide_viewport = True
        else:
            bpy.context.view_layer.layer_collection.children[collection.name].hide_viewport = True
elif case in {"clip_near", "clip_far"}:
    for camera in (o for o in scene.objects if o.type == "CAMERA"):
        if case == "clip_near":
            camera.data.clip_start = 100
            camera.data.clip_end = 1000
        else:
            camera.data.clip_end = 1
elif case == "sensor":
    camera = bpy.data.objects["机位甲"]
    camera.data.sensor_width = 36
    camera.data.keyframe_insert("sensor_width", frame=1)
    camera.data.sensor_width = 72
    camera.data.keyframe_insert("sensor_width", frame=4)
elif case == "blur_camera_dependency":
    camera = bpy.data.objects["机位甲"]
    camera.data.dof.use_dof = True
    driver = camera.data.driver_add("lens").driver
    driver.expression = "32 if enabled else 72"
    variable = driver.variables.new()
    variable.name, variable.type = "enabled", "SINGLE_PROP"
    variable.targets[0].id_type = "CAMERA"
    variable.targets[0].id = camera.data
    variable.targets[0].data_path = "dof.use_dof"
elif case == "material_override":
    material = bpy.data.materials.new("源工程红色覆盖")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (1, 0, 0, 1)
    output = nodes.new("ShaderNodeOutputMaterial")
    material.node_tree.links.new(emission.outputs[0], output.inputs["Surface"])
    bpy.context.view_layer.material_override = material
    # Different subject grays must remain effective even for a shared mesh.
    bpy.data.objects["主体乙"].data = subject.data
elif case == "display_camera_dependency":
    scene.view_settings.exposure = 2.0
    driver = bpy.data.objects["机位甲"].data.driver_add("lens").driver
    driver.expression = "32 + exposure"
    variable = driver.variables.new()
    variable.name, variable.type = "exposure", "SINGLE_PROP"
    variable.targets[0].id_type = "SCENE"
    variable.targets[0].id = scene
    variable.targets[0].data_path = "view_settings.exposure"
elif case.startswith("display_"):
    # The same genuine motion must survive every display-only normalization.
    for obj in (subject, bpy.data.objects["机位甲"], bpy.data.objects["机位乙"]):
        obj.keyframe_insert("location", frame=1)
        obj.location.x += 0.2
        obj.keyframe_insert("location", frame=8)
    scene.render.motion_blur_shutter = 0.2
    scene.render.keyframe_insert("motion_blur_shutter", frame=1)
    scene.render.motion_blur_shutter = 0.8
    scene.render.keyframe_insert("motion_blur_shutter", frame=8)

    def setting(owner, path, value):
        parent, _, attribute = path.rpartition(".")
        target = owner.path_resolve(parent) if parent else owner
        setattr(target, attribute, value)
        if case in {"display_keyframes", "display_nla"}:
            if target.bl_rna.properties[attribute].is_animatable:
                owner.keyframe_insert(path, frame=1)
                owner.keyframe_insert(path, frame=8)
        elif case == "display_driver" and type(value) in {bool, int, float, tuple}:
            if target.bl_rna.properties[attribute].is_animatable:
                curves = owner.driver_add(path)
                if isinstance(value, tuple):
                    for curve, component in zip(curves, value, strict=True):
                        curve.driver.expression = repr(component)
                else:
                    curves.driver.expression = repr(value)

    if case != "display_clean":
        for path, value in (
            ("view_settings.view_transform", "AgX"),
            ("view_settings.look", "None"),
            ("view_settings.exposure", 1.5),
            ("view_settings.gamma", 1.7),
            ("view_settings.use_curve_mapping", True),
            ("view_settings.use_white_balance", True),
            ("view_settings.white_balance_temperature", 2000.0),
            ("view_settings.white_balance_tint", 50.0),
            ("render.use_stamp", True),
            ("render.use_stamp_scene", True),
            ("render.use_stamp_frame", True),
            ("render.use_stamp_note", True),
            ("render.film_transparent", True),
            ("render.use_multiview", True),
            ("render.dither_intensity", 10.0),
            ("display.shading.light", "FLAT"),
        ):
            setting(scene, path, value)
        scene.render.stamp_note_text = "SOURCE STAMP MUST NOT LEAK"
        scene.view_settings.curve_mapping.curves[0].points[1].location = (1, 0)
        scene.view_settings.curve_mapping.update()
        for obj in scene.objects:
            if obj.type == "MESH":
                setting(obj, "color", (1.0, 0.0, 0.0, 1.0))
        if case == "display_output_override":
            settings = scene.render.image_settings
            settings.color_management = "OVERRIDE"
            settings.view_settings.use_curve_mapping = True
            settings.view_settings.curve_mapping.curves[1].points[1].location = (1, 0)
            settings.view_settings.curve_mapping.update()
            settings.view_settings.use_white_balance = True
            settings.view_settings.white_balance_temperature = 2000
        if case == "display_nla":
            for owner in (scene, *scene.objects):
                animation = owner.animation_data
                if animation is None or animation.action is None:
                    continue
                action, slot = animation.action, animation.action_slot
                animation.action = None
                strip = animation.nla_tracks.new().strips.new("显示及运动动画", 1, action)
                strip.action_slot = slot
elif case in {"external", "packed"}:
    image = bpy.data.images.new("位移输入", width=2, height=2)
    image.pixels = [0, 0, 0, 1] * 4
    image.filepath_raw = str(destination.with_suffix(".png"))
    image.file_format = "PNG"
    image.save()
    if case == "packed":
        image.pack()
    texture = bpy.data.textures.new("位移", type="IMAGE")
    texture.image = image
    modifier = subject.modifiers.new("位移", "DISPLACE")
    modifier.texture, modifier.strength = texture, 2
elif case == "cache":
    subject.modifiers.new("外部缓存", "MESH_CACHE")
elif case == "nodes":
    subject.modifiers.new("几何节点", "NODES")
elif case == "sar":
    scene.render.resolution_x = scene.render.resolution_y = 128
    scene.render.pixel_aspect_x, scene.render.pixel_aspect_y = 2, 1
elif case == "animated_font":
    data = bpy.data.curves.new("后续帧文字", "FONT")
    data.body = "MODEL WATERMARK"
    label = bpy.data.objects.new("后续帧文字", data)
    scene.collection.objects.link(label)
    label.hide_render = True
    label.keyframe_insert("hide_render", frame=1)
    label.hide_render = False
    label.keyframe_insert("hide_render", frame=4)
elif case in {"render_layer_mismatch", "multiple_render_layers"}:
    if case == "render_layer_mismatch":
        scene.view_layers[0].use = False
    other = scene.view_layers.new("另一渲染层")
    collection = bpy.data.collections.new("只有检查层可见")
    scene.collection.children.link(collection)
    for old in list(subject.users_collection):
        old.objects.unlink(subject)
    collection.objects.link(subject)
    other.layer_collection.children[collection.name].exclude = True
elif case in {"layer_exclude", "layer_holdout", "layer_indirect"}:
    collection = bpy.data.collections.new("特殊可见性")
    scene.collection.children.link(collection)
    for old in list(subject.users_collection):
        old.objects.unlink(subject)
    collection.objects.link(subject)
    layer = bpy.context.view_layer.layer_collection.children[collection.name]
    setattr(layer, {"layer_exclude": "exclude", "layer_holdout": "holdout",
                    "layer_indirect": "indirect_only"}[case], True)
elif case in {"object_holdout", "object_shadow_catcher"}:
    setattr(subject, "is_holdout" if case == "object_holdout" else "is_shadow_catcher", True)
elif case.startswith("legacy"):
    subject.name = "幼龙-短吻"
    head = bpy.data.objects.new("控制-头部", None)
    scene.collection.objects.link(head)
    if case == "legacy_clip":
        for camera in (o for o in scene.objects if o.type == "CAMERA"):
            camera.data.clip_end = 1

scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(destination))

if case.startswith("legacy"):
    tool = Path(__file__).resolve().parents[2] / "tools/视频工具/检查喝奶白模.py"
    spec = importlib.util.spec_from_file_location("legacy_inspector", tool)
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)
    saved_hash = legacy.sha256(destination)
    expected = min((subject.matrix_world @ v.co).z for v in subject.data.vertices)
    subject.location.z += 100
    changed = subject.location.z
    assert not bpy.data.is_dirty  # The regression cannot be caught by is_dirty.
    project = next(parent for parent in destination.parents if (parent / "project.yaml").is_file())
    report_path = legacy.inspect(project)
    report = json.loads(report_path.read_text("utf-8"))
    assert abs(report["minimum_muzzle_height"] - expected) < 1e-6
    assert subject.location.z == changed  # Caller memory was not discarded.
    assert legacy.sha256(destination) == saved_hash == report["blend_sha256"]
    if case == "legacy_clip":
        assert report["muzzle_cropped_frames"] == list(range(1, 9))
    print("LEGACY_ISOLATED_RELOAD_OK")
elif case == "display_guard":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools/视频工具"))
    import whitebox_blender as worker

    source_hash = worker.sha(destination)
    scene = worker.load_saved(bpy, destination, source_hash)
    contract = worker.configure_pass(
        scene,
        {"preview_scale": 50, "subjects": {"A": {"objects": ["主体甲"]},
                                           "B": {"objects": ["主体乙"]}}},
        "送模版",
    )
    scene.frame_set(4)
    worker.require_pass_settings(scene, contract)

    def restore_source_grading(*_args):
        # Simulate a render-time writer after the ordinary frame preflight.
        scene.view_settings.use_curve_mapping = True
        scene.render.use_stamp = True

    bpy.app.handlers.render_post.append(restore_source_grading)
    rejected = destination.parent / "不得发布.png"
    try:
        try:
            worker.render_still_new(
                bpy, rejected,
                validate_render=lambda: worker.require_pass_settings(scene, contract),
                layer=bpy.context.view_layer.name,
            )
        except ValueError as error:
            assert "求值后显示属性改变" in str(error)
        else:
            raise AssertionError("Render-time grading changes must reject publication")
    finally:
        bpy.app.handlers.render_post.remove(restore_source_grading)
    assert not rejected.exists()
    assert not list(destination.parent.glob(".白模渲染-*"))
    assert worker.sha(destination) == source_hash
    print("DISPLAY_RENDER_GUARD_OK")
