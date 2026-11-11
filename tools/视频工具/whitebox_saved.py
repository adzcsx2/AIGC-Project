"""Shared safeguards for saved Blender inputs and isolated legacy workers."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def project_path(project, value, *, exists=False):
    """Resolve current paths with project_owner's nearest-entry ownership rule.

    Blender's bundled Python does not import the API client's dependencies. These
    saved-scene paths are already current paths, never legacy migration aliases.
    """
    project = Path(project).resolve()
    if not (project / "project.yaml").is_file():
        raise ValueError("先建立当前作品的 project.yaml")
    path = (project / value).resolve()
    owner = next((p for p in (path, *path.parents) if (p / "project.yaml").is_file()), None)
    if not path.is_relative_to(project) or owner != project:
        raise ValueError(f"路径必须属于当前作品：{value}")
    if exists and not path.is_file():
        raise ValueError(f"来源文件不存在：{value}")
    return path


def checked_destination(destination, project=None):
    original = Path(destination)
    resolved = project_path(project, original) if project is not None else original.resolve()
    if original.exists() or original.is_symlink() or resolved.exists():
        raise FileExistsError(f"目标已存在，拒绝覆盖：{original}")
    return resolved


def publish_new(staging, destination, project=None):
    """Publish bytes exclusively; an occupied file or symlink is never replaced."""
    destination = checked_destination(destination, project)
    destination.hardlink_to(staging)


def write_json_new(destination, value, project=None):
    destination = checked_destination(destination, project)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".白模记录-", dir=destination.parent) as folder:
        staging = Path(folder) / destination.name
        staging.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
        )
        publish_new(staging, destination, project)


def save_new(bpy, destination, project=None):
    """Publish a new blend without replacing a concurrently created destination."""
    destination = checked_destination(destination, project)
    with tempfile.TemporaryDirectory(prefix=".白模保存-", dir=destination.parent) as folder:
        staging = Path(folder) / destination.name
        bpy.ops.wm.save_as_mainfile(filepath=str(staging), copy=True)
        # Linking is exclusive on both Windows and POSIX, unlike POSIX rename.
        # The temporary name is removed on exit, leaving one independent output.
        publish_new(staging, destination, project)


def render_still_new(bpy, destination, project=None, *, validate_render=None, **render_options):
    """Render a private PNG, then claim its public name without an overwrite race."""
    destination = checked_destination(destination, project)
    scene = bpy.context.scene
    previous = scene.render.filepath
    try:
        with tempfile.TemporaryDirectory(prefix=".白模渲染-", dir=destination.parent) as folder:
            staging = Path(folder) / destination.name
            scene.render.filepath = str(staging)
            bpy.ops.render.render(write_still=True, **render_options)
            if validate_render is not None:
                validate_render()
            publish_new(staging, destination, project)
    finally:
        scene.render.filepath = previous


def property_value_matches(actual, expected):
    if isinstance(expected, tuple):
        return len(actual) == len(expected) and all(
            property_value_matches(a, e) for a, e in zip(actual, expected, strict=True)
        )
    if isinstance(expected, float):
        return math.isfinite(actual) and abs(actual - expected) <= 1e-6
    if hasattr(expected, "original"):
        return actual is not None and actual.original == expected.original
    return actual == expected


def set_unanimated_property(owner, path, value, *, label="显示属性"):
    """Fix one typed property in a disposable scene, retaining other animation.

    Frame changes and render evaluation replay both actions/NLA and drivers.
    Removing only this property's channels also handles NLA blends that would
    otherwise restore its base value. Never save this modified working scene.
    """
    parent_path, _, attribute = path.rpartition(".")
    target = owner.path_resolve(parent_path) if parent_path else owner
    prop = target.bl_rna.properties[attribute]
    if getattr(prop, "is_readonly", False):
        raise ValueError(f"无法固定只读{label}：{owner.name}.{path}")
    scalar_types = {"BOOLEAN": (bool,), "INT": (int,), "FLOAT": (float, int),
                    "STRING": (str,), "ENUM": (str,)}
    values = value if isinstance(value, tuple) else (value,)
    if prop.type == "POINTER":
        valid = value is None or hasattr(value, "bl_rna")
    else:
        valid = prop.type in scalar_types and all(
            type(item) in scalar_types[prop.type]
            and (not isinstance(item, float) or math.isfinite(item)) for item in values
        )
        if getattr(prop, "is_array", False):
            valid = valid and isinstance(value, tuple) and len(value) == prop.array_length
        else:
            valid = valid and not isinstance(value, tuple)
    if not valid:
        raise ValueError(f"不支持的{label}类型：{owner.name}.{path}")
    animation = owner.animation_data
    actions = set()

    def collect(strips):
        for strip in strips:
            if strip.action is not None:
                actions.add(strip.action)
            collect(strip.strips)

    if animation is not None:
        if animation.action is not None:
            actions.add(animation.action)
        for track in animation.nla_tracks:
            collect(track.strips)
        for action in actions:
            if getattr(action, "is_action_layered", False):
                collections = []
                for layer in action.layers:
                    for strip in layer.strips:
                        if strip.type != "KEYFRAME":
                            raise ValueError(
                                f"不支持的{label}动画类型：{action.name}/{strip.type}"
                            )
                        collections.extend(bag.fcurves for bag in strip.channelbags)
            elif hasattr(action, "fcurves"):
                collections = [action.fcurves]
            else:
                raise ValueError(f"无法读取{label}动画通道：{action.name}")
            for curves in collections:
                for curve in list(curves):
                    if curve.data_path == path:
                        curves.remove(curve)
        for curve in list(animation.drivers):
            if curve.data_path == path:
                animation.drivers.remove(curve)
    setattr(target, attribute, value)
    if not property_value_matches(getattr(target, attribute), value):
        raise ValueError(f"无法固定{label}：{owner.name}.{path}")


def disable_animated_boolean(owner, path):
    """Keep the blur helper's boolean-only interface for existing callers."""
    parent_path, _, attribute = path.rpartition(".")
    target = owner.path_resolve(parent_path) if parent_path else owner
    if target.bl_rna.properties[attribute].type != "BOOLEAN":
        raise ValueError(f"不支持的模糊开关类型：{owner.name}.{path}")
    set_unanimated_property(owner, path, False, label="模糊开关")


def save_render_new(image, destination, project=None):
    destination = checked_destination(destination, project)
    with tempfile.TemporaryDirectory(prefix=".白模图片-", dir=destination.parent) as folder:
        staging = Path(folder) / destination.name
        image.save_render(str(staging))
        publish_new(staging, destination, project)


def require_self_contained(bpy):
    """Fail closed for external files and stateful geometry we cannot bind/replay."""
    if bpy.data.libraries:
        raise ValueError("工程含外链库；请在新工程副本中本地化依赖后检查")
    external = bpy.utils.blend_paths(absolute=True, packed=False)
    if external:
        raise ValueError(f"工程含未打包外部文件，请在副本中打包或移除依赖：{external[0]}")
    if any(image.source in {"SEQUENCE", "MOVIE", "TILED"} for image in bpy.data.images):
        raise ValueError("暂不支持图像序列、影片或UDIM输入；不能用单帧打包代替完整依赖")
    if bpy.data.cache_files or any(scene.rigidbody_world for scene in bpy.data.scenes):
        raise ValueError("暂不支持外部缓存或刚体模拟；请在副本中转换为工程内的网格/变换动画")
    unsupported = {
        "NODES",
        "CLOTH",
        "FLUID",
        "SOFT_BODY",
        "DYNAMIC_PAINT",
        "MESH_CACHE",
        "MESH_SEQUENCE_CACHE",
        "PARTICLE_SYSTEM",
    }
    for obj in bpy.data.objects:
        if any(mod.type in unsupported for mod in obj.modifiers):
            raise ValueError(
                f"暂不支持几何节点、模拟或缓存修改器，请在副本中实体化/烘焙：{obj.name}"
            )


def load_saved(bpy, source, expected_hash):
    """Only an isolated background worker may replace its current in-memory scene."""
    if not bpy.app.background:
        raise ValueError("只允许独立后台进程重载工程；不会丢弃当前GUI中的未保存状态")
    if sha(source) != expected_hash:
        raise ValueError("源工程已变化，拒绝加载")
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    require_self_contained(bpy)
    if sha(source) != expected_hash:
        raise ValueError("加载期间源工程已变化")
    return bpy.context.scene


def require_viewport_evaluation(bpy, scene):
    """Do not confuse render visibility with a viewport dependency graph's activity."""
    active = bpy.context.view_layer
    if [layer.name for layer in scene.view_layers if layer.use] != [active.name]:
        raise ValueError("只支持当前视图层为唯一启用渲染图层；请在工程副本中统一图层")
    # Disabled parents and constraint targets can also affect visible objects.
    for obj in scene.objects:
        if obj.hide_viewport or obj.hide_get():
            raise ValueError(f"视口禁用对象可能与渲染求值不同，请在副本中取消视口隐藏：{obj.name}")
        if obj.is_holdout or obj.is_shadow_catcher:
            raise ValueError(f"暂不支持Holdout或Shadow Catcher对象：{obj.name}")

    def visit(layer):
        if layer.hide_viewport or layer.collection.hide_viewport:
            raise ValueError(f"视口禁用集合可能与渲染求值不同：{layer.name}")
        if layer.exclude or layer.holdout or layer.indirect_only:
            raise ValueError(f"暂不支持视图层集合的Exclude、Holdout或Indirect Only：{layer.name}")
        for child in layer.children:
            visit(child)

    visit(bpy.context.view_layer.layer_collection)


def launch_saved(blender, script, arguments):
    result = subprocess.run(
        [
            str(blender),
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--python-exit-code",
            "1",
            "--python",
            str(script),
            "--",
            *map(str, arguments),
        ],
        capture_output=True,
    )
    if result.returncode:
        raise ValueError(
            result.stdout.decode("utf-8", errors="replace")[-4000:]
            + result.stderr.decode("utf-8", errors="replace")[-4000:]
        )
    return result.stdout.decode("utf-8", errors="replace")
