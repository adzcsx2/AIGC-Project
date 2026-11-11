"""Create a short procedural creature burp and its silent 32-second guide track.

No speech synthesis, sampled person, or background music. Listening review is
separate from the waveform checks and must not be inferred from this script.
"""

import argparse
import json
import math
import random
import struct
import tempfile
import wave
from pathlib import Path

from project_tool_safety import json_staging, publish_bundle
from whitebox_saved import checked_destination, project_path, sha


def resonator(samples, sr, freq, q):
    w = 2 * math.pi * freq / sr
    alpha = math.sin(w) / (2 * q)
    a0 = 1 + alpha
    b0 = alpha / a0
    b2 = -alpha / a0
    a1 = -2 * math.cos(w) / a0
    a2 = (1 - alpha) / a0
    x1 = x2 = y1 = y2 = 0.0
    result = []
    for x in samples:
        y = b0 * x + b2 * x2 - a1 * y1 - a2 * y2
        result.append(y)
        x2 = x1
        x1 = x
        y2 = y1
        y1 = y
    return result


def write_wave(path, samples, sr):
    with path.open("xb") as fp:
        with wave.open(fp, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(
                b"".join(
                    struct.pack("<h", max(-32767, min(32767, round(v * 32767)))) for v in samples
                )
            )


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--project", required=True)
    args = a.parse_args()
    root = Path(args.project).resolve()
    out = project_path(root, "02-素材/音频")
    sample = out / "幼龙短饱嗝-合成音效04.wav"
    track = out / "睡醒舔奶-32秒声音引导04.wav"
    rec = project_path(root, "06-记录/饱嗝音效制作04.json")
    for p in (sample, track, rec):
        checked_destination(p, root)
    sr = 48000
    dur = 0.31
    start = 28.73
    rand = random.Random(710)
    phase = 0.0
    raw = []
    for i in range(round(sr * dur)):
        t = i / sr
        s = t / dur
        f0 = 175 - 65 * s + 9 * math.sin(t * 93) + 4 * rand.uniform(-1, 1)
        phase += math.tau * f0 / sr
        voiced = sum(
            math.sin(phase * k + 0.16 * k * math.sin(t * 37)) / (k**1.15) for k in range(1, 16)
        )
        raw.append(voiced * (0.78 + 0.22 * math.sin(t * 170)) + 0.16 * rand.uniform(-1, 1))
    bands = [resonator(raw, sr, f, q) for f, q in [(430, 2.7), (920, 4.0), (1800, 5.0)]]
    result = []
    for i in range(len(raw)):
        s = i / (len(raw) - 1)
        env = math.sin(math.pi * s) ** 0.65 * min(
            1, i / (sr * 0.006), (len(raw) - 1 - i) / (sr * 0.012)
        )
        v = (0.18 * raw[i] + 1.5 * bands[0][i] + 0.70 * bands[1][i] + 0.25 * bands[2][i]) * env
        result.append(v)
    peak = max(abs(v) for v in result)
    result = [v * 0.28 / peak for v in result]
    full = [0.0] * (32 * sr)
    at = round(start * sr)
    full[at : at + len(result)] = result
    with tempfile.TemporaryDirectory(prefix=".饱嗝制作-", dir=root) as folder:
        staged_sample = Path(folder) / sample.name
        staged_track = Path(folder) / track.name
        write_wave(staged_sample, result, sr)
        write_wave(staged_track, full, sr)
        staged_record = json_staging(
            folder,
            rec.name,
            dict(
                method="Local procedural nonverbal creature-burp synthesis",
                sample=str(sample.relative_to(root)),
                sample_sha256=sha(staged_sample),
                track=str(track.relative_to(root)),
                track_sha256=sha(staged_track),
                start=start,
                duration=dur,
                sample_rate=sr,
                peak=0.28,
                dialogue=False,
                music=False,
                actual_listening="pending",
                user_acceptance="pending",
            ),
        )
        publish_bundle([(staged_sample, sample), (staged_track, track), (staged_record, rec)], root)
    print(json.dumps({"sample": str(sample), "track": str(track)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
