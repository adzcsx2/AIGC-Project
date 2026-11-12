"""Create exact-frame seam evidence and original-speed browser preview clips."""

import argparse
import json
import subprocess
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def run(args):
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:])
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    parser.add_argument("video", type=Path)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    work, video = args.project.resolve(), args.video.resolve()
    if not video.is_relative_to(work):
        raise ValueError("Video must belong to this work")
    edit = json.loads(
        (work / "04-输出/处理过程/前五段试制01-原声连看-24帧.mp4.剪辑记录.json").read_text(
            encoding="utf-8"
        )
    )
    meta = json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-of",
                "json",
                str(video),
            ]
        )
    )
    stream = next(s for s in meta["streams"] if s["codec_type"] == "video")
    rate = Fraction(stream["avg_frame_rate"])
    destination = work / "05-检查与验收/前五段试制01-接缝检查" / args.label
    destination.mkdir(parents=True, exist_ok=False)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 16)
    sheet = None
    records = []
    for index, seam in enumerate(edit["seams"], 1):
        time = seam["at_seconds"]
        cut = round(time * rate)
        indexes = sorted(
            {
                cut - round(2 * rate),
                cut - round(rate / 2),
                cut - 1,
                cut,
                cut + round(rate / 2),
                cut + round(2 * rate),
            }
        )
        frames = destination / f"接口{index:02d}-精确帧"
        frames.mkdir()
        expression = "+".join(f"eq(n\\,{n})" for n in indexes)
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(video),
                "-vf",
                f"select={expression},scale=320:-2",
                "-fps_mode",
                "vfr",
                str(frames / "%02d.png"),
            ]
        )
        images = sorted(frames.glob("*.png"))
        if len(images) != len(indexes):
            raise ValueError("Seam sample count mismatch")
        with Image.open(images[0]) as first:
            height = first.height + 26
        if sheet is None:
            sheet = Image.new("RGB", (320 * 6, height * 4), "#202020")
        draw = ImageDraw.Draw(sheet)
        for col, (path, frame) in enumerate(zip(images, indexes, strict=True)):
            x, y = col * 320, (index - 1) * height
            with Image.open(path) as image:
                sheet.paste(image.convert("RGB"), (x, y + 26))
            draw.text(
                (x + 4, y + 3),
                f"B{index} {frame / float(rate):.3f}s f{frame}",
                font=font,
                fill="white",
            )
        preview = destination / f"接口{index:02d}-前后各两秒.mp4"
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-n",
                "-ss",
                str(time - 2),
                "-i",
                str(video),
                "-t",
                "4",
                "-map",
                "0:v:0",
                "-map",
                "0:a:0",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(preview),
            ]
        )
        records.append(
            {
                "boundary": index,
                "at_seconds": time,
                "source": str(video),
                "fps": str(rate),
                "frames": indexes,
                "preview": str(preview),
                "dynamic": "pending",
                "listening": "pending",
            }
        )
        print(f"{args.label}: B{index} evidence ready", flush=True)
    if sheet is None:
        raise ValueError("No seams")
    sheet.save(destination / "四处接缝-精确帧对照.png")
    (destination / "接缝窗口与检查帧.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
