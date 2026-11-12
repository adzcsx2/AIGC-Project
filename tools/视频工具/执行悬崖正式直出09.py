"""Bind, validate, submit once, and resume the authorized five R09 units."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import hashlib
import json
import threading
import yaml
from PIL import Image
from autodl_video.runner import VideoProject

ROOT = Path(__file__).resolve().parents[2]
P = ROOT/'projects/悬崖上的小气球'
TAG = '正式五段直出09'
PACK = P/f'03-制作/制作计划/{TAG}/制作包05-实际输入.json'
JOBS = P/f'06-记录/视频生成/{TAG}-任务与结果01.json'
LOCK = threading.Lock()


def read(f):
    return json.loads(f.read_text('utf-8'))


def save(f, value):
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def sha(f):
    return hashlib.sha256(f.read_bytes()).hexdigest()


def bind():
    assert not JOBS.exists(), 'Never change submitted inputs'
    pack = read(P/f'03-制作/制作计划/{TAG}/制作包04-最终文案候选.json')
    hist = read(P/f'06-记录/图片生成/{TAG}-实际图片请求与筛选01.json')
    mp = P/'素材清单-三视图更新01-资产归位01.yaml'
    m = yaml.safe_load(mp.read_text('utf-8'))
    chosen = {x['id']: x for x in hist['requests'] if x.get('selected_path')}
    assert len(chosen) == 5
    for aid, item in chosen.items():
        f = P/item['selected_path']
        assert sha(f) == item['sha256']
        m['assets'][aid] = dict(kind='scene',required=False,path=item['selected_path'],state='ready',sha256=sha(f),
                                dimensions=list(Image.open(f).size),purpose='full_scene_scale_pose' if aid!='R09-ANGER' else 'face_expression_only',
                                review_basis='Actual returned image visually inspected; see R09 actual-input review and scale evidence.',
                                user_review='assistant_checked_under_current_generation_authorization',
                                generation_record=f'06-记录/图片生成/{TAG}-实际图片请求与筛选01.json')
        pack['sources'][aid] = item['selected_path']
    # Face reference must not overwrite the preceding seated/muddy body state or folded-wing action.
    pack['units'][4]['prompt'] = pack['units'][4]['prompt'].replace(
        'Image 7 is GULU later ANGRY FACE at C looking toward MIA offscreen-RIGHT;',
        'Image 7 supplies ONLY the later ANGRY FACE at C looking toward MIA offscreen-RIGHT, not its low body pose or displayed wing spread;')
    pack['images'] = [dict(id=k,prompt=v['prompt'],refs=v['refs'],path=v['selected_path'],sha256=v['sha256']) for k,v in chosen.items()]
    for u in pack['units']:
        ids = pack['common_asset_ids']+u['ids']
        bindings = {f'ref_image_{i}': aid for i,aid in enumerate(ids)}
        if u['dialogue']:
            bindings['ref_audio_0'] = 'VOICE-GIRL'
        sid = f"CLIFF-{u['n']:02d}-U30-R09"
        m['shots'][sid] = dict(speakers=['CHAR-GIRL'] if u['dialogue'] else [],
                              voice_bindings={'ref_audio_0':'CHAR-GIRL'} if u['dialogue'] else {},
                              required_assets=list(bindings.values()),reference_bindings=bindings,purpose=u['name'],
                              authorization_ref=pack['authorization'])
        inputs = dict(prompt=u['prompt'],duration=u['duration'],resolution=pack['resolution'])
        pins = {}
        for field, aid in bindings.items():
            f = (P/m['assets'][aid]['path']).resolve()
            inputs[field] = str(f)
            pins[field] = dict(id=aid,path=str(f),sha256=sha(f))
        cfg = dict(workflow_id=pack['workflow'],materials_manifest='../../../素材清单-三视图更新01-资产归位01.yaml',shot_id=sid,
                   inputs=inputs,output_dir=str((P/f"04-输出/原始片段/{TAG}/片段{u['n']:02d}").resolve()),timeout=3600,poll_interval=15)
        cp = P/f"03-制作/生成配置/{TAG}/片段{u['n']:02d}-{u['name']}-执行01.yaml"
        cp.parent.mkdir(parents=True,exist_ok=True)
        cp.write_text(yaml.safe_dump(cfg,allow_unicode=True,sort_keys=False,width=100),encoding='utf-8')
        u.update(shot_id=sid,config_path=cp.relative_to(P).as_posix(),config_sha256=sha(cp),reference_bindings=bindings,actual_input_pins=pins)
    mp.write_text(yaml.safe_dump(m,allow_unicode=True,sort_keys=False,width=100),encoding='utf-8')
    pack['state'] = 'ACTUAL_INPUTS_BOUND_PENDING_FINAL_REVIEW'
    save(PACK,pack)
    results=[]
    for u in pack['units']:
        preview=VideoProject(ROOT).generate(P/u['config_path'],dry_run=True)
        results.append(dict(n=u['n'],valid=True,config_sha256=u['config_sha256']))
    save(P/f'05-检查与验收/{TAG}-离线配置检查01.json',results)
    print(json.dumps(dict(bound=5,validated=len(results),packet_sha256=sha(PACK)),ensure_ascii=False),flush=True)


def submit():
    pack = read(PACK)
    review = read(P/f'05-检查与验收/{TAG}-实际提交review五轮02.json')
    assert review['final_status']=='CLEAN' and review['completed_rounds']==5
    assert review['final_packet_sha256']==sha(PACK)
    total = read(P/f'05-检查与验收/{TAG}-电影级生成前总审计03.json')
    assert total['status']=='PASS' and total['packet_sha256']==sha(PACK)
    assert not JOBS.exists(), 'Job record exists: resume IDs, never submit again'
    doc = dict(tag=TAG,authorization=pack['authorization'],packet_sha256=sha(PACK),jobs=[],one_submission_per_unit=True)
    save(JOBS,doc)
    # Sequential submission; independent remote jobs then run together.
    for u in pack['units']:
        assert sha(P/u['config_path'])==u['config_sha256']
        row = dict(n=u['n'],config_path=u['config_path'],state='submitting_do_not_retry')
        doc['jobs'].append(row);save(JOBS,doc)
        try:
            result=VideoProject(ROOT).generate(P/u['config_path'],wait=False)
            row.update(result,state='submitted');save(JOBS,doc)
            print(json.dumps(dict(n=u['n'],task_id=row['task_id'],status=row.get('status')),ensure_ascii=False),flush=True)
        except Exception as exc:
            row.update(error=str(exc),state='submission_error_do_not_retry');save(JOBS,doc)
            raise
    auth=P/pack['authorization'];a=read(auth);a['video_submissions_used']=len(doc['jobs']);a['task_ids']=[x.get('task_id') for x in doc['jobs']];save(auth,a)


def wait():
    doc=read(JOBS)
    def one(row):
        if row.get('state')=='downloaded':
            return
        assert row.get('task_id'), 'Unknown submission result: investigate, never resubmit'
        last=None
        def update(data):
            nonlocal last
            if data.get('status')==last:return
            last=data.get('status')
            with LOCK:
                row['remote_status']=last;save(JOBS,doc)
                print(json.dumps(dict(n=row['n'],status=last)),flush=True)
        try:
            result=VideoProject(ROOT).resume(row['task_id'],timeout=7200,poll_interval=20,on_update=update)
            with LOCK:
                row.update(result,state='downloaded');save(JOBS,doc)
                print(json.dumps(dict(n=row['n'],downloaded=result.get('files')),ensure_ascii=False),flush=True)
        except Exception as exc:
            with LOCK:
                row.update(error=str(exc),state='resume_error_do_not_resubmit');save(JOBS,doc)
                print(json.dumps(dict(n=row['n'],error=str(exc)),ensure_ascii=False),flush=True)
    with ThreadPoolExecutor(max_workers=5) as pool:
        for future in as_completed([pool.submit(one,r) for r in doc['jobs']]):future.result()
    print(json.dumps(dict(downloaded=sum(r.get('state')=='downloaded' for r in doc['jobs']),total=len(doc['jobs']))),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['bind','submit','wait']);args=ap.parse_args()
    {'bind':bind,'submit':submit,'wait':wait}[args.action]()
