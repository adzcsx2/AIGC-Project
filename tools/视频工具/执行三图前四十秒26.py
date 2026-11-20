"""Run the approved R26 batch once; resume GET/download by recorded task IDs."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import sys

from autodl_video.client import SUCCESS, task_status
from autodl_video.config import atomic_json
from autodl_video.runner import VideoProject

R = Path(__file__).resolve().parents[2]
P = R / 'projects/悬崖上的小气球'
PACK = P / '03-制作/生成配置/前四十秒三图输入26/三图执行包02.json'
GATE = P / '05-检查与验收/前四十秒三图输入26-提交版本复核02.json'
BATCH = P / '06-记录/视频生成/三图输入26-任务与结果01.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def submit():
    assert not BATCH.exists(), 'Batch already initialized; inspect IDs/attempts. Never resubmit.'
    gate = json.loads(GATE.read_text(encoding='utf-8'))
    assert gate['status'] == 'PASS_UNCHANGED_REVIEWED_CONTENT_AUTHORIZED_EIGHT_ONCE'
    assert sha(PACK) == gate['execution_package_sha256']
    pack = json.loads(PACK.read_text(encoding='utf-8'))
    assert sha(pack['materials_manifest']) == gate['manifest_sha256']
    assert len(pack['jobs']) == 8 and sum(j['seconds'] for j in pack['jobs']) == 40
    for job in pack['jobs']:
        assert sha(job['config']) == job['config_sha256']
        assert sha(job['prompt_path']) == job['prompt_sha256']
    record = {
        'stage': 'SUBMITTING_AUTHORIZED_EIGHT_ONCE',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'package': str(PACK), 'package_sha256': sha(PACK),
        'gate': str(GATE), 'gate_sha256': sha(GATE), 'auto_rerolls': False,
        'jobs': [{**{k: j[k] for k in ('id', 'seconds', 'config', 'config_sha256', 'prompt_sha256')},
                  'state': 'PENDING_FIRST_SUBMISSION'} for j in pack['jobs']],
    }
    atomic_json(BATCH, record)

    def one(job):
        try:
            result = VideoProject(R).generate(job['config'], wait=False)
            return {'state': 'SUBMITTED', 'task_id': result['task_id'], 'response': result}
        except Exception as exc:
            return {'state': 'ERROR_DO_NOT_RESUBMIT', 'error': str(exc)}

    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {pool.submit(one, job): i for i, job in enumerate(pack['jobs'])}
        for future in as_completed(pending):
            i = pending[future]
            result = future.result()
            record['jobs'][i].update(result)
            atomic_json(BATCH, record)
            print(json.dumps({'id': record['jobs'][i]['id'], **result}, ensure_ascii=False), flush=True)
    record['stage'] = ('ALL_SUBMITTED_WAIT_SAME_IDS' if all(j['state'] == 'SUBMITTED' for j in record['jobs'])
                       else 'SUBMISSION_ERRORS_INSPECT_NO_AUTOMATIC_RETRY')
    atomic_json(BATCH, record)
    print(record['stage'], flush=True)


def status():
    record = json.loads(BATCH.read_text(encoding='utf-8'))

    def one(job):
        if job.get('files'):
            assert all(Path(f).is_file() for f in job['files'])
            return {'native_status': 'ARCHIVED'}
        if not job.get('task_id'):
            return {'native_status': 'NO_RECORDED_ID', 'error': job.get('error')}
        try:
            worker = VideoProject(R)
            response = worker.status(job['task_id'])
            state = task_status(response)
            if state in SUCCESS:
                result = worker.download(job['task_id'])
                return {'native_status': state, 'files': result['files']}
            return {'native_status': state, 'server_message': response.get('msg') or response.get('message')}
        except Exception as exc:
            return {'native_status': 'READ_OR_DOWNLOAD_ERROR', 'error': str(exc)}

    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {pool.submit(one, job): i for i, job in enumerate(record['jobs'])}
        for future in as_completed(pending):
            i = pending[future]
            result = future.result()
            record['jobs'][i].update(result)
            atomic_json(BATCH, record)
            print(json.dumps({'id': record['jobs'][i]['id'], **result}, ensure_ascii=False), flush=True)
    record['stage'] = ('ALL_EIGHT_ARCHIVED' if all(j.get('files') for j in record['jobs'])
                       else 'WAIT_EXISTING_IDS_OR_INSPECT_FAILURES')
    atomic_json(BATCH, record)


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) == 2 else ''
    if action == 'submit':
        submit()
    elif action == 'status':
        status()
    else:
        raise SystemExit('Use submit ONCE or status (GET/download only).')
