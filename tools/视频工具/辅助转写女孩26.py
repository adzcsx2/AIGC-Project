"""Local ASR as auxiliary evidence only; no audio generation or hearing claim."""
from pathlib import Path
import sys,json,subprocess
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'.autodl/asr-runtime'))
from faster_whisper import WhisperModel
import numpy as np
P=R/'projects/悬崖上的小气球'
d=json.loads((P/'06-记录/视频生成/三图输入26-任务与结果01.json').read_text(encoding='utf-8'))
modeldir=next((R/'.autodl/asr-models/models--Systran--faster-whisper-base/snapshots').iterdir())
model=WhisperModel(str(modeldir),device='cpu',compute_type='int8',cpu_threads=8,local_files_only=True)
out=[]
for id in ['R26-MIA-A','R26-MIA-B']:
 f=next(j['files'][0] for j in d['jobs'] if j['id']==id)
 pcm=subprocess.check_output(['ffmpeg','-v','error','-i',f,'-map','0:a:0','-ac','1','-ar','16000','-f','f32le','-'])
 seg,info=model.transcribe(np.frombuffer(pcm,dtype=np.float32),beam_size=5,word_timestamps=True,condition_on_previous_text=False)
 segments=[{'start':s.start,'end':s.end,'text':s.text,'words':[{'start':w.start,'end':w.end,'word':w.word} for w in s.words or []]} for s in seg]
 out.append({'id':id,'file':f,'language':info.language,'language_probability':info.language_probability,'segments':segments});print(json.dumps(out[-1],ensure_ascii=False),flush=True)
f=P/'05-检查与验收/前四十秒三图输入26-女孩ASR辅助01.json';f.write_text(json.dumps({'scope':'ASR auxiliary, not real listening or natural-laugh acceptance','results':out},ensure_ascii=False,indent=2),encoding='utf-8')
