"""Trim the raw R08 result to5s and crop whole canvas to16:9. No scale repair."""
from pathlib import Path
from fractions import Fraction
import json,subprocess,hashlib
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'projects/悬崖上的小气球'
SOURCE=P/'04-输出/原始片段/一次直出08/5c712edb-5f82-4657-a707-084d96427511_01.mp4'

def probe(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],encoding='utf-8'))

def main():
    info=probe(SOURCE);v=next(x for x in info['streams'] if x['codec_type']=='video')
    w,h=v['width'],v['height'];k=min(w//16,h//9);k-=k%2;nw,nh=k*16,k*9
    x,y=(w-nw)//2,(h-nh)//2
    if nw/w < .94 or nh/h < .94:
        raise RuntimeError('Unexpected source framing: review before a large crop')
    out=P/'04-输出/测试视频/一次直出08/同框奔跑与踩草-五秒-原生帧率01.mp4';out.parent.mkdir(parents=True,exist_ok=True)
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(SOURCE),'-map','0:v:0','-map','0:a?','-t','5']
    if nw!=w or nh!=h:cmd+=['-vf',f'crop={nw}:{nh}:{x}:{y},setsar=1']
    cmd+=['-c:v','libx264','-preset','medium','-crf','17','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(out)]
    subprocess.run(cmd,check=True)
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(out),'-f','null','-'],check=True)
    result={'source':str(SOURCE.relative_to(P)).replace('\\','/'),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'source_probe':info,'used_range':[0,5],'crop_whole_canvas':{'x':x,'y':y,'width':nw,'height':nh},'operation':'Only fixed whole-frame aspect crop and remove excess tail. No character transform, matting, background reconstruction, local warp, retiming or synthetic contact/shadow.','native':str(out.relative_to(P)).replace('\\','/'),'native_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'native_probe':probe(out),'original_audio_streams_copied':True,'new_generation_jobs':1}
    rec=P/'06-记录/后期制作/一次直出08-原生导出01.json';rec.parent.mkdir(parents=True,exist_ok=True);rec.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'native':str(out),'frame_rate':v['avg_frame_rate'],'dimensions':[nw,nh],'source_size':[w,h],'crop':[x,y]},ensure_ascii=False))

if __name__=='__main__':main()
