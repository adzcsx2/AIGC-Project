"""Prepare the authorized continuation; generation is dispatched through the normal CLI."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "projects/悬崖上的小气球"
C = P / "03-制作/生成配置/后续完整剧情23"
A = P / "02-素材/镜头/后续完整剧情23"
SCRIPT = "01-文档/需求与剧本/后续完整剧情23-单主体文案03-二十厘米构图修订.md"
AUTH = "06-记录/用户确认/后续完整剧情23-二十厘米与远景修订授权03.json"
MANIFEST = P / "素材清单-后续完整剧情23.yaml"

STYLE = ("Medieval LIVE-ACTION fantasy photography, matching the approved footage: natural upper-left daylight, "
         "real wool/linen/leather, skin pores, real grass and rough gray limestone, shared exposure and contact shadows. "
         "The one pink juvenile GULU, when present, is a living photoreal cinematic VFX animal with fine irregular scales, "
         "supple skin, gray-blue wet eyes, cream belly, two curved horns, four paws, TWO original membranous wings and one tail. "
         "Keep the original braid, gray-blue cloak and clothes on MIA. No cartoon, toy, game rendering, adult transformation, "
         "red recoloring, new costume, duplicate subject, collage, text, labels, reference panels, subtitles or watermark.")
WORLD = ("Same cliff-top meadow, two timber-and-plaster cottages inland, curved path, one mature tree, wooded hills, "
         "gray limestone rim and white valley mist. A changed viewpoint may crop landmarks but cannot relocate them. "
         "The former berry lane is PARALLEL to the rim; the cliff approach is a NEW turned route, not the old berry run extended. "
         "Maintain daylight direction, grass texture scale, rigid rock geometry and steady breeze. Retain GULU nose grass/rear mud "
         "and MIA tear/sleeve/cloak marks after they occur. No storm or hurricane.")
MOTION = ("Brisk native NORMAL physical time, not slow motion, speed ramps, freezes, suspended apexes, long preparation "
          "or stretched recovery. Moves begin promptly and connect without reset. ONLY during explicitly grounded phases, paw/palm/knee loads compress contacted grass; "
          "unloaded blades partly recover. Rock stays solid. Show actual support before lifting the previous support. "
          "GULU moves across the image plane, not toward the camera; side-follow at stable distance, never a frontal approach "
          "or zoom that makes him grow. MIA standing crown-to-sole is130cm; GULU natural four-paw ground-to-highest-horn is20cm, "
          "including head/horns, excluding tail/wings. Keep skull, horn, torso and limb dimensions constant; posture, wing span "
          "and altitude are different quantities. Do not enlarge a rising or unfolding animal.")
SINGLE = ("Every shot contains ONLY the explicitly named character, or no character. Never show MIA and GULU together, "
          "including body fragments, over-shoulder figures, reflections or a recognizable companion shadow. "
          "Boards show different views of ONE individual, not multiple actors. All subject/ground/light interactions belong "
          "to one integrated photographic scene, not pasted layers. Show clean motivated HARD CUTS at the stated events. "
          "The input pictures are soft identity/pose/composition references, NOT a request to display boards or interpolate "
          "slowly between photographs, and NOT guaranteed first/last frames.")
VOICE = ("Audio1 is MIA's approved voice identity, NOT words to repeat and NOT a slow reading tempo. Audio2, when present, "
         "is the SAME MIA's later on-film English voice for vocal continuity. Audio3, when present, is her continuous natural "
         "giggle/breath performance reference, NOT a syllable sequence to recite. Keep ONE sweet youthful girl timbre for speech, "
         "breaths, laughter, alarm calls and sobs. Nonverbal emotion must emerge as a continuous acted breath/voice, never spoken "
         "'ha ha ha', spoken stage directions, rhythmic metronome laughs or an adult voice. Use ENGLISH only for the exact quoted "
         "dialogue. No extra lines, narration, sample words, Mandarin, BGM, songs, humming, musical stings or environmental/impact SFX. "
         "GULU never speaks human words or mouths MIA's voice. His explicitly scripted calls are youthful wordless dragon sounds, "
         "not an adult monster bass roar. Do not mute required dialogue to remove music.")
SILENT = "No speech, laughter, narration, music, song, humming or environmental/impact sound. Output silence unless the shot explicitly requests a wordless dragon call."

IMAGE_COMMON = "One complete widescreen16:9 photographic shot, not a reference sheet. " + STYLE + " " + WORLD

IMAGE_SPECS = {
    "D-RIM": dict(name="小龙崖口侧拍-四足起跑位置01.png", refs=["CHAR-DRAGON-THREEVIEW", "SCENE-CLIFF", "SCENE-VALLEY", "D-END"],
        prompt="Image1 identifies GULU; images2/3 identify this location and rim; image4 preserves his dirt and juvenile face. Create a SIDE full-body shot of ONLY this small dragon on the INLAND RIGHT portion of the grassy limestone lip, facing SCREEN LEFT toward the visible rim and open misty drop at left. The new side camera is perpendicular to his cliff approach. All FOUR paws are planted on solid inland grass, original wings folded, low determined posture, tight jaw and serious eyes, nose grass and rear mud retained. Highest horn about18 percent of image height, whole tail and feet visible, at least two body lengths of safe approach visible to his left before the ledge. Keep the body horizontal, short-legged and small compared with the grass/rim. No jump yet, no girl or giant stump; no long neck, swollen torso or adult wings. Firm paw support compresses grass. " + IMAGE_COMMON),
    "M-RIM": dict(name="米娅岩沿伏地-完整支撑与内侧落足空间01.png", refs=["CHAR-GIRL-THREEVIEW", "SCENE-CLIFF", "SCENE-VALLEY", "M-END"],
        prompt="Image1 is MIA identity/outfit; images2/3 are the same cliff location; image4 identifies her actual face, braid and supported low posture. Create ONLY MIA in a SIDE medium-wide COMPLETE-BODY shot at this rim. Head toward SCREEN LEFT, boots extend RIGHT into inland meadow. White valley lies at far left beyond the solid gray stone edge. Her chest/belly rest on the INLAND upper stone surface, BOTH forearms visibly loaded on stone; pelvis, knees and boots remain on solid inland ground. Only her chin/eyes peer down LEFT, never dangle her torso into the void. Worried searching face, first wet eyes, same child identity. Entire braid, cloak, both arms and boots visible; body spans about60 percent of picture width, extra room inland for later backward withdrawal and standing. Real compressed grass, slight grass/dirt on sleeves/cloak hem. No dragon or companion shadow. Preserve a plausible stone-edge profile and inland path, not a balcony or rail. " + IMAGE_COMMON),
    "D-FLY": dict(name="咕噜原有双翼展开-小体型崖外侧飞01.png", refs=["CHAR-DRAGON-THREEVIEW", "SCENE-AERIAL", "SCENE-VALLEY", "D-END"],
        prompt="Image1 identifies the SAME GULU anatomy; images2/3 identify cliff/sky/mist; image4 supplies current face and dirt. ONLY one tiny juvenile pink dragon in a readable SIDE flight profile facing SCREEN RIGHT above white valley mist, distant gray limestone rim lower-right and blue daylight sky behind. Preserve EXACTLY the existing skull/horn/torso/limb proportions. Body horizontal, four little paws naturally tucked, one full tail visible. Unfold the TWO EXISTING wings by their joints, showing their original membrane and supporting fingers; no bone growth, no extra wings, no huge adult membranes. Pose at the start of a compact effective downbeat with alert determined eyes, mouth closed. Whole wing tips, horns and tail inside the frame with8 percent safety margin, body including horns about25 percent of image height, wings may span wider without enlarging torso. Keep nose grass and light belly/rear mud. Genuine wet eyes, fine scales and supple membrane sharing sunlight and atmospheric depth. No girl, rider, magical aura, fire or frontal approach. " + IMAGE_COMMON),
    "M-CRAWL": dict(name="米娅转伏起爬-手掌接重全身01.png", refs=["CHAR-GIRL-THREEVIEW", "M-RIM", "M-END", "SCENE-CLIFF"],
        prompt="Image1 identifies MIA; image2 fixes the same new rim camera and inland rock/grass; image3 preserves her actual prior support-arm identity; image4 fixes the location. ONLY MIA, full body, HEAD LEFT and BOOTS RIGHT on the inland meadow, BEFORE arriving at the stone lip. She is low and turning from side-recline into prone crawling. The formerly free palm ALREADY bears weight on grass. The forearm that used to prop her head still rests on ground while its OWN hand reaches to plant; show the two distinct normal arms, not a transfer into the other arm. One knee folds under hips. Both arms belong to the same shoulders as image3; never swap their functional identities across camera changes. Keep torso low, worried alert face and braid, same cloak and boots. No standing, sitting, kneeling upright or jumping. Keep all hands/knees/boots in frame with generous inland crawling room; palms and knee visibly bend grass, cloak drags it with weight. The rim at LEFT is reachable by a short crawl; she remains wholly on safe inland ground. No dragon, companion shadow or extra actor. " + IMAGE_COMMON),
    "M-CRY": dict(name="米娅伏岩含泪-面部与承重手近景01.png", refs=["CHAR-GIRL-THREEVIEW", "M-RIM"],
        prompt="Image1 is MIA identity; image2 is the EXACT physical pose and location to preserve. Move the CAMERA closer for one SIDE medium close-up, not a new place or a larger girl. Only MIA's same face, braid, shoulders, forearms and hands loaded on the SAME inland stone top. Her body remains prone as image2, eyes searching DOWN-LEFT offscreen into the valley. Clearly fearful and remorseful: brows draw upward/inward, wet reddening eyes, two thin natural tear tracks, parted trembling lips and a short interrupted breath, no smile. Hands support the real body against rough stone with plausible skin pressure. Same sleeve/hem grass marks and wool texture; valley mist softly behind the left edge. Photoreal child face, not a beauty-filter adult or stylized doll. No dragon, new clothing, free-floating hands, upright kneeling or sitting. " + IMAGE_COMMON),
    "M-STAND": dict(name="米娅退回内侧站稳-全身与挥臂留白01.png", refs=["CHAR-GIRL-THREEVIEW", "M-RIM", "SCENE-CLIFF"],
        prompt="Image1 fixes MIA identity/outfit; image2 fixes the exact same cliff-side camera/ground; image3 fixes location. ONLY MIA after retreating onto the INLAND meadow, safely back from the left stone rim. Complete standing body, head about15 percent from top and boots about85 percent down; enough overhead/side room for raising both arms. She is130cm crown-to-sole with the same child proportions, braid, cloak, linen, trousers and boots, not a taller teen. Boots planted and grass compressed. Face turns toward OFFSCREEN UPPER LEFT sky, still visible tear tracks but relieved hopeful expression. Arms loosely open BEFORE the big wave, not already frozen in a victory pose. Retain sleeve/cloak grass dirt from crawling. Ground, stone rim and inland tree/cottage geography align with image2 at the new viewpoint. No dragon/body fragments/shadow, no cliff-edge balancing, levitation, jump pose, ruler, chart or text. " + IMAGE_COMMON),
}

JOBS = [
    dict(id="C23-01", seconds=6, refs=["CHAR-GIRL-THREEVIEW", "M-END", "SOLO18-MIA", "SCENE-CLIFF"], laugh=True, speakers=["CHAR-GIRL"], title="笑后揉腹与调侃起句",
         action='ONLY MIA throughout, natural cut from the preceding GULU shot. Images1/2 identify her and the actual starting support-arm; image3 refines her close shot, image4 locates the meadow.0.0-0.8s her already-running laugh eases into a real breath; original grounded support elbow stays loaded, formerly free hand moves from grass to belly.0.8-2.2s she says exactly "Oh, my stomach..." in amused breath.2.2-5.6s playful warmth returns as she says exactly "All right, all right, little chubby dragon." Face and hands expressive, eyes toward OFFSCREEN LOWER LEFT, never stand/sit/roll. Cut from a medium to a slightly tighter face/hand angle at the second sentence. Finish with a natural speech-ready breath, not a held pose; the following unit continues the teasing. No other words.'),
    dict(id="C23-02", seconds=11, refs=["CHAR-GIRL-THREEVIEW", "CHAR-DRAGON-THREEVIEW", "M-END", "D-END", "SCENE-CLIFF"], speakers=["CHAR-GIRL"], title="胖蜥蜴调侃与受挫转怒",
         action='Image1=MIA, image2=GULU, image3=MIA support/shot, image4=GULU SAME low rear-supported dirty state, image5=location.0.0-6.0s MIA ONLY in a changed slightly closer angle, same recline and elbow support. She says IN ENGLISH exactly ONCE: "Admit it - you\'re really just a fat lizard pretending to be a dragon, aren\'t you?" at a natural playful conversational pace, not slow recitation. At about6s CUT to ONLY GULU head/chest/front paws matching image4. MIA finishes any remaining words OFFSCREEN without a new utterance, complete by about8s. GULU hears the insult: a hopeful small chin lift fails, eyelids press down, jaw clamps, nostrils flare briefly, front claws load damp grass and wing roots tense. Genuine injured pride becoming ANGER, not a smile or tongue-out friendliness. Keep him low at the same tuft and camera distance. End with eyes/head turning toward the offscreen rim but feet still planted; do not run, stand bipedally or leap yet.'),
    dict(id="C23-03", seconds=9, refs=["CHAR-DRAGON-THREEVIEW", "CHAR-GIRL-THREEVIEW", "D-END", "D-RIM", "M-END"], speakers=["CHAR-GIRL"], title="转向冲崖与警告跃出",
         action='Image1=GULU, image2=MIA, image3=GULU initial frustration, image4=new SIDE cliff-approach composition with rim LEFT and inland RIGHT, image5=MIA original support.0.0-1.4s ONLY GULU: one short youthful wordless indignant growl, front paws brace, hind paws push him promptly from low rear support to FOUR-paw stance; pivot away from MIA toward rim, not toward lens.1.4-2.3s visible CUT to image4 SIDE FULL BODY: he is already accelerating RIGHT TO LEFT toward the lip, compact weighted strides and bent contacted grass.2.3-2.8s CUT briefly to ONLY MIA face/elbow/hand medium. Smile drops instantly; formerly free palm lands first, head-support elbow stays loaded. She STARTS "Gulu? Wait - it\'s dangerous!"; CONTINUE the same warning offscreen through the next shot, never squeeze all speech into0.5s.2.8-4.5s CUT BACK to GULU already FARTHER LEFT, no reset or waiting: finish run, hind-paw push visibly meets solid inland lip, leave rim and promptly descend on a short natural outward arc, tail disappears into white mist. Total effective run about1.2-2s INCLUDING MIA reaction time; apex never holds.4.5-9s CUT to ONLY MIA: shock, quick inhale, say exactly "Gulu!" once, already-landed palm bears weight while original support forearm BEGINS transferring to palm. Remain low, knees start drawing in; cut out DURING this transfer for the next wider crawling shot. No view of the hidden dragon after disappearance.'),
    dict(id="C23-04", seconds=13, refs=["CHAR-GIRL-THREEVIEW", "M-CRAWL", "M-RIM", "M-CRY", "SCENE-VALLEY"], speakers=["CHAR-GIRL"], title="爬到岩沿与第一次呼唤",
         action='Image1=MIA identity; image2=initial LOW hand-transfer/crawl, image3=eventual full-body prone rim support, image4=matching close-up, image5=her downward valley view. Do NOT start already at the rim or standing.0.0-0.6s ONLY MIA in the wider SIDE view, continuing the ALREADY-STARTED transfer: formerly free palm loaded, original head-support forearm remains down until that hand plants. Promptly roll prone with both palms bearing weight.0.6-3.5s alternate hand/knee loads in a brisk low LEFTWARD crawl to the reachable rim; press grass and drag real cloak, no floating or elastic earth.3.5-4.3s chest/belly settle on INLAND stone, forearms take weight, pelvis/knees/boots remain inland.4.3-6.0s CUT to EMPTY downward misty valley, no dragon, glow or secret recovery.6.0-13s CUT to ONLY MIA matching image4; scan DOWN-LEFT, shallow breath, brows tighten, first tear appears. Say once in ENGLISH, trembling but intelligible: "Gulu... please, stop playing. Come back..." Finish by about11.5s, keep actively looking, not frozen crying or extra words.'),
    dict(id="C23-05", seconds=14, refs=["CHAR-GIRL-THREEVIEW", "M-CRY", "M-RIM", "SCENE-VALLEY"], speakers=["CHAR-GIRL"], title="含泪认错与没有回应",
         action='ONLY MIA or an empty valley insert, NEVER GULU. Image1 identifies her; image2 is current wet-eye prone close shot, image3 fixes forearm/chest support, image4 supplies downward fog.0.0-1.4s same hands/forearms remain loaded, short interrupted inhale and fingers curl against stone; tears persist.1.4-10.5s a single continuous ENGLISH performance, exactly "I\'m sorry. I was only joking... I shouldn\'t have laughed at you... Gulu!" Maintain her approved youthful timbre through the sob, natural short gasps and full clear words. Do NOT stretch individual syllables, whisper inaudibly, laugh, use adult lament or add speech. A brief wider face/hand shot or empty fog insert may take part of her OFFSCREEN sentence without restarting it.10.5-14s she searches down again, an involuntary sniff and fast breath, wet gaze and shoulders alive, no answer. Chest/pelvis stay on inland surface; no hand floats or body shifts over the edge. End still listening downward, not standing. NO dragon roar yet; the next unit introduces it FIRST.'),
    dict(id="C23-06", seconds=12, refs=["CHAR-GIRL-THREEVIEW", "CHAR-DRAGON-THREEVIEW", "M-CRY", "D-FLY", "SCENE-VALLEY", "SCENE-AERIAL"], speakers=[], title="先闻龙吟再见破雾归来",
         action='Image1=MIA, image2=GULU, image3=MIA current prone tears, image4=GULU same small body with existing wings unfolded, images5/6=connected valley/rim/sky.0.0-2.0s ONLY MIA downward-looking close-up: FIRST a clear strong yet YOUTHFUL WORDLESS DRAGON CALL rises from below OFFSCREEN. Her sob catches briefly, eyes widen and she searches the sound. No human words or sung roar.2.0-7.2s hard CUT to ONLY GULU SIDE-on beyond the rim: same pink juvenile climbs briskly OUT OF MIST, body horizontal, four little paws tucked, original wing joints/membranes unfold without growth. Compact effective downbeats and tail corrections sustain the upward flight assisted by rising air. He has already arrested his fall; do not show a new fall/rebirth or inflated adult. Local mist parts at his path then curls back; rock/landscape stays rigid. Keep whole wings and tail in view, stable sideways camera distance.7.2-12s CUT to ONLY MIA: lift head quickly to follow OFFSCREEN UPPER LEFT, tears remain, mouth opens in silent disbelief, brows release and a real relief breath opens into a small smile. Original forearm support stays loaded; brief local flutter in loose hair/cloth matches passage, no hurricane or unbraided hair. No laugh syllables, narration or new line.'),
    dict(id="C23-07", seconds=12, refs=["CHAR-DRAGON-THREEVIEW", "D-FLY", "SCENE-AERIAL", "SCENE-VALLEY"], speakers=[], title="原速飞行滚转俯冲拉起与盘旋",
         action='ONLY GULU throughout. Image1 identifies his ONE juvenile anatomy; image2 is active small-body flight and original wing geometry; images3/4 fix the same daylight cliff and mist.0.0-2.0s ALREADY FLYING forward in a wide SIDE follow, prompt compact wingbeats, not a still pose starting slowly.2.0-5.5s keep the ENTIRE unbroken action in one readable SIDE flight shot: one quick bank, ONE axial roll about0.6-1s, recover level promptly about0.3-0.5s, a SHORT descending dive about0.6-1s and a decisive wing-driven pull-up about0.6-1s. Keep active tail/wing coordination, momentum and body weight, no hover, stalled apex, endlessly spinning dragon or front-to-camera approach.5.5-9.5s ONE complete broad proud circuit, using two coherent side views with the same cliff landmark, moving camera follows at stable distance. Show departure arc and RETURN outlet toward the rim; circle is forward travel, not hovering.9.5-12s exit that SAME circuit already flying along the outer cliff, preparing the next pass; no second circuit. Whole original wings/horns/tail retain margins, torso never enlarges. Normal sunlit fine scales/membranes, not red fire, plastic or an adult dragon. No sound except silence: no human breath, voice or added wind/music.'),
    dict(id="C23-08", seconds=5, refs=["CHAR-GIRL-THREEVIEW", "M-CRY", "M-RIM"], speakers=[], title="伏岩追望与释然微笑",
         action='ONLY MIA. Image1 identifies her, images2/3 retain prone stone support and tear tracks. A motivated CUT from the flying dragon to a side face/forearm medium close-up.0.0-1s eyes quickly follow OFFSCREEN UPPER LEFT, a small head adjustment and released breath.1-3s recognition opens into a visibly delighted wet-eyed smile, brows relax, lips no longer tremble; remain one natural continuous reaction, not three poses.3-5s original support forearm remains loaded, formerly free hand begins lifting toward the wet cheek for the later wipe, breath alive. No words, phonetic laugh, random sigh, standing, kneeling upright, sitting or both hands off rock. Preserve grass marks on sleeves/cloak. End in motion with hand only beginning to rise, do not finish the wipe prematurely.'),
    dict(id="C23-09", seconds=11, refs=["CHAR-DRAGON-THREEVIEW", "CHAR-GIRL-THREEVIEW", "D-FLY", "M-CRY", "M-RIM", "SCENE-AERIAL"], speakers=[], laugh=True, title="沿崖骄傲掠过与擦泪准备退回",
         action='Image1=GULU, image2=MIA; image3=small dragon side flight, images4/5=MIA same prone tears/support, image6=outer cliff.0.0-4s ONLY GULU, continuing the established circuit OUTLET in a SIDE pass along the rim, not a new loop or approach. Keep his flight alive while he turns eyes/head briefly DOWN toward OFFSCREEN MIA, lifts chin proudly, relaxed jaw rather than rage or a human grin.4-6.5s visible CUT to a closer SIDE head/upper-body flight view, camera distance changes by cut, actual anatomy stays identical. Turn muzzle BACK OUT toward EMPTY VALLEY before expelling ONE tiny golden spark puff. It disperses promptly without explosion, full-face glare or fire at the girl; never stop flying for the effect.6.5-11s hard CUT to ONLY MIA, same prone support: continuous relief chuckle/breath in HER same voice, original support forearm bears weight. Formerly free hand completes ONE tear wipe already initiated in previous unit, then that palm PLANTS on inland stone. Eyes remain skyward, tears not fully erased, sleeve/hem dirt retained. End ready to transfer the remaining forearm to palm and retreat, no repeated wipe, sit-up or standing yet.'),
    dict(id="C23-10", seconds=15, edit_seconds=13, refs=["CHAR-GIRL-THREEVIEW", "CHAR-DRAGON-THREEVIEW", "M-RIM", "M-STAND", "M-CRY", "D-FLY"], speakers=["CHAR-GIRL"], laugh=True, title="退回起身赞美与幼龙回应-含声音尾柄",
         action='Image1=MIA, image2=GULU; image3 is the ACTUAL INITIAL prone rim support, image4 is ONLY her LATER STANDING state, image5 fixes tear/face details, image6=GULU flight. Do not start in image4 pose.0.0-3.5s ONLY MIA, SIDE FULL BODY with room to stand: the previously wiped-and-planted hand ALREADY bears weight; remaining forearm transfers to palm. Hands step BACK one at a time, pull chest/pelvis inland, knees/feet tuck well BACK FROM LIP, enter low crouch. One small joyous hop about0.2-0.35s, prompt grounded landing about0.2-0.35s with bent grass and following cloak; do not float or teleport inland. The WHOLE transfer/withdrawal/hop/contact stays visible before cutting.3.5-10.5s CUT to ONLY MIA medium close-up with arm room: AFTER landing, wave both arms and say exactly ONCE in ENGLISH, joyful and sincere, "Gulu! You\'re amazing! You\'re the best dragon in the whole world!" Natural energetic cadence, no stretched words. Same youthful voice, wet face and dirt. After the complete sentence, release into ONE spontaneous tearful RELIEF LAUGH with continuous breath, no syllable recitation.10.5-15s CUT to ONLY GULU already flying sideways, lift chin in response and answer with ONE youthful clear WORDLESS DRAGON CALL. MIA\'s same laugh continues OFFSCREEN briefly under it; do not restart either sound. Keep forward flight through the end, no held portrait. Final2s provide an audio tail for the subsequent EMPTY valley cut, not extra plot or slow padding.'),
    dict(id="C23-11", seconds=4, refs=["SCENE-AERIAL", "SCENE-VALLEY"], speakers=[], title="无人山谷片尾留白",
         action='EMPTY valley landscape ONLY. Image1 is the same daylight aerial cliff/woods, image2 gives its lower mist and gray rock. A clean motivated CUT to a quiet wide valley view, stable camera, normally moving white mist curling gently between wooded slopes, same blue daylight and rock geography. No girl, dragon, companion shadow, silhouette, face, cottages added, text or new incident. No sunset or storm. This is a brief visual epilogue under the PREVIOUS unit\'s carried laugh/dragon call, which will be edited separately. Generate NO audio here, no new laugh/roar or music. Do not freeze mist or turn still image into a slow zoom.'),
]

# The first M-RIM request returned no image (output moderation). This is a different,
# fully supported inland composition; the valley drop is shown by a separate empty POV.
IMAGE_SPECS["M-RIM"] = dict(
    name="米娅岩沿伏地-完整支撑与内侧落足空间01.png",
    refs=["CHAR-GIRL-THREEVIEW", "M-END", "SCENE-CLIFF"],
    prompt=("Image1 identifies MIA and her complete medieval clothes. Image2 is her actual on-film face, braid and resting arm pose. "
            "Image3 supplies the same meadow, daylight, mature tree and cottage surroundings. Create one natural full-body SIDE photograph of ONLY MIA, "
            "fully dressed exactly as the references, resting low on a broad FLAT solid gray limestone surface surrounded by grass at the meadow viewpoint. "
            "She is completely supported on solid ground from elbows to boots. Head points LEFT, boots extend RIGHT, both forearms rest visibly on the stone, "
            "hands relaxed against it. Her expression is worried and attentive, eyes directed DOWN-LEFT at something outside the picture. "
            "This composition shows the inland stone/grass surface, NOT a vertical drop or a hanging body; no falling or balancing at an edge. "
            "Keep her entire braid, cloak, arms and boots visible; body spans about60 percent of width, with generous grass space behind her for later movement. "
            "Retain the original face/age/proportions and normal opaque wool/linen/leather outfit. A few grass marks on sleeves and cloak hem, "
            "natural ground contact and compressed grass. No dragon, extra person, companion shadow, railing, text or props. " + IMAGE_COMMON),
)


# Two optional pose derivatives returned no image. Reuse the actual prior support
# and accepted inland full-body pose; do not claim blocked outputs exist.
del IMAGE_SPECS['M-CRAWL']
del IMAGE_SPECS['M-CRY']
IMAGE_SPECS['D-RIM'] = dict(name='小龙二十厘米-环境主导崖口侧拍02.png', refs=['CHAR-DRAGON-THREEVIEW','SCENE-CLIFF','SCENE-VALLEY','D-END'], prompt='Image1 identifies the ONE original pink juvenile GULU, image4 only supplies dirt and face identity, NOT framing or camera distance. Images2/3 set the real meadow and limestone valley. Make a VERY WIDE environmental SIDE shot: camera pulled far back to show much more meadow, the two cottages, large mature tree, long stone rim and valley. The landscape occupies over90 percent of the image. ONLY one SMALL kitten-sized dragon stands on FOUR paws on the inland RIGHT side, facing SCREEN LEFT with two of his own body lengths of grounded approach before the rim. Ground to highest horn tip is20cm including head/horns, low crouch about10cm; tail and folded wings are not height. His actual horn-to-ground screen span should be ONLY6-8 percent of image height; entire tail-to-snout spans about15-18 percent of width, in the midground NOT a giant foreground animal. Preserve the same short-legged juvenile skull/torso proportions without shrinking only legs or head. Short3-5cm meadow blades reach ankles, not miniature forest trees. Keep full paws/tail visible, folded original wings, tight angry jaw and narrowed eyes; mud/grass marks retained. Real contact shadow and locally pressed grass only, rigid world. No girl, other creatures, giant stump, ruler, labels or collage. Do not imitate a close dragon portrait. ' + IMAGE_COMMON)
IMAGE_SPECS['D-FLY'] = dict(name='小龙二十厘米-环境主导崖外侧飞02.png', refs=['CHAR-DRAGON-THREEVIEW','SCENE-AERIAL','SCENE-VALLEY','D-END'], prompt='Image1 identifies the ONE original pink juvenile GULU; image4 supplies face and mud ONLY, not its close framing. Images2/3 fix this connected cliff/valley/daylight environment. Create a VERY WIDE environmental SIDE flight photograph with substantially more meadow, limestone cliff face, wooded valley and sky. Show one SMALL kitten-sized dragon just outside and near the middle-distance cliff lip at comparable depth to the visible lip, NOT flying close to the lens in front of distant tiny houses. The landscape occupies over90 percent of the picture. Natural FOUR-paw standing height would be20cm ground to highest horn including head/horns; low posture10cm; flight altitude and open wing span are separate. In this horizontal flight profile, highest horn to belly/paws occupies only5-7 percent of image height; complete wing envelope including tips at most14-18 percent of height, full tail-to-snout at most18-22 percent of image width. Frame the small animal around55 percent from left and42 percent from top, facing SCREEN RIGHT. Preserve original juvenile head/torso/limb dimensions, four tucked paws, full tail, TWO existing membranes unfolded naturally with their original joints, no adult wing growth. Keep nose grass/rear mud, photoreal fine scales and common sunlight. No foreground giant dragon, human, rider, close-up, extra animal, aura, flame, ruler, text or reference panels. ' + IMAGE_COMMON)
IMAGE_SPECS['D-FLY'] = dict(name='小龙二十厘米-真实外景小占比侧飞03.png', refs=['SCENE-AERIAL','PHOTO-STYLE23','CHAR-DRAGON-THREEVIEW','D-END'], prompt='EDIT THE WIDE LANDSCAPE from Image1, preserving its full framing, cliff shape, two cottages and tree locations. Image2 is ONLY real-location photographic material/tonal treatment, not a different setting. Image3 identifies ONE pink baby dragon, image4 gives face/dirt ONLY. Keep the scene an environmental wide shot, NOT a dragon portrait. Add the single TINY distant dragon beside the middle-distance cliff lip, at55 percent image width and42 percent image height, flying SIDE PROFILE toward SCREEN RIGHT. Its horn-to-tucked-paw body height must be ONLY2-3 percent of picture height (about20-28 pixels on a941-pixel-high picture). Complete tail-to-snout length about8 percent of picture width; the TWO opened wings together occupy no more than7-9 percent of picture height. Leave over95 percent of the picture as environment. It is20cm standing ground-to-highest-horn, a small kitten-sized animal, near the lip in depth, never a large foreground animal with distant tiny houses behind. Preserve its original pink juvenile head/torso/limbs, four tucked paws, two original membranes and tail, nose grass and rear mud. Its fine details are naturally barely resolvable at this distance; do not enlarge it to show every scale or facial pore. Photographic common sunlight/exposure and atmospheric contrast, natural muted pink. Do not copy identity-board composition, do not zoom/crop. No girl, adult giant, added creature, labels, UI, ruler or collage. ' + IMAGE_COMMON)
IMAGE_SPECS['D-RIM'] = dict(name='小龙二十厘米-真实外景小占比崖口03.png', refs=['SCENE-CLIFF','PHOTO-STYLE23','CHAR-DRAGON-THREEVIEW','D-END'], prompt='EDIT THE WIDE MEADOW LANDSCAPE from Image1, keeping its full scene/camera and two cottages/tree/rim geography. Image2 supplies real-location photographic treatment ONLY. Image3 identifies ONE pink juvenile dragon; image4 gives current dirt and face ONLY, not its close framing. Show a single TINY kitten-sized dragon on the inland RIGHT at about65 percent image width and62 percent image height, facing SCREEN LEFT toward the rim, on FOUR grounded paws, original wings folded. The actual standing horn-to-ground screen height is ONLY3-4 percent of picture height, about28-38 pixels on a941-pixel-high image; complete tail-to-snout length about10 percent of width. Keep at least two of its own body lengths of solid grass before the left lip. Landscape occupies over95 percent of frame. Natural standing ground-to-highest-horn height20cm including head/horns, low posture10cm, tail/wings separate. Make SAME-depth short meadow blades ankle-height, not miniature trees. Retain original juvenile anatomy, tight jaw and narrowed eyes with appropriate distant readability; never enlarge it to show face detail. Gentle real contact shadow and locally loaded grass, original nose/rear dirt. No girl, other creature, foreground giant, large stump, new props, ruler, labels, UI, montage, zoom or crop. ' + IMAGE_COMMON)
FILM_PLATE = (' Preserve landscape GEOGRAPHY and the requested small creature composition, but RE-PHOTOGRAPH the entire plate with the material/exposure realism of the film image2. Image2 is style only: ignore its adult dragon, vessel, cast, UI and framing. Do not retain the old landscape rendering finish. Real exterior location under softly cloud-filtered daylight: natural subdued greens, gray limestone, physically irregular sparse grass and earthy patches, organically uneven foliage, weathered lime plaster and timber, believable nonrepetitive stone strata. Exposure shaped by sky light with substantial natural shaded areas, restrained specular highlights, optical edge softness and modest atmospheric contrast loss at distance. No sugary luminous green, yellow fantasy glow, evenly embossed rock detail, procedural fractal tree crowns, oversharpened HDR/clarity or an illustrated/game-environment appearance. Keep the original clothes/color/anatomy and20cm scale; no dramatic new storm, smoke or sunset. ')
for _key in ['D-RIM','D-FLY']:
    IMAGE_SPECS[_key]['refs'][1] = 'FILM-USER02'
    IMAGE_SPECS[_key]['prompt'] = IMAGE_SPECS[_key]['prompt'].replace('Image2 supplies real-location photographic treatment ONLY.', 'Image2 supplies film photographic treatment ONLY.').replace('Image2 is ONLY real-location photographic material/tonal treatment, not a different setting.', 'Image2 is ONLY film photographic material/tonal treatment, not a different setting.').removesuffix(IMAGE_COMMON) + FILM_PLATE + IMAGE_COMMON
    if _key == 'D-FLY':
        IMAGE_SPECS[_key]['name'] = '小龙二十厘米-电影外景小占比侧飞04.png'
    else:
        IMAGE_SPECS[_key]['name'] = '小龙二十厘米-电影外景小占比崖口04.png'
IMAGE_SPECS['D-RIM'] = dict(name='小龙二十厘米-电影外景校准崖口05.png',refs=['D-RIM-PLATE04','CHAR-DRAGON-THREEVIEW','FILM-USER02'],prompt='Edit Image1 as one coherent photographic shot. KEEP the entire landscape, framing, tree, cottages, cliff, daylight, material treatment and camera unchanged. Make only the ONE existing pink juvenile dragon THREE TIMES SMALLER in BOTH width and height, uniformly about33 percent of its current size. Grounded feet stay at the same grass point, with original left-facing four-paw stance, folded wings and tail. The old image animal is about100pixels tall in a941pixel-high picture; the NEW whole ground-to-highest-horn projection must be only30-35pixels tall. All head, horns, trunk, limbs, wings and tail reduce together; never shorten only legs. This represents20cm actual four-paw height including head/horns, low posture10cm; do not add a duplicate animal or a large foreground replacement. Restore the surrounding grass naturally where the larger old silhouette was, keeping one continuous real contact/shadow under the tiny animal. Identity remains exactly Image2; Image3 is photographic material/exposure style only, no adult dragon/vessel/people/UI copied. Landscape occupies over95 percent; no crop, zoom, camera move, added props, text, ruler or labels. Retain natural muddy marks, subtle muted pink and distance-appropriate soft optical detail. ' + IMAGE_COMMON)
for _key, _base, _name in [
    ('M-RIM','M-RIM-PLATE01','米娅内侧石面伏地-电影外景质感02.png'),
    ('M-STAND','M-STAND-PLATE01','米娅内侧站稳-电影外景质感02.png'),
]:
    IMAGE_SPECS[_key] = dict(name=_name,refs=[_base,'CHAR-GIRL-THREEVIEW','FILM-USER02'],prompt='Edit Image1 into a convincing live-action location photograph. Keep the one fully dressed MIA, her original face/age, braid, gray-blue wool cloak, opaque linen and leather clothes, full anatomy, EXACT body pose, grounded support, composition and complete visible hands/boots unchanged. Image2 is her identity/outfit only. Image3 provides photographed film material/exposure treatment ONLY: never copy its dragon, vessel, people, scenery, pose, UI or darkness. Re-photograph the SAME meadow/stone/cottages/tree in softly filtered daylight, natural subdued greens, believable shaped shadows, restrained highlights and modest optical detail. Keep support/contact real, not a pasted person. No beauty retouching or waxy skin, no vivid synthetic green, HDR/clarity, evenly embossed texture, glow, game-environment or polished CGI display. Preserve facial expression and eye direction, natural dirt/tear marks, no new event or extra actor. Do not crop, zoom, stand up, lie down or reposition her; this is photographic treatment of the existing pose only. ' + IMAGE_COMMON)
for _job in JOBS:
    _id = _job['id']
    if _id == 'C23-04':
        _job['refs'] = ['CHAR-GIRL-THREEVIEW', 'M-END', 'M-RIM', 'SCENE-VALLEY']
        _job['action'] = _job['action'].replace('image2=initial LOW hand-transfer/crawl, image3=eventual full-body prone rim support, image4=matching close-up, image5=her downward valley view', 'image2 identifies the ORIGINAL support arm before transfer, not the exact initial hand pose; image3 is the eventual fully supported prone stone position, image4 is the downward valley view').replace('ONLY MIA matching image4', 'ONLY MIA in a closer camera view of image3, adding the continuing wet eyes through acting')
    if _id == 'C23-05':
        _job['refs'] = ['CHAR-GIRL-THREEVIEW', 'M-RIM', 'SCENE-VALLEY']
        _job['action'] = _job['action'].replace('image2 is current wet-eye prone close shot, image3 fixes forearm/chest support, image4 supplies downward fog', 'image2 fixes the prone forearm/chest support and face; use a closer camera view with the continuing tears from the preceding video, image3 supplies downward fog')
    if _id == 'C23-06':
        _job['refs'] = ['CHAR-GIRL-THREEVIEW','CHAR-DRAGON-THREEVIEW','M-RIM','D-FLY','SCENE-VALLEY','SCENE-AERIAL']
        _job['action'] = _job['action'].replace('image3=MIA current prone tears', 'image3=MIA prone support and face; retain tears established by the preceding video')
    if _id == 'C23-08':
        _job['refs'] = ['CHAR-GIRL-THREEVIEW','M-RIM']
        _job['action'] = _job['action'].replace('images2/3 retain prone stone support and tear tracks', 'image2 retains prone stone support; keep tear tracks established in the preceding video')
    if _id == 'C23-09':
        _job['refs'] = ['CHAR-DRAGON-THREEVIEW','CHAR-GIRL-THREEVIEW','D-FLY','M-RIM','SCENE-AERIAL']
        _job['action'] = _job['action'].replace('images4/5=MIA same prone tears/support, image6=outer cliff', 'image4=MIA same prone support with continuing tears from the preceding video, image5=outer cliff').replace('a closer SIDE head/upper-body flight view, camera distance changes by cut, actual anatomy stays identical', 'a changed WIDE SIDE flight angle, keeping the dragon small within the dominant landscape and actual anatomy identical')
    if _id == 'C23-10':
        _job['refs'] = ['CHAR-GIRL-THREEVIEW','CHAR-DRAGON-THREEVIEW','M-RIM','M-STAND','D-FLY']
        _job['action'] = _job['action'].replace('image5 fixes tear/face details, image6=GULU flight', 'image5=GULU small-in-landscape flight; retain MIA established tear tracks from the preceding video')

# The user corrected both world height AND composition before any video dispatch.
for _job in JOBS:
    if _job['id'] == 'C23-02':
        _job['action'] = _job['action'].replace('ONLY GULU head/chest/front paws matching image4', 'ONLY GULU in a WIDE full-body side view; image4 supplies low posture and dirt, not close camera framing')
    if 'CHAR-DRAGON-THREEVIEW' in _job['refs']:
        _job['action'] += ' GULU is20cm ground-to-highest-horn on FOUR paws, low posture about10cm. Identity boards and the old footage still are ONLY anatomy/face/dirt references, never framing or a40cm size target. Use environment-dominant WIDE side views: no large foreground dragon and no push-in. During grounded wide action horn-to-ground is roughly3-4 percent of frame height; during wide flight the horn/body/paw height is2-3 percent and opened wings remain within7-9 percent of frame height. Keep that camera distance throughout action; sideways camera travel is allowed. Small stature must be readable against meadow grass and rock at the SAME depth, not inferred by comparing foreground animal to distant houses.'


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scoped_style(ids: list[str]) -> str:
    # Re-read the current project style for EVERY independent prompt compilation.
    project = yaml.safe_load((P / 'project.yaml').read_text(encoding='utf-8'))
    style_text = (P / project['documents']['style']).read_text(encoding='utf-8')
    style_core = style_text.split('## 当前英文风格核心（逐请求使用）', 1)[1].split('```text', 1)[1].split('```', 1)[0].strip()
    result = ("Medieval LIVE-ACTION fantasy photography matching the approved footage: natural upper-left daylight, "
              "photographic texture, real grass/earth/gray limestone, shared exposure, optical depth and contact shadows. ")
    if "CHAR-GIRL-THREEVIEW" in ids:
        result += "MIA is the SAME real-looking child, skin pores, original braid, gray-blue wool cloak, linen clothes and leather boots. "
    if "CHAR-DRAGON-THREEVIEW" in ids:
        result += "GULU is the SAME living photoreal cinematic VFX pink juvenile, fine irregular scales, supple skin, gray-blue wet eyes, cream belly, two original horns, four paws, two original membrane wings and one tail. "
    result += "No cartoon, toy, game render, adult transformation, recoloring, costume change, duplicate character, collage, labels, boards, subtitles or watermark."
    return result + ' ' + style_core


def scoped_world(ids: list[str]) -> str:
    result = WORLD.replace("Retain GULU nose grass/rear mud and MIA tear/sleeve/cloak marks after they occur. ", "")
    if "CHAR-GIRL-THREEVIEW" in ids:
        result += " Retain MIA tear/sleeve/cloak marks after they occur."
    if "CHAR-DRAGON-THREEVIEW" in ids:
        result += " Retain GULU nose grass and rear/belly mud."
    return result


def scoped_motion(ids: list[str]) -> str:
    result = ("Brisk native NORMAL physical time: prompt short initiation, effective continuous execution, momentary apex, timely descent/contact and recovery. "
              "No slow motion, speed ramps, freeze, hover, long preparation or stretched recovery. Only explicitly grounded contacts load/bend grass; "
              "unloaded blades partly recover. Rock stays solid. Establish the new support before lifting the previous support. ")
    if "CHAR-GIRL-THREEVIEW" in ids:
        result += "MIA is130cm standing crown-to-sole, the same child body; a pose change is joint articulation, not growth. "
    if "CHAR-DRAGON-THREEVIEW" in ids:
        result += ("GULU natural four-paw ground-to-highest-horn is20cm including head/horns, excluding tail/wings. Preserve skull/horns/torso/limb dimensions; "
                   "posture, opened wing span and flight altitude are different quantities. Move laterally across the image, not toward lens; "
                   "follow SIDEWAYS at stable distance, no zoom/frontal approach that makes him grow. ")
    return result


def prepare(finalize: bool = False) -> None:
    C.mkdir(parents=True, exist_ok=True)
    A.mkdir(parents=True, exist_ok=True)
    project = yaml.safe_load((P / "project.yaml").read_text(encoding="utf-8"))
    source = yaml.safe_load((P / "素材清单-前四十秒单主体19-执行01.yaml").read_text(encoding="utf-8"))
    base = Path(project["current"]["delivery"]["primary"])
    assert digest(P / SCRIPT) == "da886fe3ee61b3c62f1ad99d3c5c59998b587a2fe2c5dec0e7f59b86fb68cf51"
    if not (P / AUTH).exists():
        (P / AUTH).write_text(json.dumps({
            "date": "2026-11-13", "user_message": "可以，按修订稿开始制作后面所有视频，先审计提示词和素材，再用u30生成，最后和前面的成片合并。",
            "script": SCRIPT, "script_sha256": digest(P / SCRIPT), "script_acceptance": "confirmed",
            "base_delivery": str(base), "base_sha256": digest(base),
            "scope": "Audit prompts/materials, prepare same-character/scene derivatives, generate all continuation units once each with u30, edit and merge with selected existing film, final60fps.",
            "material_review": "Assistant audits derived assets under this complete-production request; not a claim of individual user image acceptance.",
            "auto_paid_rerolls": False,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    assets = {k: copy.deepcopy(source["assets"][k]) for k in ["CHAR-GIRL-THREEVIEW", "CHAR-DRAGON-THREEVIEW", "VOICE-GIRL", "SOLO18-MIA"]}
    existing = {
        "M-RIM-PLATE01": "02-素材/镜头/后续完整剧情23/米娅岩沿伏地-完整支撑与内侧落足空间01.png",
        "M-STAND-PLATE01": "02-素材/镜头/后续完整剧情23/米娅退回内侧站稳-全身与挥臂留白01.png",
        "D-RIM-PLATE04": "02-素材/镜头/后续完整剧情23/小龙二十厘米-电影外景小占比崖口04.png",
        "FILM-USER02": "02-素材/风格参考/用户电影视效-背光与承重基准02.png",
        "PHOTO-STYLE23": "02-素材/风格参考/已认可外景摄影质感-共享基准受控副本01.png",
        "SCENE-CLIFF": "02-素材/场景/风铃崖-环境总览-候选02.png",
        "SCENE-VALLEY": "02-素材/场景/风铃崖-岩沿向下雾谷-候选01.png",
        "SCENE-AERIAL": "02-素材/场景/风铃崖-谷外飞行与回望-候选01.png",
    }
    for key, path in existing.items():
        assets[key] = dict(kind="scene", path=path, state="ready", sha256=digest(P / path), purpose="existing_approved_location", required=False)
    for key, original, name in [
        ("M-END", "05-检查与验收/后续完整剧情23-女孩尾态参考02.jpg", "米娅最近成片-原支撑肘与空闲手01.jpg"),
        ("D-END", "05-检查与验收/后续完整剧情23-现有结尾参考01.jpg", "咕噜最近成片-低位受挫与鼻草泥痕01.jpg"),
    ]:
        dst = A / name
        if not dst.exists():
            os.link(P / original, dst)
        assets[key] = dict(kind="keyframe", path=dst.relative_to(P).as_posix(), state="ready", sha256=digest(dst), purpose="existing_footage_boundary_pose", required=False, provenance=original, storage="read-only hardlink of existing evidence bytes")
    aud = P / "02-素材/音频/角色声音/披风女孩米娅/后续完整剧情23"
    aud.mkdir(parents=True, exist_ok=True)
    refs_audio = [
        ("VOICE-MATCH23", P / "02-素材/音频/角色声音/披风女孩米娅/笑声统一21/米娅-成片后段英文对白-音色匹配参照01.wav", "同一米娅-成片英文声音衔接参照01.wav"),
        ("VOICE-LAUGH23", P / "03-制作/音轨处理/女孩呼吸与自然笑声统一22/完整连续轻笑与换气-连续原声选段01.wav", "同一米娅-连续自然轻笑与换气参照01.wav"),
    ]
    for key, original, name in refs_audio:
        dst = aud / name
        if not dst.exists():
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(original), "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(dst)], check=True)
        assets[key] = dict(kind="audio", path=dst.relative_to(P).as_posix(), state="ready", sha256=digest(dst), required=False, purpose="same_character_performance_continuity_reference", provenance=str(original.relative_to(P)))
    images = []
    for key, spec in IMAGE_SPECS.items():
        dst = A / spec["name"]
        state = "ready" if finalize and dst.exists() else "planned"
        assets[key] = dict(kind="keyframe", path=dst.relative_to(P).as_posix(), state=state, required=False, purpose="single_subject_pose_and_composition_soft_reference", production_method="builtin_imagegen", user_review="authorized_derivative_not_individually_accepted")
        if state == "ready":
            assets[key]["sha256"] = digest(dst)
            assets[key]["review_record"] = "05-检查与验收/后续完整剧情23-返回素材与实际输入检查05.json"
            assets[key]["assistant_review"] = "see actual returned-image audit"
        actual_image_prompt = spec["prompt"].removesuffix(IMAGE_COMMON) + "One complete widescreen16:9 photographic shot, not a reference sheet. " + scoped_style(spec["refs"]) + " " + scoped_world(spec["refs"])
        actual_image_prompt = actual_image_prompt.replace("No dragon/body fragments/shadow", "No dragon, companion body fragments or companion shadow")
        promptfile = C / (key + "-图片英文正文01.txt")
        promptfile.write_text(actual_image_prompt, encoding="utf-8")
        images.append(dict(asset_id=key, path=assets[key]["path"], references=spec["refs"], prompt=actual_image_prompt, prompt_sha256=digest(promptfile)))
    shots = {}
    jobs = []
    for index, job in enumerate(JOBS):
        ids = job["refs"] + ["PHOTO-STYLE23"]
        action = job["action"]
        if job["id"] == "C23-03":
            # Native pacing adjustment within the accepted approximate story block: no five-second delayed hand transfer.
            job = {**job, "seconds": 6}
            action = action.replace("0.0-1.4s", "0.0-1.0s").replace("1.4-2.3s", "1.0-1.8s").replace("2.3-2.8s", "1.8-2.3s").replace("2.8-4.5s", "2.3-3.6s").replace("4.5-9s", "3.6-6.0s")
            action = action.replace("cut out DURING this transfer", "begin the transfer in the LAST0.4s and cut out DURING it; never stretch the transfer across the full reaction")
            action = action.replace("while original support forearm BEGINS transferring to palm", "while original support forearm REMAINS loaded until the final transfer starts")
        if job["id"] == "C23-10":
            action = action.replace("image3 is the ACTUAL INITIAL prone rim support", "image3 fixes prone LOCATION and body anatomy, not a hand reset; the actual INITIAL formerly-free palm is ALREADY planted as in the preceding shot")
        if job["id"] == "C23-06":
            action = action.replace("He has already arrested his fall;", "Pass rapidly through the mist boundary and above the lip within the first1.2s of this shot, then keep flying sideward into the sky; do not spend5s slowly rising. He has already arrested his fall;")
        if job["id"] == "C23-08":
            action = action.replace("3-5s original support forearm", "3-4.7s continue live relieved eye tracking and breathing, no hand wipe yet.4.7-5s original support forearm")
        if job["id"] == "C23-09":
            action = action.replace("completes ONE tear wipe already initiated in previous unit, then that palm PLANTS on inland stone.", "completes ONE tear wipe in about0.4-0.6s, already initiated in previous unit, then promptly PLANTS that palm on inland stone in about0.3-0.4s. Do not drag these short gestures across the whole shot; the remaining time is alive relieved eye tracking and breath.")
        job = {**job, "action": action}
        prompt = action + "\n\n" + SINGLE + "\n" + scoped_motion(ids) + "\n" + scoped_world(ids) + "\n" + scoped_style(ids)
        if job["id"] == "C23-07":
            prompt = action + "\n" + SINGLE + "\n" + scoped_world(ids) + "\n" + scoped_style(ids) + "\nKeep the same20cm ground-to-horn juvenile anatomy in flight; altitude and opened wing span are not body growth. Native brisk physical timing, no slow motion, hover, reset or camera approach."
        if job["id"] == "C23-11":
            prompt = action + "\n" + scoped_world(ids) + "\n" + scoped_style(ids)
        if job["id"] not in ["C23-07", "C23-11"]:
            prompt += "\n" + VOICE
        else:
            prompt += "\n" + SILENT
        prompt += '\nThe LAST image is photographic STYLE treatment only: common natural exposure/material/optical detail. Do not relocate this shot to that forest or copy its framing.'
        if 'CHAR-DRAGON-THREEVIEW' in ids:
            prompt += ' The identity boards and older close footage supply anatomy only. WIDE dragon shots follow the small-in-landscape size of the current calibrated reference, not old close-up magnification.'
        inputs = {f"ref_image_{i}": str(P / assets[k]["path"]) for i, k in enumerate(ids)}
        bindings = {f"ref_image_{i}": k for i, k in enumerate(ids)}
        audio_ids = [] if job["id"] in ["C23-07", "C23-11"] else ["VOICE-GIRL", "VOICE-MATCH23"]
        if job.get("laugh"):
            audio_ids.append("VOICE-LAUGH23")
        for i, key in enumerate(audio_ids):
            inputs[f"ref_audio_{i}"] = str(P / assets[key]["path"])
            bindings[f"ref_audio_{i}"] = key
        inputs.update(prompt=prompt, duration=job["seconds"], resolution="768p横", seed=202611132300 + index)
        cfg = dict(workflow_id="minimax_h3_zm_u30", materials_manifest=str(MANIFEST), shot_id=job["id"], inputs=inputs, output_dir=str(P / "04-输出/原始片段/后续完整剧情23" / job["id"]), timeout=3600, poll_interval=15)
        cfgfile = C / (job["id"] + "-u30-执行01.yaml")
        cfgfile.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")
        (C / (job["id"] + "-视频英文正文01.txt")).write_text(prompt, encoding="utf-8")
        shots[job["id"]] = dict(speakers=job["speakers"], voice_bindings={"ref_audio_0": "CHAR-GIRL"} if job["speakers"] else {}, required_assets=ids + audio_ids, reference_bindings=bindings, purpose=job["title"], authorization_ref=AUTH)
        jobs.append({**job, "prompt": prompt, "config": cfgfile.relative_to(P).as_posix(), "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "reference_bindings": bindings, "planned_video_seconds": job.get("edit_seconds", job["seconds"])})
    manifest = dict(schema_version=2, voice_policy=dict(version=1, project="project.yaml"), creative_confirmation=dict(state="confirmed", script_sha256=digest(P / SCRIPT), confirmation_ref=AUTH), documents=dict(script=SCRIPT, style=project["documents"]["style"]), assets=assets, shots=shots)
    MANIFEST.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    package = dict(script=SCRIPT, script_sha256=digest(P / SCRIPT), authorization=AUTH, base_delivery=str(base), base_sha256=digest(base), style=project["documents"]["style"], style_sha256=digest(P / project["documents"]["style"]), workflow="minimax_h3_zm_u30", image_specs=images, jobs=jobs, raw_generation_seconds=sum(j["seconds"] for j in jobs), planned_continuation_video_seconds=sum(j["planned_video_seconds"] for j in jobs), no_paid_rerolls=True, no_whitebox=True, no_retiming=True, final_size=[1344, 756], final_fps=60, existing60fps_prefix_reuse=True, music_plan="No music throughout: dialogue/continuous acted vocalizations carry comedy, loss and relief; valley epilogue uses prior audio tail.", stage="actual_inputs_pending_review" if finalize else "prompt_and_material_plan_pending_review")
    (C / "提示词与素材制作包01.json").write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"jobs": len(jobs), "images_to_make": len(images), "raw_seconds": package["raw_generation_seconds"], "edited_seconds": package["planned_continuation_video_seconds"], "finalize": finalize}, ensure_ascii=False))


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--finalize", action="store_true")
    prepare(a.parse_args().finalize)
