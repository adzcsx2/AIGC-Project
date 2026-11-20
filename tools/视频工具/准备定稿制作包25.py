"""Build R25 repair drafts. No network calls, no task submission or media edits."""
from pathlib import Path
import copy,hashlib,json,runpy
import yaml

R=Path(__file__).resolve().parents[2];P=R/'projects/悬崖上的小气球'
C=P/'03-制作/生成配置/固定果树单主体25修复04'
MANIFEST=P/'素材清单-固定果树单主体25-修复04.yaml'
OLD=json.loads((P/'03-制作/生成配置/固定果树单主体25/制作包01.json').read_text(encoding='utf-8'))
METHOD=runpy.run_path(str(R/'tools/视频工具/准备固定果树单主体25.py'))
JOBS=copy.deepcopy(METHOD['JOBS'])
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()

CHANGES={
'R25-LOW':'''Image1 is the actual low-pose/location reference, Image2 supplies only the ONE juvenile identity, never its standing board pose or large display framing. Hold the original low supported body at the SAME ground depth and lateral starting place. Its supported low height is about10cm, approximately4.5percent of frame height in this wide camera. Sleepy blink becomes alert: nose twitches, eyes promptly focus UPPER LEFT on the already attached berry; a small head/eye adjustment does not extend the neck or stand up the torso. One brief0.2s lip lick, tongue returns inside the CLOSED mouth, tail tip gives a short wakeful flick. Wings remain folded. No walk, jump, camera move or extra action.''',
'R25-RUN':'''Image1=low start; Image2=ONE juvenile identity only; Image3=natural20cm four-paw SIZE/ANATOMY reference at the INITIAL lateral place, NOT the end of the backward steps; Image4=brief missed-reach apex with clear empty gap; Image5=eventual snout-in-grass result at the landing tuft. These show successive states of ONE animal, never duplicates or still-image dissolves. ONE UNBROKEN FIXED SIDE WIDE shot with tree, berry, paws, running lane and landing tuft visible throughout.0-.3s promptly unfold supporting joints into the natural20cm four-paw stance at the SAME place, with no growing skull or torso. .3-.9s THREE quick backward steps totaling18cm RIGHT of that initial place. .9-1.1s one quick rear-paw scrape flicks a little loose soil.1.1-1.6s short rapid paw strides carry the body about47cm LEFT along the same lateral lane; the MUZZLE arrives DIRECTLY BELOW the attached berry, rather than jumping at the starting place.1.6-1.75s hind paws compress then extend UPWARD.1.75-2.25s all FOUR feet leave the ground in one brief ballistic UPWARD hop: the whole body translates about30cm upward, upper mouth reaches only about45cm above ground, leaving about25cm of CLEAR EMPTY AIR below the fixed berry bottom70cm. The apex passes immediately, with no hovering or slow ascent/descent. No contact with the fruit, stalk or branch; no bite, grasp, climbing, perch or stretching neck.2.25-2.45s front paws contact wet grass, blades flatten; rear paws slip on the SAME wet turf.2.45-3.05s folded wings clear the ground, shoulder contacts soft grass and one short shoulder-side roll carries snout/forechest LEFT into the modest tuft LEFT of berry but RIGHT of trunk. Grass folds and stays compressed; snout goes into soft blades, never through solid earth.3.05-6s forepaws rebrace, two brief frustrated wriggles and unhappy tail flicks retain the buried snout. No stretched flight/roll or frozen padding. Keep original skull/torso/limb dimensions during the entire run, jump and roll, at the same ground depth. Natural standing height is about8.3percent of this wide frame; actual pose bounds vary without growth. End nose-buried for the later extraction shot.''',
'R25-OUT':'''Image1=actual buried start; Image2=ONE identity only; Image3=eventual RIGHT-facing four-paw result at the SAME landing place/camera, not the old starting location. Front paws press grass; promptly extract snout/forechest from soft blades in0.3-0.5s. A few blades lift with the snout and fall, some grass flecks remain on nose. Immediately follow with a quick small FOUR-paw IN-PLACE pivot to RIGHT, completed over the next0.6-0.8s. Body center stays at the pressed tuft LEFT of berry and RIGHT of trunk. Hurt puzzled eyes seek an offscreen RIGHT response, jaw stays closed and tense, mouth corners level/down. Same20cm four-paw anatomy and about8.3percent frame height in the natural stance. No new jump/run, upright pose, foreground approach or reburial. Preserve the wet turf, pressed grass, high berry and scene.''',
'R25-FLAP':'''Image1=initial20cm FOUR-paw creature in the closer SIDE full-body reaction camera; Image2=ONE identity only; Image3=eventual rear-low muddy result at the SAME place. This visible change from the prior wide shot is a CAMERA CUT, not growth or a walk toward the lens. Maintain one fixed side camera and space around full tail, both wings at maximum spread and ground.0-1s hurt pride becomes ANNOYED: pressed upper eyelids, focused narrowed eyes, lower jaw clenched, DOWN mouth corners, nostrils briefly flare, wing roots tense. No smile or friendly tongue.1-1.35s one short inhale with limited rib motion, no balloon-like body inflation;1.35-1.65s paws brace/compress;1.65-1.95s two brisk effective wing downbeats with a short hind push.1.95-2.2s feet briefly clear ground about5cm; apex passes immediately, proud chin for a blink, then loss of wing coordination.2.2-2.45s rear contacts soft damp grass/mud, front paws take real weight, local blades bend and mud depresses with a FEW tiny rear/belly specks.2.45-2.9s short recoil and prompt wing recovery/folding.2.9-6s rear remains down with chest supported by front paws: brief unhappy breath, inspect actual contact patch, front paw regrips wet grass, then eyes turn OFFSCREEN RIGHT seeking approval. Same20cm skull/torso/limb dimensions throughout. The macro camera gives roughly47-50percent frame height in the normal stance; do not enlarge the animal further. No upright human sit, slow descent, hover, new berry attempt, tree climb or extra actor.''',
'R25-END':'''Image1=actual rear-low/front-paw-supported muddy state in the closer SIDE camera; Image2=ONE identity only. Stay at the same tuft facing RIGHT, with original20cm anatomy and roughly47-50percent frame height at this intentional macro camera. Nose grass flecks and rear mud persist. First lift eyes/chin briefly seeking approval; hopeful eyes become hurt and stubborn, upper lids lower, jaw tightens, DOWN mouth corners. Wings draw close; both front paws visibly load damp grass. A short deliberate turn RIGHT/DOWN ends the shot during the living reaction, not a freeze. Brief natural breath and a tail-tip flick, no long posing, smile, extra jump, rise to standing, forward move or new actor.'''
}
for j in JOBS:
    if j['id'] in CHANGES:j['action']=CHANGES[j['id']]

ASSETS={k:OLD['assets'][k] for k in ['CHAR-DRAGON-THREEVIEW','CHAR-GIRL-THREEVIEW','VOICE-GIRL','NAT-LAUGH','ENV','TREE','RUN','MIA','BERRY']}
repair=P/'02-素材/镜头/固定果树单主体25/修复03'
ASSETS.update({k:str(repair/name) for k,name in {
    'LOW':'幼龙侧卧晒太阳-原体量十厘米低位08.png',
    'APEX':'幼龙小跳落空-完整气隙与恒定体量04.png',
    'BURY':'幼龙落草接触-原体量与压倒草叶04.png',
    'TURN':'幼龙原落点转右-四足二十厘米04.png',
    'REACT':'幼龙恼怒-微距实拍与同场曝光02.png',
    'END':'幼龙后躯跌坐-原体量与泥草支撑01.png'}.items()})

calibration=json.loads((P/'03-制作/静态精修/固定果树25-确定性10/连通精修参数10.json').read_text(encoding='utf-8'))
ASSETS.update({k:v['path'] for k,v in calibration['outputs'].items()})

def main():
    C.mkdir(parents=True,exist_ok=True)
    old=yaml.safe_load((P/'素材清单-固定果树单主体25.yaml').read_text(encoding='utf-8'))
    reviewfile=P/'05-检查与验收/固定果树单主体25-修复04-实际图片验收.json'
    reviews=json.loads(reviewfile.read_text(encoding='utf-8')) if reviewfile.exists() else {'assets':{}}
    assets={}
    for k,path in ASSETS.items():
        f=Path(path)
        item=copy.deepcopy(old['assets'][k]) if k in {'CHAR-DRAGON-THREEVIEW','CHAR-GIRL-THREEVIEW','VOICE-GIRL','NAT-LAUGH'} else {'kind':'scene' if k in {'ENV','TREE','BERRY'} else 'keyframe','required':False,'purpose':'photoreal_single_subject_or_environment'}
        item.update(path=f.relative_to(P).as_posix(),sha256=sha(f))
        if k not in {'CHAR-DRAGON-THREEVIEW','CHAR-GIRL-THREEVIEW','VOICE-GIRL','NAT-LAUGH'}:
            rv=reviews['assets'].get(k,{})
            item['state']='ready' if rv.get('status')=='PASS' and rv.get('sha256')==sha(f) else 'planned'
            item['assistant_review']='actual_photo_scope_pending' if item['state']!='ready' else str(reviewfile.relative_to(P))
            item['user_acceptance']='assistant_reviewed_derivative_not_individually_user_accepted'
        assets[k]=item
    jobs=[];shots={}
    for i,j in enumerate(JOBS):
        style,stylesha=METHOD['style']() # current style is read for EVERY independent video request
        world=METHOD['WORLD']
        if j['id'] in {'R25-FLAP','R25-END'}:
            world='Same pressed soft tuft, damp earth and local short grass about3cm high. Same TWO timber-and-aged-plaster cottages soft behind LEFT and mature tree behind RIGHT, same sky/daylight. The fixed100cm berry sapling and attached70cm-high berry stay outside this closer crop to LEFT; never lower/reposition them to force them visible.'
        actor=METHOD['MIA'] if j['actor']=='MIA' else (METHOD['DRAGON']+world if j['actor']=='GULU' else world)
        prompt=j['action']+'\n'+actor+'\n'+METHOD['SPEED']+'\n'+METHOD['film_for'](j['actor'])
        if not j['audio']:prompt+='\n'+METHOD['SILENT']
        prompt+='\n16:9 full-frame composition. No captions, lettering or black bars.'
        assert len(prompt)<20000 and not any('\u4e00'<=c<='\u9fff' for c in prompt)
        sid=j['id'].replace('R25-','R25R4-')
        bindings={f'ref_image_{n}':k for n,k in enumerate(j['refs'])}
        bindings.update({f'ref_audio_{n}':k for n,k in enumerate(j['audio'])})
        used=list(bindings.values())
        if j['actor']=='GULU':assert not j['audio'] and not set(used)&{'MIA','CHAR-GIRL-THREEVIEW','VOICE-GIRL','NAT-LAUGH'}
        if j['actor']=='MIA':assert not set(used)&{'CHAR-DRAGON-THREEVIEW','LOW','RUN','APEX','BURY','TURN','REACT','END'}
        inputs={slot:str(Path(ASSETS[k])) for slot,k in bindings.items()}
        inputs.update(prompt=prompt,duration=j['seconds'],resolution='768p横',seed=202611142540+i)
        cfg={'workflow_id':'minimax_h3_zm_u30','materials_manifest':str(MANIFEST),'shot_id':sid,'inputs':inputs,'output_dir':str(P/'04-输出/原始片段/固定果树单主体25修复04'/sid),'timeout':3600,'poll_interval':15}
        config=C/(sid+'-u30-执行04.yaml');config.write_text(yaml.safe_dump(cfg,allow_unicode=True,sort_keys=False,width=110),encoding='utf-8')
        pf=C/(sid+'-视频英文正文04.txt');pf.write_text(prompt,encoding='utf-8',newline='\n')
        shots[sid]={'speakers':j['speakers'],'voice_bindings':{'ref_audio_0':'CHAR-GIRL'} if j['speakers'] else {},'required_assets':used,'reference_bindings':bindings,'visible_actor':j['actor'],'authorization_ref':OLD['authorization']}
        jobs.append({**j,'id':sid,'prompt':prompt,'prompt_sha256':sha(pf),'config':config.relative_to(P).as_posix(),'config_sha256':sha(config),'reference_bindings':bindings,'style_sha256':stylesha})
    docs=copy.deepcopy(old['documents'])
    manifest={**{k:copy.deepcopy(old[k]) for k in ['schema_version','voice_policy','creative_confirmation']},'documents':docs,'assets':assets,'shots':shots}
    MANIFEST.write_text(yaml.safe_dump(manifest,allow_unicode=True,sort_keys=False,width=120),encoding='utf-8')
    edl=[('ENV',0,2,False),('MIA-A',0,3,False),('LOW',0,3,False),('ENV',2,3,False),('RUN',0,6,False),('MIA-A',3,5,True),('OUT',0,2,False),('MIA-B',0,9,True),('FLAP',0,6,False),('MIA-A',5,7,True),('END',0,4,False)]
    timeline=[];pos=0
    for sid,a,b,audio in edl:
        timeline.append({'shot_id':'R25R4-'+sid,'in':a,'out':b,'timeline_start':pos,'timeline_end':pos+b-a,'audio':audio});pos+=b-a
    assert pos==40
    pack={'stage':'PREPARED_ACTUAL_INPUTS_FOR_FINAL_REVIEW','plan':OLD['plan'],'plan_sha256':OLD['plan_sha256'],'authorization':OLD['authorization'],'repair_authorization':'06-记录/用户确认/前四十秒重构25-实际修复授权03.json','style':style,'style_sha256':stylesha,'assets':ASSETS,'jobs':jobs,'edl':timeline,'total_seconds':40,'post_retiming':False,'whitebox_video':False,'single_actor_per_unit':True,'video_submissions':0,'gate':'Actual-photo acceptance, full review and cinematic final audit are required. A draft config is not authorization to bypass a failed asset.'}
    dest=C/'制作包04.json';dest.write_text(json.dumps(pack,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'units':len(jobs),'native_source_seconds':sum(j['seconds'] for j in jobs),'edit_seconds':pos,'photos_not_ready':[k for k,a in assets.items() if a['state']!='ready'],'stage':pack['stage'],'package':str(dest)},ensure_ascii=False))
if __name__=='__main__':main()
