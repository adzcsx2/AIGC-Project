"""Archive diagnostics and export the existing R29 result at native speed."""
from fractions import Fraction
from pathlib import Path
import hashlib
import json
import subprocess
import sys

from PIL import Image, ImageDraw

R = Path(__file__).resolve().parents[2]
P = R / 'projects/悬崖上的小气球'


def run(args):
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:])
    return result.stdout


def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-count_frames', '-show_streams',
                           '-show_format', '-of', 'json', str(path)]))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    task = json.loads((P / '06-记录/视频生成/身高图四参考测试29-u30任务01.json').read_text(encoding='utf-8'))
    source = Path(task['files'][0])
    source_meta = probe(source)
    video = next(s for s in source_meta['streams'] if s['codec_type'] == 'video')
    assert Fraction(video['avg_frame_rate']) == 24 and int(video['nb_read_frames']) >= 120
    width, height = int(video['width']), int(video['height'])
    crop_height = (width * 9 // 16) // 2 * 2
    assert crop_height <= height
    crop = f'crop={width}:{crop_height}:0:{(height-crop_height)//2}'
    work = P / '05-检查与验收/身高图四参考测试29-源片检查'
    work.mkdir(parents=True, exist_ok=True)
    run(['ffmpeg', '-v', 'error', '-n', '-i', str(source), '-vf',
         'select=not(mod(n\\,12)),scale=448:-2', '-fps_mode', 'vfr', '-frames:v', '12',
         str(work / '原生帧-%02d.png')])
    frames = sorted(work.glob('原生帧-*.png'))
    sheet = Image.new('RGB', (1344, 280 * ((len(frames)+2)//3)), (20, 22, 25))
    draw = ImageDraw.Draw(sheet)
    for n, path in enumerate(frames):
        x, y = n % 3 * 448, n // 3 * 280
        sheet.paste(Image.open(path).convert('RGB'), (x, y))
        draw.text((x+5, y+259), f'R29 actual native {n/2:.2f}s', fill='white')
    sheet_path = work / '身高图四参考-原生动作检查01.jpg'
    sheet.save(sheet_path, quality=93)
    out = P / '04-输出/成片/身高图四参考测试29'
    out.mkdir(parents=True, exist_ok=True)
    native = out / '身高图四参考-五秒原速01.mp4'
    final = out / '身高图四参考-五秒试看60帧01.mp4'
    assert not native.exists() and not final.exists(), 'Preserve existing exports.'
    run(['ffmpeg', '-v', 'error', '-n', '-i', str(source), '-vf',
         f'trim=start_frame=0:end_frame=120,setpts=PTS-STARTPTS,{crop},setsar=1', '-an',
         '-c:v', 'libx264', '-crf', '16', '-preset', 'fast', '-pix_fmt', 'yuv420p',
         '-fps_mode', 'passthrough', '-enc_time_base', '1:24', '-video_track_timescale',
         '24000', '-movflags', '+faststart', str(native)])
    run(['ffmpeg', '-v', 'error', '-i', str(native), '-f', 'null', '-'])
    native_meta = probe(native)
    v = next(s for s in native_meta['streams'] if s['codec_type'] == 'video')
    assert int(v['nb_read_frames']) == 120 and float(v['duration']) == 5
    metadata = {
        'task_id': task['task_id'], 'source': str(source), 'source_sha256': sha(source),
        'source_probe': source_meta, 'native': str(native), 'native_sha256': sha(native),
        'native_probe': native_meta, 'selection_native_frames': [0, 120], 'crop': crop,
        'post_retiming': False, 'audio': 'Silent test; no audio track. Original source preserved.',
        'native_action_sheet': str(sheet_path), 'creative_acceptance': 'PENDING_USER_REVIEW',
    }
    record = P / '06-记录/后期制作/身高图四参考测试29-原速导出01.json'
    record.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'native': str(native), 'sheet': str(sheet_path)}, ensure_ascii=False), flush=True)
    rife = run([sys.executable, '-X', 'utf8', str(R / 'tools/视频工具/补帧.py'), str(native),
                '--output-stem', '身高图四参考-五秒试看60帧01'])
    assert final.is_file(), rife[-2000:]
    final_meta = probe(final)
    v = next(s for s in final_meta['streams'] if s['codec_type'] == 'video')
    assert v['avg_frame_rate'] == '60/1' and int(v['nb_read_frames']) == 300 and float(v['duration']) == 5
    assert not any(s['codec_type'] == 'audio' for s in final_meta['streams'])
    metadata.update(preview=str(final), preview_sha256=sha(final), final_probe=final_meta,
                    interpolation='RIFE v4.6 TensorRT FP16 Turbo; duration/speed preserved')
    record.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'preview': str(final), 'frames': 300, 'fps': 60, 'seconds': 5,
                      'sha256': sha(final)}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
