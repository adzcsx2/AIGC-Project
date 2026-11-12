"""Prepare R09 creative/input package only. Never submits media generation."""
from pathlib import Path
import hashlib
import json
import yaml

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / 'projects/悬崖上的小气球'
TAG = '正式五段直出09'
COMMON = ['CHAR-GIRL-THREEVIEW', 'CHAR-DRAGON-THREEVIEW', 'HEIGHT-CHART-R04', 'U30-R07-STANDING-PAIR', 'HEIGHT-EMPTY-SCENE-R04']
STYLE = ('Medieval LIVE-ACTION fantasy photography in every view. Real skin and fine brown hair, woven gray-blue wool cloak, cream linen and worn leather. '
         'GULU is the same living photoreal cinematic VFX PINK juvenile with fine irregular scales, flexible soft tissue, wet GRAY-BLUE eyes, cream underside, FOUR paws, TWO dorsal wings and ONE tail. '
         'Coherent upper-left daylight, reflected grass light, shared exposure and contact shadows. No cartoon, plastic toy, game-model finish, red recoloring, golden eyes or adult transformation.')
WORLD = ('Keep ONE huge rough-barked tree RIGHT, TWO timber-and-plaster cottages on stone bases LEFT BACK, the curved path behind MIA, ONE slender berry sapling LEFT with its SINGLE attached red berry and stem, '
         'natural short grass, the gray limestone rim in the foreground, distant wooded hills and pale-blue sky. Same horizon, light direction and ground perspective; all action inland, away from the rim. '
         'Do not shift scenery or MIA to clear the route. Preserve the actual berry height/branch and all contact consequences.')
SIZE = ("MIA's standing crown-to-sole height is 130 cm. GULU's neutral FOUR-PAW ground-to-highest-horn height is 40 cm INCLUDING head and horns, excluding tail length and wing spread. "
        'Follow the HEIGHT REFERENCE Image 3 and standing scale pair Image 4 for the 40:130 physical size relationship. The compact juvenile is small enough for MIA to cradle in both forearms; size comparison only, no new holding action. '
        'Standing reference poses/panel positions control SIZE ONLY, never the reclining girl or story placement. Keep skull/horns, torso length/girth and limb lengths unchanged; crouching, turning, stretching joints and paw clearance are not growth. '
        'Use the calibrated full-scene references for comparable depth and relative size, not the independently framed identity-panel heights.')
MAP = ('Image 1 identifies ONE MIA, Image 2 identifies ONE GULU; multiple board panels are views of the same individual, not extra actors. '
       'Image 3 is the labeled HEIGHT REFERENCE, Image 4 the standing size pair, Image 5 the environment. '
       'Do not render boards, grids, rulers, labels, numbers, duplicates or collage. All scene/action references depict the SAME actors at successive moments. '
       'These are soft image references, not hard first/last-frame or geometry inputs. ')
CONTACT = ('For every planted paw: pads meet grass before taking weight; the local blades bend/compress under the load, claws push off, then released blades partly spring back. '
           'Feet support the body rather than slide in place. Keep small coherent contact/cast shadows attached to the real contacts. '
           "No ground liquefaction, girl's body distortion, rubber scenery, separate pasted creature, artificial halo or painted-on shadow.")
MIA = ('MIA remains in her pictured low side-reclining support: one elbow/forearm and her hip/legs grounded, hand supporting her head. '
       'She is alive: breathing, blinks, motivated head/eye tracking, mouth/brow reactions and free-hand responses. '
       'No sustained chest push-up, sitting or standing; do not freeze her into a photographic plate.')
NO_MUSIC = 'No BGM, score, songs, humming, musical stings, narration, subtitles, watermark, fade-out or end card. Normal real-time action; no slow motion, floating apex or retiming to fill the clip.'


def make():
    manifest = yaml.safe_load((P/'素材清单-三视图更新01-资产归位01.yaml').read_text('utf-8'))
    source_ids = COMMON + ['VOICE-GIRL', 'R08-START', 'R08-STOP', 'R05-03-GIRL']
    sources = {i: manifest['assets'][i]['path'] for i in source_ids}
    # Scene poses are derived from the accepted calibrated master, not old oversized R05 dragon shots.
    images = [
        dict(id='R09-REST', name='片段01-起点A小龙伏卧晒太阳01.png', deps=['R08-START'],
             prompt='Edit Reference 1, the accepted calibrated complete START A master. Keep the camera, all scenery, MIA and her position/size/reclining support exactly. Change only the ONE GULU at its existing RIGHT-side patch from neutral four-paw stand to relaxed belly-down rest, with its same small legs folded under the body, chin low and eyes half open. Preserve identical skull/horn dimensions, torso length/girth, limbs, folded wings and tail; lowering the joints reduces silhouette height naturally, never inflates the torso. Its body stays at the same camera depth, tail fully in frame; belly/chest compress grass under actual weight, soft contact shadow. MIA looks affectionately toward GULU with a warm relaxed face, breathing implied, free hand on grass. No second dragon. ' + SIZE.replace('Image 3 and standing scale pair Image 4', 'the established calibrated master') + ' ' + WORLD + ' ' + STYLE + ' One complete widescreen image, no text, scale marks, collage or arrows.'),
        dict(id='R09-MISS', name='片段02-果下B短跳咬空-同体型01.png', deps=['R08-STOP'],
             prompt='Edit Reference 1, the calibrated STOP B master. Keep the exact camera, scene, MIA position/support and the one attached berry. Show the SAME ONE small GULU at B directly under the berry at the brief apex of ONE small UPWARD jump, with all four paws visibly clear of grass by about 15 cm, around one third of its neutral 40cm horn-tip height. Translate the existing body upward, do not enlarge or stand it upright; torso nearly horizontal, hind legs just extended/recovering, forelegs lightly tucked, wings only fluttering. Preserve the master skull/horns, torso girth/length and limb lengths; body stays at the same depth. Open jaws aimed toward the attached berry, but a clear visible gap remains between mouth and fruit; both mouth and stem visible. No fruit contact, bite mark, detached berry, stretched neck, flight or frozen hover. MIA watches LEFT toward B with raised amused brows while still reclining and grounded. ' + WORLD + ' ' + STYLE + ' One complete widescreen image, no text, diagrams, duplicate poses or collage.'),
        dict(id='R09-LAND', name='片段02至03-左侧草丛C扎草-同体型01.png', deps=['R08-STOP'],
             prompt='Edit Reference 1, the calibrated B master, preserving the exact full-scene camera and all world anchors. The SAME ONE GULU has made one short tumble a small distance LEFT from B into grass clump C, on the berry side of MIA, clear of the sapling trunk and far from the limestone rim. C remains in the SAME horizontal support-depth band as B, not closer to camera. Show the after-fall moment: muzzle and BOTH eyes buried in bent grass, forepaws braced, cheek/chest weighted down, small rump lifted, wings folded, one tail extending/curving RIGHT. Keep the master skull/horns, torso girth/length and limb dimensions: the low pose changes only articulation, never adds bulk. Only one dragon, remove its old presence at B. Grass compresses/parts around muzzle and chest, a few blades and soil specks cling to the muzzle; no injury. MIA stays at her original position and scale, head/eyes now LEFT toward C, holding a laugh with pressed lips, supported elbow and hip/legs grounded. The berry stays attached and untouched. ' + WORLD + ' ' + STYLE + ' One complete widescreen image, no labels, arrows or extra poses.'),
        dict(id='R09-READY', name='片段03至04-草丛C恢复四足-同体型01.png', deps=['R09-LAND','R08-STOP'],
             prompt='Reference 1 is the exact AFTER-FALL C scene/camera master. Reference 2 supplies the calibrated neutral 40cm GULU structure/size at the SAME depth, not a request to move back to B. Keep all scenery and MIA unchanged. At the SAME C paw/grass patch, show the SAME small GULU after pulling its face from grass and turning on the spot to a natural three-quarter four-paw support facing MIA to the RIGHT. Do not move its body to MIA or to its old RIGHT-side start. All four paws carry its unchanged small torso; neutral horn-tip-to-sole height matches Reference 2 at comparable depth, with unchanged skull/horns, girth and limb lengths. Head turn/foreshortening is not growth. Expression: wounded pride becoming stubborn determination, brows drawing inward, mouth level/closed, eyes toward MIA, no happy grin. Preserve a few grass/soil specks on nose and compressed C grass. MIA watches C from her existing supported reclining position to its RIGHT, an amused smile forming. ' + WORLD + ' ' + STYLE + ' One complete widescreen image, no labels, duplicates or collage.'),
        dict(id='R09-ANGER', name='片段05-草丛C怒视米娅-面部参考01.png', deps=['R09-READY','CHAR-DRAGON-THREEVIEW'],
             prompt='Reference 1 supplies the current C location, same small GULU and nose grass/soil. Reference 2 supplies identity detail only. Create ONE low 70mm face/shoulder reaction shot of GULU at C, looking toward MIA offscreen-RIGHT. A camera cut-in changes framing, NOT the creature anatomy or size. Make wounded pride turn into unmistakable anger: soft inner brow ridges lowered and pressed inward, tense upper lids and braced lower lids, a hard narrow GRAY-BLUE-eyed glare, nostrils tense, jaw CLAMPED CLOSED, mouth corners LEVEL TO DOWN, head lowered slightly forward, taut neck and folded wing roots. No smile, grin, upturned mouth, cute head tilt, happy eyes or playful expression. Preserve the same juvenile skull/horns, fine pink scales, cream underside, dirt/grass on nose; no horns growth, golden eyes, extra teeth or threatening adult redesign. Sapling-side grass and softly defocused existing world behind; do not move to another patch or add MIA into this single. ' + STYLE + ' One widescreen cinematic still, no text, collage, border or labels.')
    ]
    p1 = (MAP + 'Image 6 shows the INITIAL resting pose at A. Image 7 is the later calibrated four-paw pose at the SAME A, not a second dragon. ' + SIZE + '\n\n'
          'Ten-second unit. Begin with the full-scene relationship wide, the girl center-left and GULU RIGHT at A; camera steady, no push-in. '
          '0.0-3.0s: both rest in sunlight; GULU belly/chest compress grass, eyelids relaxed, small breathing; MIA blinks and gives it an affectionate glance. '
          '3.0-4.5s: GULU notices the actual LEFT attached berry, eyes focus, ears/brows alert, head turns LEFT, appetite replaces drowsiness. '
          '4.5-5.2s: one lip lick with tongue touching lip, tiny wet trace. '
          '5.2-5.9s: it plants four paws and extends its folded legs into Image 7 neutral support, preserving skull, torso and limb size; grass partly recovers as chest leaves. '
          '5.9-9.0s: hold the lively anticipatory state, look toward the berry, subtle weight shift backward; MIA follows the gaze with a warmer amused smile. No run, jump, fall or flight yet. '
          '9.0-10.0s: explicit eyeline CUT to the same attached berry/stem on the LEFT twig; leaves bend gently in the breeze. The next unit CUTS back to the wide action, not a zoom continuing through a different scale. '
          + MIA + '\n\n' + WORLD + ' ' + STYLE + ' No spoken words; only the already-authorized soft wind/leaves. ' + NO_MUSIC)
    p2 = (MAP + 'Image 6 is the calibrated START A. Image 7 is the calibrated same-size/same-depth neutral STOP B beneath the LEFT berry. Image 8 is the later short UPWARD mouth-miss at B, Image 9 the final face-buried C state, not extra actors. ' + SIZE + '\n\n'
          'Eight-second unit. CUT from the berry insert to this steady wide lateral action composition, keeping the whole route and all paws visible. No zoom, dolly toward the creature, automatic push-in or cut during run/jump/landing. '
          '0.0-0.6s: at RIGHT-side A, three short preparatory backward steps and one paw scrape, loose soil shifts; eyes lock on the LEFT berry. '
          '0.6-3.0s: GULU accelerates into a quick natural four-paw run from A across the clear horizontal grass lane IN FRONT OF MIA to B directly UNDER the attached berry. Same camera depth throughout; visible displacement relative to the girl and sapling. Preserve the calibrated small skull, torso girth/length and limb lengths before, during and after passing MIA. Natural gait suspension is allowed, not an early jump at A. '
          'MIA follows it with head/eyes RIGHT TO LEFT and a curious amused mouth/brow reaction, free hand adjusts lightly on grass, hip/legs and support remain grounded. No run in place, overlap through her body or foreground enlargement. '
          '3.0-3.4s: ONLY after arriving at B, hind paws load and extend into ONE short clearly UPWARD jump, lowest paws around 15cm above grass at its brief apex. Torso stays nearly horizontal, body rises rather than grows; forelegs retract slightly, wings flutter briefly. Mouth opens toward the actual berry then closes on EMPTY AIR with a readable gap. Keep mouth, berry and stem visible together. No forward pounce replacing ascent, neck elongation, fruit lowering/contact/detachment, hover or flight. '
          '3.4-3.7s: paws land at B, a loaded forepaw skids on damp grass. '
          '3.7-4.6s: skid causes ONE short weighted tumble LEFT into nearby C, clear of sapling trunk/MIA/rim; show forepaw/shoulder, chest and muzzle contacts, bent grass, slight soil displacement and soft tissue compression/rebound. '
          '4.6-8.0s: face stays buried in C, both eyes/muzzle hidden, wings folded, breathing and one unhappy drooping tail response. MIA looks LEFT toward the SAME C with pressed lips holding her first laugh. Never return GULU to A. The next unit CUTS to her reaction while it remains in C.\n\n'
          + CONTACT + ' ' + MIA + ' ' + WORLD + ' ' + STYLE + ' No speech. Only already-authorized soft paw/grass, wing, tumble and wind sounds. ' + NO_MUSIC)
    line3 = 'Gulu, you flew so high! A whole grasshopper high! Are those wings or little fans?'
    p3 = (MAP + 'Image 6 is the INITIAL girl reaction medium looking offscreen-LEFT toward C; Image 7 is the true face-buried C scene after the preceding tumble. Image 8 shows her SAME small dragon after recovery at C, not a new location. ' + SIZE + '\n\n'
          'Fifteen-second reaction unit. 0.0-1.2s: explicit CUT from the landing wide to the low 50mm girl medium. She bursts into laughter, eyes crease, shoulders/abdomen bounce, free hand clutches belly, a small grounded side-rock, then retains her loaded elbow support. GULU remains offscreen-LEFT in C, never beside her face. '
          '1.2-8.5s: with warm teasing laughter MIA speaks this exact ENGLISH sentence ONCE with visible mouth shapes: "' + line3 + '" Her gaze stays toward C LEFT, no old rightward eyeline. Finish the words before the reaction cut; no repetition offscreen. '
          '8.5-9.5s: CUT to a low full-body GULU reaction AT THE SAME C, beginning with its face still in the compressed grass. It loads forepaws, pulls the muddy/grass-marked face free promptly, blades part and partly recover. '
          '9.5-15.0s: turn on the spot toward MIA to the RIGHT, without leaving C. A hopeful glance becomes wounded pride: gaze lowers, brows tense inward, mouth tightens/levels, wings draw in, tail settles with weight. Breathing continues. End in the natural four-paw readiness shown in Image 8, keeping dirt/grass on nose and flattened grass. No walk back to A, new patch, growth or next jump. '
          + MIA + ' ' + WORLD + ' ' + STYLE + ' ref_audio_0 supplies only MIA approved sweet youthful ENGLISH timbre, never sample words. Only the exact sentence once, scripted laugh/breaths and already-authorized wind. No Mandarin or new words. ' + NO_MUSIC)
    p4 = (MAP + 'Image 6 is the INITIAL natural four-paw GULU at the SAME C, with nose grass/soil from the tumble. Image 7 preserves the calibrated full-world scale/depth; it is not a request to return from C to B or to the old RIGHT start. ' + SIZE + '\n\n'
          'Six-second unit. CUT from the hurt reaction to a steady low full-body ground view of C, enough room for horn tips, all paws, folded/briefly fluttering wings, tail and soil contact. MIA remains farther RIGHT, reclining at her established patch and looking LEFT. No zoom/dolly hides the rise or changes the apparent size. '
          '0.0-1.0s: hurt becomes stubborn determination, jaw sets, forepaws and hind paws brace the grass. '
          '1.0-2.6s: one bracing inhalation and short urgent wing flutter. Cheeks puff slightly, chest/abdomen show only limited breathing; do not inflate the body or grow its bones/torso. '
          '2.6-2.8s: ONE tiny failed rise with the LOWEST paws about FIVE CENTIMETRES above that same ground, around one eighth of neutral height. Pass the apex immediately and descend; total airborne phase about0.2s, no metre jump, prolonged hovering or rear-leg stand faking clearance. '
          '2.8-3.3s: rump lands in the shallow damp-soil patch at C, mud depresses and moves slightly, belly softly compresses/rebounds, a small mud smear remains on rump/lower belly. '
          '3.3-6.0s: seated embarrassment and frustration, glance at MIA then down, drooping wing roots and weighted tail, breathing. MIA visible head/eye/free-hand reactions and growing restrained laugh; still supported and grounded. No relocation, flight or next departure. The following unit CUTS to her second laugh, same C and mud. '
          + CONTACT + ' ' + MIA + ' ' + WORLD + ' ' + STYLE + ' No spoken words; only already-authorized wing/grass/rump landing and wind sounds. ' + NO_MUSIC)
    line5 = "Oh, my tummy... All right, little chubby dragon, admit it. You're really a fat lizard pretending to be a dragon, aren't you?"
    p5 = (MAP + 'Image 6 governs the INITIAL girl reaction medium looking LEFT toward C; Image 7 is GULU later ANGRY FACE at C looking toward MIA offscreen-RIGHT; Image 8 is the full-world C placement/scale, not a request to start it standing or reset its mud. ' + SIZE + '\n\n'
          'Fifteen-second unit. 0.0-1.0s: CUT to MIA low50mm medium, laughter creases her wet eyes, a small laughter tear, free hand clutches belly. Grounded hip/legs and loaded elbow support remain. GULU remains OFFSCREEN-LEFT seated in the SAME C muddy spot after the prior rump landing. '
          '1.0-10.5s: MIA delivers this exact ENGLISH sentence ONCE at clear natural cadence: "' + line5 + '" Briefly point toward C with the free index, then hand returns to belly. '
          'At about5.5s, before "fat lizard", CUT to GULU low70mm face/shoulder reaction AT C. Continue the SAME audio sentence offscreen without restarting words. '
          'As "fat lizard" is heard, wounded pride turns into Image7 unmistakable anger: inner soft brow ridges press DOWN/IN, upper lids tense/lower, lower lids braced, HARD GRAY-BLUE-eyed glare toward MIA offscreen-RIGHT, tense nostrils, jaw CLAMPED CLOSED, mouth corners LEVEL TO DOWN. Head lowers/leans forward slightly, neck taut, wing roots close, claws load grass. No smiling, grin, smirk, happy eyes, friendly head tilt or playful tail wag. '
          '10.5-12.0s: hold that readable angry facial set with breathing/weight, not a frozen image. Preserve nose grass/soil and rump mud. '
          '12.0-15.0s: ONE brief NONVERBAL baby-dragon angry growl; jaw opens vertically from the tense mouth and closes to the same anger, not a smile. It plants paws, rises from the muddy seat with unchanged size and turns AWAY from MIA on C, tail following one weighted departure step. Show anger BEFORE turning. No walk back to A, cliff jump or flight in this unit. '
          + MIA + ' ' + WORLD + ' ' + STYLE + ' ref_audio_0 supplies only MIA approved ENGLISH timbre. Only the specified sentence once, scripted laughter/breaths, one nonverbal growl and already-authorized wind. No Mandarin or new words. ' + NO_MUSIC)
    units = [
        dict(n=1,name='晒太阳与发现浆果',duration=10,ids=['R09-REST','R08-START'],prompt=p1,dialogue=None),
        dict(n=2,name='跑到果下短跳咬空与滚草',duration=8,ids=['R08-START','R08-STOP','R09-MISS','R09-LAND'],prompt=p2,dialogue=None),
        dict(n=3,name='同一草丛第一次笑与受伤',duration=15,ids=['R05-03-GIRL','R09-LAND','R09-READY'],prompt=p3,dialogue=line3),
        dict(n=4,name='同一草丛五厘米起落与跌泥',duration=6,ids=['R09-READY','R08-STOP'],prompt=p4,dialogue=None),
        dict(n=5,name='第二次调侃与可读怒脸',duration=15,ids=['R05-03-GIRL','R09-ANGER','R09-READY'],prompt=p5,dialogue=line5),
    ]
    packet=dict(tag=TAG,state='DRAFT_NOT_APPROVED',workflow='minimax_h3_zm_u30',resolution='960p横',whitebox=False,
                authorization='06-记录/用户确认/一次直出08接受与正式五段重制09授权-20261112.json',
                accepted_scale_basis='03-制作/制作计划/一次直出08/制作包03-实际输入.json',
                style='01-文档/视觉设定/视觉设定-版本03-场景候选登记.md',common_asset_ids=COMMON,sources=sources,
                images=images,units=units,planned_duration=54,
                seams=[dict(at='01→02',design='果实特写→完整跑道宽镜；起点A四足蓄势，不把同景别当连续镜头'),
                       dict(at='02→03',design='左侧C扎草宽镜→女孩看向LEFT反应中景；C位置/草痕保留'),
                       dict(at='03→04',design='C受伤反应→低机位全身起落；同一C，泥草保留'),
                       dict(at='04→05',design='C跌泥→女孩第二次笑中景→C怒脸；同一落点与泥污')])
    out=P/f'03-制作/制作计划/{TAG}/制作包01-文案与素材方案.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(out.relative_to(P),hashlib.sha256(out.read_bytes()).hexdigest())
    print('DRAFT ONLY: five authorized units, five planned image edits, zero video jobs.')


if __name__ == '__main__':
    make()
