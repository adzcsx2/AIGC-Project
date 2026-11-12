"""Protect confirmed hard cuts from cross-shot RIFE interpolation; preserve time/audio."""

import hashlib
import json
import math
import subprocess
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "projects/悬崖上的小气球"
NATIVE = WORK / "04-输出/成片/前五段试片-24帧-版本01.mp4"
RIFE = WORK / "04-输出/成片/前五段试片-60帧-版本01.mp4"
OUTPUT = WORK / "04-输出/成片/前五段试片-60帧-版本02-切镜保护.mp4"
CUTS = [141, 176, 243, 293, 532, 571, 763, 933, 1209, 1261, 1510]


def run(args):
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:])
    return result.stdout


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    folder = WORK / "05-检查与验收/前五段试制01-切镜保护"
    folder.mkdir(parents=True, exist_ok=False)
    pins = {str(path): sha(path) for path in (NATIVE, RIFE)}
    indexes = sorted({n for cut in CUTS for n in (cut - 1, cut)})
    frame_folder = folder / "原生切镜两侧"
    frame_folder.mkdir()
    expression = "+".join(f"eq(n\\,{n})" for n in indexes)
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(NATIVE),
            "-vf",
            f"select={expression}",
            "-fps_mode",
            "vfr",
            str(frame_folder / "%03d.png"),
        ]
    )
    images = sorted(frame_folder.glob("*.png"))
    if len(images) != len(indexes):
        raise ValueError("Native cut frame count mismatch")
    by_frame = dict(zip(indexes, images, strict=True))
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 18)
    for group, offset in enumerate(range(0, len(CUTS), 6), 1):
        sheet = Image.new("RGB", (1600, 3 * 250), "#202020")
        draw = ImageDraw.Draw(sheet)
        for index, cut in enumerate(CUTS[offset : offset + 6]):
            row, pair_col = index // 2, index % 2
            for side, frame in enumerate((cut - 1, cut)):
                x, y = (pair_col * 2 + side) * 400, row * 250
                with Image.open(by_frame[frame]) as image:
                    sheet.paste(image.convert("RGB").resize((400, 225)), (x, y + 25))
                draw.text(
                    (x + 4, y + 2),
                    f"cut {cut}  frame {frame}  {frame / 24:.3f}s",
                    fill="white",
                    font=font,
                )
        sheet.save(folder / f"实际硬切两侧-对照{group:02d}.png")
    records = []
    args = ["ffmpeg", "-v", "error", "-n", "-i", str(RIFE)]
    filters = []
    last = "0:v:0"
    for index, cut in enumerate(CUTS, 1):
        start = math.ceil(Fraction(cut - 1, 24) * 60)
        stop = math.ceil(Fraction(cut, 24) * 60)
        patch = by_frame[cut - 1]
        args += ["-i", str(patch)]
        output = f"v{index}"
        # overlay's n is one-based; shift the zero-based decoded-frame interval.
        filters.append(
            f"[{last}][{index}:v:0]overlay=eof_action=repeat:shortest=0:"
            f"enable='between(n,{start + 1},{stop})'[{output}]"
        )
        last = output
        records.append(
            {
                "native_first_new_frame": cut,
                "native_last_old_frame": cut - 1,
                "target_start_frame": start,
                "target_end_exclusive": stop,
                "patch": str(patch),
                "method": "hold existing last old-shot sample only within its native exposure interval",
            }
        )
    args += [
        "-filter_complex_threads",
        "1",
        "-filter_complex",
        ";".join(filters),
        "-map",
        f"[{last}]",
        "-map",
        "0:a:0",
        "-c:v",
        "libx264",
        "-crf",
        "16",
        "-preset",
        "fast",
        "-c:a",
        "copy",
        "-fps_mode",
        "passthrough",
        "-frames:v",
        "4058",
        "-movflags",
        "+faststart",
        str(OUTPUT),
    ]
    run(args)
    for path in (NATIVE, RIFE):
        if sha(path) != pins[str(path)]:
            raise ValueError("Source changed")
    run(["ffmpeg", "-v", "error", "-i", str(OUTPUT), "-f", "null", "-"])
    before_audio = run(
        ["ffmpeg", "-v", "error", "-i", str(RIFE), "-map", "0:a:0", "-f", "md5", "-"]
    ).strip()
    after_audio = run(
        ["ffmpeg", "-v", "error", "-i", str(OUTPUT), "-map", "0:a:0", "-f", "md5", "-"]
    ).strip()
    if before_audio != after_audio:
        raise ValueError("Audio changed")
    (folder / "切镜保护记录.json").write_text(
        json.dumps(
            {
                "input_pins": pins,
                "output": str(OUTPUT),
                "output_sha256": sha(OUTPUT),
                "records": records,
                "audio_decoded_md5": after_audio,
                "audio_unchanged": True,
                "scope": "Temporal resampling at confirmed hard cuts only; no new frames or story repair.",
                "verification": "full decode passed; precise target frame comparisons pending",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(str(OUTPUT), flush=True)


if __name__ == "__main__":
    main()
