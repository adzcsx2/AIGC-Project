"""Prepare the user's fully restyled opening; never submits generation jobs."""
from pathlib import Path
import argparse
import copy
import hashlib
import json

import yaml

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'projects/悬崖上的小气球'
C=P/'03-制作/生成配置/前四十秒电影重制24'
A=P/'02-素材/镜头/前四十秒电影重制24'
G=P/'03-制作/静态构图/前四十秒电影重制24'
MANIFEST=P/'素材清单-前四十秒电影重制24.yaml'
SCRIPT='01-文档/需求与剧本/前四十秒电影重制24-同故事新风格01.md'
AUTH='06-记录/用户确认/前四十秒电影重制24-整段重制授权01.json'
CLAYS=dict(RUN='小龙四足起跑-二十厘米与果高校准04',LOW='小龙低伏-十厘米姿态04',
           BURY='小龙落草-埋头位置与物理支撑03',TURN='小龙转向后-朝右四足二十厘米04',
           SIT='小龙朝右-低坐与四足尺度03',MIA='女孩侧躺-原支撑肘与活动空间04',
           ENV='无角色-灰岩草地两屋巨树构图03')


def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()


def style():
    # Re-read the selected source for every independently compiled request.
    project=yaml.safe_load((P/'project.yaml').read_text(encoding='utf-8'))
    f=P/project['documents']['style']
    text=f.read_text(encoding='utf-8')
    (ROOT/'docs/视觉规范/中世纪写实风格规范.md').read_text(encoding='utf-8')
    core=text.split('## 当前英文风格核心（逐请求使用）',1)[1].split('```text',1)[1].split('```',1)[0].strip()
    return core,project['documents']['style'],sha(f)


WORLD=('Landmarks may lie OUTSIDE a particular view; do not force them into frame or relocate them. The same inland meadow at Windchime Cliff: TWO modest timber-and-aged-plaster cottages behind the left part of the clearing, '
       'one mature tree behind the right side, an irregular curved dirt path, wooded slopes and gray limestone rim outside the inland lane. '
       'Filtered daylight from upper left, restrained natural green/earth/gray, gently consistent breeze. The lane runs LATERALLY parallel '
       'to the rim, safely inland, not toward a drop or the lens. A small berry sapling is LEFT of the lane, its branch extends RIGHT. '
       'ONE target red berry stays attached at42cm center height,3cm diameter, bottom40.5cm. The run ends under that berry; a dark wet turf '
       'patch is just LEFT of it and the soft grass landing tuft is farther LEFT but still RIGHT of the sapling trunk. Keep the same '
       'tuft, exposed mud, geography, light and dirt continuity across angle changes. No duplicated houses, moving terrain, extra fruit or props.')
GULU=('GULU is the ONE original pink juvenile dragon from the identity board: original gray-blue eyes, short muzzle, two original horns, '
      'four short legs/paws, two original membrane wings and one tail. Standing on FOUR paws, ground to highest horn is20cm INCLUDING '
      'head/horns, EXCLUDING tail and wings; low posture about10cm. A SMALL kitten-sized living animal, not an adult or a toy. '
      'Preserve head/torso/limb dimensions through rising, running, turning, wing movement and landing. Posture, altitude and wing span '
      'are separate. The board supplies identity/anatomy only, never its large display framing or upright pose. Match the measured '
      'small-in-environment scene reference: standing horn-to-ground about7.8% of frame height at this SIDE camera, low pose about4.1%; '
      'tail increases width, not body height. Maintain SIDEWAYS travel at constant depth/distance; no frontal approach, push-in or zoom '
      'during an action that makes the body grow. Render fine irregular biological scales and supple skin integrated with the real location.')
MIA=('MIA is the SAME youthful girl from her board, standing identity height130cm crown-to-sole, original braid, gray-blue wool cloak, '
     'linen shirt, trousers, worn leather boots and shoulder strap. Preserve face/age and clothing. She stays LOW SIDE-RECLINING on '
     'the inland grass: original near-side support elbow/forearm bears weight, its hand may prop the cheek; the OTHER hand is free. '
     'Keep these arm roles through gestures and her brief half-roll. Natural skin texture, no beauty retouching, adult makeup or doll skin. '
     'Eyes track OFFSCREEN LEFT/LOWER LEFT toward her companion. No sitting up or standing, no motionless pasted actor.')
SINGLE=('Each shot contains ONLY its explicitly named character, or no character. NEVER show both together, companion fragments, '
        'over-shoulder bodies, reflections or recognizable companion shadows. Multi-view boards are ONE identity, not multiple actors. '
        'Use clean motivated HARD CUTS at the stated events; every subject/light/ground interaction is one integrated scene. '
        'Pictures are soft identity/composition references, not guaranteed first/last frames or a demand to interpolate slowly between stills.')
MOTION=('Native brisk NORMAL physical timing: prompt preparation and launch, effective travel, brief airborne arc, immediate descent, '
        'visible contact and timely recovery. No slow motion, speed ramps, freezes, apex holds, stretched preparation/recovery or '
        'post-production speed-up. Paw/palm/elbow/shoulder loads compress grass at the real contact; blades partly recover after unloading. '
        'A skid disturbs the wet turf, a shoulder roll bends the landing tuft, rear landing depresses soft mud and leaves small mud marks. '
        'Rigid earth, houses, tree and rock cannot warp around a moving character. Do not hide key missed bite, support transfer or '
        'landing contact with a cut, fog or glare.')
VOICE=('Audio1 is MIA approved voice ID, not sample words or a slow reading tempo. Audio2, when present, is the SAME MIA on-film '
       'English vocal timbre; Audio3, when present, is her continuous natural giggle/breath reference, not syllables to recite. '
       'Keep ONE sweet youthful girl voice across speech, laughter and breaths. Natural unmetered acted laughter, never spoken '
       '"ha ha ha", choppy repeated syllables, an adult/monster voice or extra sighs. Only MIA says the exact quoted ENGLISH lines '
       'once each; GULU never speaks human words or lip-syncs her OFFSCREEN voice. No Mandarin, narration, added words, BGM, songs, '
       'humming, musical stings or environmental/impact SFX. Do not mute required speech to remove music.')

IMAGE_SPECS=[
 dict(id='RUN',name='小龙二十厘米与高浆果-电影实拍起跑参考01.png',refs=['CLAY-RUN','CHAR-DRAGON-THREEVIEW','SCENE-OLD','FILM-USER02'],body=(
  'Image1 is the ACTUAL Blender perspective composition and20cm geometry; Image2 supplies GULU identity only; Image3 supplies this meadow/cottages/tree appearance; '
  'Ignore Image3 foreground sapling/fruits and framing; the SINGLE berry/ground geometry comes ONLY from Image1. Image4 is cinematic PHOTOGRAPHIC treatment only, NOT its adult dragon, boat, anatomy, size, darkness, cast or UI. Re-photograph Image1 as a believable '
  'real exterior film plate, keeping its camera, horizon, grounded paw positions and small full-body silhouette. ONLY one GULU faces SCREEN LEFT at the '
  'right side of the lane, on FOUR planted paws with original wings folded, focused hungry eyes and closed mouth, before retreat/run. Standing feet-to-highest-horn '
  'is20cm. Its horn-to-ground span is about7.8% of image height, about73pixels on a941pixel-high output; keep it within roughly8-9%, not a foreground giant. '
  'In Image1 body excluding tail lies around61-67% across; full tail extends farther RIGHT. Keep all feet/tail visible with ample LEFTWARD approach, bite and '
  'roll space. Preserve the SINGLE berry at the exact branch endpoint and image height from Image1: center42cm above the same ground, bottom40.5cm, '
  'well above even a short jump mouth apex. Turn the gray sapling/branch into a sparse real shrub; the gray landing block becomes a soft grass tuft, the '
  'flat skid marker becomes a patch of wet turf, not boxes/props. Gray far blocks become only the two cottages, gray tree stand-in becomes the mature tree. '
  'Restore natural grass3-5cm tall, so it reaches this small animal ankles/lower legs at the SAME depth. Real tiny foot contact shadows and bent grass. '
  'No girl, duplicate creature, ruler, UI, text, cartoon, scaled-up head or stock dragon portrait. Do not copy the clay material or the board framing.')),
 dict(id='LOW',name='小龙低伏十厘米-同机位电影实拍参考01.png',refs=['CLAY-LOW','RUN','CHAR-DRAGON-THREEVIEW','FILM-USER02'],body=(
  'Image1 fixes this LOW pose and its slightly HIGHER SIDE camera/location; Image2 is the validated same-world small-scale photographic treatment/identity, NOT its lower camera. '
  'Image3 is identity/anatomy only, Image4 photographic treatment only. Create one coherent film shot reprojecting Image2 world/light/material through Image1 HIGHER SIDE camera, moving '
  'the ONE dragon only into the low posture and position of Image1. He rests about10cm ground-to-highest head/horn through joint folding, SAME skull, '
  'torso and limb volume as the20cm four-paw stance, not a uniformly shrunken animal. Match Image1 projected low body height about4.1%H. Original folded '
  'wings, full tail and planted paws; relaxed sleepy face, head sideways LEFT, not a human smile. Same single high berry, wet turf and landing tuft. '
  'Keep Image1 higher camera and fixed subject depth, never enlarge him, reproduce the gray blocks, add another actor or copy the giant adult in Image4.')),
 dict(id='BURY',name='小龙落草埋头-同场落点电影实拍参考01.png',refs=['CLAY-BURY','RUN','CHAR-DRAGON-THREEVIEW','FILM-USER02'],body=(
  'Image1 fixes the SAME camera and LEFT landing position after the missed bite; Image2 supplies the real meadow/scale/light/dragon identity, '
  'Image3 is anatomy only, Image4 photographic treatment only. ONE GULU after a gentle comic tumble into SOFT grass: snout and forechest partly '
  'hidden in the tuft at Image1 position, forepaws braced on earth, rear supported, full tail tilted up. The grass bends around actual contact; '
  'no head embedded in solid rock/earth. Same small physical torso/head/limbs as Image2, projected pose follows Image1, not the old starting '
  'position. The tuft is LEFT of the still-attached berry and RIGHT of the shrub trunk. Single berry has NOT descended or been eaten. Newly '
  'disturbed grass at skid/shoulder route, a few grass flecks on nose; no injury, pain gag or second dragon. Keep the photographic background '
  'rigid and unwarped, no girl, gray blocks, adult body, labels or UI.')),
 dict(id='TURN',name='小龙拔头转右-二十厘米同落点参考01.png',refs=['CLAY-TURN','RUN','CHAR-DRAGON-THREEVIEW','FILM-USER02'],body=(
  'Image1 fixes the SAME scene camera, grounded location and FOUR-paw posture now facing SCREEN RIGHT; Image2 supplies actual photographic '
  'environment/scale, Image3 identity only, Image4 photographic treatment only. ONE GULU has already pulled his head out of the SAME soft tuft '
  'and turned in place at that landing spot, not walked closer to the lens. Actual natural ground-to-highest-horn20cm; body/head dimensions '
  'are identical to Image2 although the animal now faces RIGHT and is at Image1 landing position. Nose still has a few grass flecks, slight '
  'mud on hind paws, original wings folded. A hurt puzzled glance with mouth closed and corners level, not a grin. Full paws and tail visible; '
  'grass carries the previous pressed tuft/skid. Berry remains untouched at its locked high branch. No girl/duplicate, bipedal sit, giant '
  'foreground body, changed lens, gray geometry, labels, ruler or UI.')),
 dict(id='SIT',name='小龙再次失败低坐-泥草与体型参考01.png',refs=['CLAY-SIT','RUN','CHAR-DRAGON-THREEVIEW','FILM-USER02'],body=(
  'Image1 fixes the SAME camera and landing spot, rear lowered with front paws supporting, head SIDE-ON facing RIGHT. Image2 supplies '
  'photographic scene and physical dragon dimensions; Image3 identity only, Image4 photographic treatment only. Create ONE original small '
  'GULU with unchanged skull/torso/limb size, four-paw anatomy; hindquarters settled into the wet mud beside the same tuft, both forepaws '
  'supporting on ground. No upright human-like stance. Original folded wings, visible tail, disappointed tight jaw/pressed upper eyelids, '
  'not a smiling toy. Keep nose grass from the first fall and NEW small mud specks on rear/belly from this rear landing, localized pressed '
  'mud/grass and real contact shadows. Berry still hangs untouched. No girl, extra creature, gray blocks, camera/depth change, adult or UI.')),
 dict(id='MIA',name='米娅侧躺与支撑手-电影实拍参考01.png',refs=['CLAY-MIA','CHAR-GIRL-THREEVIEW','RUN','SCENE-OLD','FILM-USER02'],body=(
  'Image1 fixes MIA supported low SIDE-RECLINING body pose, camera and roomy full-body framing; Image2 identifies her original face/age/outfit. '
  'Image3 supplies the same meadow photographic treatment/location/light ONLY, NEVER copy its dragon into this shot; Image4 fixes the same '
  'two cottages/tree geography; Ignore Image4 foreground sapling/fruits and framing. Image5 is film photographic material/exposure ONLY, never its adult dragon/boat/cast/UI. ONLY the fully '
  'dressed original girl, head LEFT and boots RIGHT on the inland grass, complete body around53% of picture width as in Image1 with room '
  'for a short half-roll. Original near-side elbow is firmly grounded and that forearm/hand props her cheek; OTHER arm rests freely with '
  'palm on grass. Two normal distinct arms attached correctly; preserve support roles and real grass compression, cloak weight. Standing '
  'identity130cm, original child proportions, braid, gray-blue wool cloak, linen and leather, not a taller teen or a doll. Calm eyes '
  'half-closed in daylight, relaxed small smile, no forced laugh yet. Skin unretouched with natural uneven texture and shaped shadows, '
  'not beauty-portrait polish. No dragon, companion fragment/shadow, gray mannequin, image collage, text, ruler, UI or black bars.')),
 dict(id='ENV',name='风铃崖内退草地-电影实拍空景参考01.png',refs=['CLAY-ENV','RUN','SCENE-OLD','FILM-USER02'],body=(
  'Image1 defines an EMPTY real-camera view of the same space: two cottages LEFT/behind, mature tree RIGHT, inland meadow/curving path '
  'and gray limestone rim, valley outside. Image2 supplies the actual photographic material/light of this SAME location ONLY; REMOVE '
  'its dragon completely. Image3 supplies the original connected world, Image4 is film photographic treatment only, never its adult '
  'dragon/ship/cast/war/UI. Re-photograph the gray geometric space as a credible real location, natural uneven grass/earth, weathered '
  'timber/lime plaster, organic tree foliage, believable irregular limestone strata and atmospheric wooded slopes. Preserve camera '
  'and landmark geography, not the box/cylinder shapes as finished architecture. Filtered daylight and shaped shade, readable distance '
  'without oversharpening, no idealized game landscape or yellow-green glow. NO characters, creatures, silhouettes, companion shadows, '
  'additional cottages/props, storm, text, logos, UI, black bars or slow-zoom suggestion.')),
]

JOBS=[
 dict(id='R24-01',seconds=10,refs=['CHAR-DRAGON-THREEVIEW','CHAR-GIRL-THREEVIEW','ENV','MIA','LOW','RUN'],audio=False,speakers=[],title='晒太阳与发现高浆果',action=(
  'Images1/2 identify GULU/MIA respectively; image3=empty location, image4=MIA actual reclining pose, image5=LOW10cm pose, image6=20cm stance/locked berry geometry only. '
  '0-2s EMPTY fixed establishing landscape, same two cottages LEFT and mature tree RIGHT, inland lane and rim; leaves/grass gently move, no sound. '
  '2-5s hard CUT to ONLY MIA on grass in the reference low SIDE recline. Eyes briefly closed, a relaxed smile, then open to OFFSCREEN LEFT. '
  'Free hand promptly sweeps one loose strand aside in0.3-0.5s and returns; support elbow stays planted. Natural expression/blinks, no frozen body, audible sigh or standing. '
  '5-7s CUT to ONLY GULU in the slightly HIGHER SIDE environmental view of image5, matching the10cm LOW reference, body horizontal facing LEFT. One sleepy blink, '
  'nostrils twitch, then eyes/head promptly track OFFSCREEN UPPER LEFT as he notices the berry. Original wings folded, fixed juvenile body size. '
  '7-8s CUT to a closer insert of the SINGLE berry/branch, no actor; it remains ATTACHED at42cm above the lane, only slight natural breeze movement, '
  'never rises away from a bite or drops to mouth height.8-10s CUT back to ONLY the SAME low GULU at this HIGHER SIDE camera/distance; the NEXT unit visibly cuts to the LOWER SIDE full-body run camera, awake hungry eye focus, '
  'ONE quick lip lick in0.2-0.3s, mouth closes, compact head intent toward that berry, no long tongue display or stand yet. Silent entire unit.')),
 dict(id='R24-02',seconds=9,refs=['CHAR-DRAGON-THREEVIEW','CHAR-GIRL-THREEVIEW','RUN','BURY','MIA','LOW','ENV'],audio=True,laugh=True,speakers=[],title='跑到果下没够到滑滚落草',action=(
  'Images1/2=GULU/MIA; image3=standing approach/locked high berry, image4=eventual SAME tuft landing, image5=MIA recline/support, image6=initial low10cm pose, image7=world. '
  '0-2s ONLY GULU in fixed SIDE FULL-BODY meadow view:0-.35s paws load and joints promptly extend from low10cm to natural FOUR-paw20cm stance; '
  '.35-1.25s THREE quick small backward steps to the RIGHT;1.25-1.65s ONE hind-paw scrape disturbs a little soil/grass; by2s first forward stride is ALREADY launching. '
  '2-5.5s keep ONE UNBROKEN readable SIDE WIDE shot with whole animal, the HIGH target berry, wet turf and tuft in frame. '
  '2-3s sprint LEFT laterally about0.8m into the space DIRECTLY UNDER the berry, compact fast paw strides on the SAME depth plane, not in-place jumping or a lens approach. '
  '3-3.15s hind legs visibly compress then extend UP against the earth;3.15-3.45s all FOUR feet lift in a clearly UPWARD short arc, never a belly-first forward pounce, mouth stays AT LEAST a clear visible gap BELOW the berry at the apex. '
  'Standing mouth upper edge is roughly15cm, short jump translates body roughly11cm, so mouth reaches only about26cm versus berry bottom40.5cm. '
  'Berry remains attached at the ORIGINAL height throughout, never touched, bitten, lowered or suddenly lifted. No stretching neck, inflated belly or body growth. '
  '3.45-3.7s front paws meet grass then rear paw slips on the wet patch;3.7-4.3s shoulder contacts soft grass, wings fold clear and one short roll carries '
  'snout/forechest into the tuft LEFT of berry and RIGHT of shrub trunk. Visible pressed grass, disturbed turf and nose grass flecks. '
  '4.3-5.5s tail gives a quick unhappy flick, forepaws brace, natural short wriggle, not a stretched airborne fall. '
  '5.5-7s hard CUT to ONLY MIA, still side-reclining: eyes briefly widen, relief at the harmless soft-grass tumble, pressed lips open into ONE spontaneous '
  'suppressed giggle with a continuous real breath in her SAME voice, free hand heads toward belly, support elbow stays down. No words or random sigh. '
  '7-9s CUT to ONLY GULU at the SAME tuft/image4: promptly brace paws and pull snout OUT in0.3-0.5s, displaced blades spring and fall, grass flecks stay on nose. '
  'Begin a quick in-place FOUR-paw pivot toward SCREEN RIGHT/offscreen MIA, completed naturally during the following MIA shot; no renewed jump or forward-depth movement. '
  'MIA giggle may continue OFFSCREEN once without restarting; GULU does not mimic it.')),
 dict(id='R24-03',seconds=10,refs=['CHAR-DRAGON-THREEVIEW','CHAR-GIRL-THREEVIEW','MIA','TURN','RUN','ENV'],audio=True,laugh=True,speakers=['CHAR-GIRL'],title='自然笑声与第一次调侃',action=(
  'Images1/2=GULU/MIA; image3=MIA full supported reclining body/rolling room; image4=GULU ALREADY out of tuft, turned RIGHT on FOUR paws at same landing spot; image5=scale/berry only; image6=world. '
  '0-2s ONLY MIA, wider medium/full low reclining view. Her real laugh releases: free hand holds belly; cheek hand leaves cheek, original support elbow '
  'lowers so shoulder/back make ONE brief half-roll on grass in0.4-0.6s, cloak presses/drags blades, then SAME forearm promptly bears weight again in0.4-0.6s. '
  'Return to original LOW side recline; belly hand never also serves as support, no sitting/standing. Continuous natural laughter eases into speech-ready breath. '
  '2-7.1s visible CUT to ONLY MIA medium view, same support and location. She says exactly ONCE in ENGLISH: '
  '"Gulu, you flew so high—about as high as a grasshopper!" Playful warmth, lively eyes and one brief free-hand point toward OFFSCREEN LOWER LEFT, '
  'then hand returns to grass. Conversational cadence with natural breath, no word stretching or chant.7.1-7.45s natural short speech breath; at7.45s BEGIN the following second sentence while MIA remains on screen, then carry the SAME utterance across the8s cut. '
  '8-10s CUT to ONLY GULU SIDE-on in the unchanged small-scale environment, matching image4 RIGHT-facing four-paw stance, nose grass still present. '
  'MIA CONTINUES the SAME already-started utterance OFFSCREEN in her SAME voice, complete by9.95s: "Are those wings, or little fans?" Say this whole second sentence ONCE, not again after the cut. '
  'GULU hears: puzzled eye lift gives way to pressed upper lids, lower jaw tightens, mouth corners stay level/down, wing roots tense. '
  'He is genuinely hurt/annoyed, not smiling, tongue-out or friendly. Feet stay at tuft, not repeat pulling head out, not turn toward lens or grow.')),
 dict(id='R24-04',seconds=11,refs=['CHAR-DRAGON-THREEVIEW','CHAR-GIRL-THREEVIEW','TURN','SIT','MIA','RUN','ENV'],audio=True,laugh=True,speakers=[],title='恼怒试飞失败与期待落空',action=(
  'Images1/2=GULU/MIA; image3=initial RIGHT-facing FOUR-paw20cm stance with nose grass; image4=ONLY eventual rear-low supported muddy result, not initial pose; image5=MIA recline; image6=geometry/size; image7=world. '
  '0-.6s ONLY MIA in the same supported recline, a brief closed-mouth playful glance toward OFFSCREEN LOWER LEFT after her completed joke; no new words or gasp. At.6s hard CUT to ONLY GULU at the same tuft, fixed SIDE environmental full-body view through2s. His listening hurt becomes visible annoyed pride: upper lids press, jaw clenches, '
  'nostrils briefly flare, two thin short gray wisps and a FEW dim sparks escape nostrils, wing roots tense. No smile, human grin, huge fire, recolor or new speech. '
  '2-2.6s one short forceful inhale with ONLY limited rib/abdomen movement, no balloon inflation or buoyancy.2.6-3.3s paws brace, joints compress and '
  'wing roots load;3.3-4s the first compact quick downbeats are already beginning, not a frozen held setup. '
  '4-6.5s keep the COMPLETE action in ONE fixed SIDE full-body shot:4-4.35s continue those downbeats and short hind-paw push;4.35-4.6s '
  'feet briefly clear ground about5cm, apex immediately passes, no hover. His chin flashes proud for a moment; exhale breaks wing coordination. '
  '4.6-4.9s hindquarters promptly meet the soft mud beside the same tuft, front paws take weight;4.9-5.4s normal short recoil, local mud/grass '
  'depression and a few mud specks on rear/belly, folded wings recover. Through6.5s stay naturally alive in the rear-low/front-paw-supported result, '
  'a quick unhappy breath and look at the landing, no continued slow descent, bipedal rise or growth. '
  '6.5-8s hard CUT to ONLY MIA, still original low recline. Brief raised brow of hope collapses into a spontaneous natural giggle; free hand covers '
  'mouth but laugh escapes, shoulders move with breath, original forearm stays loaded. SAME youthful timbre, no words, no theatrical ha-ha syllables. '
  '8-11s CUT to ONLY GULU at SAME RIGHT-facing rear-low supported muddy state. Her SAME laugh CONTINUES OFFSCREEN without restart. '
  'He briefly lifts chin hoping for praise; as laughter continues the hope fades, eyelids sink, jaw tightens and front claws load grass/mud. '
  'Finish during a short head turn RIGHT/DOWN, still low with forepaws planted, not a freeze, smile, frontal approach or new cliff run. '
  'Do not say the later fat-lizard insult yet; it belongs to the continuation.')),
]


# Correct the remaining depth placement as a still-image edit, not a video path.
IMAGE_SPECS[0] = dict(id='RUN',name='小龙二十厘米与高浆果-电影实拍起跑参考04.png',refs=['RUN-CANDIDATE03','CLAY-RUN'],body=(
 'EDIT Image1. Change ONLY the initial placement/scale of its ONE small dragon. The animal is currently too NEAR the viewer, its feet at67 percent down the picture. '
 'RELOCATE it FARTHER AWAY on the meadow to the midground proxy ground point shown in Image2: paws at58.3 percent from TOP and about64 percent from LEFT. '
 'This is a different patch of real grass behind its present position, not lifting it into air. Remove the old foreground animal and restore that grass/shadow naturally. '
 'Perspective makes the relocated animal uniformly about80 percent of its current height and width: new ground-to-highest-horn image span about7.8 percent, '
 'around73pixels on941pixels height. Keep original20cm four-paw physical size, same head/horns/body/legs/folded wings/tail proportions, same face, colors and live biological materials. '
 'Keep the complete camera view, two cottages, large tree, sky, grass, sapling, SINGLE high attached fruit, branch, wet patch and tuft UNCHANGED from Image1. '
 'The fruit is already corrected near43 percent from TOP; do NOT move or duplicate it. Preserve ample leftward lane, contact shadow and grass support at the NEW midground paws. '
 'Do not leave a duplicate, floating beast, pasted sticker, changed camera, zoom, crop, UI or gray object. Image2 is ONLY metric pose/placement reference. '
 'Return the same integrated film-location photograph with one tiny original juvenile in the correct midground position; no added person or adult dragon.'))


# Reconciled design camera keeps20cm anatomy; photo04 is a photography candidate,
# not a measurement of physical size. One lane-patch edit precedes pose derivation.
CLAYS={k:v[:-2]+'05' for k,v in CLAYS.items()}
IMAGE_SPECS[0]=dict(id='RUN',name='小龙二十厘米与高浆果-电影实拍起跑参考05.png',refs=['RUN-CANDIDATE04','CLAY-RUN'],body=(
 'EDIT Image1. Keep its ONE small original pink juvenile dragon EXACTLY the same size, anatomy, LEFT-facing FOUR-paw pose and midground position. '
 'Keep its camera, light, colors, sky, two cottages, tree, sapling, branch and SINGLE high attached berry unchanged. Image2 is the recalibrated '
 '20cm design-camera geometry, not an instruction to repaint its gray material. Change ONLY the two GRASS/TURF contact patches to match Image2: '
 'restore the old tall foreground tuft and old large foreground wet mark into ordinary grass; make ONE SMALL soft grass landing tuft centered '
 'around36 percent from LEFT, with its ground base about62.6 percent from TOP, about5 percent of image WIDTH and3 percent HEIGHT. '
 'Make ONE compact dark wet-turf skid patch around43 percent from LEFT on the SAME ground row62.6 percent from TOP, flat and subtle, not a pond. '
 'These two small patches are on the same sideways running lane/depth as the small dragon, not closer to the lens. Tuft is LEFT of berry and RIGHT '
 'of shrub trunk. Preserve ample lateral run/short upward-hop/roll room. No animal resize or relocation, extra fruit, added person, gray block, '
 'labels, ruler, UI, black bars, sticker or game-render finish. Return a single integrated live-action fantasy location photograph.'))
# Same-camera pose edits use the verified photographic mother as the first input.
IMAGE_SPECS[2]=dict(id='BURY',name='小龙落草埋头-同场落点电影实拍参考01.png',refs=['RUN','CLAY-BURY','CHAR-DRAGON-THREEVIEW'],body=(
 'EDIT Image1, preserving its exact photographic background, camera, light, fixed high berry and ground. Image2 gives ONLY the pose and new '
 'landing position of the same ONE dragon; Image3 identity only, not framing. Move the original small animal LEFT along the SAME ground/depth '
 'row into the small soft tuft at Image2 position, snout/forechest partly hidden in soft grass, forepaws truly braced, rear supported, tail tilted up. '
 'Remove/restore the old right-side animal position, no duplicate. Keep skull/torso/limbs the SAME physical dimensions as Image1, not a bigger body. '
 'Bend contacted grass, retain disturbed wet turf, put a few grass flecks on snout; never embed head in solid earth. No camera move or foreground '
 'approach. It is the tuft on the running row, NOT a tall foreground clump. Only this one original pink juvenile, no girl/injury/adult/UI/gray object.'))
IMAGE_SPECS[3]=dict(id='TURN',name='小龙拔头转右-二十厘米同落点参考01.png',refs=['BURY','CLAY-TURN','CHAR-DRAGON-THREEVIEW','RUN'],body=(
 'EDIT Image1 at the EXACT same left landing spot/camera/background. Image2 provides the current joint pose/projection; Image3 identity only; '
 'Image4 is the SAME animal original20cm full-four-paw size, not its old location. The ONE small GULU has already pulled his head OUT of the '
 'same tuft and completed an in-place pivot to face SCREEN RIGHT on FOUR paws. Preserve the same skull/torso/limb dimensions, original horns, '
 'two folded wings and tail; a head reveal/pose change is not growth. Keep the actor feet on the SAME running ground row and pressed tuft/mud '
 'state, nose grass flecks and slight hind-paw dirt. Mouth closed, hurt puzzled eyes, level/down mouth corners, not a grin. Clear real foot support '
 'and full tail, no camera/depth change, duplicated animal, foreground walk, upright human stance, girl, gray block or UI.'))
IMAGE_SPECS[4]=dict(id='SIT',name='小龙再次失败低坐-泥草与体型参考01.png',refs=['TURN','CLAY-SIT','CHAR-DRAGON-THREEVIEW'],body=(
 'EDIT Image1, keep its camera/background/LEFT landing spot, fixed high berry and same ONE pink juvenile dragon size. Image2 supplies only '
 'the rear-low/front-paw-supported result pose; Image3 identity only. Lower hindquarters into the soft wet mud beside the SAME tuft, both forepaws '
 'firmly supporting on ground; no bipedal sitting, no torso/skull/limb enlargement. Preserve nose grass, ADD only a few localized NEW mud specks '
 'on rear/belly and visibly pressed wet grass/mud under contact. Fold original wings, full tail visible. Disappointed pressed upper lids and tight '
 'jaw, no smiling toy. Same lateral ground row/depth, not foreground. No extra actor, camera move/zoom, changed landscape, gray proxy or UI.'))
IMAGE_SPECS[2]=dict(id='BURY',name='小龙落草埋头-同场落点电影实拍参考02.png',refs=['BURY-CANDIDATE01','RUN','CLAY-BURY'],body=(
 'EDIT Image1 only. Its dragon is TOO LARGE and TOO FAR FORWARD; correct that error while preserving the entire photographic background, high fruit, light and camera. '
 'Image2 shows the SAME animal at the correct SMALL physical size; Image3 is its exact landing pose/placement design. Reduce the ENTIRE Image1 animal including head, torso, legs, wings and tail uniformly to about45 percent of its current width/height. '
 'Move this small crouched animal onto the SAME ground row as Image2 paws, about62.6 percent from TOP, centered around36.5 percent from LEFT. The COMPLETE animal including tail must fit inside approximately9 percent of image WIDTH and8 percent HEIGHT; the crouched main body without tail has only about5 percent image HEIGHT. '
 'Restore the vacated foreground grass and shadows naturally, no duplicate. Head is down LEFT with snout/forechest hidden in one SMALL soft grass tuft; forepaws and rear truly supported, tail tilted up. Keep the original juvenile20cm four-paw physical dimensions, not an adult. '
 'Keep original photographic material/identity from Images1/2, not gray Image3 geometry. No zoom, crop, new scenery, front approach, large grass clump, girl, labels, ruler or UI.'))
IMAGE_SPECS[1]['body'] += (' The complete low animal INCLUDING tail stays within roughly9 percent image WIDTH, about150pixels at1670px width. Its head/horn top-to-ground is only37pixels at941px image height; never substitute a large close-up. The unchanged empty landscape occupies almost the whole picture.')
IMAGE_SPECS[3]['body'] += (' Keep the complete animal including tail inside roughly9 percent image WIDTH and the horn-to-ground height about7.4 percent image HEIGHT, about70pixels at941px height. Its paws remain at62.6 percent from TOP. All scenery stays exactly unchanged.')
IMAGE_SPECS[4]['body'] += (' Keep the complete animal including tail inside roughly9 percent image WIDTH, horn-to-ground height about7.4 percent HEIGHT, about70pixels at941px height. Paws stay at62.6 percent from TOP. Do not make a foreground close-up.')
for _s in IMAGE_SPECS:
    _s['body']=_s['body'].replace('42cm','52.1cm').replace('40.5cm','50.6cm').replace('7.8%','7.4%').replace('4.1%','3.9%')
WORLD=WORLD.replace('42cm','52.1cm').replace('40.5cm','50.6cm')
GULU=GULU.replace('7.8%','7.4%').replace('4.1%','3.9%')
for _j in JOBS:
    _j['action']=_j['action'].replace('42cm','52.1cm').replace('40.5cm','50.6cm')


# Returned extra pose plates failed scale; do not bind them to video.
# One approved small-scale master plus the girl's supported pose and its clean
# environment plate carry the photographic inputs. Static pose studies remain
# engineering evidence only. Story, duration, language and actor identities stay.
IMAGE_SPECS=[s for s in IMAGE_SPECS if s['id'] in ('RUN','MIA','ENV')]
IMAGE_SPECS[-1]=dict(id='ENV',name='风铃崖内退草地-电影实拍空景参考02.png',refs=['RUN'],body=(
 'EDIT this photograph into a clean EMPTY location plate. Remove ONLY the ONE tiny pink dragon at about63 percent from LEFT and60 percent from TOP, '
 'including its little shadow, and restore ordinary matching grass underneath. Keep the entire camera view, horizon, trees, TWO cottages, sapling, SINGLE high attached berry, '
 'small wet turf patch, small landing tuft, path, light, colors and photographic texture EXACTLY unchanged. No replacement animal, girl, silhouette, shadow or new object. '
 'This is the same real-location film plate with absolutely NO people or creatures. No camera change, crop, enlargement, label or gray geometry.'))
_mapping='Images1/2 identify the original GULU/MIA respectively. Image3 is the ONLY small-scale photographic dragon/world master, four-paw height20cm and single fixed high berry; use its camera/body scale, NOT its initial pose in later actions. Image4 supplies ONLY MIA supported reclining pose and identity; do not copy her into dragon shots. Image5 is the same EMPTY environment. Each shot shows at most ONE main actor. '
for _j in JOBS:
    _j['refs']=['CHAR-DRAGON-THREEVIEW','CHAR-GIRL-THREEVIEW','RUN','MIA','ENV']
    _j['action']=_mapping+_j['action'][_j['action'].index('0-'):] if _j['id']!='R24-04' else _mapping+_j['action'][_j['action'].index('0-.6s'):]
    _j['action']=_j['action'].replace('slightly HIGHER SIDE environmental view of image5, matching the10cm LOW reference','fixed SIDE environmental camera of image3, joints folded to10cm low posture').replace('this HIGHER SIDE camera/distance; the NEXT unit visibly cuts to the LOWER SIDE full-body run camera','this SAME SIDE camera/distance; the next unit continues the action at this scale')
    _j['action']=_j['action'].replace('at the SAME tuft/image4','at the SAME small tuft in image3').replace('matching image4 RIGHT-facing four-paw stance','at the SAME image3 landing tuft but now facing RIGHT on four paws')
    _j['action']=_j['action'].replace('inland lane and rim;','inland lane; the limestone rim remains outside this inland view;')
    if _j['id']=='R24-01':
        _j['action']=_j['action'].replace('body horizontal facing LEFT.','body horizontal facing LEFT, about18cm LEFT of the standing animal location in image3 on the SAME depth row.')
    if _j['id']=='R24-02':
        _j['action']=_j['action'].replace('0-.35s paws load','start about18cm LEFT of the image3 standing animal position on the SAME ground row;0-.35s paws load').replace('THREE quick small backward steps to the RIGHT;','THREE quick small backward steps totaling18cm to the RIGHT, finishing at the image3 animal position;')
    if _j['id']=='R24-03':
        _j['action']=_j['action'].replace('8-10s CUT to ONLY GULU SIDE-on in the unchanged small-scale environment,','8-10s HARD CUT to a closer SIDE medium-full reaction of ONLY GULU at the SAME ground spot, original20cm body framed about20percent of image HEIGHT by this new camera, not body enlargement. The nearby3-5cm grass and tuft retain the SAME proportions against him. In the unchanged environment,')
    if _j['id']=='R24-04':
        _j['action']=_j['action'].replace('fixed SIDE environmental full-body view through2s.','closer SIDE medium-full reaction view through2s, original20cm body framed about20percent HEIGHT by a visible camera CUT, same grass-to-body scale.')
        _j['action']=_j['action'].replace('2-2.6s one short forceful inhale','At2s HARD CUT back to the original WIDE action camera of image3, standing body about7.4percent frame HEIGHT and same ground spot;2-2.6s one short forceful inhale')
        _j['action']=_j['action'].replace('8-11s CUT to ONLY GULU at SAME','8-11s HARD CUT to the closer SIDE medium-full reaction camera, original20cm body about20percent frame HEIGHT, same nearby3-5cm grass proportions. ONLY GULU at SAME')
GULU=GULU.replace('standing horn-to-ground about7.4% of frame height at this SIDE camera, low pose about3.9%;','standing horn-to-ground about7.4% of frame height at the WIDE SIDE action camera, low pose about3.9%; explicitly stated reaction-camera HARD CUTS may frame the same20cm body about20%H while preserving local grass/tuft-to-body proportions. Camera changes are not growth;')

def build(finalize=False):
    C.mkdir(parents=True,exist_ok=True);A.mkdir(parents=True,exist_ok=True)
    core,sty,style_sha=style()
    old=yaml.safe_load((P/'素材清单-前四十秒单主体19-执行01.yaml').read_text(encoding='utf-8'))
    assets={k:copy.deepcopy(old['assets'][k]) for k in ['CHAR-DRAGON-THREEVIEW','CHAR-GIRL-THREEVIEW','VOICE-GIRL']}
    for k,path in {
        'SCENE-OLD':'02-素材/场景/风铃崖-环境总览-候选02.png',
        'RUN-CANDIDATE01':'02-素材/镜头/前四十秒电影重制24/小龙二十厘米与高浆果-电影实拍起跑参考01.png',
        'RUN-CANDIDATE02':'02-素材/镜头/前四十秒电影重制24/小龙二十厘米与高浆果-电影实拍起跑参考02.png',
        'RUN-CANDIDATE03':'02-素材/镜头/前四十秒电影重制24/小龙二十厘米与高浆果-电影实拍起跑参考03.png',
        'RUN-CANDIDATE04':'02-素材/镜头/前四十秒电影重制24/小龙二十厘米与高浆果-电影实拍起跑参考04.png',
        'BURY-CANDIDATE01':'02-素材/镜头/前四十秒电影重制24/小龙落草埋头-同场落点电影实拍参考01.png',
        'FILM-USER02':'02-素材/风格参考/用户电影视效-背光与承重基准02.png',
        'VOICE-MATCH24':'02-素材/音频/角色声音/披风女孩米娅/后续完整剧情23/同一米娅-成片英文声音衔接参照01.wav',
        'VOICE-LAUGH24':'02-素材/音频/角色声音/披风女孩米娅/后续完整剧情23/同一米娅-连续自然轻笑与换气参照01.wav',
    }.items():
        assets[k]=dict(kind='audio' if k.startswith('VOICE') else 'scene',path=path,sha256=sha(P/path),state='ready',required=False,purpose='existing_reference_with_scoped_role')
    for key,name in CLAYS.items():
        f=G/(name+'.png')
        assets['CLAY-'+key]=dict(kind='keyframe',path=f.relative_to(P).as_posix(),sha256=sha(f),state='ready',required=False,purpose='static_geometry_for_image_conversion_only_NOT_u30_input',geometry_record=str(f.with_suffix('.json').relative_to(P)),not_video=True)
    ims=[]
    for s in IMAGE_SPECS:
        f=A/s['name'];key=s['id']
        assets[key]=dict(kind='keyframe' if key!='ENV' else 'scene',path=f.relative_to(P).as_posix(),state='ready' if finalize and f.exists() else 'planned',required=False,purpose='single_subject_photoreal_camera_and_scale_reference',user_review='authorized_derivative_assistant_checks_not_individual_user_acceptance')
        if finalize and f.exists():assets[key].update(sha256=sha(f),review_record='05-检查与验收/前四十秒电影重制24-实际返回图与比例检查03.json')
        current_core,_,_=style()
        prompt=s['body']+'\n'+WORLD+'\n'+current_core+'\nOne coherent16:9 photograph, no text, labels, board panels, UI, watermark, letterboxing or gray proxy appearance.'
        promptfile=C/(key+'-图片英文正文01.txt');promptfile.write_text(prompt,encoding='utf-8',newline='\n')
        ims.append({**s,'prompt':prompt,'prompt_sha256':sha(promptfile),'output':assets[key]['path']})
    shots={};jobs=[]
    for i,j in enumerate(JOBS):
        current_core,_,_=style()
        prompt=j['action']+'\n'+SINGLE+'\n'+GULU+'\n'+MIA+'\n'+WORLD+'\n'+MOTION+'\n'+current_core
        audio_text=VOICE
        if j['audio'] and not j['speakers']:
            audio_text=('Audio1 is the SAME MIA on-film English vocal timbre; Audio2 is her continuous spontaneous giggle/breath performance. Use only that SAME youthful voice for the scripted wordless natural laughter, never recite the sample words. No new spoken words, human speech from GULU, random sighs, theatrical ha-ha syllables, choppy laugh loops, BGM, songs, humming, narration or environmental/impact SFX. Continue one laugh/breath across the stated cuts without restarting.')
        prompt+='\n'+(audio_text if j['audio'] else 'Completely SILENT: no speech, laughter, sigh, narration, dragon call, BGM, song, humming or environmental/impact sound.')
        inputs={f'ref_image_{n}':str(P/assets[k]['path']) for n,k in enumerate(j['refs'])}
        bindings={f'ref_image_{n}':k for n,k in enumerate(j['refs'])}
        aud=[]
        if j['audio']:
            aud=(['VOICE-GIRL'] if j['speakers'] else [])+['VOICE-MATCH24']+(['VOICE-LAUGH24'] if j.get('laugh') else [])
        for n,k in enumerate(aud):inputs[f'ref_audio_{n}']=str(P/assets[k]['path']);bindings[f'ref_audio_{n}']=k
        inputs.update(prompt=prompt,duration=j['seconds'],resolution='768p横',seed=202611132400+i)
        cfg=dict(workflow_id='minimax_h3_zm_u30',materials_manifest=str(MANIFEST),shot_id=j['id'],inputs=inputs,output_dir=str(P/'04-输出/原始片段/前四十秒电影重制24'/j['id']),timeout=3600,poll_interval=15)
        cf=C/(j['id']+'-u30-执行01.yaml');cf.write_text(yaml.safe_dump(cfg,allow_unicode=True,sort_keys=False,width=110),encoding='utf-8')
        pf=C/(j['id']+'-视频英文正文01.txt');pf.write_text(prompt,encoding='utf-8',newline='\n')
        shots[j['id']]=dict(speakers=j['speakers'],voice_bindings={'ref_audio_0':'CHAR-GIRL'} if j['speakers'] else {},required_assets=j['refs']+aud,reference_bindings=bindings,purpose=j['title'],authorization_ref=AUTH)
        jobs.append({**j,'prompt':prompt,'prompt_sha256':sha(pf),'config':cf.relative_to(P).as_posix(),'reference_bindings':bindings})
    documents=copy.deepcopy(old['documents'])
    documents.update(style=dict(path=sty,state='ready'),script=dict(path=SCRIPT,state='ready'),storyboard=dict(path=SCRIPT,state='ready'))
    documents.pop('plan',None)
    manifest=dict(schema_version=2,voice_policy=dict(version=1,project='project.yaml'),creative_confirmation=dict(state='confirmed',script_sha256=sha(P/SCRIPT),confirmation_ref=AUTH),documents=documents,assets=assets,shots=shots)
    MANIFEST.write_text(yaml.safe_dump(manifest,allow_unicode=True,sort_keys=False,width=120),encoding='utf-8')
    package=dict(script=SCRIPT,script_sha256=sha(P/SCRIPT),authorization=AUTH,style=sty,style_sha256=style_sha,image_specs=ims,jobs=jobs,assets={k:str(P/v['path']) for k,v in assets.items()},duration_seconds=40,raw_durations=[10,9,10,11],workflow='minimax_h3_zm_u30',reference_method='static_blender_to_photoreal; first single-image trial before extension',final_size=[1344,756],final_fps=60,expected_native_fps=24,fps_api_field=False,whitebox_video=False,post_retiming=False,auto_paid_rerolls=False,music_plan='No music; speech and spontaneous laughter carry this comic opening; no added environment/impact sound.',stage='actual_inputs_pending_review' if finalize else 'prompt_and_reference_plan_pending_review')
    (C/'制作包01.json').write_text(json.dumps(package,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(jobs=len(jobs),images=len(ims),seconds=40,finalize=finalize),ensure_ascii=False))


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--finalize',action='store_true');build(a.parse_args().finalize)
