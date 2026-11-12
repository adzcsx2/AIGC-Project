"""Decode and make analysis sheets for the single actual-video-driven test."""

import argparse
import array
import hashlib
import json
import subprocess
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "projects/悬崖上的小气球"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--test", choices=("titim01", "titim02", "titim04"), default="titim01")
test = parser.parse_args().test
receipt = json.loads((WORK / f"06-记录/视频生成/一致性测试-{test}-任务与结果.json").read_text("utf-8"))
assert receipt["status"] in {"SUCCESS", "COMPLETED"} and len(receipt["files"]) == 1
source = Path(receipt["files"][0]).resolve()
assert source.is_relative_to(WORK)
directory = WORK / f"05-检查与验收/一致性测试-{test}-原生检查"
directory.mkdir(exist_ok=False)
frames = directory / "完整解码帧"
frames.mkdir()
meta = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(source)]))
subprocess.run(["ffmpeg", "-v", "error", "-n", "-i", str(source), "-map", "0:v:0", "-fps_mode", "passthrough", str(frames / "%04d.png")], check=True)
video = next(s for s in meta["streams"] if s["codec_type"] == "video")
fps = float(Fraction(video["avg_frame_rate"]))
paths = sorted(frames.glob("*.png"))
selected = list(range(0, len(paths), max(1, round(fps / 4))))
if selected[-1] != len(paths) - 1:
    selected.append(len(paths) - 1)
width, height = 448, 256
rows = (len(selected) + 2) // 3
canvas = Image.new("RGB", (width * 3, (height + 23) * rows), (20, 20, 20))
draw = ImageDraw.Draw(canvas)
for i, frame in enumerate(selected):
    x, y = i % 3 * width, i // 3 * (height + 23)
    with Image.open(paths[frame]) as im:
        canvas.paste(im.convert("RGB").resize((width, height)), (x, y + 23))
    draw.text((x + 8, y + 4), f"frame {frame:03d} | {frame / fps:.3f}s", fill="white")
canvas.save(directory / "五秒全程-每四分之一秒对照.png")
audio_peak = None
if any(s["codec_type"] == "audio" for s in meta["streams"]):
    samples = array.array("f")
    samples.frombytes(subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(source), "-map", "0:a:0", "-f", "f32le", "-"]))
    audio_peak = max((abs(v) for v in samples), default=0)
report = {
    "source": str(source),
    "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "decoded_frames": len(paths),
    "fps": fps,
    "audio_peak_decoded": audio_peak,
    "native_probe": meta,
    "scope": "Full technical decode and dense static samples; no claim of continuous dynamic watching or hearing.",
}
(directory / "原生技术探测.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
print(json.dumps({key: value for key, value in report.items() if key != "native_probe"}, ensure_ascii=True))
