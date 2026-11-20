"""Protect observed hard cuts only; no speed, action or size repair."""
import json
import math
import subprocess
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'projects/悬崖上的小气球'
F=P/'04-输出/成片/前四十秒电影重制24'
NATIVE=F/'悬崖上的小气球-电影重制40秒-未达标审片版24帧01.mp4'
RIFE=F/'悬崖上的小气球-电影重制40秒-未达标审片版24帧01-补帧60帧.mp4'
OUTPUT=F/'悬崖上的小气球-电影重制40秒-未达标审片版60帧01.mp4'

def run(args):
    r=subprocess.run(args,capture_output=True,text=True,encoding='utf-8')
    if r.returncode: raise RuntimeError(r.stderr[-4000:])
    return r.stdout

def main():
    cuts=[25,240,456,650,696,721,758,873]
    evidence=P/'05-检查与验收/前四十秒电影重制24-切镜保护'
    evidence.mkdir(exist_ok=True)
    intermediate=evidence/'切镜保护画面-中间版01.mp4'
    if OUTPUT.exists() and not intermediate.exists():
        # This helper's previous output has complete video but the frame-limited
        # mux omitted the last AAC packet. Preserve it as the reusable video.
        OUTPUT.rename(intermediate)
    args=['ffmpeg','-v','error','-n','-i',str(RIFE)]
    filters=['[0:v]settb=expr=1/60000,setpts=N*1000[vbase]']
    last='vbase';records=[]
    for i,cut in enumerate(cuts,1):
        patch=evidence/f'原生切点{cut}-前帧.png'
        if not patch.exists():
            run(['ffmpeg','-v','error','-n','-i',str(NATIVE),'-vf',f'select=eq(n\\,{cut-1})','-fps_mode','vfr','-frames:v','1',str(patch)])
        start=math.floor((cut-1)*2.5)+1
        end=math.ceil(cut*2.5)-1
        args+=['-i',str(patch)]
        out=f'v{i}'
        filters.append(f'[{last}][{i}:v]overlay=eof_action=repeat:shortest=0:enable=\'between(n,{start+1},{end+1})\'[{out}]')
        last=out
        records.append({'native_cut_frame':cut,'cut_seconds':cut/24,'target_subframes':[start,end],'patch':str(patch),'purpose':'Existing outgoing sample in cross-cut subframes only, not an animation hold or action repair.'})
    args+=['-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map',f'[{last}]','-map','0:a:0','-c:v','libx264','-crf','16','-preset','fast','-pix_fmt','yuv420p','-c:a','copy','-fps_mode','passthrough','-enc_time_base','1:60','-video_track_timescale','60000','-frames:v','2400','-movflags','+faststart',str(intermediate)]
    if not intermediate.exists():run(args)
    # Frame-limited video encoding may stop muxing before the final AAC packet.
    # Remux the complete already-edited soundtrack, without a frame/time cap.
    run(['ffmpeg','-v','error','-n','-i',str(intermediate),'-i',str(NATIVE),'-map','0:v:0','-map','1:a:0','-c','copy','-movflags','+faststart',str(OUTPUT)])
    run(['ffmpeg','-v','error','-i',str(OUTPUT),'-f','null','-'])
    audio=lambda f:run(['ffmpeg','-v','error','-i',str(f),'-map','0:a:0','-f','md5','-']).strip()
    assert audio(NATIVE)==audio(RIFE)==audio(OUTPUT)
    meta=json.loads(run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(OUTPUT)]))
    v=next(x for x in meta['streams'] if x['codec_type']=='video')
    assert v['avg_frame_rate']=='60/1' and int(v['nb_read_frames'])==2400 and abs(float(v['duration'])-40)<.001
    record={'output':str(OUTPUT),'sha256':hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),'probe':meta,'records':records,'source_video':str(NATIVE),'rife_video':str(RIFE),'audio_decoded_md5':audio(OUTPUT),'audio_unchanged':True,'seams':[{'at_seconds':t,'id':f'R24-SEAM-{i+1}'} for i,t in enumerate([10,19,29])],'creative_status':'NOT_APPROVED; original model action/single-actor deviations persist','hearing':'NOT_VERIFIED'}
    (P/'06-记录/视频生成/前四十秒电影重制24-60帧切镜保护01.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(OUTPUT),'sha256':record['sha256'],'frames':2400,'fps':60,'seconds':40,'audio_unchanged':True},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
