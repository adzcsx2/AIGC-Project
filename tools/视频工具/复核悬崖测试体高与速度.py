"""Read existing media/geometry evidence; never render or submit a new task."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("config", type=Path)
args = parser.parse_args()
cfg = json.loads(args.config.read_text(encoding="utf-8"))
work = Path(cfg["project"]).resolve(strict=True)
assert (work / "project.yaml").is_file()


def owned(relative):
    path = (work / relative).resolve()
    assert path.is_relative_to(work)
    return path


for item in cfg["pinned_inputs"]:
    assert sha(owned(item["path"])) == item["sha256"]
geometry = json.loads(owned(cfg["geometry"]).read_text(encoding="utf-8"))
samples = geometry["samples"]
fps = cfg["fps"]
heights = [s["bottom_m"] for s in samples]
velocity = [(heights[i + 1] - heights[i]) * fps for i in range(len(heights) - 1)]
acceleration = [(velocity[i + 1] - velocity[i]) * fps for i in range(len(velocity) - 1)]
keys = cfg["lift_keys"]
rise = (keys[2]["frame"] - keys[1]["frame"]) / fps
hold = (keys[3]["frame"] - keys[2]["frame"]) / fps
fall = (keys[4]["frame"] - keys[3]["frame"]) / fps
maximum = max(heights)
gravity = 9.8
ballistic_up = math.sqrt(2 * maximum / gravity)
reference_height = (
    cfg["reference_creature_height_px"] / cfg["reference_size"][1] * cfg["native_size"][1]
)
measurements = []
for item in cfg["grounded_measurements"]:
    height = item["paw_y"] - item["crest_y"]
    measurements.append(
        {
            **item,
            "height_px": height,
            "fraction_of_frame_height": height / cfg["native_size"][1],
            "relative_to_reference_percent": (height / reference_height - 1) * 100,
        }
    )
initial_height = measurements[0]["height_px"]
for item in measurements:
    item["relative_to_first_percent"] = (item["height_px"] / initial_height - 1) * 100

report = {
    "body_height": {
        "reference_native_equivalent_px": reference_height,
        "reference_original_height_px": cfg["reference_creature_height_px"],
        "grounded_measurements": measurements,
        "scope": (
            "Visible crest-to-paw projection, not exact world centimetres or 3D volume. "
            "Wing/tail excluded in grounded samples; head/neck/leg posture and "
            "+/-2px landmark uncertainty remain."
        ),
    },
    "whitebox_speed": {
        "fps": fps,
        "frames": len(samples),
        "max_lift_m": maximum,
        "rise_seconds": rise,
        "flat_peak_seconds": hold,
        "fall_seconds": fall,
        "takeoff_to_landing_seconds": rise + hold + fall,
        "average_rise_m_per_s": maximum / rise,
        "average_fall_m_per_s": maximum / fall,
        "sampled_max_upward_m_per_s": max(velocity),
        "sampled_max_downward_m_per_s": min(velocity),
        "sampled_acceleration_range_m_per_s2": [min(acceleration), max(acceleration)],
        "proxy_dimensions_first_m": samples[0]["dimensions_m"],
        "physics_reference": {
            "assumption": (
                "Rigid body's COM rises 0.05m under Earth gravity, equal launch/landing "
                "height, no powered lift, drag ignored. "
                "Not a universal foot-gap/dragon-flight constraint."
            ),
            "g_m_per_s2": gravity,
            "time_up_seconds": ballistic_up,
            "airborne_seconds": 2 * ballistic_up,
            "whitebox_duration_ratio": (rise + hold + fall) / (2 * ballistic_up),
            "source": "https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ballistic-flight-equations/",
        },
    },
    "generation": {
        "lowest_paw_gap_over_initial_height_candidate": 58 / 142,
        "target_gap_ratio": 1 / 6,
        "scope": (
            "Existing frame53 candidate, visually cross-checked in native frames; "
            "segmentation uncertain, not world cm."
        ),
    },
    "conclusion": (
        "Initial projected height close to reference; later grounded height differs with posture, "
        "strict scale constancy unproven. Proxy timing was slow with a flat apex; "
        "do not blame the model alone. No new media generation."
    ),
}
output = owned(cfg["output_json"])
output.parent.mkdir(parents=True, exist_ok=True)
with output.open("x", encoding="utf-8") as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)

font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 21)
small = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 17)
canvas = Image.new("RGB", (1920, 530), "#171b21")
draw = ImageDraw.Draw(canvas)
reference = Image.open(owned(cfg["reference"])).convert("RGB").resize(tuple(cfg["native_size"]))
panels = [
    (
        "同框参考：归一到视频画幅",
        reference,
        cfg["reference_crest_native"],
        cfg["reference_paw_native"],
        reference_height,
    )
]
for item in (measurements[0], measurements[-1]):
    source = owned(cfg["frames_dir"]) / f"{item['frame'] + 1:04d}.png"
    panels.append(
        (
            f"原生第{item['frame']}帧 · {item['frame'] / fps:.3f}秒",
            Image.open(source).convert("RGB"),
            item["crest_y"],
            item["paw_y"],
            item["height_px"],
        )
    )
for index, (label, im, top, bottom, height) in enumerate(panels):
    x = index * 640
    crop = im.crop((250, 385, 570, 580)).resize((640, 390))
    canvas.paste(crop, (x, 55))
    draw.text((x + 12, 10), label, font=font, fill="white")
    for y in (top, bottom):
        py = 55 + (y - 385) * 2
        draw.line((x + 5, py, x + 625, py), fill="#7cfc9d", width=2)
    draw.text(
        (x + 12, 451), f"落地体高投影 ≈ {height:.1f}px（翼、尾不计）", font=small, fill="white"
    )
draw.text(
    (12, 491),
    "仅比较落地体高投影；末段抬头/腿姿不同，表观差异不等于实体放大。测量点误差约±2px。",
    font=small,
    fill="#d0d6e0",
)
figure = owned(cfg["output_figure"])
assert not figure.exists()
canvas.save(figure)
print(
    json.dumps(
        {
            "reference_height_px": reference_height,
            "grounded": measurements,
            "rise_s": rise,
            "hold_s": hold,
            "fall_s": fall,
            "total_s": rise + hold + fall,
            "max_up_mps": max(velocity),
            "max_down_mps": min(velocity),
            "ballistic_air_s": 2 * ballistic_up,
        },
        ensure_ascii=False,
    )
)
