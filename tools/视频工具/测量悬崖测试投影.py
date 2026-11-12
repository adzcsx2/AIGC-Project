"""Candidate pink-creature projection measurements, requiring visual confirmation."""

import argparse
import json
from collections import deque
from pathlib import Path

from PIL import Image

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--test", choices=("titim01", "titim02", "titim04"), required=True)
test = parser.parse_args().test
work = Path(__file__).resolve().parents[2] / "projects/悬崖上的小气球"
directory = work / f"05-检查与验收/一致性测试-{test}-原生检查"
paths = sorted((directory / "完整解码帧").glob("*.png"))
assert paths
technical = json.loads((directory / "原生技术探测.json").read_text("utf-8"))
fps = technical["fps"]
output = directory / "粉色主体投影-候选测量02.json"
assert not output.exists()


def largest_component(mask, width, height):
    """Use connected components so a face or a reddish leaf cannot set the box."""
    best = None
    for seed in range(width * height):
        if mask[seed] != 1:
            continue
        queue = deque([seed])
        mask[seed] = 2
        points = []
        while queue:
            index = queue.popleft()
            points.append((index % width, index // width))
            x = index % width
            for candidate in (
                index - width if index >= width else -1,
                index + width if index < width * (height - 1) else -1,
                index - 1 if x else -1,
                index + 1 if x < width - 1 else -1,
            ):
                if candidate >= 0 and mask[candidate] == 1:
                    mask[candidate] = 2
                    queue.append(candidate)
        if best is None or len(points) > len(best):
            best = points
    return best or []


measurements = []
for frame, path in enumerate(paths):
    with Image.open(path) as source:
        assert source.size == (1344, 768), "Recalibrate the mask coordinates for other native sizes."
        im = source.convert("RGB").resize((672, 384))
    rgb = list(im.get_flattened_data())
    mask = bytearray(
        int(r > 90 and r > g + 18 and r > b + 15 and b * 20 > g * 11 and g > 45)
        for r, g, b in rgb
    )
    points = largest_component(mask, 672, 384)
    assert len(points) > 100, (frame, "pink subject not reliably detected")
    left, right = min(x for x, _ in points), max(x for x, _ in points)
    top, bottom = min(y for _, y in points), max(y for _, y in points)
    body_front = [(x, y) for x, y in points if x <= left + 0.65 * (right - left)]
    low = max(y for _, y in body_front)
    crest = min(y for _, y in body_front)
    measurements.append(
        {
            "frame": frame,
            "time": frame / fps,
            "bbox_native_pixels": [left * 2, top * 2, (right + 1) * 2, (bottom + 1) * 2],
            "center_x_fraction": (left + right) / (2 * 672),
            "front_65_percent_lowest_candidate_y": low * 2,
            "front_65_percent_top_candidate_y": crest * 2,
            "mask_pixels_half_resolution": len(points),
        }
    )
base = measurements[0]
ground = base["front_65_percent_lowest_candidate_y"]
height = ground - base["front_65_percent_top_candidate_y"]
for m in measurements:
    m["clearance_over_initial_height_candidate"] = (
        ground - m["front_65_percent_lowest_candidate_y"]
    ) / height
peak = max(measurements, key=lambda v: v["clearance_over_initial_height_candidate"])
report = {
    "test": test,
    "initial_center_x_fraction": base["center_x_fraction"],
    "initial_ground_candidate_y": ground,
    "initial_creature_height_candidate_pixels": height,
    "peak_candidate": peak,
    "scope": "2D segmentation candidates, NOT calibrated world cm or body volume. Wings/tail/skin gaps may bias extrema; visually confirm initial and peak native frames before use. No automatic pass verdict.",
    "samples": measurements,
}
with output.open("x", encoding="utf-8") as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
print(json.dumps({k: v for k, v in report.items() if k != "samples"}, ensure_ascii=True))
