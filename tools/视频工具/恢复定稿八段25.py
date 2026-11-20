"""GET/download only for recorded R25 task IDs; no generate/submit path."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
from autodl_video.runner import VideoProject
from autodl_video.client import SUCCESS,task_status

R=Path(__file__).resolve().parents[2];P=R/'projects/悬崖上的小气球'
F=P/'06-记录/视频生成/固定果树单主体25-修复04-任务与结果01.json'
def main():
    record=json.loads(F.read_text(encoding='utf-8'));assert len(record['jobs'])==8
    def read(j):
        if j.get('files'):return {'native_status':'ARCHIVED','files':j['files']}
        if not j.get('task_id'):return {'native_status':'NO_RECORDED_ID','error':j.get('error')}
        try:
            v=VideoProject(R);d=v.status(j['task_id']);state=task_status(d)
            if state in SUCCESS:
                downloaded=v.download(j['task_id']);return {'native_status':state,'files':downloaded['files'],'result':downloaded}
            return {'native_status':state,'server_status':d.get('status'),'server_message':d.get('msg') or d.get('message')}
        except Exception as e:return {'native_status':'READ_OR_DOWNLOAD_ERROR','error':str(e)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(read,j):i for i,j in enumerate(record['jobs'])}
        for f in as_completed(futures):
            i=futures[f];result=f.result();record['jobs'][i].update(result)
            print(json.dumps({'id':record['jobs'][i]['id'],**result},ensure_ascii=False),flush=True)
            tmp=F.with_suffix('.tmp');tmp.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(F)
    record['stage']='ALL_EIGHT_ARCHIVED' if all(j.get('files') for j in record['jobs']) else 'WAIT_EXISTING_IDS_OR_INSPECT_FAILURES'
    tmp=F.with_suffix('.tmp');tmp.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(F)
    print('BATCH '+record['stage'],flush=True)
if __name__=='__main__':main()
