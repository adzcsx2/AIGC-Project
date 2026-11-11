"""Inspect disk bytes in a child Blender process, preserving the caller's live scene."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view

sys.path.insert(0, str(Path(__file__).resolve().parent))
from whitebox_saved import (  # noqa: E402
    launch_saved,
    load_saved,
    project_path,
    require_viewport_evaluation,
    write_json_new,
)


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inspection_paths(project):
    """Bind a new report to a saved, unmodified scene in this project."""
    project = Path(project).resolve()
    if not bpy.data.filepath or bpy.data.is_dirty:
        raise ValueError("检查前必须保存工程，不能包含未保存修改")
    blend = project_path(project, bpy.data.filepath, exists=True)
    if blend.suffix.lower() != ".blend":
        raise ValueError("被检查工程必须属于当前作品")
    if not blend.is_file():
        raise ValueError("被检查工程不存在，请先保存")
    destination = project / f"05-检查与验收/白模工程检查-{blend.stem}.json"
    out = project_path(project, destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"已有该工程的检查记录，不覆盖：{destination}")
    return blend, out


def inspect(project):
    blend, out = inspection_paths(project)
    launch_saved(
        bpy.app.binary_path,
        Path(__file__),
        [
            project,
            "--saved-source",
            blend,
            "--source-sha256",
            sha256(blend),
        ],
    )
    if not out.is_file():
        raise ValueError("独立检查进程未生成记录")
    print(
        json.dumps(
            {
                "report": str(out),
                "source": "saved_disk",
                "note": "只检查磁盘版本；调用方未保存的内存状态保持不变",
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return out


def inspect_saved(project, source, expected_hash):
    source = project_path(project, source, exists=True)
    load_saved(bpy, source, expected_hash)
    blend, out = inspection_paths(project)
    source_hash = sha256(blend)
    if blend != Path(source).resolve() or source_hash != expected_hash:
        raise ValueError("实际加载工程与请求来源不一致")
    scene = bpy.context.scene
    mouth = bpy.data.objects["幼龙-短吻"]
    head = bpy.data.objects["控制-头部"]
    samples = []
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        require_viewport_evaluation(bpy, scene)
        graph = bpy.context.evaluated_depsgraph_get()
        evaluated = mouth.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        try:
            vertices = [evaluated.matrix_world @ v.co for v in mesh.vertices]
        finally:
            evaluated.to_mesh_clear()
        projected = [world_to_camera_view(scene, scene.camera, v) for v in vertices]
        samples.append(
            {
                "frame": frame,
                "muzzle_min_z": min(v.z for v in vertices),
                "muzzle_in_frame": all(
                    0 <= v.x <= 1
                    and 0 <= v.y <= 1
                    and scene.camera.data.clip_start <= v.z <= scene.camera.data.clip_end
                    for v in projected
                ),
                "head_world": list(head.matrix_world.translation),
            }
        )
    if (
        bpy.data.is_dirty
        or sha256(blend) != source_hash
        or Path(bpy.data.filepath).resolve() != blend
    ):
        raise ValueError("采样期间源工程已变化，不生成检查记录")
    report = {
        "blend": str(blend),
        "blend_sha256": source_hash,
        "fps": scene.render.fps / scene.render.fps_base,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "minimum_muzzle_height": min(x["muzzle_min_z"] for x in samples),
        "muzzle_below_floor_frames": [x["frame"] for x in samples if x["muzzle_min_z"] < 0],
        "muzzle_cropped_frames": [x["frame"] for x in samples if not x["muzzle_in_frame"]],
        "animation_actions": len(bpy.data.actions),
        "caveat": (
            "独立进程只采样磁盘已保存工程；不代表调用方未保存修改、全部碰撞、动态或听音已通过。"
        ),
        "samples": samples,
    }
    write_json_new(out, report, project)
    print(
        json.dumps({k: v for k, v in report.items() if k != "samples"}, ensure_ascii=False),
        flush=True,
    )
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    parser.add_argument("--saved-source", type=Path)
    parser.add_argument("--source-sha256")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    if args.saved_source is not None:
        inspect_saved(args.project, args.saved_source, args.source_sha256)
    else:
        inspect(args.project)
