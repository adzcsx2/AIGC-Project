"""Prepare the authorized three rebuilt scenes; does not submit generation jobs."""

import hashlib
import json
import subprocess
from pathlib import Path

import yaml

if __name__ == "__main__":
    raise SystemExit("Historical preparer retired: read project.yaml and its current manifest.")

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "projects/悬崖上的小气球"
VERSION = "正式前三段重制02"
VOICE_SHA = "4e9c1c7841d4861308f991788ee03dd665f4a242c161b375304e86b215ab4007"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        f.write(text)


def dump(path, data):
    write(path, json.dumps(data, ensure_ascii=False, indent=2))


def run(args):
    subprocess.run(args, check=True, capture_output=True)


def packet_hashes(path):
    data = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_packets",
            "-show_data_hash",
            "sha256",
            "-show_entries",
            "packet=data_hash",
            "-of",
            "json",
            str(path),
        ]
    )
    return [v["data_hash"] for v in json.loads(data)["packets"]]


config_dir = P / "03-制作/生成配置" / VERSION
style = (
    "Medieval live-action fantasy throughout: real skin, wool, linen, leather; living photoreal "
    "VFX dragon, irregular pink scales, wet gray-blue eyes, thin wing membranes, shared daylight "
    "and contact shadows. No cartoon, plastic, game look, text, watermark or music. "
)
space = (
    "Preserve the guide's grass plane, limestone foreground, two timber cottages behind LEFT, "
    "curving path, huge tree RIGHT, high attached berry LEFT, "
    "distant hills and mist below the rim. "
    "Daylight stays from upper left. Follow its camera crops and visible cuts. "
)
size = (
    "ONE baby: FOUR paws, TWO wings, ONE tail. Grounded crest-to-paw 0.30 m; muzzle-to-rump "
    "0.35 m (27% of the reclining girl's 1.30 m head-to-heel); 0.55 m with tail. Constant "
    "skull, trunk and limb sizes; posture changes outlines, never body scale. "
)
mapping = (
    "Image 1: complete scene/relative scale. Image 2: SAME dragon identity. Image 3: SAME girl "
    "identity. ONE of each; boards never add actors. "
)
prompts = [
    mapping
    + "Replace ONLY the guide's short cylinder LEFT with that baby dragon; remove it completely. "
    "Keep the real girl already in the guide reclining on her LEFT elbow, "
    "never standing or sitting up. "
    + size
    + "At 0-5s they rest safely inland. The dragon rests belly-down, breathing with weight; "
    "its drowsy eyes catch the high berry and brighten with appetite. This relaxed pose may lie "
    "inside the proxy envelope. At 5-6.33s the cut shows the berry still attached to its stem, "
    "unreachable without real lift. At 6.33-9s cut closer to the dragon: eyes widen, tongue "
    "actually touches and wets its upper lip, forepaws load and flatten grass, shoulders push "
    "up to its normal low quadruped stance. Grass rebounds where its chest leaves. It fixes "
    "its gaze on the berry and shifts weight back; no charge yet. Natural body articulation, "
    "not rigid cylinder motion. The girl stays relaxed with a fond gaze. Silent; no dialogue, "
    "singing, humming or sound effects. " + space + style,
    mapping
    + "Replace ONLY the short cylinder LEFT with that dragon; leave no roller, rod or prop. "
    "The real girl remains reclining RIGHT, watching silently; "
    "never stand her up or begin her laugh. "
    + size
    + "Follow the actual grounded path at NORMAL SPEED. 0-0.95s: exactly three small backward "
    "steps, eyes fixed on the berry. 0.95-1.35s: one hindpaw scrapes a small soil furrow and "
    "loads for the rush. 1.35-1.65s: rush forward about 0.43 m with quick ineffective wingbeats. "
    "1.65-1.77s: RIGHT hindpaw slips on damp grass under load; eyes snap wide, weight pitches "
    "forward. 1.77-2.19s: one short sideways tumble through soft grass, wings fold before "
    "shoulder contact. 2.19-2.31s: muzzle/front chest contact and part the grass; a few loose "
    "soil grains shift. The body compresses and rebounds briefly AFTER contact, settling by "
    "2.6s. No aerial float, high jump, slow landing or repeated somersault. At the 3.33s cut "
    "the head stays buried in that grass, ONE tail droops and wags unhappily. Flattened grass "
    "and nose dirt persist; berry untouched, no injury or cliff fall. Natural paws, wings "
    "and soft tissue complete the proxy path. Silent, no words, laughter or music. "
    + space
    + style,
    mapping + "Replace the small LEFT cylinder with that dragon and the long low RIGHT cylinder "
    "with that girl. Remove BOTH cylinders; use their space/timing, with natural anatomy. "
    + size
    + "The girl NEVER stands or sits upright. 0-0.6s she sees the tail, her held smile breaks "
    "into laughter; eyes crease, shoulders bounce, hands hold her belly. 0.6-1.2s she makes "
    "ONE quick side-roll; shoulder and wool compress grass, braid follows with weight. "
    "By 1.95s she props on LEFT elbow, RIGHT hand on belly, and speaks with amused familiar "
    "warmth and short breaths. Match lips to the guide's Mandarin voice; no new voice, "
    "translation or added words: "
    "“噗哈哈哈哈哈！” “咕噜，你飞得真高啊，足足有一只蚂蚱那么高呢！你那是翅膀还是蒲扇呀？” "
    "At 6.5s cut to the dragon; her remaining line continues offscreen. It braces forepaws "
    "in the same flattened patch and pulls its dirty nose free in about 0.6s; grass parts "
    "and some blades stay bent. Hopeful eyes turn toward her, then hurt: gaze drops, jaw "
    "tightens, wing roots tense. Nose dirt persists. No new takeoff. Dialogue ends at its "
    "source-track time; allow the final wounded reaction, not a slow-motion recovery. "
    "No added music, song, humming, narration or sound effects. " + space + style,
]

for i, prompt in enumerate(prompts, 1):
    if len(prompt) > 2048:
        raise ValueError(f"Prompt {i} too long: {len(prompt)}")

tts = (
    P
    / "02-素材/音频/对白"
    / VERSION
    / "片段03-米娅原文对白01/4cb692c5-ce15-487b-ba5e-8272dc438ffd_01.wav"
)
track = tts.parent.parent / "片段03-米娅原速完整音轨01.m4a"
run(
    [
        "ffmpeg",
        "-v",
        "error",
        "-n",
        "-i",
        str(tts),
        "-af",
        "adelay=200:all=1,apad",
        "-t",
        "12",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(track),
    ]
)
provenance = P / "06-记录/视频生成/正式前三段重制02-配音来源01.json"
dump(
    provenance,
    {
        "tts_task_id": "4cb692c5-ce15-487b-ba5e-8272dc438ffd",
        "tts_config": str(config_dir / "片段03-米娅原文对白-IndexTTS2-01.yaml"),
        "tts_config_sha256": sha(config_dir / "片段03-米娅原文对白-IndexTTS2-01.yaml"),
        "reference_audio_sha256": VOICE_SHA,
        "tts_output_sha256": sha(tts),
        "delivery_track_sha256": sha(track),
        "processing": (
            "Original speed, 0.20s initial delay, silence padding to 12s; "
            "AAC48kHz stereo192kbps. No music or speech acceleration."
        ),
        "auditory_review": (
            "not_claimed; selected source identity retained, "
            "new TTS performance remains for audible review"
        ),
    },
)
configs = []
guide_records = []
for i, duration, version in [(1, 9, "04"), (2, 6, "04"), (3, 12, "05")]:
    cfg = json.loads(
        (P / f"03-制作/制作计划/{VERSION}/片段{i:02d}-白模参数{version}.json").read_text(
            encoding="utf-8"
        )
    )
    guide = P / cfg["guide"]
    guide.parent.mkdir(parents=True, exist_ok=True)
    frames = P / cfg["frames"]
    assert len(list(frames.glob("*.png"))) == duration * 24
    ff = ["ffmpeg", "-v", "error", "-n", "-framerate", "24", "-i", str(frames / "帧-%04d.png")]
    ff += ["-i", str(track)] if i == 3 else ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    ff += [
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-t",
        str(duration),
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy" if i == 3 else "aac",
        "-movflags",
        "+faststart",
        str(guide),
    ]
    run(ff)
    source_hashes = packet_hashes(track) if i == 3 else []
    result_hashes = packet_hashes(guide) if i == 3 else []
    if i == 3:
        assert result_hashes == source_hashes, "Source AAC packets changed during mux"
        evidence = P / f"05-检查与验收/{VERSION}/片段03-源音轨绑定01.json"
        dump(
            evidence,
            {
                "schema_version": 1,
                "kind": "embedded_source_audio",
                "character_id": "CHAR-GIRL",
                "video_sha256": sha(guide),
                "dialogue_sha256": sha(track),
                "voice_sample_sha256": VOICE_SHA,
                "audio_stream_copy_verified": True,
                "matching_aac_packets": len(result_hashes),
                "provenance": {
                    "path": provenance.relative_to(P).as_posix(),
                    "sha256": sha(provenance),
                },
            },
        )
    config = {
        "workflow_id": "minimax_h3_zm_titim",
        "materials_manifest": "../../../materials.yaml",
        "shot_id": f"CLIFF-{i:02d}-R02",
        "inputs": {
            "prompt": prompts[i - 1],
            "ref_image_0": "../../../02-素材/镜头/一致性测试/女孩躺姿-幼龙-高浆果-同框控制03.png",
            "ref_image_1": (
                "../../../02-素材/人物/粉色幼龙身份参考板/"
                "粉色幼龙身份参考板-PINK-DRAGON-BOARD-版本03.png"
            ),
            "ref_image_2": (
                "../../../02-素材/人物/中世纪小女孩灰蓝披风参考板/"
                "中世纪小女孩灰蓝披风参考板-MEDIEVAL-GIRL-BOARD-版本04.png"
            ),
            "ref_video": str(guide.resolve()),
            "video_subject_to_replace": "cylinder",
            "duration": duration,
            "resolution": "768p横",
        },
        "output_dir": str((P / f"04-输出/原始片段/{VERSION}/片段{i:02d}").resolve()),
        "timeout": 3600,
        "poll_interval": 15,
    }
    dest = config_dir / f"片段{i:02d}-titim-英文执行稿02.yaml"
    write(dest, yaml.safe_dump(config, allow_unicode=True, sort_keys=False, width=105))
    configs.append(str(dest))
    guide_records.append(
        {
            "shot_id": config["shot_id"],
            "guide": cfg["guide"],
            "guide_sha256": sha(guide),
            "config": cfg,
            "prompt_length": len(prompts[i - 1]),
        }
    )

dump(
    P / f"06-记录/视频生成/{VERSION}-准备结果01.json", {"configs": configs, "guides": guide_records}
)
write(
    P / f"01-文档/提示词/{VERSION}-英文执行稿02.md",
    "# 正式前三段重制：英文执行稿02\n\n待实际送模版原速复核与生成前总审计，尚未作为可提交版本。\n\n"
    + "\n\n".join(
        f"## CLIFF-{i:02d}-R02\n\n```text\n{prompt}\n```" for i, prompt in enumerate(prompts, 1)
    ),
)
print(
    json.dumps(
        {"configs": configs, "prompt_lengths": [len(v) for v in prompts]}, ensure_ascii=False
    )
)
