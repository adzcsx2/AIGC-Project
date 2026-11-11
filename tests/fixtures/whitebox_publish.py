"""Real legacy builder with another writer claiming an output during construction."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy

project = Path(sys.argv[sys.argv.index("--") + 1])
kind = sys.argv[sys.argv.index("--") + 2]
project.mkdir(parents=True)
(project / "project.yaml").write_text("name: 排他发布验证\n", encoding="utf-8")
config = project / "03-制作/制作计划/白模动作配置.json"
config.parent.mkdir(parents=True)
pose = {
    "t": 0,
    "pelvis": [0, 0, 0.5],
    "chest": [0, -0.3, 0.8],
    "head": [0, -0.5, 1],
    "up": [0, 0, 1],
    "face": [0, -1, 0],
    "head_up": [0, 0, 1],
    "fore_a": [-0.2, -0.5, 0.1],
    "fore_b": [0.2, -0.5, 0.1],
    "hind_a": [-0.2, 0.2, 0.1],
    "hind_b": [0.2, 0.2, 0.1],
    "elbow_bias": [0, 0, 0],
    "paw_face": [0, -1, 0],
    "paw_up": [0, 0, 1],
    "tail_mid": [0.2, 0.4, 0.3],
    "tail_end": [0.4, 0.8, 0.1],
    "bowl_tilt": 0,
    "bowl": [0, -0.8, 0.1],
    "camera_target": [0, 0, 0.5],
    "camera": [3, -6, 3],
}
config.write_text(
    json.dumps({"width": 64, "height": 64, "fps": 24, "frames": 1, "poses": [pose]}),
    encoding="utf-8",
)
tool = Path(__file__).resolve().parents[2] / "tools/视频工具/制作喝奶白模.py"
spec = importlib.util.spec_from_file_location("legacy_builder_publish", tool)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
outputs = builder.output_paths(project, "并发")
target = {
    "blend": outputs[0],
    "record": outputs[3],
    "frame": outputs[1] / "帧-0001.png",
}[kind]
sentinel = b"another task's existing output"


def save_copy(filepath, copy):
    assert copy is True
    result = bpy.ops.wm.save_as_mainfile(filepath=filepath, copy=copy)
    if kind in {"blend", "record"}:
        target.write_bytes(sentinel)
    return result


def render_frame(**options):
    # The production builder still makes its actual geometry and animation.
    # Only this isolated fixture uses a tiny EEVEE render in place of Cycles/OptiX.
    bpy.context.scene.render.engine = "BLENDER_EEVEE"
    bpy.context.scene.eevee.taa_render_samples = 1
    result = bpy.ops.render.render(**options)
    target.write_bytes(sentinel)
    return result


builder.bpy = SimpleNamespace(
    context=bpy.context,
    data=bpy.data,
    ops=SimpleNamespace(
        object=bpy.ops.object,
        mesh=bpy.ops.mesh,
        wm=SimpleNamespace(save_as_mainfile=save_copy),
        render=SimpleNamespace(render=render_frame),
    ),
)
try:
    builder.build(SimpleNamespace(project=project, version="并发", mode="animation"))
except FileExistsError:
    pass
else:
    raise AssertionError("The builder must reject the concurrently occupied output")
assert target.read_bytes() == sentinel
assert not list(project.rglob(".白模保存-*"))
assert not list(project.rglob(".白模渲染-*"))
print("CONCURRENT_OUTPUT_PRESERVED=" + kind)
