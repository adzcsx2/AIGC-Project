"""Prepare the accepted R05 spatial continuity plan; no network or paid submission."""

# ruff: noqa: E501 -- Exact audited model instructions and Chinese artifact names.
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "projects/悬崖上的小气球"
TAG = "空间重制05"

STYLE = "Medieval LIVE-ACTION fantasy photography: real skin and fine hair, woven gray-blue wool, cream linen and worn leather; GULU is the same living photoreal cinematic VFX PINK juvenile with irregular fine scales, flexible soft tissue, wet GRAY-BLUE eyes, cream underside, FOUR paws, TWO wings and ONE tail. Coherent upper-left daylight and shared contact shadows. No cartoon, toy, plastic/game-model finish, adult growth, red recoloring, new gold eyes, text, labels or collage."
WORLD = "Preserve ONE massive rough-barked tree RIGHT, TWO timber/plaster cottages on stone bases LEFT BACK, the curved dirt path behind the actors, the ONE berry sapling LEFT with its single target red berry attached to the outward twig, short natural grass, the gray limestone rim and distant wooded hills/blue sky. Do not move the tree, cottages, girl or sapling to fake a clear route. Keep all action inland."
SCALE = "MIA's standing crown-to-sole height is 130 cm. GULU's neutral FOUR-PAW ground-to-highest-horn height is 40 cm INCLUDING head and horns, ratio 40:130, as defined by the height chart and standing pair. Preserve skull/horns, torso girth/length and limb lengths; no enlargement to reach the berry. Scale charts control SIZE ONLY, never actor positions or the girl's reclining pose."
L1 = "Gulu, you flew so high! A whole grasshopper high! Are those wings or little fans?"
L2 = "Oh, my tummy... All right, little chubby dragon, admit it. You're really a fat lizard pretending to be a dragon, aren't you?"


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")


def main() -> None:
    old = json.loads((P / "03-制作/制作计划/局部重制04/制作包02-实际输入.json").read_text("utf-8"))
    manifest = yaml.safe_load((P / "素材清单-三视图更新01-资产归位01.yaml").read_text("utf-8"))
    common = [
        "CHAR-GIRL-THREEVIEW",
        "CHAR-DRAGON-THREEVIEW",
        "HEIGHT-CHART-R04",
        "U30-R07-STANDING-PAIR",
        "HEIGHT-EMPTY-SCENE-R04",
    ]
    paths = {k: str((P / manifest["assets"][k]["path"]).resolve()) for k in common}
    paths["old_start"] = str(P / "02-素材/镜头/局部重制04/片段02-侧向起点-完整镜头图01.png")
    paths["old_anger"] = str(P / "02-素材/表情参考/局部重制04/片段05-咕噜恼怒表情01.png")
    images = [
        {
            "id": "R05-02-START",
            "name": "片段02-净空跑道与果下起跳点-起点01.png",
            "deps": ["old_start", *common[:4]],
            "prompt": "Reference1 supplies the established world and reclining girl. References2/3 identify MIA/GULU; References4/5 supply size only. Derive ONE complete 16:9 STARTING frame for a continuous right-to-left run. Use a slightly raised wide lateral 28–35mm camera, pulled back and framed farther LEFT so the berry is around the left third, with extra clear grass LEFT of its projection for the later tumble. GULU starts on FOUR paws in the right quarter, side-profile facing LEFT toward the berry. MIA remains reclining in the middle distance BEHIND the running lane, left forearm supported, hip and legs grounded, initially watching GULU on her right. The clear grass lane passes in front of her body without touching it; the entire route from GULU to the ground directly UNDER the hanging berry must be visible and unobstructed. Leave a clear landing clump just beyond that under-berry point in the LEFT foreground, separated from the sapling trunk and limestone rim. Preserve comparable actor sizes and a stable depth along the running lane. Show the actual fixed berry and its stem, not another fruit near the dragon. No dragon copy at the target, no drawn route/letters/arrows. "
            + SCALE
            + " "
            + WORLD
            + " "
            + STYLE,
        },
        {
            "id": "R05-02-MISS",
            "name": "片段02-已跑到果下-张嘴咬空01.png",
            "deps": ["R05-02-START", "CHAR-DRAGON-THREEVIEW"],
            "prompt": "Reference1 is the new action world/camera; Reference2 is GULU's identity. Preserve the exact framing, scenery, MIA's world position and the single attached target berry. Move the ONE same small GULU from its right-side start to the ground DIRECTLY UNDER that berry on the LEFT, after traversing the clear lane. Show ONE short jump at that destination: four paws just clear of grass, torso nearly horizontal with a modest neck reach, open jaws aimed UP at the actual berry; a readable gap remains between mouth and fruit. No touch, bite mark, fruit movement/detachment, enlarged body, elongated neck or standing upright at the old right-side start. The berry remains about 90 cm above its own ground; the dragon is still 40 cm neutral four-paw height. MIA's eyes/head have followed toward the LEFT target, still grounded and reclining, with supported forearm and a slightly twisted shoulder rather than a sit-up. Keep the whole dragon, berry, its stem and nearby clear landing grass in frame. The jump pose is a single brief instant, not flight or a hover. No old-position copy of GULU. "
            + WORLD
            + " "
            + STYLE,
        },
        {
            "id": "R05-02-LANDING",
            "name": "片段02至03-果树旁同一草丛C-扎草01.png",
            "deps": ["R05-02-START", "CHAR-DRAGON-THREEVIEW"],
            "prompt": "Reference1 fixes the new action camera, girl's position, sapling, under-berry takeoff point and clear grass lane. Reference2 identifies GULU. Derive ONE complete 16:9 AFTER-FALL frame. The same ONE GULU is now face-down in the LEFT foreground clump just beyond the ground projection of the berry, following the short run-left/jump/failed landing/tumble. It is NOT in its old right-hand starting patch. Keep the clump clear of the trunk, girl's body and limestone rim. Its muzzle and BOTH eyes disappear into compressed grass; forepaws brace, chest/belly weighted against blades, wings folded, one tail lifted then drooping. Keep physical size fixed; do not enlarge the fallen body. MIA remains in her original reclining position to the RIGHT of this landing clump, supported on her forearm with grounded hip/legs. Her head and eyes are now turned LEFT toward GULU, lips pressing in a held laugh. Use a natural head/shoulder turn, not a contorted neck or a palm push-up. The attached red berry and stem remain intact above the nearby takeoff patch. Keep flattened blades/soil feedback visible, a little grass/dirt at the hidden nose. No second dragon, right-side dragon or new grass patch. "
            + SCALE
            + " "
            + WORLD
            + " "
            + STYLE,
        },
        {
            "id": "R05-03-GIRL",
            "name": "片段03-女孩看向果树草丛-笑的中景01.png",
            "deps": ["R05-02-LANDING", "CHAR-GIRL-THREEVIEW"],
            "prompt": "Reference1 supplies MIA's current world position, reclining support and the fallen GULU at the LEFT berry-side clump C. Reference2 is her identity. Make a complete 16:9 low medium reaction view of MIA's face/torso/abdomen and loaded supporting forearm. She looks OFFSCREEN-LEFT toward C, with a held smile breaking into open laughter, creased eyes, right hand near her belly. Her grounded hip and reclining forearm support remain readable; keep headroom and the full support elbow in frame. Choose a natural front three-quarter reaction angle showing her face as she turns toward C, without mirroring the whole scene or making her sit. GULU stays offscreen at C; no new dragon beside her head. Preserve the world's actual tree/cottage relationships from that angle rather than repainting a reversed duplicate scene. No old rightward eyeline. "
            + STYLE,
        },
        {
            "id": "R05-04-READY",
            "name": "片段04-果树旁C起身-五厘米试飞起点01.png",
            "deps": ["R05-02-LANDING", "CHAR-DRAGON-THREEVIEW"],
            "prompt": "Reference1 is the exact LEFT berry-side clump C after the fall; Reference2 is GULU's identity. Make a complete 16:9 ground-referenced full-body view at C. GULU has just pulled its dirty nose out of the grass and remains in a LOW CROUCHED four-paw rest, limbs bent and forepaws braced, ready to extend into the next stand. The fully extended natural four-paw height is 40cm to the horn tip; its lower crouched silhouette is posture, not smaller anatomy. Keep grass/soil on the nose and flattened blades. It faces toward MIA to screen-RIGHT, hurt tightening into stubborn determination, closed jaw, shoulders loaded, small wings beginning to prepare. Its belly has only normal breathing, no inflated giant torso. The old right-side starting patch must remain empty. MIA is still reclining farther RIGHT at her original world position, watching LEFT toward C. Preserve clear paws/ground, horns, tail and wings with enough headroom for a very small five-centimetre hop, not a high flight. The clump has a small exposed damp-soil patch beside its pressed blades for the later rump landing, not a new mud pond. Keep the sapling and attached berry in their established positions. "
            + SCALE
            + " "
            + WORLD
            + " "
            + STYLE,
        },
        {
            "id": "R05-05-GIRL",
            "name": "片段05-女孩看向C第二次笑-中景01.png",
            "deps": ["R05-02-LANDING", "CHAR-GIRL-THREEVIEW"],
            "prompt": "Reference1 supplies the girl's current place and the dragon's distant berry-side patch C; Reference2 identifies the same MIA. Create a complete 16:9 MEDIUM shot from a low front three-quarter angle. MIA is still reclining with a clearly loaded forearm/elbow and grounded hip, looking OFFSCREEN-LEFT toward C. She begins another wholehearted laugh, creased wet eyes and right hand holding the belly; preserve a little laughter tear rather than an angry expression. Frame face, torso, belly-hand and full supporting elbow, with clear headroom; boots and lower legs can be outside the frame. GULU remains OFFSCREEN at C, not beside her face or in a convenient two-shot. Preserve the real gray-blue wool, linen, leather, skin, braid and correct environment direction from this angle; no mirrored costume/scene, sitting pose or rightward eyeline. "
            + STYLE,
        },
        {
            "id": "R05-05-ANGER",
            "name": "片段05-草丛C怒视女孩方向-咕噜怒脸01.png",
            "deps": ["old_anger", "R05-04-READY", "CHAR-DRAGON-THREEVIEW"],
            "prompt": "Reference1 supplies the effective angry facial configuration, not its old LEFT eyeline. Reference2 supplies the current berry-side location C and the direction toward MIA to the RIGHT. Reference3 identifies the same GULU. Create ONE living photoreal close-up at C, viewed from a front three-quarter angle. The same gray-blue eyes glare decisively OFFSCREEN-RIGHT toward MIA, head slightly lowered and thrust forward. Inner soft brow ridges press DOWN/IN, upper lids tense and lower, lower lids braced, nostrils tense, jaw CLAMPED CLOSED, mouth line flat with corners level to DOWN. Preserve skull/horns/eye size; no human eyebrows, enlarged eyes, new fangs or grin. Nose retains grass/dirt; rump/lower belly have a few matching damp-soil smears from the previous seated landing. Wings drawn in, front paws load the grass, single tail stiff rather than wagging. Keep clump C's pressed blades and background from the new world, not the old starting position. This is hurt becoming defiant anger, not friendly curiosity or delight. Only one expression instant. "
            + STYLE,
        },
    ]
    for item in images:
        folder = "表情参考" if "ANGER" in item["id"] else "镜头"
        item["path"] = f"02-素材/{folder}/{TAG}/{item['name']}"
    header = (
        "Image 1 identifies MIA and Image 2 identifies GULU, each board shows multiple views of ONE character. Images 3/4 are the labeled HEIGHT REFERENCE and standing size pair; their panel positions are SIZE ONLY, not story placement. Image 5 supplies the environment. Do not render boards, labels, rulers or duplicates. "
        + SCALE
    )
    scene = (
        WORLD
        + " "
        + STYLE
        + " Preserve all established contact consequences and body size through each cut."
    )
    p2 = (
        "Eight-second 16:9 shot. "
        + header
        + " Image 6 is the INITIAL full action composition with a clear running lane; Image 7 shows the later mouth-miss BELOW THE BERRY, Image 8 the final berry-side clump C. These are soft stage references, not guaranteed first/last-frame controls.\n\nShow a continuous wide lateral action view including GULU's start A on the RIGHT, the entire unobstructed grass lane in front of the reclining girl, takeoff B directly under the LEFT attached berry, and nearby landing clump C. Keep the fixed world anchors in view so forward travel is visible; no zoom, camera tracking toward the animal, foreground enlargement or cut hides the run, bite attempt or ground contacts. The camera is stable at this wide composition during the action.\n0.0–0.6 s: three small backward preparatory steps and one soil scrape at A, gaze on the actual berry.\n0.6–2.6 s: accelerate and RUN on four paws from A all the way across the clear grass lane to B, covering the actual distance, with visible paw push-offs and full-body displacement relative to MIA and the sapling. Pass in front of MIA without hitting or passing through her. The old starting patch A is left behind. MIA's head and eyes follow the travel RIGHT TO LEFT while hip/legs remain grounded and a forearm stays loaded. Do not run in place, jump prematurely at A or substitute wing flapping for travel.\n2.6–3.0 s: ONLY once the paws reach directly under the berry at B, visibly extend the hind legs into ONE brief small upward jump; all paws clear grass. Open the mouth toward the berry, then close on EMPTY AIR with a readable gap at the closest point. Mouth and actual berry/stem must be visible together. No contact, eaten fruit, stem detachment, berry lowering, neck elongation, body enlargement, upright stationary bouncing or hover. The berry remains about 90cm above its own ground; failure is shown by the mouth missing it, not horn height alone.\n3.0–4.5 s: drop onto B; a loaded paw skids on damp grass, blades bend, and the failed landing causes ONE short weighted forward tumble into reachable C beside the LEFT berry tree, clear of trunk/MIA/rim. Show shoulder, chest and muzzle contacts, compressed grass, slight soil displacement and a single soft belly rebound. Match Image 8's world position and size; do NOT return to A or the old clump on MIA's right.\n4.5–8.0 s: remain face-down in C, eyes/muzzle hidden, folded wings, breathing, one drooping unhappy tail response. MIA watches LEFT toward C, holding in her first laugh, still supported and reclining, no sit-up/standing. The next unit cuts to her reaction while GULU remains HERE.\n\n"
        + scene
        + " Normal real-time motion; the run and short jump do not expand to fill the clip. Only already-authorized soft paw/grass, wing, landing and wind sounds; no speech, BGM, song, humming, narration, subtitles, watermark or fade-out."
    )
    p3 = (
        "Fifteen-second 16:9 reaction unit. "
        + header
        + ' Image 6 is the INITIAL MIA medium shot with gaze toward C to the LEFT; Image 7 is the actual berry-side landing state C after the preceding run. The old right-side clump is not used.\n\n0.0–1.5 s: a clear CUT from the landing wide to the low 50mm girl medium. GULU stays offscreen-LEFT in C; MIA bursts into laughter, eyes crease, shoulders/abdomen bounce, her right hand presses her belly. One small grounded side-roll then return to loaded forearm support, hip/legs grounded, no sitting or palm push-up. Keep her face and support in frame.\n1.5–8.8 s: MIA speaks the exact English line ONCE with amused warmth and matching visible mouth shapes: "'
        + L1
        + "\" She looks toward C; do not inherit the former rightward gaze. Complete the line before the reaction cut, no repetition offscreen.\n8.8–9.7 s: CUT to low 70mm GULU at the SAME C beside the LEFT berry tree. Begin with eyes/muzzle still buried and compressed blades matching Image 7. It braces forepaws and pulls its dirty face out in about 0.6 seconds, blades parting and partly recovering. No jump to a different patch, dirt reset or change in physical size. A new close-up changes the projection, not the animal's dimensions.\n9.7–15.0 s: its hopeful glance BACK toward MIA, located to the RIGHT of C in this world, becomes hurt: gaze drops, lids lose hopeful lift, mouth tightens, wing roots draw in; breathing and weighted tail continue. Keep nose grass/soil. It stays at C for the next attempt, no walk back to A. A new angle may change screen positions only with consistent eyelines, background and world relationships.\n\n"
        + scene
        + " ref_audio_0 supplies MIA's approved sweet youthful ENGLISH timbre only, not sample words. Only the exact line once, scripted laugh/breaths and already-authorized soft wind. No Mandarin, extra words, music, song, humming, narration, subtitles or watermark. Normal speed."
    )
    p4 = (
        "Six-second 16:9 ground-referenced shot. "
        + header
        + " Image 6 shows the SAME GULU at berry-side C preparing the second attempt; Image 7 preserves C after the earlier face-down tumble, not a second simultaneous pose/actor.\n\nUse a steady low full-body 35–50mm view at C that keeps every paw, the ground contact, horn tips, wings and tail visible. The scale reference is neutral 40cm ground-to-horn; a 5cm LOWEST-PAW gap is only one eighth of that standing height. Preserve actual head/torso/limb dimensions and the world's ground texture. No dolly/zoom or cut hides lift-off/landing. MIA remains farther RIGHT in her original supported reclining position, watching LEFT toward C, with an amused gaze and small live head/hand response.\n0.0–1.0 s: GULU completes its weighted recovery from the low posture into the pictured natural four-paw stand at C, grass/soil still on the nose; hurt becomes stubborn determination, jaw sets.\n1.0–2.6 s: one normal bracing inhalation and short determined wing flutter; chest/abdomen show only breathing, never balloon inflation or a larger body. Load hind paws and forepaws against grass, preparing one tiny rise.\n2.6–2.8 s: ONE brief failed lift, with the lowest paws only about FIVE CENTIMETRES above the same ground, then immediate descent. This is about 0.2 seconds, not a slow high takeoff, a metre-high jump, level hover or flight. The apex is passed without pausing. Do not stand on rear legs to fake the gap.\n2.8–3.3 s: it falls onto its rump in the shallow damp-soil spot at C, depressing mud, slight local soil movement and soft belly compression/rebound; small smears remain on rump/lower belly. No deep crater, injury or magic dust.\n3.3–6.0 s: sit there in embarrassed frustration, gaze to MIA then down, wings droop, heavy tail settles, breathing continues. MIA holds a growing laugh. No relocation to A, no return to her right side, no next run or flight. The following unit cuts to her laugh while GULU remains HERE.\n\n"
        + scene
        + " No spoken words. Only the already-authorized small wing/grass/rump landing sounds and soft wind; no music, humming, narration, subtitles or watermark. All ordinary actions at normal speed; final60fps does not change action time."
    )
    p5 = (
        "Fifteen-second 16:9 unit. "
        + header
        + " Image 6 governs the INITIAL girl-only medium shot looking toward C offscreen-LEFT. Image 7 is GULU's later ANGRY FACE at C, looking back toward MIA to the RIGHT. Image 8 supplies C's world placement from the ground view, not an instruction to restart in a standing pose.\n\n0.0–1.0 s: CUT to MIA's low 50mm reaction medium. She laughs openly with creased wet eyes and a small laughter tear, RIGHT hand clutching belly; a supporting forearm/elbow remains loaded and hip/legs grounded. GULU remains in the distant muddy berry-side patch C OFFSCREEN, not beside her face. No convenient two-shot, sit-up, palm push-up or right-side reset.\n1.0–10.5 s: MIA delivers this exact ENGLISH sentence ONCE at a clear natural cadence: \""
        + L2
        + '" Right index briefly points toward C then returns to the belly. Before the words "fat lizard", CUT at about 5.5 s to a stable 70mm GULU face/shoulder reaction AT C. Continue the SAME audio sentence offscreen without restarting words; do not wait until all speech ends to reveal the dragon.\nAs "fat lizard" is heard, a brief embarrassed hopeful glance at MIA turns visibly into Image 7\'s anger: inner soft brow ridges press DOWN/IN, upper lids tense/lower into a HARD GLARE to MIA offscreen-RIGHT, lower lids braced, nostrils tense, jaw CLAMPED CLOSED, mouth corners LEVEL TO DOWN. Head lowers/thrusts forward, neck taut, wing roots close, front claws load grass. Keep gray-blue eyes and skull/horns fixed. No innocent round-eyed final expression, friendly tilt, smile, grin, smirk or happy tail wag.\n10.5–12.0 s: hold that readable angry facial set with breathing and weight, not a frozen still. Keep nose grass and the previous rump mud.\n12.0–15.0 s: one short NONVERBAL baby-dragon angry growl, lower jaw opens vertically from the tense mouth, then closes into the same anger. It plants paws, rises from the muddy seat and turns AWAY from MIA from C, one weighted stiff tail following the first departure step. Show anger before turning; do not walk back to the old start, run to the cliff or fly.\n\n'
        + scene
        + " ref_audio_0 provides only MIA's approved English timbre. Only the specified sentence once, scripted laughter/breaths, one nonverbal growl and already-authorized wind. No Mandarin, new words, BGM, songs, humming, narration, subtitles or watermark. Normal speed."
    )
    units = [
        {
            "n": 2,
            "name": "跑到果下咬空与滚草",
            "duration": 8,
            "prompt": p2,
            "main_id": "R05-02-START",
            "aux_ids": ["R05-02-MISS", "R05-02-LANDING"],
        },
        {
            "n": 3,
            "name": "同一草丛第一次笑与受伤",
            "duration": 15,
            "prompt": p3,
            "main_id": "R05-03-GIRL",
            "aux_ids": ["R05-02-LANDING"],
            "dialogue": L1,
        },
        {
            "n": 4,
            "name": "草丛C五厘米起落与跌泥",
            "duration": 6,
            "prompt": p4,
            "main_id": "R05-04-READY",
            "aux_ids": ["R05-02-LANDING"],
        },
        {
            "n": 5,
            "name": "看向同一落点调侃与恼怒",
            "duration": 15,
            "prompt": p5,
            "main_id": "R05-05-GIRL",
            "aux_ids": ["R05-05-ANGER", "R05-04-READY"],
            "dialogue": L2,
        },
    ]
    pack = {
        "tag": TAG,
        "workflow": "minimax_h3_zm_u30",
        "whitebox": False,
        "scope": [2, 3, 4, 5],
        "reuse_units": [1],
        "accepted_spatial_candidate": "01-文档/提示词/第二至五段-果树跑道与落点统一-修订候选05.md",
        "shared_world": "A right start; B LEFT directly under berry; C nearby LEFT grass; MIA stays in original place and follows A to C",
        "style": old.get("style"),
        "common_asset_ids": common,
        "source_paths": paths,
        "images": images,
        "units": units,
        "planned_merged_duration": 54,
        "state": "draft_before_image_review",
    }
    folder = P / "03-制作/制作计划" / TAG
    save(folder / "制作包01-素材方案.json", pack)
    auth = {
        "date": "2026-11-12",
        "user_reply": "好",
        "accepts": pack["accepted_spatial_candidate"],
        "accepted_units": [2, 3, 4, 5],
        "authorization_context": "Earlier explicit request to audit, optimize, actually redo affected units and merge, followed by acceptance of the revised4-unit spatial plan. Continue preparation and one submission per accepted unit after audits; no repeated approval.",
        "generation_authorized": True,
        "paid_units_used": [],
        "individual_new_image_acceptance_inferred": False,
        "no_auto_retry": True,
    }
    auth_path = P / "06-记录/用户确认/空间重制05-四段方案接受与重做合并授权接续-20261112.json"
    if not auth_path.exists():
        save(auth_path, auth)
    doc = "# 空间重制05：英文图片/视频完整候选01\n\n已接受空间方案；图片未返回，不能标实际输入就绪。\n\n"
    for item in images:
        doc += f"## 图片：{item['id']}\n\n依赖：{', '.join(item['deps'])}\n\n```text\n{item['prompt']}\n```\n\n"
    for unit in units:
        doc += f"## 视频{unit['n']:02d}：{unit['name']}（{unit['duration']}秒）\n\n```text\n{unit['prompt']}\n```\n\n"
    prompt_path = P / "01-文档/提示词/空间重制05-英文图片与视频候选01.md"
    prompt_path.write_text(doc, "utf-8")
    project_path = P / "project.yaml"
    project = yaml.safe_load(project_path.read_text("utf-8"))
    project["current"].update(
        stage="formal_first5_u30_R05_preparing",
        version=TAG,
        next_step="用户接受4段统一空间方案；已整理完整图/视频提示词，review后制作新图并核对真实输入，总审计后接续已授权02–05各一次生成及合并。",
    )
    project["documents"].update(
        spatial_R05_plan="03-制作/制作计划/空间重制05/制作包01-素材方案.json",
        spatial_R05_prompts=prompt_path.relative_to(P).as_posix(),
        spatial_R05_authorization=auth_path.relative_to(P).as_posix(),
    )
    project_path.write_text(
        yaml.safe_dump(project, allow_unicode=True, sort_keys=False, width=100), "utf-8"
    )
    print(
        json.dumps(
            {
                "images": len(images),
                "units": [(u["n"], u["duration"]) for u in units],
                "planned_seconds": 54,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
