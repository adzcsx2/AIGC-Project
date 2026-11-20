"""R26 text/input revision only: exactly scene + MIA board + GULU board."""
from pathlib import Path
import json,copy,hashlib
import yaml

R=Path(__file__).resolve().parents[2];P=R/'projects/悬崖上的小气球'
C=P/'03-制作/生成配置/前四十秒三图输入26'
MANIFEST=P/'素材清单-前四十秒三图输入26-审计稿01.yaml'
PLAN='01-文档/需求与剧本/前四十秒三图输入26-方案修订01.md'
DOC='01-文档/提示词/前四十秒三图输入26-英文提示词与审计修订01.md'
AUTH='06-记录/用户确认/三图输入26-仅审计与修订要求01.json'
REFS=['SCENE','CHAR-GIRL-THREEVIEW','CHAR-DRAGON-THREEVIEW']
MAP=('Reference map: Image1 is SCENE, the location; Image2 is MIA, the girl; Image3 is GULU, the pink juvenile dragon. '
     'Character boards define identity only, not display scale, standing pose, studio lighting or the board layout. These names are reference labels, never visible text.')
LOCATION=('Use the same sunny inland meadow. In SCENE\'s establishing view, two modest timber-and-plaster cottages are behind LEFT and one mature tree behind RIGHT, with a curved dirt path and wooded slopes. '
          'Preserve this physical location and its upper-left daylight when reframing; landmarks need not stay at identical screen coordinates after a camera change.')
FRUIT=('The one berry sapling is 100 cm tall. Exactly one 3 cm red berry hangs from a slender sloping twig, its bottom 70 cm above the ground. '
       'Keep that tree, twig and attached fruit unchanged; no low fruit or extra berries. The slender twig is not a landing perch.')
STYLE=('Grounded live-action medieval fantasy, photographed on location with seamless photoreal creature VFX. '
       'Use shared natural light, shaped shadows, restrained color and gentle highlight roll-off. '
       'Show irregular matte scales, supple joints, moist eyes, thin membranes and believable grass/earth response; preserve the approved identity. '
       'Use lens-appropriate softness and motion blur, not a toy, cartoon or polished game-render look.')
FRAME='16:9. Choose cinematic framing and cuts from the same side of the established action axis, keeping direction, important effort and contact readable. Actions play at brisk, believable real-time speed. No visible labels, subtitles or black bars.'
SILENT='Silent soundtrack: no speech, laughter, animal calls, narration, music or added effects.'
JOBS=[
 {'id':'R26-ENV','seconds':3,'visible':[],'audio':[],'speakers':[],
  'action':'Only the empty location is visible; neither MIA nor GULU appears. Establish the clearing and its small sapling, then draw attention to the SAME single attached berry with a closer view. Natural breeze stirs leaves; the twig remains intact. Let the camera choose a clean reveal without redesigning the location.',
  'fruit':True,'scale':''},
 {'id':'R26-MIA-A','seconds':7,'visible':['MIA'],'audio':['NAT-LAUGH'],'speakers':[],
  'action':'Only MIA is visible; GULU stays outside the frame. MIA rests in a low side-recline, head LEFT and boots RIGHT. One elbow supports her weight and its hand props her cheek; the other hand is free. She enjoys the sun, briskly brushes aside a loose strand, then notices the offscreen mishap. Surprise turns into a spontaneous giggle; her free hand goes to her belly, then covers her mouth as laughter grows. Her shoulders follow normal breathing; she never sits or stands. Keep the gestures prompt and the performance alive, not frozen posing.',
  'fruit':False,'scale':'MIA is 130 cm tall when standing; preserve her child proportions in the reclining pose.',
  'sound':'Only MIA has an audible natural laugh and breathing, using Audio1 as her laugh-performance reference. No spoken words, opening sigh, other voice or music.'},
 {'id':'R26-LOW','seconds':3,'visible':['GULU'],'audio':[],'speakers':[],
  'action':'Only GULU is visible; MIA remains offscreen and silent. GULU rests belly-low on folded forelegs and hind legs, facing LEFT, with folded wings. A sleepy blink gives way to alert eyes: he notices the high berry above LEFT, gives one quick lip lick and closes his mouth. A small tail flick reveals his interest. He stays low instead of rising or walking. Use brisk little reactions, not slow posing.',
  'fruit':True,'scale':'In this supported low posture, ground to highest horn is about 10 cm, one tenth of the 100 cm sapling at the same ground depth. Keep his skull, torso and limbs the same physical size as in other shots; do not inflate his body.'},
 {'id':'R26-RUN','seconds':6,'visible':['GULU'],'audio':[],'speakers':[],
  'action':'Only GULU is visible; MIA stays offscreen and silent. Start with GULU low on folded legs, facing LEFT. He promptly pushes onto four paws, takes three quick backward steps and scrapes the turf once. He then RUNS LEFT to directly beneath the berry and springs UPWARD, not forward at the camera. His mouth still falls clearly short of the attached fruit at the apex, leaving about 25 cm of empty air. The berry is never touched; he never perches on or grabs its twig. His forepaws land on wet grass, rear paws slip, and the resulting momentum carries one compact shoulder-side roll into the soft tuft LEFT of the berry but RIGHT of the trunk. Wings tuck clear; grass bends under shoulder and chest, with blades left on his snout. Finish nose-buried, paws bracing and tail flicking in frustration. The short hop rises and falls promptly; landing immediately leads into the slip and roll. No hovering or drawn-out recovery.',
  'fruit':True,'scale':'His natural four-paw height is 20 cm from ground to highest horn, including head/horns but excluding wings/tail: one fifth of the sapling height at the same ground depth. Rising from low support straightens joints; skull and torso never grow. Keep his travel lateral at the tree-root depth, with no approach toward the lens.'},
 {'id':'R26-OUT','seconds':2,'visible':['GULU'],'audio':[],'speakers':[],
  'action':'Only GULU is visible; MIA stays offscreen and silent. Begin with his snout buried in the SAME pressed tuft LEFT of the berry and RIGHT of the trunk. Front paws press down as he pulls his head out sharply, lifting a few blades that fall back; some stay on his nose. He immediately pivots IN PLACE to face RIGHT and looks toward offscreen MIA with hurt, puzzled eyes and a closed tense jaw. End right-facing, not looking into the camera; do not walk out of the tuft or repeat the fall.',
  'fruit':True,'scale':'GULU has the same 20 cm natural four-paw height, including head/horns and excluding wings/tail: one fifth of the sapling height at the same ground depth. Head and torso size stay unchanged while he straightens and pivots.'},
 {'id':'R26-MIA-B','seconds':9,'visible':['MIA'],'audio':['VOICE-GIRL'],'speakers':['CHAR-GIRL'],
  'action':'Only MIA is visible; GULU remains offscreen. Begin with MIA in a low side-recline, head LEFT and boots RIGHT, one elbow supporting her weight and its hand propping her cheek. Laughing, her free hand goes to her belly; she briefly releases cheek support for one quick half-roll through her shoulder/back, then returns to this low side-recline on the same forearm. Her cloak drags and presses the grass. She never sits or stands. With playful eyes and natural conversational breath, she says exactly once in English: "Gulu, you flew so high—about as high as a grasshopper!" After a brief speech breath, she adds: "Are those wings, or little fans?" Her free hand briefly points offscreen LEFT and settles back. Keep her reactions lively and the delivery conversational, not slow or chanted.',
  'fruit':False,'scale':'MIA is 130 cm tall when standing; preserve her original child proportions while reclining and half-rolling.',
  'sound':'Only MIA speaks. Audio1 supplies her approved voice identity, not its sample words or slow audition tempo. Use only the two specified English lines and their natural breaths; no other voice, extra words, singing or music.'},
 {'id':'R26-FLAP','seconds':6,'visible':['GULU'],'audio':[],'speakers':[],
  'action':'Only GULU is visible at the SAME pressed tuft, facing RIGHT toward offscreen MIA. Grass remains on his nose. Hurt pride hardens into annoyance: upper lids press down, jaw tightens, mouth corners turn down and wing roots tense. No friendly smile. He takes one short breath, braces his paws and makes a quick determined burst of wingbeats with a short hind push. His feet clear the grass by only about 5 cm before he promptly drops onto his rear, with both front paws taking his chest weight. Damp grass compresses and a few mud specks stick to his rear/belly. He promptly folds his wings, regrips the turf and looks right for approval. Keep takeoff, brief flight and landing snappy; do not hover or stretch the descent.',
  'fruit':False,'scale':'GULU remains the same 20 cm natural four-paw creature, including head/horns and excluding wings/tail. His natural horn height is one fifth of the location\'s 100 cm sapling; preserve that physical ratio even when the tree is out of frame. The 5 cm value is foot clearance above the grass, not body height. Preserve his original head and torso dimensions.'},
 {'id':'R26-END','seconds':4,'visible':['GULU'],'audio':[],'speakers':[],
  'action':'Only GULU is visible at the SAME tuft, facing RIGHT. His rear stays down on damp grass while both front paws support his chest. Nose grass and the few rear/belly mud specks persist. He briefly lifts his eyes for approval; hope turns into wounded stubbornness. Lids lower, jaw tightens, mouth corners stay down and wings draw close. One front paw presses harder into the mud, followed by a short tail flick and a decisive glance right/down. End on a living reaction, not a freeze; no new jump or walking toward the camera.',
  'fruit':False,'scale':'GULU is the same 20 cm natural four-paw animal, including head/horns and excluding wings/tail. His natural horn height is one fifth of the location\'s 100 cm sapling; preserve that physical ratio even when the tree is out of frame. Lowering his hindquarters changes joint support, not skull or torso size.'},
]

def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def style():
 d=yaml.safe_load((P/'project.yaml').read_text(encoding='utf-8'));f=P/d['documents']['style'];f.read_text(encoding='utf-8');g=R/'docs/视觉规范/中世纪写实风格规范.md';g.read_text(encoding='utf-8')
 return {'path':d['documents']['style'],'sha256':sha(f),'shared_sha256':sha(g)}
def style_for(visible):
 if 'GULU' in visible:return STYLE
 common='Grounded live-action medieval fantasy, photographed on location. Keep shared natural daylight, shaped shadows, restrained color, gentle highlight roll-off and lens-appropriate detail; no cartoon, glossy plastic, polished game-render look or HDR halos. '
 if 'MIA' in visible:return common+'Preserve MIA\'s identity, natural unretouched skin, braid, wool, linen and worn leather, with grounded cloth and grass response.'
 return common+'Use believable bark, leaves, grass, earth and aged timber/plaster, with natural optical depth.'
def build():
 C.mkdir(parents=True,exist_ok=True)
 old=yaml.safe_load((P/'素材清单-固定果树单主体25-修复04.yaml').read_text(encoding='utf-8'))
 assets={k:copy.deepcopy(old['assets'][k]) for k in ['CHAR-GIRL-THREEVIEW','CHAR-DRAGON-THREEVIEW','VOICE-GIRL','NAT-LAUGH']}
 assets['SCENE']=copy.deepcopy(old['assets']['ENV']);assets['SCENE']['purpose']='location_appearance_only_no_character_pose_or_height_chart'
 jobs=[];shots={};doc=['# 前40秒三图输入26：英文提示词审计修订稿\n','2026-11-15。本轮仅审计与改稿，没有提交生成。图片固定三张，顺序为场景、米娅身份板、咕噜身份板。人物板不作为站姿、身高像素或棚拍光线依据；语言、动作、空间和尺寸由正文说明。\n']
 for i,j in enumerate(JOBS):
  st=style()
  scene=LOCATION+' '+(FRUIT if j['fruit'] else 'The berry sapling remains outside this tighter framing; do not add a fruit-bearing plant beside the visible character.')
  if 'MIA' in j['visible']:
   scene+=' MIA reclines on the grass patch RIGHT of the sapling, at its ground depth, looking LEFT toward offscreen GULU.'
  if j['id'] in {'R26-FLAP','R26-END'}:
   scene+=' The pressed grass tuft is between the sapling trunk and the hanging berry\'s vertical projection onto the ground: RIGHT of the trunk and LEFT of the berry in the established view.'
  q='\n\n'.join([MAP,j['action'],j['scale'],scene,style_for(j['visible']),j.get('sound',SILENT),FRAME])
  assert not any('\u4e00'<=c<='\u9fff' for c in q)
  bindings={f'ref_image_{n}':k for n,k in enumerate(REFS)}
  bindings.update({f'ref_audio_{n}':k for n,k in enumerate(j['audio'])})
  inputs={slot:str(P/assets[k]['path']) for slot,k in bindings.items()};inputs.update(prompt=q,duration=j['seconds'],resolution='768p横',seed=202611152600+i)
  f=C/(j['id']+'-u30-审计稿01.yaml')
  cfg={'workflow_id':'minimax_h3_zm_u30','materials_manifest':str(MANIFEST),'shot_id':j['id'],'inputs':inputs,'output_dir':str(P/'04-输出/原始片段/前四十秒三图输入26'/j['id']),'timeout':3600,'poll_interval':15}
  f.write_text(yaml.safe_dump(cfg,allow_unicode=True,sort_keys=False,width=110),encoding='utf-8')
  pf=C/(j['id']+'-英文正文01.txt');pf.write_text(q,encoding='utf-8',newline='\n')
  shots[j['id']]={'speakers':j['speakers'],'voice_bindings':{'ref_audio_0':'CHAR-GIRL'} if j['speakers'] else {},'required_assets':list(bindings.values()),'reference_bindings':bindings,'visible_characters':j['visible'],'authorization_ref':AUTH}
  jobs.append({**j,'prompt':q,'prompt_path':str(pf),'prompt_sha256':sha(pf),'config':str(f),'config_sha256':sha(f),'bindings':bindings,'style':st})
  doc+=['\n## '+j['id']+'｜来源时长 '+str(j['seconds'])+' 秒\n','```text\n'+q+'\n```\n']
 docs=copy.deepcopy(old['documents']);docs.update(script={'path':PLAN,'state':'ready'},storyboard={'path':PLAN,'state':'ready'})
 manifest={'schema_version':2,'voice_policy':old['voice_policy'],'creative_confirmation':{'state':'pending','script_sha256':sha(P/PLAN),'confirmation_ref':AUTH},'documents':docs,'assets':assets,'shots':shots}
 MANIFEST.write_text(yaml.safe_dump(manifest,allow_unicode=True,sort_keys=False,width=110),encoding='utf-8')
 (P/DOC).write_text('\n'.join(doc),encoding='utf-8')
 out={'client_date':'2026-11-15','stage':'TEXT_INPUT_AUDIT_DRAFT_NO_SUBMISSION','scope':'same opening40s story, new exact3image input method; user-requested textual revision only','source_plan':'01-文档/需求与剧本/前四十秒重构25-固定果树与单主体规划01.md','plan':PLAN,'plan_sha256':sha(P/PLAN),'prompt_document':DOC,'prompt_document_sha256':sha(P/DOC),'assets':{k:{'path':str(P/v['path']),'sha256':sha(P/v['path'])} for k,v in assets.items()},'image_order':REFS,'jobs':jobs,'total_source_seconds':sum(j['seconds'] for j in JOBS),'new_generation_submissions':0,'validation_scope':'Text/roles/known input capability, not future movie compliance. Current user instruction overrides prior auxiliary-picture/static-guide workflow for THIS revision only.'}
 (C/'三图制作包01.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'jobs':len(jobs),'each_image_count':3,'source_seconds':out['total_source_seconds'],'words':{j['id']:len(j['prompt'].split()) for j in jobs}},ensure_ascii=False))
if __name__=='__main__':build()
