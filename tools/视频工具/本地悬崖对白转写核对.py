"""Offline ASR of already-generated dialogue; downloads a public model, uploads no media."""

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
TAG = "正式前五段u30重制03"
pack_path = P / f"03-制作/制作计划/{TAG}/制作包02-实际输入.json"
jobs_path = P / f"06-记录/视频生成/{TAG}-任务与结果01.json"
pack = json.loads(pack_path.read_text(encoding="utf-8"))
jobs = json.loads(jobs_path.read_text(encoding="utf-8"))["jobs"]
model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=4,
                     download_root=str(ROOT / ".autodl/asr-models"))
records = []
for unit in pack["units"]:
    if "dialogue" not in unit:
        continue
    job = next(value for value in jobs if value["n"] == unit["n"])
    source = Path(job["files"][0]).resolve(strict=True)
    assert source.is_relative_to(P)
    pcm = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1",
    ])
    samples = np.frombuffer(pcm, dtype="<f4").copy()
    segments, info = model.transcribe(samples, language=None, task="transcribe",
                                      beam_size=5, vad_filter=False, temperature=0,
                                      condition_on_previous_text=False)
    actual = [{"start": segment.start, "end": segment.end, "text": segment.text,
               "avg_logprob": segment.avg_logprob} for segment in segments]
    item = {"n": unit["n"], "source": str(source.relative_to(P)),
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "model": "faster-whisper1.2.1 / multilingual base / CPU int8",
            "language_forced": False, "language_detected": info.language,
            "language_probability": info.language_probability,
            "expected_english": unit["dialogue"], "segments": actual,
            "actual_text": " ".join(segment["text"].strip() for segment in actual),
            "scope": "Auxiliary ASR only; not listening, voice-timbre or lip-sync approval."}
    records.append(item)
    print(json.dumps(item, ensure_ascii=False), flush=True)
    (P / f"05-检查与验收/{TAG}-本地对白转写01.json").write_text(
        json.dumps({"records": records, "media_uploaded": False}, ensure_ascii=False, indent=2),
        encoding="utf-8")
