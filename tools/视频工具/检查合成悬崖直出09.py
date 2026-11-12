"""Inspect/assemble R09 files without changing subject size or action time."""
from pathlib import Path
import argparse,json,hashlib,subprocess,re,sys
from fractions import Fraction
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'projects/悬崖上的小气球'
TAG='正式五段直出09'
PACK=P/f'03-制作/制作计划/{TAG}/制作包05-实际输入.json'
JOBS=P/f'06-记录/视频生成/{TAG}-任务与结果01.json'
REC=P/f'06-记录/后期制作/{TAG}-原生检查与合成01.json'
OUT=P/f'04-输出/成片/{TAG}'
EVID=P/f'05-检查与验收/{TAG}'

def read(f):return json.loads(f.read_text('utf-8'))
def save(f,x):
 f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def run(cmd):
 r=subprocess.run([str(x) for x in cmd],capture_output=True,text=True,encoding='utf-8')
 if r.returncode:raise RuntimeError(r.stderr[-5000:])
 return r.stdout
def probe(f):return json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',f]))
def raw_file(job):
 files=job.get('files') or read(ROOT/'.autodl/tasks'/f"{job['task_id']}.json").get('files')
 if not files:return None
 f=Path(files[0]).resolve(strict=True);assert f.is_relative_to(P.resolve());return f

def inspect():
 pack=read(PACK);jobs=read(JOBS)['jobs'];rec=read(REC) if REC.exists() else {'units':[]}
 for unit in pack['units']:
  n=unit['n'];job=next(j for j in jobs if j['n']==n)
  if any(x['n']==n for x in rec['units']):continue
  try:f=raw_file(job)
  except FileNotFoundError:continue
  if not f:continue
  info=probe(f);v=next(s for s in info['streams'] if s['codec_type']=='video');fps=float(Fraction(v['avg_frame_rate']))
  run(['ffmpeg','-v','error','-i',f,'-f','null','-'])
  length=min(unit['duration'],float(v['duration']));frames=int(round(length*fps))
  times={1:[0,1,3,4.6,5.4,5.9,7,8.8,9.5],2:[0,.5,1,1.5,2,2.5,2.9,3.1,3.3,3.6,4,4.6,6,7.9],3:[0,1,4,7.5,8.8,9.5,11,14.9],4:[0,1,2,2.5,2.6,2.7,2.8,3,3.3,5.9],5:[0,1,3,5.5,7,10.5,12,14.9]}[n]
  inds=sorted({min(max(0,round(t*fps)),frames-1) for t in times}|{frames-1})
  folder=EVID/f'片段{n:02d}-原生帧';folder.mkdir(parents=True,exist_ok=True)
  expr='+'.join(f'eq(n,{k})' for k in inds)
  run(['ffmpeg','-v','error','-i',f,'-vf',f"select='{expr}'",'-fps_mode','vfr',folder/'帧%03d.png'])
  sheet=Image.new('RGB',(1344,((len(inds)+1)//2)*404),'#18212b');d=ImageDraw.Draw(sheet);font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',17)
  for i,k in enumerate(inds):
   im=Image.open(folder/f'帧{i+1:03d}.png').convert('RGB');im.thumbnail((672,374));x=(i%2)*672;y=(i//2)*404;sheet.paste(im,(x,y));d.text((x+5,y+376),f'{k/fps:.3f}s / native frame {k}',fill='white',font=font)
  sheet.save(folder/'原生动作总览01.jpg',quality=94)
  item=dict(n=n,source=f.relative_to(P.resolve()).as_posix(),source_sha256=sha(f),probe=info,full_decode='PASS',source_fps=fps,planned_duration=unit['duration'],used_range=[0,length],source_frame_evidence=folder.relative_to(P).as_posix(),actual_visual_review='PENDING')
  rec['units'].append(item);save(REC,rec);print(json.dumps(dict(n=n,fps=fps,dimensions=[v['width'],v['height']],seconds=length,decode='PASS'),ensure_ascii=False),flush=True)
 print(json.dumps(dict(inspected=len(rec['units']),total=5)),flush=True)

def assemble():
 pack=read(PACK);rec=read(REC);assert len(rec['units'])==5
 assert not rec.get('combined'), 'Native assembly exists; inspect/reuse it'
 OUT.mkdir(parents=True,exist_ok=True)
 native=OUT/'前五段-同框直出09-原速24帧01.mp4';assert not native.exists()
 cmd=['ffmpeg','-v','error','-n'];filters=[];audio_inputs=[];seams=[];position=0;units=sorted(rec['units'],key=lambda x:x['n'])
 for i,u in enumerate(units):
  f=P/u['source'];assert sha(f)==u['source_sha256'];v=next(s for s in u['probe']['streams'] if s['codec_type']=='video')
  assert u['source_fps']==24,'Unexpected native fps: preserve/replan instead of forcing24'
  assert any(s['codec_type']=='audio' for s in u['probe']['streams'])
  source_start=u['used_range'][0];duration=u['used_range'][1]-source_start;cmd+=['-i',f];w,h=v['width'],v['height'];unit=int(min(w/16,h/9))//2*2;cw,ch=16*unit,9*unit;x=((w-cw)//2)//2*2;y=((h-ch)//2)//2*2
  assert (cw,ch)==(1696,954), 'Different output dimension: explicitly plan a whole-frame compatible export'
  filters.append(f'[{i}:v:0]trim=start={source_start}:duration={duration},setpts=PTS-STARTPTS,crop={cw}:{ch}:{x}:{y},setsar=1[v{i}]')
  filters.append(f'[{i}:a:0]aresample=48000,atrim=start={source_start}:duration={duration},asetpts=PTS-STARTPTS[a{i}]')
  audio_inputs.append(f'[v{i}][a{i}]');u['whole_canvas_crop']=dict(x=x,y=y,width=cw,height=ch);u['timeline']=[position,position+duration];position+=duration
  if i<4:seams.append(position)
 filters.append(''.join(audio_inputs)+'concat=n=5:v=1:a=1[v][a]')
 cmd+=['-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map','[v]','-map','[a]','-c:v','libx264','-crf','16','-preset','medium','-c:a','aac','-b:a','192k','-movflags','+faststart',native]
 run(cmd);run(['ffmpeg','-v','error','-i',native,'-f','null','-'])
 rec['combined']=dict(path=native.relative_to(P).as_posix(),sha256=sha(native),probe=probe(native),full_decode='PASS',source_order=[u['n'] for u in units],seams_seconds=seams,operation='Trim excess API tail only; fixed whole-frame16:9 crop; concatenate original-speed source clips/audio. No subject scaling, local warp, matting, background replacement, new contact shadow, retiming, music or synthetic bridge.')
 rec['units']=units;save(REC,rec);print(str(native),flush=True)
 # Shot-change detection is auxiliary; actual cut pairs require visual inspection.
 c=subprocess.run(['ffmpeg','-v','info','-i',str(native),'-vf',"select='gt(scene,0.28)',showinfo",'-an','-f','null','-'],capture_output=True,text=True,encoding='utf-8')
 assert c.returncode==0
 cuts=[float(t) for t in re.findall(r'pts_time:([0-9.]+)',c.stderr)]
 save(EVID/'实际切镜候选01.json',dict(threshold=.28,times=cuts,planned_seams=seams,note='scene-score candidates only; not proof of visual cut/continuity'))

def asr():
 sys.path.insert(0,str(ROOT/'.autodl/audio-audit-deps'))
 import numpy as np
 from faster_whisper import WhisperModel
 model=WhisperModel('base',device='cpu',compute_type='int8',cpu_threads=4,download_root=str(ROOT/'.autodl/asr-models'),local_files_only=True)
 pack=read(PACK);rec=read(REC);dest=EVID/'本地对白转写01.json';rows=read(dest) if dest.exists() else []
 for u in pack['units']:
  if not u['dialogue']:continue
  if any(x['n']==u['n'] for x in rows):continue
  item=next((x for x in rec['units'] if x['n']==u['n']),None)
  if item is None:continue
  f=P/item['source']
  pcm=subprocess.check_output(['ffmpeg','-v','error','-i',str(f),'-vn','-ac','1','-ar','16000','-c:a','pcm_f32le','-f','f32le','pipe:1'])
  segs,info=model.transcribe(np.frombuffer(pcm,dtype='<f4').copy(),language=None,beam_size=5,vad_filter=False,temperature=0,condition_on_previous_text=False)
  row=dict(n=u['n'],source=item['source'],sha256=sha(f),expected=u['dialogue'],language=info.language,language_probability=info.language_probability,segments=[dict(start=s.start,end=s.end,text=s.text) for s in segs],scope='Offline ASR auxiliary only; not hearing/timbre/lip-sync acceptance')
  rows.append(row);save(dest,rows);print(json.dumps(row,ensure_ascii=False),flush=True)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('action',choices=['inspect','assemble','asr']);args=ap.parse_args();{'inspect':inspect,'assemble':assemble,'asr':asr}[args.action]()
