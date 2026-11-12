"""Process already-downloaded authorized u30 units, retaining speed and source media."""
# ruff: noqa: E501 -- Exact Chinese artifact paths and media labels.

import hashlib
import json
import subprocess
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "projects/悬崖上的小气球"
TAG = "正式前五段u30重制03"
PY = ROOT / ".venv/Scripts/python.exe"


def run(command):
    result = subprocess.run([str(v) for v in command], capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(result.stderr[-2500:] + result.stdout[-2500:])
    return result.stdout


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(path):
    return json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path]))


def interpolate(source, stem):
    output = source.parent / (stem + ".mp4")
    assert not output.exists()
    text = run([PY, "-X", "utf8", ROOT / "tools/视频工具/补帧.py", source, "--output-stem", stem])
    assert output.is_file(), text[-1500:]
    return output, text


def main():
    jobs = json.loads((P / f"06-记录/视频生成/{TAG}-任务与结果01.json").read_text(encoding="utf-8"))["jobs"]
    pack = json.loads((P / f"03-制作/制作计划/{TAG}/制作包02-实际输入.json").read_text(encoding="utf-8"))
    assert len(jobs) == 5
    record_path = P / f"06-记录/视频生成/{TAG}-处理交付01.json"
    previous = json.loads(record_path.read_text(encoding="utf-8")) if record_path.exists() else {}
    records = previous.get("units", [])
    if "combined" in previous:
        assert sha(P / previous["combined"]["path"]) == previous["combined"]["sha256"]
        print("Already completed; verified existing combined output")
        return
    middle = P / "04-输出/后期中间" / TAG
    final_dir = P / "04-输出/成片" / TAG
    middle.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 21)
    for unit in pack["units"]:
        n, duration = unit["n"], unit["seconds"]
        job = next(j for j in jobs if j["n"] == n)
        if any(record["n"] == n for record in records):
            continue
        if job["status"] != "SUCCESS" or not job.get("files"):
            continue
        source = Path(job["files"][0]).resolve(strict=True)
        assert source.is_relative_to(P) and source.suffix.lower() == ".mp4"
        info = probe(source)
        video = next(s for s in info["streams"] if s["codec_type"] == "video")
        assert video["r_frame_rate"] == "24/1", "Unexpected native fps; preserve/replan instead of forcing24"
        width, height = video["width"], video["height"]
        target_h = width * 9 // 16
        assert width % 16 == 0 and target_h % 2 == 0 and 0 <= height - target_h <= 16
        top = (height - target_h) // 2
        inter = middle / f"片段{n:02d}-{unit['name']}-原速24帧01.mp4"
        assert not inter.exists()
        run(["ffmpeg", "-v", "error", "-i", source, "-map", "0:v:0", "-map", "0:a:0?", "-vf",
             f"crop={width}:{target_h}:0:{top}", "-t", str(duration), "-c:v", "libx264", "-crf", "16",
             "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", inter])
        stem = f"片段{n:02d}-{unit['name']}-60帧01"
        output, log = interpolate(inter, stem)
        destination = final_dir / output.name
        assert not destination.exists()
        output.rename(destination)
        (P / f"06-记录/视频生成/{TAG}-片段{n:02d}-补帧01.txt").write_text(log, encoding="utf-8")
        frames = P / "05-检查与验收" / TAG / f"片段{n:02d}-实际帧"
        frames.mkdir(parents=True, exist_ok=True)
        indices = sorted({0, int(duration * 24 / 2), duration * 24 - 1})
        if n in (2, 4):
            indices = sorted({0, 30, 48, 60, 72, 84, 96, duration * 24 - 1})
        expression = "+".join(f"eq(n,{i})" for i in indices)
        run(["ffmpeg", "-v", "error", "-i", source, "-vf", f"select='{expression}'", "-fps_mode", "vfr", frames / "帧%02d.png"])
        rows = (len(indices) + 1) // 2
        sheet = Image.new("RGB", (1344, rows * 414), "#e5e8eb")
        draw = ImageDraw.Draw(sheet)
        for i, index in enumerate(indices):
            image = Image.open(frames / f"帧{i+1:02d}.png").convert("RGB")
            image.thumbnail((672, 384))
            x, y = i % 2 * 672, i // 2 * 414
            sheet.paste(image, (x, y))
            draw.text((x + 8, y + 385), f"{index/24:.3f}s / frame {index}", font=font, fill="#15232d")
        sheet.save(frames / "原片总览01.jpg", quality=92)
        record = {"n": n, "task_id": job["task_id"], "source": str(source.relative_to(P)),
                  "source_sha256": sha(source), "native": video, "raw_info": info,
                  "intermediate": str(inter.relative_to(P)), "final": str(destination.relative_to(P)),
                  "final_sha256": sha(destination), "final_info": probe(destination), "speed": 1,
                  "duration": duration, "crop_top": top, "crop_bottom": height-target_h-top,
                  "frames_evidence": str(frames.relative_to(P)), "audio_policy": "Preserve generated story audio; no added music"}
        records.append(record)
        record_path.write_text(json.dumps({"units": records}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"n": n, "final": str(destination), "duration": duration}, ensure_ascii=False), flush=True)
    if len(records) < 5:
        print(json.dumps({"processed_units": [record["n"] for record in records], "waiting_for_other_existing_tasks": True}), flush=True)
        return
    records.sort(key=lambda record: record["n"])
    clips = [{"path": str(P / record["intermediate"]), "in_seconds": 0,
              "out_seconds": record["duration"], "speed": 1} for record in records]
    config = P / f"03-制作/制作计划/{TAG}/整批试看剪辑01.yaml"
    config.write_text(yaml.safe_dump({"fps": 24, "clips": clips}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    combined = middle / "前五段整批试看-原速24帧01.mp4"
    run([PY, "-X", "utf8", ROOT / "tools/视频工具/剪辑.py", config, "--output", combined])
    # All five units are already RIFE60. Join their existing frames to keep hard cuts
    # free from a second interpolation pass across generation-unit boundaries.
    final_config = P / f"03-制作/制作计划/{TAG}/整批试看60帧拼接01.yaml"
    final_clips = [{"path": str(P / record["final"]), "in_seconds": 0,
                    "out_seconds": record["duration"], "speed": 1} for record in records]
    final_config.write_text(yaml.safe_dump({"fps": 60, "clips": final_clips}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    destination = final_dir / "前五段整批试看-60帧01.mp4"
    assert not destination.exists()
    log = run([PY, "-X", "utf8", ROOT / "tools/视频工具/剪辑.py", final_config, "--output", destination])
    (P / f"06-记录/视频生成/{TAG}-整批60帧拼接01.txt").write_text(log, encoding="utf-8")
    result = {"units": records, "combined": {"path": str(destination.relative_to(P)), "sha256": sha(destination),
              "info": probe(destination), "source_24fps": str(combined.relative_to(P)), "speed": 1,
              "cut_seconds": [10, 18, 33, 41], "interpolation": "Each unit once; existing60fps frames joined without cross-unit RIFE",
              "seam_review": "pending_actual_browser_review"}}
    (P / f"06-记录/视频生成/{TAG}-处理交付01.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"combined": str(destination), "status": "processed_technical_checks_passed"}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
