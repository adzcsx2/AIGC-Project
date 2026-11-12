"""Read-only technical checks and timestamped stills for the first-five trial."""

import argparse
import hashlib
import json
import subprocess
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    result = subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    batch = json.loads(
        (project / "06-记录/视频生成/前五段试制01-任务与结果.json").read_text(encoding="utf-8")
    )
    destination = project / "05-检查与验收/前五段试制01-源段检查"
    destination.mkdir(parents=True, exist_ok=True)
    report = []
    planned = [10, 13, 15, 13, 15]
    sample_times = [
        [0, 0.5, 2, 4, 5.9, 6.8, 7.8, 8.8, 9.7],
        [0, 1.5, 3.5, 5.5, 7, 8.5, 9.5, 11, 12.7],
        [0, 1.5, 4, 6, 8.8, 9.5, 11, 13, 14.7],
        [0, 1.5, 3.5, 5, 6.5, 8, 9.5, 11.2, 12.7],
        [0, 1.5, 4, 6, 8.8, 9.5, 11, 13, 14.7],
    ]
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
    for index, row in enumerate(batch["tasks"], 1):
        if row.get("state") != "downloaded":
            continue
        source = Path(row["files"][0]).resolve()
        if not source.is_relative_to(project):
            raise ValueError("Source outside this work")
        source_hash = digest(source)
        entry_path = destination / f"片段{index:02d}-技术检查.json"
        if entry_path.exists():
            entry = json.loads(entry_path.read_text(encoding="utf-8"))
            if entry["sha256"] != source_hash or entry["source"] != str(source):
                raise ValueError("Previously checked source changed; use a new review version")
            report.append(entry)
            continue
        data = json.loads(
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
        video = next(stream for stream in data["streams"] if stream["codec_type"] == "video")
        audio = [stream for stream in data["streams"] if stream["codec_type"] == "audio"]
        rate = Fraction(video["avg_frame_rate"])
        count = int(video["nb_read_frames"])
        duration = float(video.get("duration") or data["format"]["duration"])
        frame_indexes = sorted({min(count - 1, int(t * rate)) for t in sample_times[index - 1]})
        frames = destination / f"片段{index:02d}-检查帧"
        frames.mkdir(exist_ok=False)
        expression = "+".join(f"eq(n\\,{n})" for n in frame_indexes)
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(source),
                "-vf",
                f"select={expression},scale=480:-2",
                "-fps_mode",
                "vfr",
                str(frames / "%02d.png"),
            ]
        )
        images = sorted(frames.glob("*.png"))
        if len(images) != len(frame_indexes):
            raise ValueError("Extracted frame count mismatch")
        with Image.open(images[0]) as first:
            tile_height = first.height + 30
        sheet = Image.new("RGB", (480 * 3, tile_height * 3), "#202020")
        draw = ImageDraw.Draw(sheet)
        for n, (path, frame_index) in enumerate(zip(images, frame_indexes, strict=True)):
            x, y = n % 3 * 480, n // 3 * tile_height
            with Image.open(path) as frame:
                sheet.paste(frame.convert("RGB"), (x, y + 30))
            draw.text(
                (x + 5, y + 3),
                f"CLIFF-{index:02d}  {frame_index / float(rate):.3f}s  frame {frame_index}",
                fill="white",
                font=font,
            )
        sheet_path = destination / f"片段{index:02d}-首中尾与接触对照.png"
        sheet.save(sheet_path)
        if digest(source) != source_hash:
            raise ValueError("Source changed during checks")
        entry = {
            "shot_id": f"CLIFF-{index:02d}",
            "task_id": row["task_id"],
            "source": str(source),
            "sha256": source_hash,
            "planned_duration": planned[index - 1],
            "duration": duration,
            "width": video["width"],
            "height": video["height"],
            "fps": str(rate),
            "frame_count": count,
            "audio_streams": [
                {
                    k: stream.get(k)
                    for k in ("codec_name", "sample_rate", "channels", "duration", "start_time")
                }
                for stream in audio
            ],
            "decode": "passed",
            "sample_frame_indexes": frame_indexes,
            "contact_sheet": str(sheet_path),
            "dynamic_review": "pending",
            "actual_listening": "pending",
            "user_acceptance": "pending",
        }
        report.append(entry)
        with entry_path.open("x", encoding="utf-8") as handle:
            json.dump(entry, handle, ensure_ascii=False, indent=2)
        print(
            json.dumps(
                {
                    k: entry[k]
                    for k in (
                        "shot_id",
                        "duration",
                        "width",
                        "height",
                        "fps",
                        "frame_count",
                        "decode",
                    )
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    with (destination / "技术检查与检查帧.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
