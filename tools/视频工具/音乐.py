"""Instrumental sketch creation, asset import, full-timeline scoring and mixing."""

from __future__ import annotations

import argparse
import array
import json
import math
import os
import re
import shutil
import stat
import subprocess
import tempfile
import wave
from fractions import Fraction
from pathlib import Path

from video_tools import (
    ROOT,
    executable,
    ffmpeg,
    number,
    output_path,
    prepare_media_record,
    probe,
    publish,
    read_yaml,
    resolve,
    sha,
    write_yaml,
)

from autodl_video.errors import AutoDLError
from autodl_video.locking import resource_lock
from autodl_video.paths import ensure_project_output, project_owner


def ensure_mix_inputs(plan_path, *sources):
    """A registered work must archive every input; standalone scratch mixes remain valid."""
    ensure_project_output(plan_path, *sources, root=ROOT)
    owner = project_owner(plan_path, root=ROOT)
    if owner and any(not source.is_relative_to(owner) for source in sources):
        raise AutoDLError(f"混音输入必须先导入或归档到当前作品：{owner}")


def select_audio_track(meta, requested, field, *, allow_silent=False):
    """Require an explicit choice whenever an input has more than one audio track."""
    tracks = meta["audio"]
    if requested is None:
        if len(tracks) == 1:
            return 0
        if not tracks and allow_silent:
            return None
        raise ValueError(f"{field} 必须明确选择存在的零起算音轨；输入有 {len(tracks)} 条音轨")
    if (
        isinstance(requested, bool)
        or not isinstance(requested, int)
        or not 0 <= requested < len(tracks)
    ):
        raise ValueError(f"{field} 必须选择存在的零起算音轨")
    return requested


def audio_covers(path, start, duration, audio_track=0):
    """Count selected-track samples at source PTS using the same trim as mix()."""
    rate, frame_bytes = 48000, 8  # float32 stereo; no generated padding or silence.
    chain = (
        f"atrim=start={start}:duration={duration},asetpts=PTS-STARTPTS,"
        f"aresample={rate},aformat=channel_layouts=stereo"
    )
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(
            [
                executable("ffmpeg"),
                "-hide_banner",
                "-v",
                "error",
                "-nostdin",
                "-xerror",
                "-copyts",
                "-i",
                str(path),
                "-map",
                f"0:a:{audio_track}",
                "-af",
                chain,
                "-c:a",
                "pcm_f32le",
                "-f",
                "f32le",
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=errors,
        )
        count = 0
        try:
            while chunk := process.stdout.read(1024 * 1024):
                count += len(chunk)
            status = process.wait()
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()
        if status:
            errors.seek(0)
            raise ValueError(
                "音轨解码校验失败：" + errors.read().decode("utf-8", "replace")[-2000:]
            )
    # Permit only resampling/decimal rounding, not a missing audio region.
    return count % frame_bytes == 0 and count / frame_bytes >= duration * rate - 2


def measure_audio(path):
    """Measure exported audio; never claim a listening verdict from these numbers."""
    result = subprocess.run(
        [
            executable("ffmpeg"),
            "-hide_banner",
            "-nostdin",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-af",
            "loudnorm=print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
    )
    text = result.stderr.decode("utf-8", errors="replace")
    matches = re.findall(r'\{\s*"input_i".*?\}', text, re.S)
    if result.returncode or not matches:
        raise ValueError("无法测量导出音轨响度与峰值")
    measured = json.loads(matches[-1])
    return {k: measured[k] for k in ("input_i", "input_tp", "input_lra", "input_thresh")}


def validate_output_audio_coverage(path, duration):
    """Require decoded audio frames to cover the full PTS timeline before publication."""
    tracks = probe(path)["audio"]
    if len(tracks) != 1:
        raise ValueError("导出应包含一条完整的混合音轨")
    track = tracks[0]
    rate = int(track["sample_rate"])
    time_base = Fraction(track["time_base"])
    # Container timestamp rounding is not a missing audio interval.
    tolerance = max(Fraction(1, rate), 2 * time_base)
    result = subprocess.run(
        [
            executable("ffprobe"),
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_frames",
            "-show_entries",
            "frame=pts,nb_samples",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
    )
    if result.returncode:
        raise ValueError("无法解码核对导出音频时间线")
    frames = json.loads(result.stdout).get("frames", [])
    cursor, previous = Fraction(0), None
    for frame in frames:
        if "pts" not in frame or int(frame.get("nb_samples", 0)) <= 0:
            raise ValueError("导出音频缺少真实时间戳或样本数")
        start = int(frame["pts"]) * time_base
        if previous is not None and start <= previous:
            raise ValueError("导出音频时间戳不是严格递增")
        previous = start
        end = start + Fraction(int(frame["nb_samples"]), rate)
        if start > cursor + tolerance:
            raise ValueError(f"导出音频时间线缺口：{float(cursor):.6f}–{float(start):.6f} 秒")
        cursor = max(cursor, end)
    if not frames or cursor < Fraction(str(duration)) - tolerance:
        raise ValueError("导出音频未覆盖完整剪辑时间线")


def create_sketch(config, output):
    """Deterministic note-based instrumental guide, explicitly not an AI model."""
    data = read_yaml(config)
    rate = 48000
    duration = number(data["duration_seconds"], "duration", 0.1, 600)
    samples = [0.0] * int(duration * rate)
    for note in data.get("notes", []):
        start = number(note["start_seconds"], "note start", 0, duration)
        length = number(note["duration_seconds"], "note duration", 0.01, duration - start)
        pitch = number(note["midi_note"], "MIDI note", 21, 108)
        gain = number(note.get("gain", 0.12), "gain", 0, 0.4)
        hz = 440 * 2 ** ((pitch - 69) / 12)
        for n in range(int(length * rate)):
            t = n / rate
            envelope = min(1, t / 0.02, (length - t) / 0.08) * math.exp(-2 * t / length)
            samples[int(start * rate) + n] += (
                gain
                * envelope
                * (math.sin(2 * math.pi * hz * t) + 0.2 * math.sin(4 * math.pi * hz * t))
            )
    peak = max((abs(v) for v in samples), default=0)
    if peak == 0:
        raise ValueError("没有可听音符，不生成假音轨")
    scale = min(1, 0.9 / peak)
    dest = output_path(config, output, "器乐草稿")
    if dest.suffix.lower() != ".wav":
        raise ValueError("本地器乐草稿使用 WAV")
    prepare_media_record(dest, "制作")
    with tempfile.TemporaryDirectory(prefix=".器乐-", dir=dest.parent) as folder:
        temp = Path(folder) / "器乐.wav"
        with wave.open(str(temp), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(rate)
            pcm = array.array("h", [round(v * scale * 32767) for v in samples])
            stream.writeframes(pcm.tobytes())
        publish(
            temp,
            dest,
            record=(
                "制作",
                lambda _: {
                    "method": "local_note_synthesis",
                    "ai_model": None,
                    "config": str(Path(config).resolve()),
                    "output_sha256": sha(temp),
                    "status": "draft_requires_listening",
                    "purpose": "可听的器乐动机/配乐预演，非已验收电影配乐",
                },
            ),
        )
    return dest


def import_asset(source, manifest, asset_id, name, provenance):
    source, manifest = Path(source).resolve(), Path(manifest).resolve()
    project = project_owner(manifest, root=ROOT)
    if project is None:
        raise ValueError("manifest 必须属于含 project.yaml 的作品")
    # Deduplication shares the whole work's asset namespace, even when callers
    # register in different manifests. Never adopt another uncommitted import.
    with resource_lock(project / "project.yaml", root=ROOT):
        with resource_lock(manifest, root=ROOT):
            ensure_project_output(manifest, project / "project.yaml", root=ROOT)
            return _import_asset_locked(source, manifest, asset_id, name, provenance)


def _import_asset_locked(source, manifest, asset_id, name, provenance):
    """Reload and publish one asset while holding the manifest's process lock."""
    data = read_yaml(manifest)
    assets = data.setdefault("assets", {})
    if asset_id in assets:
        raise ValueError("资产 ID 已存在")
    if not probe(source)["audio"]:
        raise ValueError("没有音轨")
    project = next((p for p in manifest.parents if (p / "project.yaml").exists()), None)
    if not project:
        raise ValueError("manifest 必须属于含 project.yaml 的作品")
    if Path(name).name != name or not any("\u4e00" <= c <= "\u9fff" for c in name):
        raise ValueError("请使用中文语义文件名，不含目录")
    dest = ensure_project_output(project / "02-素材/音频/配乐" / name, manifest, root=ROOT)
    if dest.suffix.lower() != source.suffix.lower():
        raise ValueError("保留真实扩展名")
    # Existing project asset: reference directly rather than copying identical audio.
    source_sha = sha(source)
    if dest.exists() and (not dest.is_file() or sha(dest) != source_sha):
        raise ValueError("目标已存在且内容不同，保留原文件")
    # A killed process can leave its published audio without a manifest entry.
    # Reuse identical bytes under the work lock; do not claim rollback ownership.
    matching = (
        dest
        if dest.exists()
        else next(
            (
                p.resolve()
                for p in project.rglob("*")
                if p.is_file()
                and p.suffix.lower() == source.suffix.lower()
                and p.resolve().is_relative_to(project)
                and project_owner(p, root=ROOT) == project
                and sha(p) == source_sha
            ),
            None,
        )
    )
    created = None
    try:
        if matching:
            dest = matching
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest = ensure_project_output(dest, manifest, root=ROOT)
            with tempfile.TemporaryDirectory(prefix=".导入配乐-", dir=dest.parent) as folder:
                temp = Path(folder) / dest.name
                shutil.copy2(source, temp)
                ensure_project_output(dest, manifest, root=ROOT)
                publish(temp, dest)
                created = dest.stat()

        assets[asset_id] = {
            "kind": "audio",
            "required": False,
            "path": os.path.relpath(dest, manifest.parent).replace("\\", "/"),
            "sha256": sha(dest),
            "state": "needs_review",
            "provenance": provenance,
        }
        manifest = ensure_project_output(manifest, project / "project.yaml", root=ROOT)
        write_yaml(manifest, data)
    except BaseException as error:
        if created is not None:
            try:
                # An interruption can arrive just after atomic replacement has
                # committed the manifest. Preserve bytes already referenced there.
                committed = read_yaml(manifest).get("assets", {})
                if not isinstance(committed, dict):
                    raise ValueError("无法确定清单是否已登记，保留本次音频")
                referenced = any(
                    isinstance(asset, dict)
                    and isinstance(asset.get("path"), str)
                    and resolve(manifest.parent, asset["path"]) == dest
                    for asset in committed.values()
                )
                candidate = ensure_project_output(dest, manifest, root=ROOT)
                if (
                    not referenced
                    and candidate == dest
                    and os.path.samestat(candidate.stat(), created)
                ):
                    candidate.unlink()
            except (OSError, AutoDLError, ValueError) as cleanup_error:
                error.add_note(f"本次新增音频未能回滚，请保留并核对：{dest}；{cleanup_error}")
        raise
    return dest


class MixInputs:
    """Capture actual encoder inputs once, independently of their mutable paths."""

    def __init__(self, directory):
        self.directory = Path(directory)
        self.files = {}

    def capture(self, source):
        source = Path(source)
        if source in self.files:
            return self.files[source]["snapshot"]
        source = source.resolve()
        if source in self.files:
            return self.files[source]["snapshot"]
        snapshot = self.directory / f"input-{len(self.files):04}{source.suffix}"
        with source.open("rb") as reader, snapshot.open("xb") as writer:
            before = os.fstat(reader.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("混音输入必须是普通文件")
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
            after = os.fstat(reader.fileno())

        def stamp(info):
            # Same open handle avoids Windows path/fstat ctime differences.
            return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

        digest = sha(snapshot)
        if (
            stamp(before) != stamp(after)
            or not os.path.samestat(before, source.stat())
            or sha(source) != digest
        ):
            raise ValueError(f"混音依据在捕获时变化：{source}")
        self.files[source] = {"snapshot": snapshot, "sha256": digest}
        return snapshot

    def digest(self, source):
        return self.files[Path(source)]["sha256"]

    def bindings(self):
        return [{"path": str(path), "sha256": item["sha256"]} for path, item in self.files.items()]

    def check_current(self):
        for path, item in self.files.items():
            if path.resolve() != path or not path.is_file() or sha(path) != item["sha256"]:
                raise ValueError(f"混音依据已变化，未发布结果：{path}")


def validate(plan_path, *, captured=None):
    plan_path = Path(plan_path).resolve()
    read_path = captured.capture if captured is not None else lambda path: path
    plan = read_yaml(read_path(plan_path))
    timeline = plan["timeline"]
    video = resolve(plan_path.parent, timeline["video_path"])
    manifest = resolve(plan_path.parent, plan["materials_manifest"])
    ensure_mix_inputs(plan_path, video, manifest)
    video_input = read_path(video)
    meta = probe(video_input)
    if not meta["video"] or sha(video_input) != timeline.get("video_sha256"):
        raise ValueError("剪辑版本/哈希不匹配，配乐时间线已失效")
    if (
        timeline.get("time_unit") != "seconds"
        or timeline.get("time_origin") != "edited_timeline_start"
    ):
        raise ValueError("使用完整剪辑起点的秒坐标")
    if not timeline.get("verified"):
        raise ValueError("时间线尚未核实")
    if abs(number(timeline["duration_seconds"], "duration") - meta["duration"]) > 0.1:
        raise ValueError("时间线时长不匹配")
    materials = read_yaml(read_path(manifest))
    cues = plan["music"].get("cues", [])
    regions = plan["music"].get("no_music_regions", [])
    coverage, prepared = [], []
    ids = set()
    for cue in cues:
        if cue["cue_id"] in ids:
            raise ValueError("cue_id 重复")
        ids.add(cue["cue_id"])
        for field in ("purpose", "entry_trigger", "exit_trigger", "instrumentation"):
            if not cue.get(field):
                raise ValueError(f"cue 缺少 {field}")
        start = number(cue["start_seconds"], "cue start", 0, meta["duration"])
        end = number(cue["end_seconds"], "cue end", start, meta["duration"])
        if end <= start:
            raise ValueError("cue 出点必须晚于入点")
        length = end - start
        fade_in = number(cue.get("fade_in_seconds", 0), "fade in", 0, length)
        fade_out = number(cue.get("fade_out_seconds", 0), "fade out", 0, length)
        if fade_in + fade_out > length:
            raise ValueError("淡入淡出总长超出 cue")
        asset = materials["assets"][cue["source_asset_id"]]
        path = resolve(manifest.parent, asset["path"])
        ensure_mix_inputs(plan_path, video, manifest, path)
        if asset.get("kind") != "audio" or asset.get("state") != "ready":
            raise ValueError("音乐素材尚未检查为 ready")
        audio_input = read_path(path)
        if not asset.get("sha256") or sha(audio_input) != asset["sha256"]:
            raise ValueError("音乐素材哈希缺失或已改变")
        audio_track = select_audio_track(
            probe(audio_input), cue.get("audio_track"), f"cue {cue['cue_id']}.audio_track"
        )
        source_in = number(cue.get("source_in_seconds", 0), "source in", 0)
        if not audio_covers(audio_input, source_in, length, audio_track):
            raise ValueError("音乐不足以覆盖 cue；不自动循环或拉伸")
        gain = number(cue.get("gain_db", -12), "gain dB", -60, 12)
        duck = cue.get("dialogue_ducking", {"method": "none"})
        if duck.get("method") not in {"none", "regions"}:
            raise ValueError("当前支持 none / regions 对白区间自动化")
        if duck["method"] == "regions":
            number(duck.get("gain_db", -12), "duck gain", -60, 0)
            for region in duck.get("regions", []):
                a = number(region["start_seconds"], "dialogue start", 0, meta["duration"])
                b = number(region["end_seconds"], "dialogue end", a, meta["duration"])
                if b <= a:
                    raise ValueError("对白区间为空")
        for prior in prepared:
            if max(start, prior["start"]) < min(end, prior["end"]) and not cue.get(
                "cross_cue_transition"
            ):
                raise ValueError("重叠 cue 需说明混音目的")
        prepared.append(
            {
                "cue": cue,
                "path": path,
                "sha256": asset["sha256"],
                "audio_track": audio_track,
                "start": start,
                "end": end,
                "source_in": source_in,
                "gain": gain,
                "fade_in": fade_in,
                "fade_out": fade_out,
            }
        )
        coverage.append((start, end))
    for region in regions:
        a = number(region["start_seconds"], "no music start", 0, meta["duration"])
        b = number(region["end_seconds"], "no music end", a, meta["duration"])
        if b <= a or not region.get("reason"):
            raise ValueError("无音乐区域需要非空区间及理由")
        if any(max(a, c["start"]) < min(b, c["end"]) for c in prepared):
            raise ValueError("cue 覆盖无音乐区域")
        coverage.append((a, b))
    cursor = 0
    for a, b in sorted(coverage):
        if a > cursor + 0.01:
            raise ValueError("时间线有未说明的配乐/留白区域")
        cursor = max(cursor, b)
    if cursor < meta["duration"] - 0.01:
        raise ValueError("时间线尾部未规划")
    dialogue = plan.get("dialogue", {})
    stem = dialogue.get("stem_asset_id")
    if meta["audio"] and dialogue.get("source_has_embedded_music") is not False and not stem:
        raise ValueError("先确认干净对白底轨；已有 BGM 不能直接叠配乐或标为无音乐区")
    base_audio = None
    if stem:
        asset = materials["assets"][stem]
        clean = resolve(manifest.parent, asset["path"])
        ensure_mix_inputs(plan_path, video, manifest, clean)
        clean_input = read_path(clean)
        if (
            asset.get("state") != "ready"
            or asset.get("kind") != "audio"
            or sha(clean_input) != asset.get("sha256")
        ):
            raise ValueError("对白底轨未检查或哈希不匹配")
        clean_meta = probe(clean_input)
        audio_track = select_audio_track(
            clean_meta, dialogue.get("stem_audio_track"), "dialogue.stem_audio_track"
        )
        if abs(clean_meta["duration"] - meta["duration"]) > 0.1 or not audio_covers(
            clean_input, 0, meta["duration"], audio_track
        ):
            raise ValueError("对白底轨必须与完整剪辑等长对齐")
        base_audio = {
            "path": clean,
            "sha256": asset["sha256"],
            "source_asset_id": stem,
            "audio_track": audio_track,
            "start_seconds": float(clean_meta["audio"][audio_track].get("start_time", 0)),
            "clean_stem": True,
        }
    else:
        audio_track = select_audio_track(
            meta, dialogue.get("audio_track"), "dialogue.audio_track", allow_silent=True
        )
        if audio_track is not None:
            base_audio = {
                "path": video,
                "sha256": timeline["video_sha256"],
                "source_asset_id": None,
                "audio_track": audio_track,
                "start_seconds": float(meta["audio"][audio_track].get("start_time", 0)),
                "clean_stem": False,
            }
    return plan, video, meta, prepared, base_audio


def ducking_expression(duck, cue_start, cue_length):
    """Use one envelope for the interval union; overlapping voices never stack gain."""
    regions = sorted(
        (float(r["start_seconds"]) - cue_start, float(r["end_seconds"]) - cue_start)
        for r in duck.get("regions", [])
    )
    merged = []
    for start, end in regions:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    ramp, envelope = 0.08, None
    for start, end in merged:
        if end + ramp <= 0 or start - ramp >= cue_length:
            continue
        region = f"max(0,min(1,min((t-({start})+{ramp})/{ramp},(({end})+{ramp}-t)/{ramp})))"
        # Even the ramps of nearby non-overlapping regions must not multiply.
        envelope = region if envelope is None else f"max({envelope},{region})"
    if envelope is None:
        return None
    factor = 10 ** (float(duck.get("gain_db", -12)) / 20)
    return f"1-(1-{factor})*({envelope})"


def mix(plan_path, output):
    # Keep snapshots outside any work's asset tree so an import cannot deduplicate
    # against temporary inputs that disappear when this operation finishes.
    with tempfile.TemporaryDirectory(prefix="autodl-mix-inputs-") as directory:
        return mix_captured(Path(plan_path).resolve(), output, MixInputs(directory))


def mix_captured(plan_path, output, captured):
    plan, video, meta, cues, base_audio = validate(plan_path, captured=captured)
    captured.check_current()
    plan_path = Path(plan_path)
    manifest = resolve(plan_path.parent, plan["materials_manifest"])
    video_input = captured.capture(video)
    dest = output_path(
        video,
        output,
        "配乐混音",
        sources=(
            plan_path,
            manifest,
            *(item["path"] for item in cues),
            *((base_audio["path"],) if base_audio else ()),
        ),
    )
    prepare_media_record(dest, "混音")
    # All cue coordinates and source_in values refer to media PTS. Keep the copied
    # video at its original PTS instead of independently zeroing video and dialogue.
    args = ["-copyts", "-i", video_input]
    filters = []
    next_input = 1
    if base_audio:
        if base_audio["clean_stem"]:
            args += ["-i", captured.capture(base_audio["path"])]
            next_input += 1
        base_index = 1 if base_audio["clean_stem"] else 0
        base = f"[{base_index}:a:{base_audio['audio_track']}]"
        # Match source PTS by filling gaps/trimming overlaps, without stretching
        # samples (async=1). first_pts=0 retains leading silence and negative-PTS
        # trimming while internal gaps no longer interrupt the music bus.
        filters.append(
            base
            + "aresample=48000:async=1:min_hard_comp=0.001:first_pts=0,"
            + "aformat=channel_layouts=stereo"
            + f",apad,atrim=duration={meta['duration']}[base]"
        )
    else:
        filters.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={meta['duration']}[base]")
    labels = ["[base]"]
    for i, item in enumerate(cues):
        cue = item["cue"]
        length = item["end"] - item["start"]
        args += ["-i", captured.capture(item["path"])]
        chain = (
            f"[{next_input + i}:a:{item['audio_track']}]"
            f"atrim=start={item['source_in']}:duration={length},"
            f"asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,"
            f"volume={item['gain']}dB"
        )
        if item["fade_in"]:
            chain += f",afade=t=in:d={item['fade_in']}"
        if item["fade_out"]:
            chain += f",afade=t=out:st={length - item['fade_out']}:d={item['fade_out']}"
        duck = cue.get("dialogue_ducking", {})
        # Piecewise gain with 80ms ramps avoids clicks at dialogue interval edges.
        if duck.get("method") == "regions":
            expr = ducking_expression(duck, item["start"], length)
            if expr is not None:
                chain += f",volume='{expr}':eval=frame"
        chain += f",adelay={round(item['start'] * 1000)}:all=1[m{i}]"
        filters.append(chain)
        labels.append(f"[m{i}]")
    filters.append(
        "".join(labels) + f"amix=inputs={len(labels)}:duration=first:normalize=0,"
        f"alimiter=limit=0.95:level=0:latency=1,atrim=duration={meta['duration']}[mix]"
    )
    with tempfile.TemporaryDirectory(prefix=".混音-", dir=dest.parent) as folder:
        temp = Path(folder) / f"mix{dest.suffix}"
        ffmpeg(
            [
                *args,
                "-filter_complex",
                ";".join(filters),
                "-map",
                "0:v:0",
                "-map",
                "[mix]",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-avoid_negative_ts",
                "disabled",
                temp,
            ]
        )
        validate_output_audio_coverage(temp, meta["duration"])
        measured = measure_audio(temp)

        def build_record(after):
            captured.check_current()
            return {
                "source": str(video),
                "source_sha256": captured.digest(video),
                "plan": str(Path(plan_path).resolve()),
                "plan_sha256": captured.digest(plan_path),
                "materials_manifest": str(manifest),
                "materials_manifest_sha256": captured.digest(manifest),
                "input_binding_method": "private_file_snapshots",
                "input_bindings": captured.bindings(),
                "output": str(dest),
                "sha256": sha(temp),
                "video_stream_copy": True,
                "timeline_time_origin": "source_media_pts_zero",
                "source_video_start_seconds": float(meta["video"].get("start_time", 0)),
                "audio_inputs": {
                    "dialogue": (
                        {**base_audio, "path": str(base_audio["path"])} if base_audio else None
                    ),
                    "music": [
                        {
                            "cue_id": item["cue"]["cue_id"],
                            "source_asset_id": item["cue"]["source_asset_id"],
                            "path": str(item["path"]),
                            "sha256": item["sha256"],
                            "audio_track": item["audio_track"],
                            "source_in_seconds": item["source_in"],
                        }
                        for item in cues
                    ],
                },
                "cues": [x["cue"]["cue_id"] for x in cues],
                "technical_decode": "passed",
                "audio_timeline_coverage": "passed",
                "measured_loudness": measured,
                "audio_format": [
                    {k: s.get(k) for k in ("sample_rate", "channels", "start_time")}
                    for s in after["audio"]
                ],
                "actual_listening": "pending",
                "dialogue_intelligibility": "pending",
                "user_acceptance": None,
            }

        publish(
            temp,
            dest,
            reference=video_input,
            record=("混音", build_record),
        )
    return dest


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="action", required=True)
    for name in ("create", "mix"):
        p = sub.add_parser(name)
        p.add_argument("config")
        p.add_argument("--output", required=True)
    p = sub.add_parser("validate")
    p.add_argument("config")
    p = sub.add_parser("import")
    p.add_argument("source")
    p.add_argument("--manifest", required=True)
    p.add_argument("--asset-id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--provenance", required=True)
    sub.add_parser("capabilities")
    args = vars(ap.parse_args())
    action = args.pop("action")
    if action == "create":
        result = create_sketch(**args)
    elif action == "mix":
        result = mix(args["config"], args["output"])
    elif action == "validate":
        validate(args["config"])
        result = "结构、哈希、时长、素材、音乐/留白区域校验通过；仍需真实听音"
    elif action == "import":
        result = import_asset(**args)
    else:
        result = {
            "local_note_synthesis": True,
            "import": True,
            "mix": True,
            "ai_music_provider": None,
            "ai_music_status": "not_connected",
        }
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
