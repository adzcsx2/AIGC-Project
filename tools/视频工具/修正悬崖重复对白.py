"""Remove confirmed repeated off-screen dialogue; preserve all video frames and originals."""
# ruff: noqa: E501 -- Exact Chinese artifact filenames.

import hashlib
import json
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "projects/悬崖上的小气球"
TAG = "正式前五段u30重制03"
PY = ROOT / ".venv/Scripts/python.exe"


def run(args):
    r = subprocess.run([str(v) for v in args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(r.stderr[-2000:] + r.stdout[-2000:])
    return r.stdout


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


previous = P / f"06-记录/视频生成/{TAG}-处理交付01.json"
data = json.loads(previous.read_text(encoding="utf-8"))
unit = next(value for value in data["units"] if value["n"] == 3)
old_video_sha = {}
for key, suffix in [("intermediate", "原速24帧02-对白去重复"), ("final", "60帧02-对白去重复")]:
    source = P / unit[key]
    target = source.with_name(f"片段03-第一次笑与调侃-{suffix}.mp4")
    assert not target.exists()
    # The first full line ends by8.6s. Fade only after8.8s, before the verified repeated
    # phrase at10.0+s. No required dragon words/vocalization exists in this unit's tail.
    run(["ffmpeg", "-v", "error", "-i", source, "-map", "0:v:0", "-map", "0:a:0",
         "-c:v", "copy", "-af", "afade=t=out:st=8.8:d=0.5,volume=0:enable='gte(t,9.3)'",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", target])
    def video_digest(path):
        return run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:v:0", "-c:v", "copy", "-f", "hash", "-hash", "sha256", "pipe:1"]).strip()
    assert video_digest(source) == video_digest(target)
    old_video_sha[key] = {"source": str(source.relative_to(P)), "source_sha256": sha(source),
                          "patched": str(target.relative_to(P)), "patched_sha256": sha(target),
                          "video_packets_identical": True}
    unit[key] = str(target.relative_to(P))
    if key == "final":
        unit["final_sha256"] = sha(target)

for fps, source_key, name in [(24, "intermediate", "前五段整批试看-原速24帧02-对白去重复"),
                              (60, "final", "前五段整批试看-60帧02-对白去重复")]:
    config = P / f"03-制作/制作计划/{TAG}/整批试看{fps}帧剪辑02-对白去重复.yaml"
    clips = [{"path": str(P / value[source_key]), "in_seconds": 0,
              "out_seconds": value["duration"], "speed": 1} for value in sorted(data["units"], key=lambda v: v["n"])]
    config.write_text(yaml.safe_dump({"fps": fps, "clips": clips}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    folder = "04-输出/后期中间" if fps == 24 else "04-输出/成片"
    target = P / folder / TAG / (name + ".mp4")
    assert not target.exists()
    run([PY, "-X", "utf8", ROOT / "tools/视频工具/剪辑.py", config, "--output", target])
    if fps == 24:
        data["combined"]["source_24fps"] = str(target.relative_to(P))
    else:
        data["combined"]["path"] = str(target.relative_to(P))
        data["combined"]["sha256"] = sha(target)
data["previous_record"] = str(previous.relative_to(P))
data["dialogue_correction"] = {"unit": 3, "first_complete_line_end_asr": 8.6,
    "independent_duplicate_confirmation": "05-检查与验收/正式前五段u30重制03-片段03重复对白独立复核01.json",
    "fade_out_seconds": [8.8, 9.3], "mute_after": 9.3, "changes": old_video_sha,
    "tradeoff": "Mixed-source wind/room sound in the same tail is also faded; first full dialogue retained.",
    "no_new_generation_or_interpolation": True}
output = P / f"06-记录/视频生成/{TAG}-处理交付02-对白去重复.json"
output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"final": data["combined"]["path"], "record": str(output.relative_to(P)),
                  "duration": 56, "speed": 1, "repeated_phrase_removed": True}, ensure_ascii=False))
