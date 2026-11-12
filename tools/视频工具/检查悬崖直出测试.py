"""Inspect raw one-pass output; no character replacement or scale repair."""
from pathlib import Path
import sys,json,subprocess,hashlib
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.autodl/video-edit-runtime'))
import cv2,numpy as np
from PIL import Image,ImageDraw
P=ROOT/'projects/悬崖上的小气球'
SOURCE=P/'04-输出/原始片段/一次直出08/5c712edb-5f82-4657-a707-084d96427511_01.mp4'
CHECK=P/'05-检查与验收/一次直出08'

def write(path,im):
    path.parent.mkdir(parents=True,exist_ok=True);cv2.imencode(path.suffix,im)[1].tofile(str(path))

def grid(items,path,width=560,height=315,columns=3):
    canvas=Image.new('RGB',(columns*width,((len(items)+columns-1)//columns)*(height+26)),'#17202a');draw=ImageDraw.Draw(canvas)
    for j,(label,im) in enumerate(items):
        x=j%columns*width;y=j//columns*(height+26)
        canvas.paste(Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB)).resize((width,height)),(x,y));draw.text((x+5,y+height+5),label,fill='white')
    path.parent.mkdir(parents=True,exist_ok=True);canvas.save(path)

def main():
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(SOURCE)],encoding='utf-8'))
    cap=cv2.VideoCapture(str(SOURCE));fps=cap.get(cv2.CAP_PROP_FPS);frames=[]
    while True:
        ok,im=cap.read()
        if not ok:break
        frames.append(im)
    cap.release();assert len(frames)>=round(5*fps)
    samples=[0,.2,.4,.6,.8,1,1.2,1.4,1.6,1.8,2,2.2,2.4,2.6,3,4,4.95]
    items=[]
    for t in samples:
        i=min(len(frames)-1,round(t*fps));im=frames[i]
        write(CHECK/'原生实际帧'/f'{i:04d}.png',im);items.append((f'{i/fps:.3f}s / native frame {i}',im))
    grid(items,CHECK/'原生首中尾与奔跑总览01.jpg')
    contact=[];tracking=[]
    for i in range(min(round(.3*fps),len(frames)),min(round(2.9*fps),len(frames))):
        im=frames[i];h,w=im.shape[:2];b,g,r=cv2.split(im.astype(np.int16))
        mask=((r-g>24)&(r-b>9)&(r>85)).astype(np.uint8);mask[:int(h*.38)]=0;mask[int(h*.85):]=0
        mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
        n,labels,stats,cent=cv2.connectedComponentsWithStats(mask)
        choices=[q for q in range(1,n) if stats[q,cv2.CC_STAT_AREA]>100]
        if not choices:continue
        q=max(choices,key=lambda q:stats[q,cv2.CC_STAT_AREA]);x,y,bw,bh,area=map(int,stats[q])
        # Chroma only suggests the inspection crop. It is not an anatomical size measurement.
        tracking.append({'frame':i,'crop_hint_bbox':[x,y,bw,bh],'centroid':cent[q].tolist(),'purpose':'diagnostic_crop_only_not_size_or3D_metric'})
        x0,x1=max(0,x-15),min(w,x+bw+15);y0,y1=max(0,int(y+bh*.55)),min(h,y+bh+35)
        crop=im[y0:y1,x0:x1]
        write(CHECK/'脚草连续原生裁片'/f'{i:04d}.png',crop)
        if i%3==0:contact.append((f'native {i} / {i/fps:.3f}s: paws + grass crop',crop))
    grid(contact,CHECK/'原生脚草接触连续帧01.jpg',width=560,height=180,columns=3)
    result={'source':str(SOURCE.relative_to(P)).replace('\\','/'),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'probe':info,'decoded_frames':len(frames),'fps':fps,'native_motion_times_used':samples,'chroma_crop_hints':tracking,'diagnostic_limits':'Sparse frames/crops only, no claimed continuous playback or audio listening. Colour bbox is not size proof. No alteration of source video.'}
    (CHECK/'原生技术与辅助取证01.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'fps':fps,'frames':len(frames),'dimensions':[frames[0].shape[1],frames[0].shape[0]],'source_sha256':result['source_sha256']},ensure_ascii=False))

if __name__=='__main__':main()
