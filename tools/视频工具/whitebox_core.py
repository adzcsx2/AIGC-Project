"""Project-owned whitebox plans and evidence; no Blender import or paid API calls."""

from __future__ import annotations

import hashlib
import json
import math
import re
import tempfile
from fractions import Fraction
from pathlib import Path

import yaml
from video_tools import decode_check, executable, frame_timeline, probe, run, sha
from whitebox_saved import publish_new

from autodl_video.paths import project_owner


def integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} 必须为不小于 {minimum} 的整数")
    return value


def number(value, label, minimum=0, maximum=float("inf")):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} 必须为数值")
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{label} 超出范围")
    return value


def mapping(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} 必须为对象")
    return value


def fields(value, allowed, label):
    mapping(value, label)
    if any(not isinstance(k, str) for k in value) or set(value) - set(allowed):
        raise ValueError(f"{label} 含未知字段")
    return value


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} 不能为空")
    return value


def inside(project, value, *, exists=True):
    """All plan paths are relative to the owning project, including new outputs."""
    path = (project / text(value, "路径")).resolve()
    if not path.is_relative_to(project) or project_owner(path) not in (None, project):
        raise ValueError(f"路径必须属于当前作品：{value}")
    if exists and not path.is_file():
        raise ValueError(f"文件不存在：{value}")
    return path


def descriptor(path):
    return {"path": str(path), "sha256": sha(path)}


def check_evidence(items):
    for item in items:
        path = Path(item["path"])
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError(f"依据已变化，旧检查失效：{path}")


def write_new(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never replace an earlier run, including a concurrent writer's result.
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def load_plan(path):
    path = Path(path).resolve()
    project = project_owner(path)
    if project is None:
        raise ValueError("白模计划必须属于含 project.yaml 的作品")
    data = mapping(yaml.safe_load(path.read_text("utf-8-sig")), "白模计划")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ValueError("白模计划仅支持 schema_version: 1")
    allowed = {
        "schema_version",
        "fps",
        "frame_start",
        "frame_count",
        "source",
        "subjects",
        "shots",
        "source_documents",
        "locks",
        "preview_scale",
        "notes",
        "plan_hide",
    }
    if extra := set(data) - allowed:
        raise ValueError(f"未知计划字段：{sorted(extra)}")
    rate = fields(data.get("fps"), {"num", "den"}, "fps")
    fps = Fraction(integer(rate.get("num"), "fps.num", 1), integer(rate.get("den"), "fps.den", 1))
    if not 1 <= fps <= 240:
        raise ValueError("fps 必须在 1–240 之间")
    count = integer(data.get("frame_count"), "frame_count", 1)
    integer(data.get("frame_start", 1), "frame_start", 1)
    integer(data.get("preview_scale", 25), "preview_scale", 1)
    if data.get("preview_scale", 25) > 100:
        raise ValueError("preview_scale 最大100")
    source = fields(data.get("source"), {"blend", "sha256"}, "source")
    blend = inside(project, source.get("blend"))
    if blend.suffix.lower() != ".blend":
        raise ValueError("source.blend 必须为已保存的 .blend 工程")
    expected = source.get("sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError("source.sha256 必须填写真实工程 SHA-256；模板不能当ready")
    if sha(blend) != expected:
        raise ValueError("source.sha256 与实际工程不一致")
    entry = mapping(
        yaml.safe_load((project / "project.yaml").read_text("utf-8-sig")), "project.yaml"
    )
    characters = entry.get("characters") or {}
    subjects = mapping(data.get("subjects"), "subjects")
    if not subjects:
        raise ValueError("至少声明一个检查主体")
    for sid, subject in subjects.items():
        text(sid, "主体ID")
        fields(subject, {"objects", "role", "model_gray", "character_id"}, sid)
        names = subject.get("objects")
        if (
            not isinstance(names, list)
            or not names
            or not all(isinstance(n, str) and n for n in names)
        ):
            raise ValueError(f"{sid}.objects 需要实际对象名列表")
        if subject.get("role", "subject") not in {"subject", "prop", "set"}:
            raise ValueError(f"{sid}.role 无效")
        number(subject.get("model_gray", 0.35), f"{sid}.model_gray", 0.05, 0.9)
        cid = subject.get("character_id")
        if cid is not None:
            if cid not in characters:
                raise ValueError(f"人物未登记在 project.yaml.characters：{cid}")
            character = mapping(
                yaml.safe_load(inside(project, characters[cid]).read_text("utf-8-sig")), cid
            )
            if character.get("character_id") != cid:
                raise ValueError(f"人物档案ID不匹配：{cid}")
    shots = data.get("shots")
    if not isinstance(shots, list) or not shots:
        raise ValueError("shots 不能为空")
    cursor, ids = 0, set()
    for shot in shots:
        fields(
            shot,
            {
                "id",
                "start_frame",
                "end_frame",
                "camera",
                "camera_motion",
                "subjects",
                "framing",
                "contacts",
                "generation_shot_id",
            },
            "shot",
        )
        sid = text(shot.get("id"), "镜头ID")
        if sid in ids:
            raise ValueError(f"重复镜头ID：{sid}")
        ids.add(sid)
        start = integer(shot.get("start_frame"), f"{sid}.start_frame")
        end = integer(shot.get("end_frame"), f"{sid}.end_frame", 1)
        if start != cursor or end <= start:
            raise ValueError(f"{sid} 时间轴有缺口、重叠或反向；使用零起算、出点不含的连续帧区间")
        cursor = end
        text(shot.get("camera"), f"{sid}.camera")
        if shot.get("camera_motion", "any") not in {"fixed", "moving", "any"}:
            raise ValueError(f"{sid}.camera_motion 无效")
        selected = shot.get("subjects")
        if (
            not isinstance(selected, list)
            or not selected
            or any(s not in subjects for s in selected)
        ):
            raise ValueError(f"{sid}.subjects 引用了未知主体或为空")
        framing = mapping(shot.get("framing", {}), f"{sid}.framing")
        for subject, limits in framing.items():
            if subject not in selected:
                raise ValueError(f"{sid} 构图检查主体不属于本镜：{subject}")
            mapping(limits, "构图限制")
            if set(limits) - {"inside", "margin", "min_height", "max_height", "max_occlusion"}:
                raise ValueError("未知构图检查字段")
            if "inside" in limits and type(limits["inside"]) is not bool:
                raise ValueError("inside 必须为布尔值")
            number(limits.get("margin", 0), "margin", 0, 0.49)
            low = number(limits.get("min_height", 0), "min_height")
            high = number(limits.get("max_height", 100), "max_height")
            if high < low:
                raise ValueError("max_height 小于 min_height")
            if "max_occlusion" in limits:
                number(limits["max_occlusion"], "max_occlusion", 0, 1)
        contacts = shot.get("contacts", [])
        if not isinstance(contacts, list):
            raise ValueError("contacts 必须为列表")
        contact_ids = set()
        for contact in contacts:
            fields(contact, {"id", "a", "b", "max_distance", "start_frame", "end_frame"}, "contact")
            text(contact.get("id"), "contact.id")
            if contact["id"] in contact_ids:
                raise ValueError("同镜头接触检查ID重复")
            contact_ids.add(contact["id"])
            number(contact.get("max_distance"), "max_distance")
            c0 = integer(contact.get("start_frame", start), "contact.start_frame")
            c1 = integer(contact.get("end_frame", end), "contact.end_frame", 1)
            if not start <= c0 < c1 <= end:
                raise ValueError("接触区间必须在所属镜头内")
            for key in ("a", "b"):
                anchor = fields(contact.get(key), {"object", "point"}, f"contact.{key}")
                text(anchor.get("object"), "anchor.object")
                point = anchor.get("point", [0, 0, 0])
                if not isinstance(point, list) or len(point) != 3:
                    raise ValueError("锚点point必须为局部坐标三元组")
                for n in point:
                    number(n, "point", -float("inf"))
        if generation := shot.get("generation_shot_id"):
            manifest = inside(project, entry.get("materials_manifest"))
            materials = mapping(yaml.safe_load(manifest.read_text("utf-8-sig")), "materials")
            if generation not in materials.get("shots", {}):
                raise ValueError(f"生成片段未登记：{generation}")
    if cursor != count:
        raise ValueError("镜头时间轴未完整覆盖 frame_count")
    dependencies = [descriptor(path), descriptor(project / "project.yaml"), descriptor(blend)]
    for key in ("locks", "plan_hide"):
        items = data.get(key, [])
        if not isinstance(items, list) or not all(isinstance(x, str) and x for x in items):
            raise ValueError(f"{key} 必须为非空文字组成的列表")
    documents = data.get("source_documents", [])
    if not isinstance(documents, list):
        raise ValueError("source_documents 必须为列表")
    for item in documents:
        fields(item, {"path", "sha256"}, "source_documents")
        document = inside(project, item["path"])
        if sha(document) != item.get("sha256"):
            raise ValueError(f"创作依据哈希不匹配：{document}")
        dependencies.append(descriptor(document))
    for subject in subjects.values():
        if cid := subject.get("character_id"):
            dependencies.append(descriptor(inside(project, characters[cid])))
    if any(s.get("generation_shot_id") for s in shots):
        dependencies.append(descriptor(inside(project, entry["materials_manifest"])))
    # Deduplicate by canonical path; no media copies are made.
    dependencies = list({d["path"]: d for d in dependencies}.values())
    return {
        "plan": data,
        "plan_path": str(path),
        "project": str(project),
        "blend": str(blend),
        "dependencies": dependencies,
        "fps": str(fps),
        "duration": float(count / fps),
    }


def new_run(context, version, render=False):
    if not isinstance(version, str) or not re.fullmatch(r"[\w\-]+", version):
        raise ValueError("版本只能包含文字、数字、下划线或连字符")
    project = Path(context["project"])
    paths = {
        "work": inside(project, f"03-制作/中间数据/白模检查-版本{version}", exists=False),
        "evidence": inside(project, f"05-检查与验收/白模-版本{version}", exists=False),
    }
    if render:
        paths["output"] = inside(project, f"04-输出/处理过程/白模-版本{version}", exists=False)
    if any(p.exists() for p in paths.values()):
        raise FileExistsError("白模版本已占用，请换新版本；不会覆盖旧工程、帧或检查记录")
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=False)
    return paths


def match_cuts(expected, detected, tolerance):
    """Monotone one-to-one matching: maximize hits, then minimize total error."""
    expected, detected = sorted(expected), sorted(detected)
    number(tolerance, "切点容差")
    for t in expected + detected:
        number(t, "切点时间")
    n, m = len(expected), len(detected)
    # A malformed/high-motion detector must not allocate an unbounded matrix.
    if (n + 1) * (m + 1) > 2_000_000:
        raise ValueError("切点候选过多，请检查阈值或分段核验")
    dp = [[(0, 0.0) for _ in range(m + 1)] for _ in range(n + 1)]
    action = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            choices = [(dp[i - 1][j], "missing"), (dp[i][j - 1], "extra")]
            error = abs(expected[i - 1] - detected[j - 1])
            if error <= tolerance:
                hits, cost = dp[i - 1][j - 1]
                choices.append(((hits + 1, cost - error), "match"))
            dp[i][j], action[i][j] = max(choices, key=lambda x: x[0])
    i, j, pairs, used_i, used_j = n, m, [], set(), set()
    while i and j:
        act = action[i][j]
        if act == "match":
            pairs.append(
                {
                    "expected": expected[i - 1],
                    "detected": detected[j - 1],
                    "error_seconds": abs(expected[i - 1] - detected[j - 1]),
                }
            )
            used_i.add(i - 1)
            used_j.add(j - 1)
            i, j = i - 1, j - 1
        elif act == "missing":
            i -= 1
        else:
            j -= 1
    return {
        "matches": list(reversed(pairs)),
        "missing": [v for k, v in enumerate(expected) if k not in used_i],
        "extra": [v for k, v in enumerate(detected) if k not in used_j],
    }


def verify_cuts(context, video, *, threshold=0.28, tolerance_frames=2):
    project = Path(context["project"])
    video = inside(project, str(video))
    number(threshold, "threshold", 0, 1)
    number(tolerance_frames, "tolerance_frames", 0, 24)
    evidence = context["dependencies"] + [descriptor(video)]
    decode_check(video)
    meta = probe(video)
    if not meta["video"]:
        raise ValueError("输入不含视频")
    # Showinfo writes stderr; explicitly require FFmpeg success before interpreting it.
    import subprocess

    result = subprocess.run(
        [
            executable("ffmpeg"),
            "-nostdin",
            "-hide_banner",
            "-i",
            str(video),
            "-map",
            f"0:{meta['video']['index']}",
            "-an",
            "-vf",
            f"setpts=PTS-STARTPTS,select='gt(scene,{threshold})',showinfo",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
    )
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", errors="replace")[-4000:])
    detected = [
        float(t)
        for t in re.findall(
            r"pts_time:([-+\d.eE]+)", result.stderr.decode("utf-8", errors="replace")
        )
    ]
    rate = Fraction(context["fps"])
    expected = [float(s["start_frame"] / rate) for s in context["plan"]["shots"][1:]]
    tolerance = float(tolerance_frames / rate)
    matches = match_cuts(expected, detected, tolerance)
    points, last_duration, _ = frame_timeline(video, meta["video"])
    if last_duration <= 0:
        raise ValueError("无法确定尾帧时长，不能确认时间轴匹配")
    video_duration = float(points[-1] + last_duration)
    duration_ok = abs(video_duration - context["duration"]) <= max(float(1 / rate), 0.01)
    check_evidence(evidence)
    return {
        "schema_version": 1,
        "dependencies": evidence,
        "threshold": threshold,
        "video_stream_index": meta["video"]["index"],
        "tolerance_seconds": tolerance,
        "expected": expected,
        "detected": detected,
        **matches,
        "duration_matches": duration_ok,
        "status": "detected_match"
        if duration_ok and not matches["missing"] and not matches["extra"]
        else "mismatch",
        "visual_review": "pending",
        "limitations": (
            "帧差仅产生切点候选；闪光/快速动作会误报，相似画面会漏报。不得自动降阈值凑数。"
        ),
    }


def execute_blender(context, paths, blender, render=False):
    worker = Path(__file__).with_name("whitebox_blender.py")
    implementation = [
        descriptor(worker),
        descriptor(Path(__file__)),
        descriptor(worker.with_name("白模.py")),
        descriptor(worker.with_name("video_tools.py")),
        descriptor(worker.with_name("whitebox_saved.py")),
    ]
    check_evidence(context["dependencies"])
    job = {
        **context,
        "paths": {k: str(v) for k, v in paths.items()},
        "render": render,
        "implementation": implementation,
    }
    job_path = paths["work"] / "执行输入.json"
    write_new(job_path, job)
    job_evidence = descriptor(job_path)
    import subprocess

    log = paths["work"] / "Blender执行日志.txt"
    with log.open("xb") as stream:
        result = subprocess.run(
            [
                str(blender),
                "--background",
                "--factory-startup",
                "--disable-autoexec",
                "--python-exit-code",
                "1",
                "--python",
                str(worker),
                "--",
                str(job_path),
            ],
            stdout=stream,
            stderr=subprocess.STDOUT,
        )
    check_evidence(context["dependencies"] + implementation + [job_evidence])
    if result.returncode:
        raise ValueError(f"Blender检查/渲染失败，查看：{log}")
    report_path = paths["evidence"] / "场景检查.json"
    report = json.loads(report_path.read_text("utf-8"))
    artifacts = [descriptor(report_path)]
    if render and not report["failures"]:
        rate = context["fps"]
        format_ = report["render_format"]
        sar = (
            Fraction(str(format_["pixel_aspect_x"])) / Fraction(str(format_["pixel_aspect_y"]))
        ).limit_denominator(65535)
        scale = format_["percentage"] * context["plan"].get("preview_scale", 25) / 10000
        expected_size = (int(format_["width"] * scale), int(format_["height"] * scale))
        for name in ("审片版", "送模版"):
            movie = paths["output"] / f"{name}.mp4"
            with tempfile.TemporaryDirectory(prefix=".白模编码-", dir=movie.parent) as folder:
                staging = Path(folder) / movie.name
                run(
                    [
                        executable("ffmpeg"),
                        "-nostdin",
                        "-v",
                        "error",
                        "-n",
                        "-framerate",
                        rate,
                        "-start_number",
                        "0",
                        "-i",
                        str(paths["work"] / name / "帧-%06d.png"),
                        "-an",
                        "-vf",
                        f"setsar={sar.numerator}/{sar.denominator}:max=65535",
                        "-c:v",
                        "libx264",
                        "-crf",
                        "18",
                        "-pix_fmt",
                        "yuv420p",
                        staging,
                    ]
                )
                decode_check(staging)
                meta = probe(staging)
                video = meta["video"]
                actual_sar = Fraction(video.get("sample_aspect_ratio", "1:1").replace(":", "/"))
                if (video["width"], video["height"]) != expected_size or actual_sar != sar:
                    raise ValueError("预览显示画幅/像素比例与工程不匹配，不发布验收记录")
                count = int(
                    run(
                        [
                            executable("ffprobe"),
                            "-v",
                            "error",
                            "-count_frames",
                            "-select_streams",
                            "v:0",
                            "-show_entries",
                            "stream=nb_read_frames",
                            "-of",
                            "csv=p=0",
                            staging,
                        ]
                    ).strip()
                )
                if (
                    count != context["plan"]["frame_count"]
                    or abs(meta["duration"] - context["duration"]) > 0.01
                ):
                    raise ValueError("预览帧数/时长不匹配，不发布验收记录")
                publish_new(staging, movie, context["project"])
            artifacts.append(descriptor(movie))
        artifacts += [descriptor(p) for p in paths["evidence"].glob("*.png")]
    check_evidence(context["dependencies"] + implementation + [job_evidence])
    bundle = {
        "schema_version": 1,
        "dependencies": context["dependencies"],
        "implementation": implementation,
        "job": job_evidence,
        "artifacts": artifacts,
        "status": "checks_failed" if report["failures"] else "checks_passed",
        "dynamic_review": "pending",
        "model_readability_review": "pending",
        "user_acceptance": "pending",
        "audio": "silent_whitebox_preview",
        "limitations": report["limitations"],
    }
    path = paths["evidence"] / "白模检查包.json"
    write_new(path, bundle)
    return path, bundle


def validate_implementation(items):
    """Accept exactly the current local whitebox toolchain, never arbitrary code paths."""
    directory = Path(__file__).resolve().parent
    expected = {
        directory / name
        for name in (
            "whitebox_blender.py", "whitebox_core.py", "白模.py", "video_tools.py",
            "whitebox_saved.py",
        )
    }
    if not isinstance(items, list) or len(items) != len(expected):
        raise ValueError("检查包必须绑定完整的当前白模工具实现白名单")
    seen = set()
    for item in items:
        fields(item, {"path", "sha256"}, "工具实现")
        path = Path(text(item.get("path"), "工具实现路径"))
        # Do not allow an expected filename to redirect to a different file.
        if not path.is_absolute() or path != path.resolve() or path not in expected:
            raise ValueError("工具实现路径不在当前白模工具白名单内")
        if path in seen or not re.fullmatch(r"[a-f0-9]{64}", str(item.get("sha256", ""))):
            raise ValueError("工具实现白名单重复或缺少真实哈希")
        seen.add(path)
    if seen != expected:
        raise ValueError("检查包缺少当前白模工具实现")
    return items


def validate_bundle(context, path):
    path = inside(Path(context["project"]), str(path))
    bundle = mapping(json.loads(path.read_text("utf-8")), "白模检查包")
    if bundle.get("schema_version") != 1:
        raise ValueError("不支持的检查包版本")
    if bundle.get("dependencies") != context["dependencies"]:
        raise ValueError("检查包不属于当前计划及来源")
    implementation = validate_implementation(bundle.get("implementation"))
    inside(Path(context["project"]), bundle["job"]["path"])
    for item in bundle.get("artifacts", []):
        inside(Path(context["project"]), item["path"])
    check_evidence(
        bundle["dependencies"] + implementation + [bundle["job"]] + bundle["artifacts"]
    )
    return bundle


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()
