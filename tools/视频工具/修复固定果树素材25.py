"""Prepare and archive R25 repair image requests. Never submits generation jobs."""
from pathlib import Path
import argparse,hashlib,json,shutil
import yaml
R=Path(__file__).resolve().parents[2];P=R/'projects/悬崖上的小气球'
C=P/'03-制作/生成配置/固定果树单主体25修复03';A=P/'02-素材/镜头/固定果树单主体25/修复03'
OLD=P/'02-素材/镜头/固定果树单主体25'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def style():
 d=yaml.safe_load((P/'project.yaml').read_text(encoding='utf-8'));f=P/d['documents']['style'];f.read_text(encoding='utf-8');s=R/'docs/视觉规范/中世纪写实风格规范.md';s.read_text(encoding='utf-8');return {'path':str(f),'sha256':sha(f),'shared_sha256':sha(s)}
FILM=('Preserve the photographed medieval meadow, two modest cottages behind LEFT and mature tree behind RIGHT, with the same filtered daylight from upper LEFT. '
 'Living cinematic creature VFX: irregular matte scales, supple joints, moist eyes, thin membranes, shared exposure and grounded shadows. Natural greens and restrained pink, optical softness appropriate to distance. No cartoon, toy, game display, glossy plastic, HDR halos, uniform sharpness, extra actor, UI, text or black bars.')
SOURCES={'RUN':OLD/'小龙四足二十厘米-固定果树尺度母图06.png','OLD-APEX':OLD/'小跳最高点-嘴低于高浆果二十五厘米03.png','OLD-BURY':OLD/'落草埋头-固定尺度与接触落点03.png','OLD-REACT':OLD/'小龙受挫侧面近景-实拍材质01.png','LOW05':A/'幼龙原地低伏-十厘米与正确左上视线05.png','CLAY-LOW03':P/'03-制作/静态构图/固定果树单主体25/同机位-小龙低伏十厘米03.png'}
SOURCES['CLAY-LOW04']=P/'03-制作/静态构图/固定果树单主体25/同机位-侧枕低伏十厘米04.png'
SOURCES['CLAY-LOW05']=P/'03-制作/静态构图/固定果树单主体25/同机位-侧卧低伏十厘米05.png'
SOURCES['CLAY-END05']=P/'03-制作/静态构图/固定果树单主体25/近景切镜-后躯低坐与失落05.png'
SPECS=[
 ('LOW','幼龙侧卧晒太阳-原体量十厘米低位08.png',['RUN','CLAY-LOW05'],
  'Edit the existing tiny juvenile in Image1 into a familiar sleeping-animal SIDE-LYING pose. It lies on ONE FLANK with folded paws tucked toward its chest, belly partly facing the camera, and its head resting sideways on ONE CHEEK in the grass. Nose points LEFT, one eye faces upward, horns lie sideways with the head rather than pointing up. Keep the exact original rounded juvenile skull, short muzzle, curved horns, torso and limbs; no rescaling or elongation. The supported side-rest body is low, about10cm high, roughly half its current standing height. Keep its CENTER at the same spot, fruit UPPER LEFT, original folded wings and continuous tail. Natural cheek/flank grass compression. Quiet sleepy half-closed eye, closed mouth. Every background object, camera and light remains unchanged.'),
 ('APEX','幼龙小跳落空-完整气隙与恒定体量04.png',['OLD-APEX'],
  'Edit Image1 with ONE rigid translation only: move the ENTIRE existing airborne dragon DOWN by about 32 pixels and RIGHT by about 10 pixels on this 941-pixel-high image. Do not reshape, resize, rotate, stretch its neck or change any joint pose. Its upper mouth should be near y440, with about 94 pixels of EMPTY AIR below the berry bottom near y348, roughly the animal whole head-to-foot height. All four feet remain airborne. Restore former edges naturally. Keep the complete tree, single fruit, camera, light and scenery unchanged.'),
 ('BURY','幼龙落草接触-原体量与压倒草叶04.png',['OLD-BURY'],
  'Edit ONLY the small grass blades already TOUCHING the tiny dragon snout and front chest in Image1. Bend and spread those blades around and over its muzzle, partly obscuring the nose/face and visibly compressed beneath the chest. Do not change ANY part of the dragon, its size, body center, paws, folded wings, raised tail, pose or identity. Forepaws remain braced, rear feet supported, no solid-earth penetration. Keep the tuft modest, not a giant shrub. Preserve camera, tree, single berry, landscape and light exactly.'),
 ('TURN','幼龙原落点转右-四足二十厘米04.png',['BURY','RUN'],
  'Edit the ONE tiny juvenile in Image1 after it pulls its snout out: turn it IN PLACE to face RIGHT, all four paws on the SAME pressed tuft. Keep its body center fixed. Image2 supplies ONLY the original skull/torso/limb dimensions and juvenile identity, never the old right-side location. Natural level-neck four-paw stance, ground to highest horn about 20 cm, roughly 79 pixels in this wide camera. Short original horns and rounded short snout, gray-blue eyes, closed tense jaw and down mouth corners. A few grass flecks stay on nose. Same core size, no upright neck, growth, forward approach or camera change. Preserve every scene object and light.'),
 ('REACT','幼龙恼怒-微距实拍与同场曝光02.png',['OLD-REACT'],
  'Edit Image1 for photographed live-action material and exposure ONLY, not composition or anatomy. Retain the exact original juvenile, full body, RIGHT-facing four-paw pose and all scenery positions. This is an intentional ground-level macro reaction camera, approximately 22 mm at 46 cm from the same 20 cm creature, not a physically larger dragon. Keep wings/paws/tail room. Make scale roughness naturally varied, joints supple, eyes moist with restrained reflections; reduce the uniformly bright polished-pink display effect so belly and legs share the shaped shade of the grass. Preserve pink identity and gray-blue eyes, no blanket desaturation. Natural optical focus, not etched microdetail. Annoyed pressed upper lids, closed clenched jaw and down mouth corners, no smile. A few nose grass flecks and paw dirt remain.'),
 ('END','幼龙后躯跌坐-原体量与泥草支撑01.png',['REACT','CLAY-END05'],
  'Edit ONLY the hindquarter joint pose in Image1, with rear-low/front-paw support from gray Image2. Keep its front PAWS, SKULL and forward NECK at the SAME positions; lower only the HINDQUARTERS onto the same soft damp grass. Chest remains supported by both front paws. Same original skull/torso/limb dimensions and same macro camera, facing RIGHT. Never sit upright like a person; highest horn stays near the same height, about20cm above ground. Original folded wings/tail and nose grass remain. Add only a few local mud specks on rear/belly and pressed muddy grass at actual rear contact. Disappointed stubborn eyes, tight closed jaw, down mouth corners. Gray reference is pose only, never anatomy/material. Preserve scene/exposure/camera and physical body size; no new actor or growth.')]
def prepare():
 C.mkdir(parents=True,exist_ok=True);A.mkdir(parents=True,exist_ok=True);sources=dict(SOURCES)
 for k,name,_,_ in SPECS:sources[k]=A/name
 out=[]
 for k,name,refs,body in SPECS:
  st=style();body=('Image1 is the photographed identity/scene to edit. Image2 is only the calibrated low side-rest joint/size study, not its simplified anatomy or gray material.\n'+body) if k=='LOW' else body;q=body+'\n'+FILM+'\nOne coherent 16:9 photographed frame, not a collage.'
  f=C/(k+'-图片英文修复03.txt');f.write_text(q,encoding='utf-8',newline='\n');out.append({'id':k,'output':str(A/name),'refs':[str(sources[r]) for r in refs],'reference_roles':refs,'prompt':q,'prompt_sha256':sha(f),'style':st})
 (C/'图片修复请求03.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');return out
def record(key,source,status,note):
 d=json.loads((C/'图片修复请求03.json').read_text(encoding='utf-8'));s=next(x for x in d if x['id']==key);f=Path(s['output']);assert not f.exists(),'Version output before another attempt'
 shutil.copy2(source,f);log=P/'06-记录/图片生成/固定果树单主体25-实际修复请求03.json';log.parent.mkdir(parents=True,exist_ok=True);rows=json.loads(log.read_text(encoding='utf-8')) if log.exists() else []
 rows.append({**s,'actual_inputs':[{'path':x,'sha256':sha(x)} for x in s['refs']],'sha256':sha(f),'builtin_original':source,'status':status,'observed':note});log.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'id':key,'output':str(f),'status':status},ensure_ascii=False))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--spec');ap.add_argument('--record',nargs=2);ap.add_argument('--status',default='NEEDS_ACTUAL_REVIEW');ap.add_argument('--note',default='');a=ap.parse_args()
 if a.record:record(*a.record,a.status,a.note)
 else:
  d=prepare();print(json.dumps(next(x for x in d if x['id']==a.spec) if a.spec else {'requests':len(d),'path':str(C/'图片修复请求03.json')},ensure_ascii=False))
