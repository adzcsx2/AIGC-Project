"""Derive a labeled optical-transition preview from the verified neutral geometry frames."""
import argparse
import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from project_tool_safety import read_json_bound, require_hash
from video_tools import decode_check, executable, probe
from whitebox_saved import project_path, publish_new, write_json_new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True)
    ap.add_argument('--config', required=True)
    a = ap.parse_args()
    p = Path(a.project).resolve()
    cp = project_path(p, a.config, exists=True)
    c, ch = read_json_bound(cp)
    report = project_path(p, c['independent_report'], exists=True)
    measured, mh = read_json_bound(report)
    if measured['status'] != 'passed_for_spatial_camera_proxies_only':
        raise ValueError('Independent spatial check has not passed')
    blend = project_path(p, c['blend'], exists=True)
    require_hash(blend, measured['blend_sha256'])
    frame_dir = project_path(p, c['base_frames'])
    frames = [project_path(p, str(frame_dir/f'帧-{i:06d}.png'), exists=True) for i in range(720)]
    destination = project_path(p, c['output_video'])
    output_frames = project_path(p, c['output_frames'])
    record = project_path(p, c['record'])
    for path in [destination, output_frames, record]:
        if path.exists():
            raise FileExistsError(path)
    inputs = [{'path': str(f.relative_to(p)), 'sha256': hashlib.sha256(f.read_bytes()).hexdigest()} for f in frames]
    output_frames.mkdir(parents=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    aerial = Image.open(frames[239]).convert('RGB')
    w, h = aerial.size
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', max(14, h//33))
    transition_start = round(c.get('transition_start_seconds', 10)*24)
    convergence_end = round(c.get('convergence_end_seconds', 14)*24)
    reveal_start = round(c.get('reveal_start_seconds', 14)*24)
    reveal_end = round(c.get('reveal_end_seconds', 18)*24)
    end_bounds = measured['samples'][convergence_end]['iris_bounds']
    end_w = max(2, (end_bounds[2]-end_bounds[0])*w*.82)
    end_h = max(2, (end_bounds[3]-end_bounds[1])*h*.80)
    def pixel_box(bounds):
        x0, y0, x1, y1 = bounds
        return [round(x0*w), round((1-y1)*h), round(x1*w), round((1-y0)*h)]
    for i, frame in enumerate(frames):
        base = Image.open(frame).convert('RGB')
        t = i/24
        if transition_start <= i < reveal_end:
            b = measured['samples'][i]['iris_bounds']
            cx, cy = (b[0]+b[2])*w/2, (1-(b[1]+b[3])/2)*h
            if i < convergence_end:
                u = (i-transition_start)/(convergence_end-transition_start)
                ww = w+(end_w-w)*u
                hh = h+(end_h-h)*u
                cx = w/2+(cx-w/2)*u
                cy = h/2+(cy-h/2)*u
                roundness = u
                alpha = 1-.24*u
            else:
                ww = max(2, (b[2]-b[0])*w*.82)
                hh = max(2, (b[3]-b[1])*h*.80)
                roundness = 1
                alpha = .76*min(1, ww/(w*.055))
            if ww >= 2 and hh >= 2:
                iw, ih = max(2, round(ww)), max(2, round(hh))
                reflected = aerial.resize((iw, ih), Image.Resampling.LANCZOS)
                mask = Image.new('L', (iw, ih), 0)
                md = ImageDraw.Draw(mask)
                if roundness >= .999:
                    md.ellipse((0, 0, iw-1, ih-1), fill=round(alpha*255))
                else:
                    md.rounded_rectangle((0, 0, iw-1, ih-1),
                                         radius=round(min(iw, ih)*.5*roundness), fill=round(alpha*255))
                untouched = base.copy()
                base.paste(reflected, (round(cx-iw/2), round(cy-ih/2)), mask)
                # Restore the actual rendered slit mark, so this remains a recognizable eye.
                pupil_box = pixel_box(measured['samples'][i]['pupil_bounds'])
                pm = Image.new('L', (w, h), 0)
                ImageDraw.Draw(pm).ellipse(pupil_box, fill=round(255*min(1, max(0, (t-11)/1.2))))
                base = Image.composite(untouched, base, pm)
        if t < 3.2:
            label = '① 贴脸互蹭：圆柱与锚点只表达空间关系'
        elif t < 4:
            label = '闭眼微笑：真实表情由视频模型完成'
        elif t < 10:
            label = '② 后退升空：人物保持实体大小，最终缩成小点'
        elif i < reveal_start:
            label = '③ 广景先汇聚到眼睛里：光学转场预演'
        elif i < reveal_end:
            label = c.get('reveal_label', '④ 再从同一只眼睛拉远，揭示巨龙整体体积')
        elif t < 26.5:
            label = f'⑤ 空间飞行绕行一圈：进度 {(t-18)/8.5:.0%}'
        else:
            label = '⑥ 完成一圈后飞远：镜头柔和后撤收尾'
        draw = ImageDraw.Draw(base)
        draw.rectangle((0, h-35, w, h), fill=(20, 23, 25))
        draw.text((12, h-30), label, fill='white', font=font)
        draw.text((w-105, h-30), f'{t:05.2f}s', fill='#cfdbdf', font=font)
        base.save(output_frames/f'预演-{i:06d}.png')
    def validate():
        require_hash(cp, ch)
        require_hash(report, mh)
        require_hash(blend, measured['blend_sha256'])
        for item in inputs:
            require_hash(p/item['path'], item['sha256'])
    with tempfile.TemporaryDirectory(prefix='.入眼预演-', dir=destination.parent) as folder:
        staging = Path(folder)/destination.name
        subprocess.run([executable('ffmpeg'), '-nostdin', '-v', 'error', '-n', '-framerate', '24',
                        '-i', str(output_frames/'预演-%06d.png'), '-c:v', 'libx264', '-crf', '18',
                        '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(staging)], check=True)
        decode_check(staging)
        meta = probe(staging)
        if int(meta['video']['nb_frames']) != 720 or abs(meta['duration']-30) > .02:
            raise ValueError('Optical preview timeline differs from the saved scene')
        validate()
        publish_new(staging, destination, p)
    result = {'status': 'derived_optical_preview_encoded', 'config_sha256': ch,
              'independent_report_sha256': mh, 'blend_sha256': measured['blend_sha256'],
              'source_frames': inputs, 'frames': 720, 'fps': 24, 'duration': 30,
              'output': str(destination.relative_to(p)),
              'output_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
              'method': 'Neutral geometry frames plus a gray aerial-frame contraction into the measured iris bounds, followed by the measured 3D eye-to-body pullback.',
              'limitation': 'Labeled review-only optical schematic; not an untouched neutral model guide, not proof of photoreal expression or final generated transition.'}
    write_json_new(record, result, p)
    print(json.dumps({k: v for k, v in result.items() if k != 'source_frames'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
