"""Assemble authorized native sources into a clearly labelled40s review preview."""
from pathlib import Path
from fractions import Fraction
import subprocess,json,hashlib

R=Path(__file__).resolve().parents[2];P=R/'projects/悬崖上的小气球'
C=P/'03-制作/剪辑/三图输入26-原速剪辑方案01.json'
B=P/'06-记录/视频生成/三图输入26-任务与结果01.json'
D=P/'04-输出/成片/前四十秒三图输入26';OUT=D/'前40秒-三图方案-原速试看24帧01.mp4'
def run(args):
 r=subprocess.run(args,capture_output=True,text=True,encoding='utf-8')
 if r.returncode:raise RuntimeError(r.stderr[-4000:])
 return r.stdout
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def main():
 D.mkdir(parents=True,exist_ok=True);assert not OUT.exists(),'Preserve existing preview.'
 pack=json.loads(C.read_text(encoding='utf-8'));batch=json.loads(B.read_text(encoding='utf-8'))
 assert all(j.get('files') for j in batch['jobs'])
 jobs={j['id']:j for j in batch['jobs']};indices={j['id']:i for i,j in enumerate(batch['jobs'])}
 edl=pack['edl']
 t=0
 for e in edl:e['timeline_start']=t;t+=e['out']-e['in'];e['timeline_end']=t
 assert t==40
 args=['ffmpeg','-v','error','-n'];sources=[];filters=[];vlabels={};alabels={}
 for n,j in enumerate(batch['jobs']):
  f=Path(j['files'][0]);q=json.loads(run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(f)]));v=next(s for s in q['streams'] if s['codec_type']=='video')
  assert Fraction(v['avg_frame_rate'])==24 and int(v['nb_read_frames'])>=j['seconds']*24
  assert v['width']==1344 and v['height']==768
  args+=['-i',str(f)];sources.append({'id':j['id'],'file':str(f),'sha256':sha(f),'probe':q})
  uses=[k for k,e in enumerate(edl) if e['shot_id']==j['id']];vl=[f's{n}_{k}' for k in uses]
  filters.append(f'[{n}:v]split={len(vl)}'+''.join('['+x+']' for x in vl))
  vlabels.update(dict(zip(uses,vl)))
  au=[k for k in uses if edl[k]['audio']]
  if au:
   assert any(s['codec_type']=='audio' for s in q['streams'])
   al=[f'sa{n}_{k}' for k in au];filters.append(f'[{n}:a]asplit={len(al)}'+''.join('['+x+']' for x in al));alabels.update(dict(zip(au,al)))
 labels=[]
 for n,e in enumerate(edl):
  a,b=e['in'],e['out'];length=b-a
  filters.append(f'[{vlabels[n]}]trim=start_frame={round(a*24)}:end_frame={round(b*24)},setpts=PTS-STARTPTS,crop=1344:756:0:6,setsar=1[v{n}]')
  if e['audio']:
   filters.append(f'[{alabels[n]}]atrim=start={a}:end={b},asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,afade=t=in:d=0.005,afade=t=out:st={length-.005}:d=0.005[a{n}]')
  else:filters.append(f'anullsrc=r=48000:cl=stereo,atrim=duration={length},asetpts=PTS-STARTPTS[a{n}]')
  labels.append(f'[v{n}][a{n}]')
 filters.append(''.join(labels)+f'concat=n={len(edl)}:v=1:a=1[v][a]')
 args+=['-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map','[v]','-map','[a]','-c:v','libx264','-preset','fast','-crf','16','-pix_fmt','yuv420p','-fps_mode','passthrough','-enc_time_base','1:24','-video_track_timescale','24000','-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-t','40','-movflags','+faststart',str(OUT)]
 run(args);run(['ffmpeg','-v','error','-i',str(OUT),'-f','null','-'])
 probe=json.loads(run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(OUT)]));v=next(s for s in probe['streams'] if s['codec_type']=='video')
 assert int(v['nb_read_frames'])==960 and Fraction(v['avg_frame_rate'])==24
 cuts=[e['timeline_end'] for e in edl[:-1]]
 record={'output':str(OUT),'sha256':sha(OUT),'probe':probe,'sources':sources,'edl':edl,'cuts_seconds':cuts,'post_retiming':False,'whole_frame_crop':'1344x768 ->1344x756,6pixels top/bottom; no actor layer or local resize','audio':'Only visible-girl dialogue/laugh retained; all dragon/environment/rest audio digitally silent; no music/added effects.5ms click fades only.','source_deviations':pack.get('source_deviations',[]),'creative_status':'REVIEW_PREVIEW_USER_ACCEPTANCE_PENDING','hearing_status':'NOT_CLAIMED; ASR auxiliary only','seams':[{'id':f'R26-SEAM-{i+1:02}','at_seconds':s,'start':max(0,s-2),'end':min(40,s+2),'kind':'visible_reaction_or_insert_cut','status':'PENDING_WEB_AND_FINAL_REVIEW'} for i,s in enumerate(cuts)]}
 dest=P/'06-记录/后期制作/三图输入26-原速合并01.json';dest.parent.mkdir(exist_ok=True);dest.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'output':str(OUT),'frames':960,'seconds':40,'cuts':cuts,'creative_status':record['creative_status']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
