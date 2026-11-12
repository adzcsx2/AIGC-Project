"""Existing-footage scale-compositing proof. No paid video/image generation."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT / '.autodl/video-edit-runtime'),
    str(ROOT / '.autodl/dragon-edit-deps'),
    str(ROOT / '.autodl/video-edit-models/mobile-sam/vendor/MobileSAM-master'),
]
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PROJECT = ROOT / 'projects/悬崖上的小气球'
SOURCE = PROJECT / '04-输出/原始片段/空间重制05/片段02/2913ef35-5976-48a1-93ce-f35971aa52fc_01.mp4'
WORK = PROJECT / '03-制作/后期工程/体型控制06-本地测试01'
CHECK = PROJECT / '05-检查与验收/体型控制06-本地测试01'


def write_image(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imencode(path.suffix, value)[1].tofile(str(path))


def read_image(path):
    return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)


def frames():
    cap = cv2.VideoCapture(str(SOURCE))
    result = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        result.append(frame)
    cap.release()
    assert len(result) == 192
    return result


def pink_seed(frame):
    b, g, r = cv2.split(frame.astype(np.int16))
    mask = ((r-g > 17) & (r-b > 7) & (r > 85)).astype(np.uint8)
    mask[:90] = 0
    mask[660:] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    largest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    return (labels == largest).astype(np.uint8), stats[largest]


def overview(items, path, columns=3):
    w, h = 560, 320
    canvas = Image.new('RGB', (columns*w, ((len(items)+columns-1)//columns)*(h+27)), '#1b2028')
    draw = ImageDraw.Draw(canvas)
    for j, (title, a) in enumerate(items):
        im = Image.fromarray(cv2.cvtColor(a, cv2.COLOR_BGR2RGB)).resize((w, h))
        x, y = j % columns * w, j // columns * (h+27)
        canvas.paste(im, (x, y))
        draw.text((x+8, y+h+5), title, fill='white')
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def berry_protection(im):
    b,g,r=cv2.split(im.astype(np.int16))
    red=((r>90)&(r>g*1.7)&(r>b*1.45)).astype(np.uint8)
    allowed=np.zeros_like(red);allowed[80:225,100:350]=1;red*=allowed
    n,labels,stats,centers=cv2.connectedComponentsWithStats(red)
    candidates=[j for j in range(1,n) if 8<=stats[j,cv2.CC_STAT_AREA]<=500 and stats[j,cv2.CC_STAT_WIDTH]<35 and stats[j,cv2.CC_STAT_HEIGHT]<35]
    result=np.zeros_like(red)
    if candidates:
        j=min(candidates,key=lambda j:centers[j,1]);result[labels==j]=255
        result=cv2.dilate(result,np.ones((5,5),np.uint8))
    return result


def segment(keyframes_only):
    import torch
    from mobile_sam import sam_model_registry, SamPredictor
    torch.set_num_threads(6)
    model = sam_model_registry['vit_t'](checkpoint=str(ROOT / '.autodl/video-edit-models/mobile-sam/vendor/MobileSAM-master/weights/mobile_sam.pt'))
    model.to('cuda').eval()
    predictor = SamPredictor(model)
    fs = frames()
    indices = [0, 24, 36, 48, 60, 72, 84, 108, 132, 156, 168, 191] if keyframes_only else range(192)
    items, records = [], []
    with torch.inference_mode():
        for i in indices:
            target = WORK / '龙遮罩' / f'{i:04d}.png'
            im = fs[i]
            seed, st = pink_seed(im)
            x, y, w, h, area = map(int, st)
            x0, y0 = max(0, x-85), max(0, y-85)
            x1, y1 = min(im.shape[1], x+w+85), min(im.shape[0], y+h+65)
            crop = im[y0:y1, x0:x1]
            box = np.array([max(0,x-x0-20), max(0,y-y0-25), min(x1-x0-1,x+w-x0+20), min(y1-y0-1,y+h-y0+20)])
            dist = cv2.distanceTransform(seed, cv2.DIST_L2, 5)
            _, _, _, pt = cv2.minMaxLoc(dist)
            predictor.set_image(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            masks, scores, logits = predictor.predict(point_coords=np.array([[pt[0]-x0, pt[1]-y0]]), point_labels=np.array([1]), box=box, multimask_output=False)
            full = np.zeros(im.shape[:2], np.uint8)
            full[y0:y1, x0:x1] = masks[0].astype(np.uint8)*255
            write_image(target, full)
            contour, _ = cv2.findContours(full, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            preview = im.copy()
            overlay = preview.copy()
            overlay[full > 0] = (50, 230, 100)
            preview = cv2.addWeighted(preview, .55, overlay, .45, 0)
            cv2.drawContours(preview, contour, -1, (20, 255, 20), 1)
            if i in [0,24,36,48,60,72,84,108,132,156,168,191]:
                write_image(CHECK / f'遮罩检查-{i:04d}.jpg', preview)
                items.append((f'frame {i} / {i/24:.3f}s / score {scores[0]:.3f}', preview))
            ys, xs = np.where(full > 0)
            records.append({'frame':int(i),'score':float(scores[0]),'bbox':[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())], 'pink_area':area})
            if i % 12 == 0:
                print('MASK',i,records[-1],flush=True)
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / ('关键帧分割.json' if keyframes_only else '全部分割.json')).write_text(json.dumps(records,indent=2),encoding='utf-8')
    overview(items, CHECK/'遮罩总览01.jpg')


def compose():
    fs = frames()
    h, w = fs[0].shape[:2]
    masks = [cv2.imdecode(np.fromfile(str(WORK/'龙遮罩'/f'{i:04d}.png'), np.uint8), 0) for i in range(192)]
    berries=[berry_protection(im) for im in fs]
    for i in range(192):masks[i][berries[i]>0]=0
    # Source camera follows the action. Register environment independently of actors.
    sift = cv2.SIFT_create(nfeatures=1800)
    features = []
    for i, im in enumerate(fs):
        small = cv2.resize(im, (w//2,h//2))
        allowed = np.full(small.shape[:2],255,np.uint8)
        allowed[260:] = 0
        allowed[160:265,190:510] = 0
        allowed[cv2.resize(cv2.dilate(masks[i],np.ones((31,31),np.uint8)),(w//2,h//2))>0] = 0
        features.append(sift.detectAndCompute(cv2.cvtColor(small,cv2.COLOR_BGR2GRAY),allowed))
    transforms, registration = [], []
    matcher = cv2.BFMatcher()
    kp0, des0 = features[0]
    for i,(kp,des) in enumerate(features):
        matches = matcher.knnMatch(des,des0,k=2)
        good = [a for a,b in matches if a.distance < .72*b.distance]
        a = np.float32([kp[m.queryIdx].pt for m in good])*2
        b = np.float32([kp0[m.trainIdx].pt for m in good])*2
        aff,inliers = cv2.estimateAffinePartial2D(a,b,method=cv2.RANSAC,ransacReprojThreshold=3,maxIters=3000)
        if aff is None or int(inliers.sum()) < 12:
            raise RuntimeError(f'Background registration failed at {i}')
        mat = np.eye(3);mat[:2] = aff
        transforms.append(mat)
        registration.append({'frame':i,'inliers':int(inliers.sum()),'matrix':mat.tolist()})
    (WORK/'背景配准.json').write_text(json.dumps(registration),encoding='utf-8')
    keys = np.array([0,24,36,48,60,72,84,96,108,120,132,144,156,168,191])
    scales = np.array([.58,.55,.50,.47,.46,.47,.47,.47,.47,.47,.47,.48,.50,.50,.50])
    root_x = np.array([1060,1100,925,685,410,365,365,340,330,340,350,285,245,245,245])
    ground_y = np.array([530,528,540,548,550,550,553,554,554,549,540,527,516,516,516])
    # Smooth the keyframe curve, without retiming source motion.
    def curve(values, i):
        j=max(0,min(len(keys)-2,int(np.searchsorted(keys,i,side='right')-1)))
        t=np.clip((i-keys[j])/(keys[j+1]-keys[j]),0,1)
        t=t*t*(3-2*t)
        return float(values[j]*(1-t)+values[j+1]*t)
    donor_indices = [0,12,24,48,72,120,156,191]
    all_records, samples = [], []
    start, end = 36,156
    for i in range(start,end):
        im=fs[i];mask=masks[i]
        ys,xs=np.where(mask>0)
        x0,y0,x1,y1=map(int,[xs.min(),ys.min(),xs.max(),ys.max()])
        s=curve(scales,i);px=curve(root_x,i);gy=curve(ground_y,i)
        # The low support trajectory is retained. Bounding-box size is not the scale metric.
        py=float(y1)
        old_shadow=np.zeros((h,w),np.uint8)
        cv2.ellipse(old_shadow,(int(px+65),int(gy+18)),(int(min(350,(x1-x0)*.8)),44),0,0,360,255,-1)
        hole=cv2.dilate(mask,np.ones((13,13),np.uint8))
        # Register source donors and recover only pixels hidden by the old large body.
        accum=np.zeros_like(im,dtype=np.float32)
        weights=np.zeros((h,w),np.float32)
        for d in donor_indices:
            if d==i:continue
            transform=np.linalg.inv(transforms[i])@transforms[d]
            donor=cv2.warpAffine(fs[d],transform[:2],(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
            invalid=cv2.dilate(masks[d],np.ones((23,23),np.uint8))
            invalid=cv2.max(invalid,cv2.dilate(berries[d],np.ones((9,9),np.uint8)))
            # Do not copy the donor's dragon shadow into the recovered background.
            dy,dx=np.where(masks[d]>0)
            dp=curve(root_x,d);dg=curve(ground_y,d)
            cv2.ellipse(invalid,(int(dp+65),int(dg+18)),(min(350,int((dx.max()-dx.min())*.8)),45),0,0,360,255,-1)
            valid=cv2.warpAffine((invalid==0).astype(np.uint8),transform[:2],(w,h),flags=cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)
            dist=cv2.distanceTransform(valid,cv2.DIST_L2,3)
            weight=np.minimum(dist/16,1)/(1+abs(d-i)/36)**3
            # Nearby source frames preserve local temporal appearance where visible.
            accum+=donor.astype(np.float32)*weight[:,:,None]
            weights+=weight
        plate=accum/np.maximum(weights[:,:,None],1e-6)
        # Do not average different head poses into a ghost face. Reconstruct only the
        # newly revealed head area using motion-aligned neighboring visible poses.
        if 30 <= i <= 78:
            aligned=[]
            for d in [24,72]:
                transform=np.linalg.inv(transforms[i])@transforms[d]
                aligned.append(cv2.warpAffine(fs[d],transform[:2],(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)[305:485,690:930])
            a,b=aligned
            flow_engine=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
            flow_ab=flow_engine.calc(cv2.cvtColor(a,cv2.COLOR_BGR2GRAY),cv2.cvtColor(b,cv2.COLOR_BGR2GRAY),None)
            flow_ba=flow_engine.calc(cv2.cvtColor(b,cv2.COLOR_BGR2GRAY),cv2.cvtColor(a,cv2.COLOR_BGR2GRAY),None)
            fraction=np.clip((i-24)/48,0,1)
            xx,yy=np.meshgrid(np.arange(a.shape[1],dtype=np.float32),np.arange(a.shape[0],dtype=np.float32))
            ma=cv2.remap(a,(xx-fraction*flow_ab[:,:,0]).astype(np.float32),(yy-fraction*flow_ab[:,:,1]).astype(np.float32),cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
            mb=cv2.remap(b,(xx-(1-fraction)*flow_ba[:,:,0]).astype(np.float32),(yy-(1-fraction)*flow_ba[:,:,1]).astype(np.float32),cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
            plate[305:485,690:930]=ma.astype(np.float32)*(1-fraction)+mb.astype(np.float32)*fraction
        shade_strength=np.clip((plate.mean(axis=2)-im.mean(axis=2)-7)/24,0,1)
        hole=cv2.max(hole,(old_shadow*shade_strength).astype(np.uint8))
        absent=((weights<1e-5)&(hole>0)).astype(np.uint8)*255
        if absent.any():
            plate=cv2.inpaint(np.clip(plate,0,255).astype(np.uint8),absent,5,cv2.INPAINT_TELEA).astype(np.float32)
        feather=cv2.GaussianBlur(hole.astype(np.float32)/255,(0,0),3)
        feather[berries[i]>0]=0
        clean=im.astype(np.float32)*(1-feather[:,:,None])+plate*feather[:,:,None]
        # New ground shadow follows the actual support/airborne relationship.
        sh=np.zeros((h,w),np.float32)
        cv2.ellipse(sh,(int(px+13),int(gy+8)),(max(20,int((x1-x0)*s*.30)),max(4,int(11*s))),0,0,360,.24,-1)
        sh=cv2.GaussianBlur(sh,(0,0),5)
        clean*=1-sh[:,:,None]
        # Premultiplied-alpha transform avoids a dark outline.
        alpha=cv2.GaussianBlur(mask.astype(np.float32)/255,(0,0),.65)
        mat=np.float32([[s,0,px*(1-s)],[0,s,py*(1-s)]])
        wa=cv2.warpAffine(alpha,mat,(w,h),flags=cv2.INTER_LINEAR)
        rgb=cv2.warpAffine(im.astype(np.float32)*alpha[:,:,None],mat,(w,h),flags=cv2.INTER_LINEAR)
        result=np.clip(rgb+clean*(1-wa[:,:,None]),0,255).astype(np.uint8)
        write_image(WORK/'合成帧02'/f'{i-start:04d}.png',result[6:-6])
        write_image(WORK/'源片对照帧'/f'{i-start:04d}.png',im[6:-6])
        record={'source_frame':i,'source_time':i/24,'output_time':(i-start)/24,'scale':s,'pivot':[px,py],'ground_y':gy,'unfilled_pixels':int((absent>0).sum()),'mask_bbox':[x0,y0,x1,y1]}
        all_records.append(record)
        if i in [36,48,60,72,84,96,108,120,132,144,155]:
            pair=np.hstack((im,result))
            samples.append((f'{i/24:.3f}s ORIGINAL / COMPOSITE s={s:.3f}',pair))
            write_image(CHECK/f'合成对照02-{i:04d}.jpg',pair)
        if i%12==0:print('COMPOSITE',i,'scale',s,'unfilled',record['unfilled_pixels'],flush=True)
    (WORK/'逐帧尺寸与接触锚点02.json').write_text(json.dumps({'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'source_range':[start/24,end/24],'fps':24,'frames':all_records,'calibration_status':'候选视觉投影标定；并非三维40cm测量','keyframe_scale_values':list(zip(keys.tolist(),scales.tolist()))},ensure_ascii=False,indent=2),encoding='utf-8')
    overview(samples,CHECK/'合成对照总览02.jpg',columns=2)


def refine_and_export():
    fs=frames();h,w=fs[0].shape[:2]
    reg=json.loads((WORK/'背景配准.json').read_text(encoding='utf-8'))
    transforms=[np.array(x['matrix']) for x in reg]
    records=json.loads((WORK/'逐帧尺寸与接触锚点02.json').read_text(encoding='utf-8'))['frames']
    items=[]
    for j,rec in enumerate(records):
        i=rec['source_frame'];im=fs[i]
        current=read_image(WORK/'合成帧02'/f'{j:04d}.png')
        full=np.pad(current,((6,6),(0,0),(0,0)),mode='edge')
        if i<65:
            transform=np.linalg.inv(transforms[i])@transforms[72]
            donor=cv2.warpAffine(fs[72],transform[:2],(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
            mask=cv2.imdecode(np.fromfile(str(WORK/'龙遮罩'/f'{i:04d}.png'),np.uint8),0)
            x0,x1,y0,y1=700,915,300,480
            a=im[y0:y1,x0:x1];b=donor[y0:y1,x0:x1]
            invalid=cv2.dilate(mask[y0:y1,x0:x1],np.ones((7,7),np.uint8))
            flow=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM).calc(cv2.cvtColor(a,cv2.COLOR_BGR2GRAY),cv2.cvtColor(b,cv2.COLOR_BGR2GRAY),None)
            for k in range(2):
                flow[:,:,k]=cv2.inpaint(flow[:,:,k],invalid,3,cv2.INPAINT_NS)
            xx,yy=np.meshgrid(np.arange(x1-x0,dtype=np.float32),np.arange(y1-y0,dtype=np.float32))
            aligned=cv2.remap(b,xx+flow[:,:,0],yy+flow[:,:,1],cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
            feather=cv2.GaussianBlur(cv2.dilate(mask,np.ones((13,13),np.uint8)).astype(np.float32)/255,(0,0),3)
            clean=im.astype(np.float32)
            alpha=feather[y0:y1,x0:x1,None]
            clean[y0:y1,x0:x1]=a*(1-alpha)+aligned*alpha
            s=rec['scale'];px,py=rec['pivot']
            mat=np.float32([[s,0,px*(1-s)],[0,s,py*(1-s)]])
            dragon_alpha=cv2.GaussianBlur(mask.astype(np.float32)/255,(0,0),.65)
            wa=cv2.warpAffine(dragon_alpha,mat,(w,h))
            rgb=cv2.warpAffine(im.astype(np.float32)*dragon_alpha[:,:,None],mat,(w,h))
            patch=rgb+clean*(1-wa[:,:,None])
            region=np.zeros((y1-y0,x1-x0),np.float32)
            cv2.ellipse(region,(100,90),(83,76),0,0,360,1,-1)
            region=cv2.GaussianBlur(region,(0,0),9)[:,:,None]
            full[y0:y1,x0:x1]=np.clip(full[y0:y1,x0:x1]*(1-region)+patch[y0:y1,x0:x1]*region,0,255).astype(np.uint8)
        write_image(WORK/'合成帧04'/f'{j:04d}.png',full[6:-6])
        # Comparison is an inspection artifact; the main test remains clean 16:9.
        before=Image.fromarray(cv2.cvtColor(im[6:-6],cv2.COLOR_BGR2RGB)).resize((960,540))
        after=Image.fromarray(cv2.cvtColor(full[6:-6],cv2.COLOR_BGR2RGB)).resize((960,540))
        panel=Image.new('RGB',(1920,588),'#14191f');panel.paste(before,(0,0));panel.paste(after,(960,0))
        draw=ImageDraw.Draw(panel);font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',24)
        draw.text((18,548),'原片｜同一时刻',font=font,fill='white')
        draw.text((978,548),'体型校正测试｜原速',font=font,fill='white')
        write_image(WORK/'并排对照帧04'/f'{j:04d}.png',cv2.cvtColor(np.array(panel),cv2.COLOR_RGB2BGR))
        if i in [36,42,48,54,60,72,84,108,132,144,155]:
            pair=np.hstack((im,full));write_image(CHECK/f'合成对照04-{i:04d}.jpg',pair)
            items.append((f'{i/24:.3f}s original / corrected',pair))
    overview(items,CHECK/'合成对照总览04.jpg',columns=2)
    out=PROJECT/'04-输出/测试视频/体型控制06';out.mkdir(parents=True,exist_ok=True)
    for frames_dir,name in [('合成帧04','跑跳体型校正-五秒-24帧02'),('并排对照帧04','原片与体型校正-并排对照-24帧02')]:
        cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate','24','-i',str(WORK/frames_dir/'%04d.png'),'-ss','1.5','-i',str(SOURCE),'-map','0:v:0','-map','1:a:0?','-t','5','-c:v','libx264','-crf','17','-preset','medium','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart',str(out/(name+'.mp4'))]
        subprocess.run(cmd,check=True)
        print('EXPORTED',out/(name+'.mp4'),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['keys','masks','compose','export'])
    args = parser.parse_args()
    if args.stage=='compose':compose()
    elif args.stage=='export':refine_and_export()
    else:segment(args.stage == 'keys')
