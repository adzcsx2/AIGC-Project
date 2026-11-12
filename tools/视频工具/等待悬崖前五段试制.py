from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime
import json
import threading

from autodl_video.runner import VideoProject

root = Path(__file__).resolve().parents[2]
work = root / 'projects/悬崖上的小气球'
record = work / '06-记录/视频生成/前五段试制01-任务与结果.json'
batch = json.loads(record.read_text(encoding='utf-8'))
lock = threading.Lock()

def save():
    batch['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding='utf-8')

def wait_one(row):
    last = None
    def update(data):
        nonlocal last
        status = data.get('status')
        if status == last:
            return
        last = status
        with lock:
            row['remote_status'] = status
            save()
            print(json.dumps({'task_id': row['task_id'], 'status': status}, ensure_ascii=False), flush=True)
    try:
        result = VideoProject(root).resume(row['task_id'], timeout=7200, poll_interval=15, on_update=update)
        with lock:
            row.update(result, state='downloaded')
            save()
            print(json.dumps({'task_id': row['task_id'], 'downloaded': result['files']}, ensure_ascii=False), flush=True)
    except Exception as exc:
        with lock:
            row.update(state='resume_error_do_not_resubmit', error=str(exc))
            save()
            print(json.dumps({'task_id': row['task_id'], 'error': str(exc)}, ensure_ascii=False), flush=True)

with ThreadPoolExecutor(max_workers=5) as pool:
    jobs = [pool.submit(wait_one, row) for row in batch['tasks'] if row.get('task_id') and row.get('state') != 'downloaded']
    for job in as_completed(jobs):
        job.result()
print(json.dumps({'downloaded': sum(row.get('state') == 'downloaded' for row in batch['tasks']), 'total': len(batch['tasks'])}, ensure_ascii=False), flush=True)
