"""Submit the eight explicitly authorized R25 units once; never retries POST."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib,json
from autodl_video.runner import VideoProject

R=Path(__file__).resolve().parents[2];P=R/'projects/悬崖上的小气球'
C=P/'03-制作/生成配置/固定果树单主体25修复04'
F=P/'06-记录/视频生成/固定果树单主体25-修复04-任务与结果01.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(d):
    t=F.with_suffix('.tmp');t.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');t.replace(F)
def main():
    assert not F.exists(),'Batch already initialized: inspect recorded task IDs/attempts; NEVER resubmit automatically.'
    a=P/'05-检查与验收/固定果树单主体25-修复04-完整复审09-10与生成前总审计.json'
    audit=json.loads(a.read_text(encoding='utf-8'));assert audit['status']=='CLEAN_FOR_AUTHORIZED_GENERATION'
    pack=C/'制作包04.json';assert sha(pack)==audit['package_sha256']
    assert sha(P/'素材清单-固定果树单主体25-修复04.yaml')==audit['manifest_sha256']
    d=json.loads(pack.read_text(encoding='utf-8'));assert len(d['jobs'])==8 and sum(j['seconds'] for j in d['jobs'])==40
    for j in d['jobs']:assert sha(P/j['config'])==j['config_sha256']
    F.parent.mkdir(parents=True,exist_ok=True)
    record={'stage':'SUBMITTING_AUTHORIZED_EIGHT_ONCE','created_at':datetime.now(timezone.utc).isoformat(),'package':str(pack),'package_sha256':sha(pack),'audit':str(a),'audit_sha256':sha(a),'auto_rerolls':False,'jobs':[{**{k:j[k] for k in ['id','seconds','config','config_sha256','prompt_sha256']},'state':'PENDING_FIRST_SUBMISSION'} for j in d['jobs']]}
    save(record)
    def submit(j):
        try:return {'state':'SUBMITTED','response':VideoProject(R).generate(P/j['config'],wait=False)}
        except Exception as exc:return {'state':'ERROR_DO_NOT_RESUBMIT','error':str(exc)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(submit,j):i for i,j in enumerate(d['jobs'])}
        for future in as_completed(futures):
            i=futures[future];r=future.result();record['jobs'][i].update(r)
            if r.get('response',{}).get('task_id'):record['jobs'][i]['task_id']=r['response']['task_id']
            save(record);print(json.dumps({'id':record['jobs'][i]['id'],**r},ensure_ascii=False),flush=True)
    record['stage']='ALL_SUBMITTED_WAIT_SAME_IDS' if all(j['state']=='SUBMITTED' for j in record['jobs']) else 'SUBMISSION_ERRORS_INSPECT_DO_NOT_RETRY'
    save(record);print('BATCH '+record['stage'],flush=True)
if __name__=='__main__':main()
