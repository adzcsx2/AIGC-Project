"""Protect existing cut subframes in the60fps preview; no motion/size repair."""
from pathlib import Path
import subprocess,json,math,hashlib
R=Path(__file__).resolve().parents[2];P=R/'projects/悬崖上的小气球';D=P/'04-输出/成片/固定果树单主体25修复04'
N=D/'悬崖上的小气球-40秒-未达标试看24帧01.mp4'
I=D/'悬崖上的小气球-40秒-未达标试看24帧01-补帧60帧.mp4'
O=D/'悬崖上的小气球-40秒-未达标试看60帧-切镜保护01.mp4'
W=P/'05-检查与验收/固定果树单主体25修复04-切镜保护'
def run(a):
 r=subprocess.run(a,capture_output=True,text=True,encoding='utf-8')
 if r.returncode:raise RuntimeError(r.stderr[-4000:])
 return r.stdout
def main():
 assert not O.exists();W.mkdir(exist_ok=True)
 ed=json.loads((P/'06-记录/后期制作/固定果树单主体25修复04-原速合并01.json').read_text(encoding='utf-8'))
 cuts=[round(t*24) for t in ed['cuts_seconds']];args=['ffmpeg','-v','error','-n','-i',str(I)]
 filters=['[0:v]settb=expr=1/60000,setpts=N*1000[v0]'];last='v0';rows=[]
 for i,n in enumerate(cuts,1):
  patch=W/f'切点{n}-原生前帧.png'
  if not patch.exists():run(['ffmpeg','-v','error','-n','-i',str(N),'-vf',f'select=eq(n\\,{n-1})','-fps_mode','vfr','-frames:v','1',str(patch)])
  start=math.floor((n-1)*2.5)+1;end=math.ceil(n*2.5)-1
  args+=['-i',str(patch)];out='v'+str(i)
  filters.append(f'[{last}][{i}:v]overlay=eof_action=repeat:shortest=0:enable=\'between(n,{start+1},{end+1})\'[{out}]');last=out
  rows.append({'native_cut_frame':n,'seconds':n/24,'target_subframes_zero_based':[start,end],'meaning':'reuse outgoing sample only across interpolation subframes; no source action retiming'})
 tmp=W/'切镜保护画面-无音频中间版01.mp4'
 args+=['-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map',f'[{last}]','-an','-c:v','libx264','-crf','16','-preset','fast','-pix_fmt','yuv420p','-fps_mode','passthrough','-enc_time_base','1:60','-video_track_timescale','60000','-frames:v','2400','-movflags','+faststart',str(tmp)]
 run(args)
 run(['ffmpeg','-v','error','-n','-i',str(tmp),'-i',str(N),'-map','0:v','-map','1:a','-c','copy','-movflags','+faststart',str(O)])
 run(['ffmpeg','-v','error','-i',str(O),'-f','null','-'])
 meta=json.loads(run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(O)]));v=next(s for s in meta['streams'] if s['codec_type']=='video')
 assert v['avg_frame_rate']=='60/1' and int(v['nb_read_frames'])==2400 and abs(float(v['duration'])-40)<.001
 md5=lambda f:run(['ffmpeg','-v','error','-i',str(f),'-map','0:a:0','-f','md5','-']).strip()
 assert md5(N)==md5(I)==md5(O)
 record={**ed,'output':str(O),'sha256':hashlib.sha256(O.read_bytes()).hexdigest(),'probe':meta,'native':str(N),'rife':str(I),'cut_guards':rows,'audio_decoded_md5':md5(O),'audio_unchanged':True,'creative_status':'FAILED_SOURCE_ADHERENCE_PREVIEW_ONLY','web_dynamic_and_hearing':'NOT_CLAIMED_PASSED'}
 dest=P/'06-记录/后期制作/固定果树单主体25修复04-60帧切镜保护01.json';dest.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'output':str(O),'frames':2400,'fps':60,'seconds':40,'cuts_protected':len(rows),'audio_unchanged':True},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
