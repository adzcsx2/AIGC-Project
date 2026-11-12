"""Decode and sample the downloaded three-scene rebuild; no creative auto-pass."""

import hashlib
import json
import re
import subprocess
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "projects/悬崖上的小气球"
VERSION = "正式前三段重制02"
BATCH = P / f"06-记录/视频生成/{VERSION}-任务与结果.json"


def run(args):
    result = subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:])
    return result


batch = json.loads(BATCH.read_text(encoding="utf-8"))
font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 18)
reports = []
for i, task in enumerate(batch["tasks"], 1):
    if not task.get("files"):
        continue
    source = Path(task["files"][0]).resolve(strict=True)
    assert source.is_relative_to(P.resolve())
    folder = P / f"05-检查与验收/{VERSION}/片段{i:02d}-源段检查01"
    folder.mkdir(parents=True, exist_ok=True)
    report_file = folder / "技术与采样.json"
    with source.open("rb") as stream:
        source_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    if report_file.exists():
        existing = json.loads(report_file.read_text(encoding="utf-8"))
        if existing.get("sha256") != source_hash or existing.get("source") != str(source):
            raise RuntimeError(
                "Existing review belongs to different video bytes; use a new review folder"
            )
        reports.append(existing)
        continue
    probe = json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-count_frames",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(source),
            ]
        ).stdout
    )
    run(["ffmpeg", "-v", "error", "-i", str(source), "-f", "null", "-"])
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    fps = Fraction(video["avg_frame_rate"])
    samples = folder / "四分之一秒采样"
    samples.mkdir(exist_ok=False)
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(source),
            "-vf",
            "fps=4,scale=672:-2",
            str(samples / "%04d.png"),
        ]
    )
    frames = sorted(samples.glob("*.png"))
    for offset in range(0, len(frames), 12):
        sheet = Image.new("RGB", (1344, 3 * 270), "#18212b")
        draw = ImageDraw.Draw(sheet)
        for k, frame in enumerate(frames[offset : offset + 12]):
            x, y = (k % 4) * 336, (k // 4) * 270
            with Image.open(frame) as im:
                im.thumbnail((336, 240))
                sheet.paste(im.convert("RGB"), (x, y + 27))
            draw.text((x + 5, y + 3), f"S{i:02d} {(offset + k) / 4:.2f}s", font=font, fill="white")
        sheet.save(folder / f"时序接触表-{offset // 12 + 1:02d}.png")
    scene_log = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(source),
            "-an",
            "-vf",
            "select=gt(scene\\,0.28),showinfo",
            "-fps_mode",
            "vfr",
            "-f",
            "null",
            "-",
        ]
    ).stderr
    candidates = [float(t) for t in re.findall(r"pts_time:([\d.]+)", scene_log)]
    report = {
        "source": str(source),
        "sha256": source_hash,
        "probe": probe,
        "fps": str(fps),
        "frames": int(video["nb_read_frames"]),
        "cut_candidates_seconds": candidates,
        "sampling": "4fps image sampling, not audio review",
        "review_states": {
            "decode": "passed",
            "size": "pending",
            "speed": "pending",
            "style": "pending",
            "dialogue_lips": "pending",
        },
    }
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    reports.append(report)
    print(
        json.dumps(
            {
                "segment": i,
                "fps": str(fps),
                "frames": report["frames"],
                "size": [video["width"], video["height"]],
                "cut_candidates": candidates,
            }
        )
    )
(P / f"05-检查与验收/{VERSION}/三段技术检查汇总01.json").write_text(
    json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8"
)
