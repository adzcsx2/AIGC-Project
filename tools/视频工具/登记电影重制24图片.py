"""Archive a built-in imagegen result and its exact reviewed request."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('asset')
    ap.add_argument('source')
    ap.add_argument('--note', required=True)
    ap.add_argument('--status', default='REVIEWED_REFERENCE')
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[2]
    project = root / 'projects/悬崖上的小气球'
    package = json.loads((project/'03-制作/生成配置/前四十秒电影重制24/制作包01.json').read_text(encoding='utf-8'))
    spec = next(x for x in package['image_specs'] if x['id'] == args.asset)
    source = Path(args.source)
    target = project / spec['output']
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    log = project/'06-记录/图片生成/前四十秒电影重制24-实际请求与采用01.json'
    records = json.loads(log.read_text(encoding='utf-8')) if log.exists() else []
    records.append({'asset_id':args.asset,'output':spec['output'],'builtin_original':str(source),'sha256':sha(target),'prompt':spec['prompt'],'prompt_sha256':hashlib.sha256(spec['prompt'].encode()).hexdigest(),'reference_order':spec['refs'],'actual_inputs':[{'role':k,'path':package['assets'][k],'sha256':sha(package['assets'][k])} for k in spec['refs']],'result':args.status,'observed':args.note,'limitation':'RGB projection checks do not prove world centimeters or video size control.'})
    log.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'asset':args.asset,'output':str(target),'sha256':sha(target)},ensure_ascii=False))

if __name__ == '__main__':
    main()
