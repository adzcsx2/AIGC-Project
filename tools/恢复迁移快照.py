"""Reconstruct pre-migration files in a new directory; never overwrite active work."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    state = root / '.autodl/reorganization/20261110'
    ap = argparse.ArgumentParser()
    ap.add_argument('--destination', type=Path, required=True)
    ap.add_argument('--only', help='可选：快照内原始相对路径，恢复单个文件')
    args = ap.parse_args()
    destination = args.destination.resolve()
    if destination.exists():
        raise ValueError('恢复目录必须不存在，不能覆盖现有作品')
    entries = json.loads((state/'snapshot.json').read_text('utf-8'))
    if args.only:
        entries = [e for e in entries if e['path'] == args.only.replace('\\', '/')]
        if not entries:
            raise ValueError('快照中没有该路径')
    for entry in entries:
        target = (destination/entry['path']).resolve()
        if not target.is_relative_to(destination):
            raise ValueError('快照路径越界')
        source = state/'objects'/entry['sha256']
        with source.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != entry['sha256']:
                raise ValueError('备份哈希不匹配')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    print(json.dumps({'restored_files': len(entries), 'destination': str(destination)}))


if __name__ == '__main__':
    main()
