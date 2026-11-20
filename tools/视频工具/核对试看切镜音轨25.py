"""Native/60fps cut-boundary pixel comparison and silent-track separation."""
from pathlib import Path
from PIL import Image,ImageChops,ImageStat
import subprocess,json,array

R=Path(__file__).resolve().parents[2];P=R/'projects/悬崖上的小气球'
F=P/'06-记录/后期制作/固定果树单主体25修复04-60帧切镜保护01.json'
def main():
 d=json.loads(F.read_text(encoding='utf-8'));w=P/'05-检查与验收/固定果树单主体25修复04-切镜像素核对';w.mkdir(exist_ok=True)
 all_images=[]
 for name,fps,file in [('native',24,d['native']),('final',60,d['output'])]:
  numbers=[n for t in d['cuts_seconds'] for n in [round(t*fps)-1,round(t*fps)]]
  folder=w/name;folder.mkdir(exist_ok=True)
  expression='+'.join(f'eq(n\\,{n})' for n in numbers)
  subprocess.run(['ffmpeg','-v','error','-n','-i',file,'-vf','select='+expression,'-fps_mode','vfr','-start_number','0',str(folder/'%02d.png')],check=True,capture_output=True)
  all_images.append([Image.open(folder/f'{n:02}.png').convert('RGB') for n in range(len(numbers))])
 rows=[]
 for n,t in enumerate(d['cuts_seconds']):
  errors=[sum(ImageStat.Stat(ImageChops.difference(all_images[0][n*2+k],all_images[1][n*2+k])).mean)/3 for k in range(2)]
  rows.append({'at_seconds':t,'outgoing_incoming_rgb_mean_abs_error':errors,'status':'PASS_PIXEL_CORRESPONDENCE' if max(errors)<5 else 'INSPECT_PIXEL_DIFFERENCE'})
 pcm=subprocess.check_output(['ffmpeg','-v','error','-i',d['output'],'-map','0:a:0','-ac','1','-ar','48000','-f','s16le','-']);samples=array.array('h');samples.frombytes(pcm)
 silent=[]
 for a,b in [(0,15),(17,19),(28,34),(36,40)]:
  lo=round((a+.05)*48000);hi=round((b-.05)*48000);peak=max(map(abs,samples[lo:hi]),default=0);silent.append({'interval_seconds':[a+.05,b-.05],'peak_s16':peak,'status':'PASS_SILENCE' if peak==0 else 'NONZERO'})
 out={'seam_pixels':rows,'silent_interiors':silent,'audio_md5_unchanged':d['audio_unchanged'],'limits':'Pixel correspondence confirms cut sampling, not motion/physical continuity. Silence tests exclude50ms boundary overlap; no listening/natural-laughter claim. Native model deviations remain.'}
 f=P/'05-检查与验收/固定果树单主体25修复04-切镜与音轨技术复核01.json';f.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
