"""Native-frame diagnostic sheets/probes, not a substitute for1x audiovisual review."""
from pathlib import Path
from PIL import Image,ImageDraw
import json,subprocess,io,hashlib
R=Path(__file__).resolve().parents[2];P=R/'projects/悬崖上的小气球'
F=P/'06-记录/视频生成/三图输入26-任务与结果01.json'
O=P/'05-检查与验收/前四十秒三图输入26-源片诊断'
TIMES={'ENV':[0,.8,1.6,2.1,2.5,2.95],'LOW':[0,.7,1.5,2.3,2.95],'RUN':[0,.3,.7,1.1,1.6,1.9,2.2,2.5,2.8,3.1,3.5,4,5,5.95],'OUT':[0,.4,1,1.6,1.95],'MIA-A':[0,1,2.9,3.9,4.9,5.5,6.9],'MIA-B':[0,1,3,5,7,8.95],'FLAP':[0,1,1.8,2.1,2.4,3,4.5,5.95],'END':[0,1,2,3.95]}
def main():
 O.mkdir(parents=True,exist_ok=True);d=json.loads(F.read_text(encoding='utf-8'));records=[]
 for j in d['jobs']:
  if not j.get('files'):continue
  f=Path(j['files'][0]);id=j['id'].removeprefix('R26-');dest=O/(id+'-原生诊断.jpg')
  q=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(f)],text=True,encoding='utf-8'))
  if not dest.exists():
   sheet=Image.new('RGB',(448*3,280*((len(TIMES[id])+2)//3)),(20,22,25));draw=ImageDraw.Draw(sheet)
   for n,t in enumerate(TIMES[id]):
    b=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(f),'-frames:v','1','-vf','scale=448:256','-f','image2pipe','-vcodec','png','-'])
    im=Image.open(io.BytesIO(b));x=(n%3)*448;y=(n//3)*280;sheet.paste(im,(x,y));draw.text((x+5,y+258),f'{id} | native {t:.2f}s | 1x source',fill='white')
   sheet.save(dest,quality=93)
  records.append({'id':j['id'],'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'probe':q,'diagnostic':str(dest)})
 (O/'源片技术与抽帧记录01.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'available':len(records),'ids':[r['id'] for r in records]},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
