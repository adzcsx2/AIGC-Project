"""Auxiliary offline ASR of R04 source dialogue; never certifies listening or voice quality."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".autodl/audio-audit-deps"))
import numpy as np  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402

P = ROOT / "projects/悬崖上的小气球"
EXPECTED = {
    3: "Gulu, you flew so high! A whole grasshopper high! Are those wings or little fans?",
    5: "Oh, my tummy... All right, little chubby dragon, admit it. "
    "You're really a fat lizard pretending to be a dragon, aren't you?",
}


def main() -> None:
    jobs = json.loads((P / "06-记录/视频生成/局部重制04-任务与结果01.json").read_text("utf-8"))[
        "jobs"
    ]
    model = WhisperModel(
        "base",
        device="cpu",
        compute_type="int8",
        cpu_threads=4,
        download_root=str(ROOT / ".autodl/asr-models"),
        local_files_only=True,
    )
    records = []
    for n, expected in EXPECTED.items():
        job = next(x for x in jobs if x["n"] == n)
        task = json.loads((ROOT / ".autodl/tasks" / (job["task_id"] + ".json")).read_text("utf-8"))
        if not task.get("files"):
            continue
        source = Path(task["files"][0]).resolve(strict=True)
        assert source.is_relative_to(P)
        pcm = subprocess.check_output(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(source),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_f32le",
                "-f",
                "f32le",
                "pipe:1",
            ]
        )
        samples = np.frombuffer(pcm, dtype="<f4").copy()
        segments, info = model.transcribe(
            samples,
            language=None,
            task="transcribe",
            beam_size=5,
            vad_filter=False,
            temperature=0,
            condition_on_previous_text=False,
        )
        actual = [{"start": x.start, "end": x.end, "text": x.text} for x in segments]
        item = {
            "n": n,
            "source": source.relative_to(P).as_posix(),
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "model": "faster-whisper1.2.1 / multilingual base / CPU int8",
            "language_forced": False,
            "language_detected": info.language,
            "language_probability": info.language_probability,
            "expected_english": expected,
            "segments": actual,
            "actual_text": " ".join(x["text"].strip() for x in actual),
            "scope": "Auxiliary ASR; not hearing, timbre, emotion or lip-sync acceptance.",
        }
        records.append(item)
        print(json.dumps(item, ensure_ascii=False), flush=True)
        (P / "05-检查与验收/局部重制04-本地对白转写01.json").write_text(
            json.dumps({"records": records, "media_uploaded": False}, ensure_ascii=False, indent=2),
            "utf-8",
        )


if __name__ == "__main__":
    main()
