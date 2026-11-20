"""Assemble the four authorized u30 returns at native speed; no pose repair."""
import hashlib
import json
import subprocess
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT/'projects/悬崖上的小气球'

def run(args):
    r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
    if r.returncode:
        raise RuntimeError(r.stderr[-5000:])
    return r.stdout

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    package = json.loads((WORK/'03-制作/生成配置/前四十秒电影重制24/制作包01.json').read_text(encoding='utf-8'))
    downloads = json.loads((WORK/'06-记录/视频生成/前四十秒电影重制24-完成下载01.json').read_text(encoding='utf-8'))
    if len(downloads) != 4 or any(x['exit_code'] for x in downloads):
        raise ValueError('All four source files must finish first.')
    by_config = {x['config']:x for x in downloads}
    destination = WORK/'04-输出/成片/前四十秒电影重制24'
    destination.mkdir(parents=True, exist_ok=True)
    output = destination/'悬崖上的小气球-电影重制40秒-未达标审片版24帧01.mp4'
    if output.exists():
        raise ValueError('Preserve existing assembly; inspect before creating a new version.')
    args = ['ffmpeg','-v','error','-n']
    filters, sources, labels = [], [], []
    cursor = 0
    for n, job in enumerate(package['jobs']):
        paths = by_config[job['config']]['response']['files']
        source = next(Path(f) for f in paths if str(f).lower().endswith('.mp4'))
        metadata = json.loads(run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(source)]))
        video = next(s for s in metadata['streams'] if s['codec_type']=='video')
        rate = Fraction(video['avg_frame_rate'])
        count = job['seconds']*24
        if rate != 24 or int(video['nb_read_frames']) < count:
            raise ValueError(f'Inspect native duration/fps before editing: {source}')
        if video['width'] != 1344 or video['height'] not in (756,768):
            raise ValueError('Inspect native canvas; never resize a character layer.')
        if n and not any(s['codec_type']=='audio' for s in metadata['streams']):
            raise ValueError('Required dialogue/laughter track is missing.')
        args += ['-i',str(source)]
        filters.append(f'[{n}:v:0]trim=end_frame={count},setpts=PTS-STARTPTS,crop=1344:756:0:{(video["height"]-756)//2},setsar=1[v{n}]')
        sources.append({'shot_id':job['id'],'path':str(source),'sha256':sha(source),'probe':metadata,'source_start_seconds':0,'source_end_seconds':job['seconds'],'timeline_start_seconds':cursor,'timeline_end_seconds':cursor+job['seconds'],'retiming':False,'crop':'whole frame center to1344x756; no local scale/compositing'})
        cursor += job['seconds']
    args += ['-f','lavfi','-i','anullsrc=channel_layout=stereo:sample_rate=48000']
    for n, job in enumerate(package['jobs']):
        audio = '4:a:0' if n==0 else f'{n}:a:0'
        filters.append(f'[{audio}]atrim=duration={job["seconds"]},asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,afade=t=in:d=0.008,afade=t=out:st={job["seconds"]-.008}:d=0.008[a{n}]')
        labels.append(f'[v{n}][a{n}]')
    filters.append(''.join(labels)+'concat=n=4:v=1:a=1[v][a]')
    args += ['-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map','[v]','-map','[a]','-c:v','libx264','-preset','fast','-crf','16','-pix_fmt','yuv420p','-fps_mode','passthrough','-enc_time_base','1:24','-video_track_timescale','24000','-frames:v','960','-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-t','40','-movflags','+faststart',str(output)]
    run(args)
    run(['ffmpeg','-v','error','-i',str(output),'-f','null','-'])
    probe = json.loads(run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(output)]))
    video = next(s for s in probe['streams'] if s['codec_type']=='video')
    assert int(video['nb_read_frames'])==960 and Fraction(video['avg_frame_rate'])==24
    record = {'source_segments':sources,'output':str(output),'output_sha256':sha(output),'probe':probe,'cuts_seconds':[10,19,29],'post_speed_change':False,'first_unit_audio':'digital silence; this unit requires no sound','other_audio':'source performances retained,8ms click fades; no invented words or laugh splicing','music':'none','visual_status':'FAILED single-actor and planned-action adherence; raw review preview, not approved final','audio_perception_status':'not claimed heard; ASR indicates dialogue mismatch'}
    record['sha256']=record['output_sha256']
    record['seams']=[{'id':f'R24-SEAM-{n+1:02d}','at_seconds':t,'start':t-2,'end':t+2,'kind':'planned_action_or_reaction_cut','status':'pending_actual_review'} for n,t in enumerate(record['cuts_seconds'])]
    (WORK/'06-记录/视频生成/前四十秒电影重制24-原速合并01.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(str(output),flush=True)

if __name__=='__main__':
    main()
