"""Read-only media analysis; publish new frame evidence without claiming visual approval."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from whitebox_saved import checked_destination, project_path, sha
from project_tool_safety import publish_bundle


def analyse(project, video, output, times, shots):
    project = Path(project).resolve()
    source = project_path(project, video, exists=True)
    dest = project_path(project, output)
    if dest.exists():
        raise FileExistsError(dest)
    digest = sha(source)
    meta = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format",
        "-of", "json", str(source),
    ]))
    subprocess.run([
        "ffmpeg", "-v", "error", "-nostdin", "-xerror", "-i", str(source),
        "-f", "null", "-",
    ], check=True, capture_output=True)
    cap = cv2.VideoCapture(str(source))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    pictures = []
    for time in times:
        index = round(time * fps)
        if not 0 <= index < total:
            raise ValueError(f"Frame outside video: {time}")
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = cap.read()
        if not ok:
            raise ValueError(f"Cannot read frame {index}")
        pictures.append((index, index / fps, Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))))
    tracking = []
    for start, end in shots:
        begin, stop = round(start * fps), min(round(end * fps), total)
        cap.set(cv2.CAP_PROP_POS_FRAMES, begin)
        ok, first = cap.read()
        if not ok:
            raise ValueError(f"Cannot read shot {start}")
        base = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)
        h, w = base.shape
        mask = np.zeros_like(base)
        mask[:int(h * .18), :] = 255
        mask[:, :int(w * .08)] = 255
        mask[:, int(w * .92):] = 255
        points = cv2.goodFeaturesToTrack(base, 160, .02, 8, mask=mask)
        moves = []
        if points is not None and len(points) >= 10:
            for index in range(begin + 1, stop):
                ok, frame = cap.read()
                if not ok:
                    raise ValueError(f"Cannot read frame {index}")
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                target, status, error = cv2.calcOpticalFlowPyrLK(base, gray, points, None)
                if target is None:
                    continue
                valid = (status[:, 0] == 1) & (error[:, 0] < 15)
                if valid.sum() >= 10:
                    shift = target[valid, 0] - points[valid, 0]
                    moves.append({"frame": index, "matched": int(valid.sum()),
                                  "median_dx": float(np.median(shift[:, 0])),
                                  "median_dy": float(np.median(shift[:, 1]))})
        tracking.append({"requested_range_seconds": [start, end], "source_range_frames": [begin, stop],
                         "samples": moves,
                         "max_abs_median_dx": max((abs(x["median_dx"]) for x in moves), default=None),
                         "max_abs_median_dy": max((abs(x["median_dy"]) for x in moves), default=None),
                         "limitation": "Border feature displacement is auxiliary evidence; moving subjects or cut contamination require visual review."})
    cap.release()
    columns, tile_width = 3, 480
    tile_height = round(pictures[0][2].height * tile_width / pictures[0][2].width) + 28
    sheet = Image.new("RGB", (columns * tile_width, ((len(pictures) + columns - 1) // columns) * tile_height), "#202020")
    draw = ImageDraw.Draw(sheet)
    record = {"source": str(source), "sha256": digest, "probe": meta, "decode": "passed",
              "stills": [{"index": i, "seconds": t} for i, t, _ in pictures], "camera_tracking": tracking,
              "continuous_dynamic_review": "pending", "actual_listening": "pending"}
    dest.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix=".抽查-", dir=project) as folder:
        folder = Path(folder)
        pairs = []
        for n, (index, time, pic) in enumerate(pictures):
            path = folder / f"帧{index:05d}.jpg"
            pic.save(path, quality=95)
            target = dest / path.name
            checked_destination(target, project)
            pairs.append((path, target))
            thumbnail = pic.copy()
            thumbnail.thumbnail((tile_width, tile_height - 28))
            x, y = (n % columns) * tile_width, (n // columns) * tile_height
            sheet.paste(thumbnail, (x, y + 28))
            draw.text((x + 8, y + 6), f"{time:.3f}s / frame {index}", fill="white")
        sheet_path = folder / "动作抽帧总览.jpg"
        sheet.save(sheet_path, quality=92)
        record_path = folder / "文件与背景位移.json"
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        pairs.extend([(sheet_path, dest / sheet_path.name), (record_path, dest / record_path.name)])
        if sha(source) != digest:
            raise ValueError("Source changed during inspection")
        publish_bundle(pairs, project)
    print(json.dumps({"evidence": str(dest), "probe": meta, "tracking": [
        {k: v for k, v in item.items() if k != "samples"} for item in tracking]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--times", required=True, help="Comma-separated actual seconds")
    parser.add_argument("--shots", default="", help="Comma-separated start:end seconds excluding cuts")
    args = parser.parse_args()
    analyse(args.project, args.video, args.output, [float(x) for x in args.times.split(",")],
            [tuple(map(float, x.split(":"))) for x in args.shots.split(",") if x])
