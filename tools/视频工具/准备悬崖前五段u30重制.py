"""Prepare authorized five-unit u30 remake text, asset plan and audit inputs."""
# ruff: noqa: E501 -- Media instructions and Chinese production paths remain readable literals.

import hashlib
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "projects/悬崖上的小气球"
TAG = "正式前五段u30重制03"
BASE = "02-素材/镜头/u30六图同框测试07/女孩左肘躺姿-小龙伏卧-完整同框02.png"
GIRL = "02-素材/人物/中世纪小女孩灰蓝披风参考板/中世纪小女孩灰蓝披风参考板-MEDIEVAL-GIRL-BOARD-版本05.png"
DRAGON = "02-素材/人物/粉色幼龙身份参考板/粉色幼龙身份参考板-PINK-DRAGON-BOARD-版本04.png"
CHART = "02-素材/尺寸参考/米娅130厘米-咕噜40厘米-身高对照01.png"
PAIR = "02-素材/尺寸参考/u30六图同框测试07/米娅左-咕噜右-纯站立比例-定稿03.png"
ENV = "02-素材/镜头/正式前三段重制02/同框03派生-无人无龙环境底板01.png"

STYLE = (
    "Maintain the approved medieval LIVE-ACTION fantasy photography in EVERY view. "
    "MIA has real skin texture, fine brown hair/braid, the same gray-blue woven wool cloak, "
    "cream linen, brown bodice, dark trousers, worn leather boots and satchel. GULU is the SAME "
    "living photoreal cinematic VFX PINK juvenile, with fine irregular scales, flexible soft tissue, "
    "wet gray-blue eyes, cream underside, two curved crown horns, FOUR separate paws, TWO dorsal "
    "wings and ONE continuous tail. Shared natural daylight, exposure, reflected grass light and "
    "contact shadows. No cartoon, plastic toy, game-model finish, adult transformation, red recoloring "
    "or golden eyes. Preserve identity and juvenile anatomy through movement and close-ups."
)
ENVIRONMENT = (
    "Keep the same connected grassy cliff plateau, ONE huge rough-barked tree RIGHT, TWO adjoining "
    "timber-and-plaster cottages on stone bases LEFT BACK, the curved dirt path behind the actors, "
    "ONE slender berry sapling LEFT, small-scale short grass, gray limestone rim in the foreground, "
    "distant wooded hills and pale-blue lightly clouded sky. Upper-left filtered daylight and a mild "
    "consistent breeze. The designated ripe red berry stays attached to the same outward twig about90cm "
    "above its soil, well above GULU's40cm standing horn height. It is never eaten or detached. Action "
    "stays safely inland; no extra house, railing, person or creature and no approach to the rim."
)
SCALE = (
    "MIA's STANDING crown-to-sole height is130cm. GULU's natural FOUR-PAW STANDING height, ground to "
    "highest horn tip INCLUDING head and horns, is40cm:40:130. Physical height and relative body scale "
    "MUST follow HEIGHT REFERENCE Image3 and the standing scale comparison Image4. Their standing "
    "poses are SIZE ONLY, never instructions to stand MIA up. Image6 supplies this unit's actual pose, "
    "positions, camera and relative size. Keep skull/horns, torso girth/length and limb lengths fixed. "
    "Body posture, paw clearance and camera projection are different from physical size. At the wide "
    "initial framing use MIA's approximately39% frame-width reclining span and GULU's approximately20% "
    "frame-height neutral standing horn span; a lower resting silhouette is not a smaller creature. "
    "Keep comparable actor depth, not a foreground giant. No creature growth or body inflation."
)
ROLES = (
    "Image1 is MIA's approved identity board, Image2 is GULU's approved identity board; each contains "
    "several views of ONE character, with a deliberately headless body panel only as a layout convention. "
    "Image3 is the labeled height chart, Image4 the clean two-character standing scale image, Image5 "
    "the empty environment, and Image6 the MAIN complete shot/pose reference. Use the main image's "
    "character placement, scale and support. Show exactly ONE MIA LEFT and ONE GULU RIGHT in the "
    "relationship wide view; cut-in singles never create copies. Do not render boards, grid lines, "
    "rulers, names, numbers or A4 paper. One16:9 full frame, no subtitles, watermark, border or collage."
)

DIALOGUE3 = (
    "Gulu, you flew so high! A whole grasshopper high! Are those wings or little fans?"
)
DIALOGUE5 = (
    "Oh, my tummy... All right, little chubby dragon, admit it. You're really a fat lizard "
    "pretending to be a dragon, aren't you?"
)
UNITS = [
    {
        "n": 1, "name": "晒太阳与发现浆果", "seconds": 10, "scene": BASE,
        "chinese": "两人草地晒太阳；咕噜发现高处浆果、舔嘴，四足起身准备尝试。米娅始终侧躺，注视、眨眼并微笑回应。",
        "action": (
            "0.0-4.5s: reproduce Image6's resting relationship wide view. MIA remains on her LEFT elbow, "
            "left hand supporting her head, hip and extended legs on grass; her right hand rests in front. "
            "Visible breathing, a blink and an affectionate glance toward GULU, not a frozen photo. GULU "
            "rests with folded legs, belly compressing grass, two wings folded. At3.0s its eyes find the "
            "berry LEFT and its head turns toward the attached fruit, curiosity becoming appetite. "
            "Keep the camera wide and steady, no automatic push-in.\n"
            "4.5-6.0s: an explicit eyeline CUT to the same attached red berry; leaves/twig bend gently "
            "in the breeze with the stem visibly connected. No character rescaling.\n"
            "6.0-10.0s: CUT back to the original wide composition. GULU licks its lips once, tongue "
            "touching the lip and leaving a tiny wet trace. From7.2-7.8s it presses its four paws down "
            "and promptly extends its bent legs into a40cm neutral four-paw stand; grass springs back "
            "where its chest leaves. It keeps staring at the berry, then shifts weight backward to "
            "prepare. MIA follows with eyes/head and a warmer amused smile while retaining her low "
            "elbow support: no chest push-up, sitting or standing. The next unit makes a visible cut "
            "to a lower full-body action view, not a false continuous zoom. No fall or flight yet."
        ),
    },
    {
        "n": 2, "name": "冲刺小跳滑倒滚草", "seconds": 8,
        "chinese": "咕噜三小步后退刨土，短促冲刺后确实向上小跳；离地约8厘米仍够不到90厘米浆果，落脚打滑、侧滚一次，脸扎进草丛、尾巴委屈晃动。女孩在原位有惊讶和忍笑反应。",
        "image_action": (
            "GULU stands naturally on FOUR paws to MIA's RIGHT, angled toward the berry sapling LEFT. "
            "All paws are grounded; the body is40cm to the highest horn, wings folded, alert determined "
            "eyes. Leave a clear short grassy action strip in front of and to the right of MIA's head. "
            "Its later tiny backward steps and short attempted charge/sideways tumble stay on this "
            "strip, never crossing MIA's body. The girl remains low on her LEFT elbow, left hand at "
            "her head, right arm resting; she watches with interested eyes. Keep both full bodies, "
            "feet and the complete tail visible. No mud on either body yet. A small soft grass clump "
            "is on the action strip to GULU's left, still RIGHT of MIA's head. Low35mm relationship "
            "wide view, camera near grass height, no enlarged foreground dragon."
        ),
        "action": (
            "0.0-2.0s: low fixed full-body view based on Image6, with the berry LEFT and MIA resting "
            "LEFT BACK. GULU takes three tiny backward steps, no more than about24cm total, keeping "
            "its gaze on the berry. One hind paw scrapes soft earth, dragging a small amount backward "
            "and leaving a shallow groove; its shoulders load and eyes narrow with determination.\n"
            "2.0-3.1s: one short charge LEFT, less than one body length, wings fluttering rapidly. "
            "The hind legs visibly extend against the soil to create an UPWARD hop: all FOUR paws "
            "briefly leave the ground together, the lowest paw reaches about8cm clearance, about "
            "0.25seconds airborne. This is a small visible jump, not a flat forward belly-pounce. "
            "Its horn remains far below the90cm berry, so no mouth-fruit contact. The landing right "
            "hind paw skids on damp grass; grass bends under that sliding loaded paw.\n"
            "3.1-4.2s: weight tips forward, wings fold clear of the ground and the soft body makes "
            "ONE short sideways tumble, ending muzzle/chest first in the grass clump RIGHT of MIA, "
            "still far inland. Show the actual shoulder/grass and muzzle/grass contacts without a "
            "cut: blades part/flatten, a little soil shifts, grass pieces stick to the nose, belly "
            "rebounds once and settles. Never loop somersaults or make it fly. MIA's eyes widen, "
            "then her lips tighten into a suppressed smile; she stays reclining, head following.\n"
            "4.2-8.0s: keep the same full-body view; its face stays buried, one tail droops then "
            "wags unhappily while its chest breathes. Keep the compressed grass and nose dirt. "
            "The next unit CUTS to the girl's laugh, with this same failed landing still present. "
            "All motion at natural real-time speed, no slow flight, apex hold or slowed roll."
        ),
    },
    {
        "n": 3, "name": "第一次笑与调侃", "seconds": 15, "dialogue": DIALOGUE3,
        "chinese": "米娅看到尾巴忍不住开怀笑，捧腹侧滚一次后回到左肘躺撑，说出第一次调侃。龙从同一草丛拔出带草屑的脸，期待变成受伤，保持幼体尺寸。",
        "image_action": (
            "MIA reclines on her LEFT elbow on the LEFT, left hand beside her head and right hand "
            "moving toward her abdomen; she sees the failed landing and is just beginning an amused "
            "open smile. GULU remains on the RIGHT in the same grass strip, its muzzle and front "
            "chest buried in a small soft grass clump, wings safely folded, one short tail tilted "
            "up with a discouraged droop. Its body remains the SAME small40cm neutral-standing "
            "creature, now lower because of the folded posture. Blades are pressed under muzzle "
            "and chest; a few grass pieces and soil flecks adhere to the nose, not a mud bath. "
            "Both bodies have grounded contact shadows. Medium-wide relationship composition "
            "with room for one grounded side-roll; same scene, daylight and LEFT girl/RIGHT dragon."
        ),
        "action": (
            "0.0-2.0s: CUT from the preceding buried-face/tail action to a50mm low medium shot of "
            "MIA with room for her grounded side-roll. Her suppressed smile breaks into real open "
            "laughter, eyes crease, shoulders bounce and hands clutch her abdomen. She rolls ONCE "
            "onto her side in about0.6seconds, shoulder and heavy wool compressing grass, then "
            "returns to her LEFT elbow support by2.0s. Hips/legs stay on the ground; no sitting "
            "or standing. Braid and cloak follow with weight.\n"
            "2.0-11.5s: she says the exact English line ONCE with playful familiar warmth and short "
            "laugh breaths, right hand over her belly. Natural expressive eyebrows and mouth, "
            "matching visible lips while in view. At8.0s make an explicit eyeline CUT to a70mm "
            "low GULU reaction view; MIA's same line continues OFFSCREEN to its end, without repeats. "
            "GULU braces its forepaws and pulls its dirty face out of the SAME clump in about0.6s. "
            "Grass parts at the cheeks; some blades recover, others remain bent, nose dirt persists.\n"
            "11.5-15.0s: its hopeful look toward MIA becomes hurt as it understands the joke: gaze "
            "drops, jaw tightens, nostrils tense, wing roots draw in. Keep gray-blue eyes and "
            "the small juvenile anatomy. No new takeoff, fire jet or added speech. End on the hurt "
            "reaction; next unit visibly CUTS to a low full-body view for the5cm flight attempt."
        ),
    },
    {
        "n": 4, "name": "五厘米试飞与跌泥", "seconds": 8,
        "chinese": "咕噜受挫喷出两缕灰气和暗火星，吸气蓄力、迅速拍翼，最低爪短暂离地5厘米；得意一瞬后泄气失衡，一屁股落入邻近软泥，泥面凹陷、泥点留身，转为窘迫。女孩仍躺卧有期待再惊讶的反应。",
        "image_action": (
            "GULU is on the RIGHT in its natural FOUR-PAW40cm standing stance, just recovered "
            "from the grass clump. Fine grass pieces/soil still cling to its nose. It looks toward "
            "the reclining MIA LEFT with wounded determination, jaw set and shoulders loaded. "
            "Wings remain the same small folded pair, not newly grown. A shallow damp bare-soil "
            "patch lies immediately behind its rump, beside the flattened grass, still safely "
            "inland. No mud on its rump yet and no crater. MIA stays on her LEFT elbow, right "
            "hand near her abdomen, amused expression beginning to soften. Low fixed35mm full-body "
            "shot showing ALL four feet, clear surrounding ground and room above. Same scale, "
            "girl LEFT and small dragon RIGHT at comparable depth; no foreshortened giant."
        ),
        "action": (
            "0.0-1.2s: CUT to Image6's low fixed full-body view, all paws and the nearby ground "
            "visible. GULU exhales two thin gray wisps with a few dim ember specks, not a flame "
            "jet. It inhales with only modest breathing expansion, no balloon transformation. "
            "Forepaws widen, claws press soil/grass, shoulders and wing roots tense.\n"
            "1.2-2.4s: rapid purposeful wingbeats and leg unloading create a short powered lift. "
            "Do not slow the flaps or smoothly levitate for several seconds. At about2.4-2.6s "
            "the lowest paw is only5cm above the SAME grass plane, clearly visible in the low "
            "fixed view; the40cm neutral-standing body size is unchanged. Air from the small "
            "wingbeats bends nearby grass locally. One brief proud look, no prolonged apex hold.\n"
            "2.6-3.1s: the breath escapes, coordination falters, wings fold safely and it drops "
            "the tiny gap in about0.1-0.2s, landing on its RUMP in the adjacent soft mud. Show "
            "the rump touching mud BEFORE a shallow depression and small outward smear appear. "
            "A short soft-tissue rebound settles under weight; feet brace, no crater, giant "
            "splash or weightless bounce. Mud remains on rump/lower belly and in the depression.\n"
            "3.1-5.5s: it exhales, shoulders sink and proud eyes become embarrassed. MIA's head "
            "and eyebrows follow lift then fall with a surprised blink; she remains on her LEFT "
            "elbow with hips/legs grounded. Keep nose grass/dirt from the first fall.\n"
            "5.5-8.0s: explicit CUT to a70mm dragon face/chest reaction; it cautiously looks toward "
            "MIA for approval. No second dialogue yet. The next unit cuts to MIA laughing again. "
            "All action at normal real-time speed; no slow-motion jump or stretched landing."
        ),
    },
    {
        "n": 5, "name": "第二次调侃与恼怒", "seconds": 15, "dialogue": DIALOGUE5,
        "chinese": "米娅再次捧腹笑出泪，左肘保持躺撑，调侃咕噜是伪装成龙的胖蜥蜴。龙先期待、再受伤愤怒，完整话音结束后奶凶地吼一声，转身离开，尚不奔崖或跃崖。",
        "image_action": (
            "MIA remains reclining on her LEFT elbow on the LEFT, RIGHT hand over her abdomen, "
            "face just beginning a second amused laugh. GULU sits low on its rump in the shallow "
            "mud patch on the RIGHT, its forepaws bracing the ground, head looking toward MIA "
            "with embarrassed hope. Preserve the same juvenile40cm neutral FOUR-PAW standing "
            "height; its sitting outline is lower without shrinking head or body. A little "
            "damp mud clings to rump/lower belly, with the shallow seated imprint in the mud, "
            "and the earlier grass flecks/soil on its nose. Keep four limbs, two folded wings "
            "and one tail. Same cottages, tree, sapling, grass/rim and daylight. Medium-wide "
            "relationship frame with both actors and contact points visible, girl LEFT/dragon RIGHT."
        ),
        "action": (
            "0.0-1.5s: visible CUT from the embarrassed dragon reaction to a50mm low MIA medium "
            "shot. She bursts into a second open laugh, eyes creasing with small laugh tears, "
            "RIGHT hand clutching her belly. Her LEFT elbow remains loaded on compressed grass, "
            "hips/legs grounded; laughing shoulders move without pushing her chest up or sitting.\n"
            "1.5-12.5s: say the exact English line ONCE, naturally, clear consonants and breath "
            "pauses, no speed-up or repeated words. Her right index finger briefly points toward "
            "GULU then returns to her belly; she believes she is sharing a familiar joke. At8.5s "
            "CUT to a70mm low dragon reaction; her same sentence continues OFFSCREEN to the end. "
            "GULU first looks hopeful, then the phrase 'fat lizard' triggers a hurt fixed stare, "
            "tight jaw/nostrils and widened GRAY-BLUE eyes. Never recolor the eyes gold.\n"
            "12.5-15.0s: ONLY after the complete question, give ONE short nonverbal baby-dragon "
            "angry growl, not words. It plants all paws, lifts its muddy rump out of the existing "
            "depression and pivots away from MIA with angry short-legged determination. Grass "
            "bends under the loaded paws; its one tail follows with weight. Preserve wet mud and "
            "nose grass/dirt. Show hurt beneath anger, no adult growth. End at the first departure "
            "step. Do NOT run to the cliff, jump off or reveal flight; those belong to later story."
        ),
    },
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(value)


def main():
    style_path = P / "01-文档/视觉设定/视觉设定-版本03-场景候选登记.md"
    assert "中世纪外景实拍奇幻" in style_path.read_text(encoding="utf-8")
    manifest = yaml.safe_load((P / "素材清单-三视图更新01-资产归位01.yaml").read_text(encoding="utf-8"))
    voice = manifest["assets"]["VOICE-GIRL"]
    package = {
        "tag": TAG, "workflow": "minimax_h3_zm_u30", "whitebox": False,
        "style": {"path": str(style_path.relative_to(P)), "sha256": sha(style_path)},
        "identity_and_scale": [GIRL, DRAGON, CHART, PAIR, ENV],
        "voice_asset": "VOICE-GIRL", "voice_path": voice["path"], "units": [],
    }
    video_md = ["# 正式前五段u30重制03：分段与英文执行稿\n",
                "2026-11-12。用户已认可测试07效果并授权按原剧情重做前5段，每段一次，不中途重复确认。新视频仅u30，无白模。按人物language=en翻译原对白；声样沿用用户认可慢速02。\n",
                "共10/8/15/8/15秒，56秒。4处段界预设可见切镜：莓果准备→低位全身；尾部受挫→女孩笑；受伤脸→低位全身试飞；窘迫脸→女孩再笑。主动作短促，余时用于铺垫与反应，不延长腾空/落地。\n"]
    image_md = ["# 正式前五段u30重制03：素材方案与图片英文稿\n",
                "先review此方案与全部英文正文，再生成4张新完整镜头图。01复用已接受测试07同框图，公共身份板/刻度图/纯角色比例图/空环境全部复用；不重新设计身份，不生成白模。\n"]
    image_common = (
        "Make ONE complete16:9 film frame, using the supplied accepted two-character scene as the "
        "composition/environment base. The other references supply the SAME girl's and SAME dragon's "
        "identities, the130cm/40cm height chart and clean standing comparison. ONE MIA LEFT and ONE "
        "GULU RIGHT. MIA standing crown-to-sole is130cm; GULU neutral FOUR-PAW ground-to-highest-horn "
        "height including head/horns is40cm, ratio40:130. Their physical size MUST follow the supplied "
        "height-reference images. Those standing poses are scale ONLY; MIA must recline as described. "
        "Keep the accepted scene's small actor occupancy (reclining girl's heel-to-crown horizontal "
        "span about39% frame width; a neutral standing dragon about20% frame height), with head/foot/"
        "wing/tail room and comparable depth, never a foreground giant. Do not render the boards, "
        "rulers, A4, text, collage, watermark or extra people/creatures. "
    )
    for unit in UNITS:
        n = unit["n"]
        scene = unit.get("scene", f"02-素材/镜头/{TAG}/片段{n:02d}-{unit['name']}-完整镜头图01.png")
        audio = (
            "AUDIO: ref_audio_0 is ONLY MIA's approved sweet youthful English voice timbre; do not "
            "repeat the sample's words. MIA's actual language is ENGLISH, not Mandarin. She laughs "
            f"briefly as scripted and speaks this exact line ONCE: \"{unit['dialogue']}\". "
            "Only MIA speaks; GULU has no human words."
            if "dialogue" in unit else
            "AUDIO: no spoken dialogue, narration or human words."
        )
        # Retain only the previously authorized story sounds and no generation music.
        sounds = {
            1: "Soft natural wind/leaves only, no extra vocalization.",
            2: "Restrained paw/grass contact, wing flutters and soft grass landing with soft wind only.",
            3: "MIA's scripted laughter, breaths and exact English dialogue, soft wind only.",
            4: "Wing flutters, one frustrated exhale and a soft mud contact with soft wind only.",
            5: "MIA's scripted laughter/breaths/dialogue, ONE nonverbal GULU growl and soft wind only.",
        }[n]
        prompt = "\n\n".join([
            f"DURATION {unit['seconds']} seconds. {ROLES}", SCALE, STYLE, ENVIRONMENT,
            "STORY AND NATURAL REAL-TIME ACTION\n" + unit["action"], audio + " " + sounds +
            " NO background music, score, songs, humming, musical stings or added narration. "
            "No freeze frame, end card or fade to black. Preserve all stated contact consequences.",
        ])
        entry = {**unit, "scene": scene, "video_prompt": prompt,
                 "dialogue_words": len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", unit.get("dialogue", "")))}
        if n != 1:
            entry["image_prompt"] = "\n\n".join([
                image_common, unit["image_action"], ENVIRONMENT, STYLE,
                "Visible elbows/hip/paws compress grass with stable grounded contact shadows; "
                "wool folds settle on grass. Render this one readable story instant, not an action montage.",
            ])
            image_md += [f"\n## 片段{n:02d}：{unit['name']}\n\n目标：{scene}\n\n",
                         "```text\n" + entry["image_prompt"] + "\n```\n"]
        video_md += [f"\n## 片段{n:02d}：{unit['name']}（{unit['seconds']}秒）\n\n",
                     unit["chinese"] + "\n\n", "```text\n" + prompt + "\n```\n"]
        package["units"].append(entry)
    video_md += ["\n## 审计范围\n\n本稿先经review文字/素材方案审计；图片返回后按实际图修订绑定，再做电影级总审计。新图未返回前不标输入就绪；不把软参考当硬身高/首帧控制。\n"]
    write_new(P / f"01-文档/提示词/{TAG}-英文执行稿01.md", "".join(video_md))
    write_new(P / f"01-文档/提示词/{TAG}-图片方案英文稿01.md", "".join(image_md))
    write_new(P / f"03-制作/制作计划/{TAG}/制作包01.json",
              json.dumps(package, ensure_ascii=False, indent=2))
    print(json.dumps({"units": [{"n": u["n"], "seconds": u["seconds"],
                     "prompt_chars": len(u["video_prompt"]), "dialogue_words": u["dialogue_words"]}
                    for u in package["units"]], "total_seconds": 56}, ensure_ascii=False))


if __name__ == "__main__":
    main()
