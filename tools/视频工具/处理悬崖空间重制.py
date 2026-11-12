"""Process R05 replacements and merge with unchanged R03 unit01 at original speed."""

# ruff: noqa: E501 -- Exact versioned Chinese media names.
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "projects/悬崖上的小气球"
TAG = "空间重制05"
spec = importlib.util.spec_from_file_location(
    "r03_media_helpers", Path(__file__).with_name("处理悬崖前五段u30重制.py")
)
assert spec and spec.loader
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
run, sha, probe, interpolate = helpers.run, helpers.sha, helpers.probe, helpers.interpolate
PY = ROOT / ".venv/Scripts/python.exe"


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")


def make_sheet(source: Path, n: int, seconds: int) -> str:
    folder = P / "05-检查与验收" / TAG / f"片段{n:02d}-实际帧"
    folder.mkdir(parents=True, exist_ok=True)
    times = (
        [0, 1, 2, 2.5, 3, 3.5, 4.2, 5.5, 7, 7.95]
        if n == 2
        else [0, 1, 3, 5.5, 6.5, 8, 9, 10.5, 12, 13.5, 14.95]
    )
    if n == 4:
        times = [0, 1, 2, 2.5, 2.6, 2.7, 2.8, 3, 3.5, 5.95]
    indices = sorted({min(int(t * 24), seconds * 24 - 1) for t in times})
    expression = "+".join(f"eq(n,{i})" for i in indices)
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            source,
            "-vf",
            f"select='{expression}'",
            "-fps_mode",
            "vfr",
            folder / "帧%02d.png",
        ]
    )
    sheet = Image.new("RGB", (1344, ((len(indices) + 1) // 2) * 408), "#e8edf1")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)
    for i, frame in enumerate(indices):
        with Image.open(folder / f"帧{i + 1:02d}.png") as im:
            im.thumbnail((672, 378))
            x, y = i % 2 * 672, i // 2 * 408
            sheet.paste(im, (x, y))
            draw.text(
                (x + 8, y + 380), f"{frame / 24:.3f}s / frame {frame}", font=font, fill="#13202b"
            )
    sheet.save(folder / "原片总览01.jpg", quality=94)
    return folder.relative_to(P).as_posix()


def main() -> None:
    rec_path = P / f"06-记录/视频生成/{TAG}-处理交付01.json"
    rec = json.loads(rec_path.read_text("utf-8")) if rec_path.exists() else {"units": []}
    if "combined" in rec:
        assert sha(P / rec["combined"]["path"]) == rec["combined"]["sha256"]
        print("Already processed; existing output hash verified.")
        return
    jobs_path = P / f"06-记录/视频生成/{TAG}-任务与结果01.json"
    jobs_doc = json.loads(jobs_path.read_text("utf-8"))
    pack = json.loads((P / f"03-制作/制作计划/{TAG}/制作包03-实际输入.json").read_text("utf-8"))
    old = json.loads(
        (P / "06-记录/视频生成/正式前五段u30重制03-处理交付02-对白去重复.json").read_text("utf-8")
    )
    for n in (1,):
        if any(x["n"] == n for x in rec["units"]):
            continue
        item = dict(next(x for x in old["units"] if x["n"] == n))
        assert sha(P / item["final"]) == item["final_sha256"]
        item["reuse_from"] = "正式前五段u30重制03"
        rec["units"].append(item)
    middle = P / "04-输出/后期中间" / TAG
    output = P / "04-输出/成片" / TAG
    middle.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    for unit in pack["units"]:
        n, duration = unit["n"], unit["duration"]
        if any(x["n"] == n for x in rec["units"]):
            continue
        job = next(x for x in jobs_doc["jobs"] if x["n"] == n)
        task_path = ROOT / ".autodl/tasks" / (job["task_id"] + ".json")
        task = json.loads(task_path.read_text("utf-8"))
        if task.get("response", {}).get("status") != "SUCCESS" or not task.get("files"):
            print(f"Still waiting for existing task: {n}", flush=True)
            continue
        source = Path(task["files"][0]).resolve(strict=True)
        assert source.is_relative_to(P) and source.suffix.lower() == ".mp4"
        job.update(status="SUCCESS", files=task["files"])
        save(jobs_path, jobs_doc)
        info = probe(source)
        video = next(x for x in info["streams"] if x["codec_type"] == "video")
        assert video["r_frame_rate"] == "24/1", "Unexpected native FPS; preserve and reassess."
        w, h = video["width"], video["height"]
        target_h = w * 9 // 16
        assert w % 16 == 0 and target_h % 2 == 0 and 0 <= h - target_h <= 16
        assert float(info["format"]["duration"]) >= duration - 0.05
        top = (h - target_h) // 2
        inter = middle / f"片段{n:02d}-{unit['name']}-原速24帧01.mp4"
        if not inter.exists():
            run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-i",
                    source,
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a:0?",
                    "-vf",
                    f"crop={w}:{target_h}:0:{top}",
                    "-t",
                    duration,
                    "-c:v",
                    "libx264",
                    "-crf",
                    "16",
                    "-preset",
                    "medium",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-ar",
                    "48000",
                    "-movflags",
                    "+faststart",
                    inter,
                ]
            )
        stem = f"片段{n:02d}-{unit['name']}-60帧01"
        destination = output / (stem + ".mp4")
        if not destination.exists():
            generated, log = interpolate(inter, stem)
            generated.rename(destination)
            (P / f"06-记录/视频生成/{TAG}-片段{n:02d}-补帧01.txt").write_text(log, "utf-8")
        final_info = probe(destination)
        final_video = next(x for x in final_info["streams"] if x["codec_type"] == "video")
        assert (
            final_video["r_frame_rate"] == "60/1" and int(final_video["nb_frames"]) == duration * 60
        )
        item = {
            "n": n,
            "task_id": job["task_id"],
            "source": source.relative_to(P).as_posix(),
            "source_sha256": sha(source),
            "raw_info": info,
            "intermediate": inter.relative_to(P).as_posix(),
            "final": destination.relative_to(P).as_posix(),
            "final_sha256": sha(destination),
            "final_info": final_info,
            "duration": duration,
            "speed": 1,
            "crop_top": top,
            "crop_bottom": h - target_h - top,
            "frames_evidence": make_sheet(inter, n, duration),
            "audio_policy": "Preserve generated dialogue/audio; no added music",
        }
        rec["units"].append(item)
        save(rec_path, rec)
        print(json.dumps({"n": n, "final": item["final"]}, ensure_ascii=False), flush=True)
    if len(rec["units"]) != 5:
        save(rec_path, rec)
        print("Waiting for remaining existing tasks.")
        return
    rec["units"].sort(key=lambda x: x["n"])
    for fps, key, target in [
        (24, "intermediate", middle / "前五段空间重制试看-原速24帧01.mp4"),
        (60, "final", output / "前五段空间重制试看-60帧01.mp4"),
    ]:
        edit = {
            "fps": fps,
            "clips": [
                {
                    "path": str(P / item[key]),
                    "in_seconds": 0,
                    "out_seconds": item["duration"],
                    "speed": 1,
                }
                for item in rec["units"]
            ],
        }
        config = P / f"03-制作/制作计划/{TAG}/前五段{fps}帧拼接01.yaml"
        config.write_text(yaml.safe_dump(edit, allow_unicode=True, sort_keys=False), "utf-8")
        if not target.exists():
            run([PY, "-X", "utf8", ROOT / "tools/视频工具/剪辑.py", config, "--output", target])
        if fps == 60:
            info = probe(target)
            v = next(x for x in info["streams"] if x["codec_type"] == "video")
            assert v["r_frame_rate"] == "60/1" and int(v["nb_frames"]) == 3195
            rec["combined"] = {
                "path": target.relative_to(P).as_posix(),
                "sha256": sha(target),
                "info": info,
                "duration": 53.25,
                "cut_seconds": [10, 18, 32.25, 38.25],
                "speed": 1,
                "interpolation": "Each replacement once; unchanged01 reuse60fps; no cross-unit interpolation.",
                "seam_review": "pending_actual_browser_review",
                "creative_acceptance": "pending_user_review",
            }
    save(rec_path, rec)
    print(json.dumps({"combined": rec["combined"]["path"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
