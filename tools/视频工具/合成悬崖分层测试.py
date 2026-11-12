"""Composite an existing dragon over an independently generated complete clean plate.

The clean plate is never spatially resampled or repaired. Only the foreground is
transformed; shadow changes illumination locally without deforming scene pixels.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('scale06', Path(__file__).with_name('测试幼龙尺寸合成.py'))
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
cv2, np = old.cv2, old.np
P = old.PROJECT
WORK = P / '03-制作/后期工程/分层底片07'
CHECK = P / '05-检查与验收/分层底片07'
OUT = P / '04-输出/测试视频/分层底片07'
BASE = P / '04-输出/原始片段/分层底片07/dc0f5fbe-98f8-4051-8fe0-72b51fa47527_01.mp4'


def read_video(path):
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    result = []
    while True:
        ok, im = cap.read()
        if not ok:
            break
        result.append(im)
    cap.release()
    return fps, result


def inspect_plate(path):
    fps, fs=read_video(path)
    if not fs:
        raise RuntimeError('No decoded clean-plate frames')
    CHECK.mkdir(parents=True,exist_ok=True)
    items=[]
    ids=sorted(set([min(len(fs)-1,int(t*fps)) for t in [0,.5,1,1.5,2,2.5,3,3.5,4,4.5,4.95]]))
    h,w=fs[0].shape[:2]
    gray0=cv2.cvtColor(fs[0],cv2.COLOR_BGR2GRAY)
    rigid=np.zeros((h,w),np.uint8)
    rigid[int(h*.22):int(h*.52),int(w*.17):int(w*.45)]=255
    rigid[int(h*.06):int(h*.62),int(w*.69):int(w*.84)]=255
    pts=cv2.goodFeaturesToTrack(gray0,600,.015,7,mask=rigid)
    evidence=[]
    for i in ids:
        im=fs[i];old.write_image(CHECK/'实际底片帧'/f'{i:04d}.png',im)
        items.append((f'{i/fps:.3f}s clean plate',im))
        if i==0:continue
        gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
        nxt,ok,_=cv2.calcOpticalFlowPyrLK(gray0,gray,pts,None,winSize=(25,25),maxLevel=3)
        back,okb,_=cv2.calcOpticalFlowPyrLK(gray,gray0,nxt,None,winSize=(25,25),maxLevel=3)
        valid=ok.ravel().astype(bool)&okb.ravel().astype(bool)&(np.linalg.norm(back-pts,axis=2).ravel()<1.5)
        a=nxt[valid,0];b=pts[valid,0]
        aff,inliers=cv2.estimateAffinePartial2D(a,b,method=cv2.RANSAC,ransacReprojThreshold=2.5)
        if aff is not None:
            residual=np.linalg.norm(a@aff[:,:2].T+aff[:,2]-b,axis=1)
            evidence.append({'frame':int(i),'tracked_rigid_points':len(a),'global_fit_inlier_fraction':float(inliers.mean()),'residual_median_px':float(np.median(residual)),'residual_p90_px':float(np.percentile(residual,90)),'note':'Sparse geometry diagnostic, not continuous playback or whole-scene visual acceptance.'})
    old.overview(items,CHECK/'实际无龙底片总览01.jpg',columns=3)
    p=CHECK/'实际底片技术与稀疏刚体跟踪01.json'
    p.write_text(json.dumps({'plate':str(path),'fps':fps,'decoded_frames':len(fs),'dimensions':[w,h],'rigid_buildings_trunk_tracking':evidence,'visual_quality':'待实看抽帧及用户原速审片'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'fps':fps,'frames':len(fs),'tracking':evidence},ensure_ascii=False),flush=True)


def composite(plate_path, preview=False):
    fs = old.frames()
    rec = json.loads((old.WORK / '逐帧尺寸与接触锚点02.json').read_text(encoding='utf-8'))['frames']
    reg = json.loads((old.WORK / '背景配准.json').read_text(encoding='utf-8'))
    if preview:
        im = old.read_image(P / '02-素材/镜头/分层底片07/女孩与环境-完整无龙底板01.png')
        im = cv2.resize(im, (1344, 768))
        plates = [im] * 120
        fps = 24
        indices = [0, 12, 24, 48, 72, 96, 119]
    else:
        fps, plates = read_video(plate_path)
        if abs(fps-24) > .001 or len(plates) < 120:
            raise RuntimeError(f'Expected at least 120 native24 frames, got fps={fps}, frames={len(plates)}')
        plates = plates[:120]
        indices = range(120)
    h, w = plates[0].shape[:2]
    if w*9 != (h-12)*16 and w*9 != h*16:
        raise RuntimeError(f'Unexpected frame shape: {w}x{h}')
    crop_y = 6 if w*9 == (h-12)*16 else 0
    sift = cv2.SIFT_create(nfeatures=2200)
    allowed = np.full(fs[0].shape[:2], 255, np.uint8)
    allowed[285:555, 400:900] = 0  # Girl is dynamic and is not a registration anchor.
    allowed[240:640, 870:] = 0  # Old dragon is not background.
    allowed[590:] = 0
    kref, dref = sift.detectAndCompute(cv2.cvtColor(fs[0], cv2.COLOR_BGR2GRAY), allowed)
    matcher = cv2.BFMatcher()
    matrices, matches_log = [], []
    for j, im in enumerate(plates):
        mask = cv2.resize(allowed, (w, h))
        kp, des = sift.detectAndCompute(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), mask)
        pairs = matcher.knnMatch(des, dref, k=2)
        good = [a for a,b in pairs if a.distance < .72*b.distance]
        src = np.float32([kp[m.queryIdx].pt for m in good])
        dst = np.float32([kref[m.trainIdx].pt for m in good])
        aff, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=3, maxIters=4000)
        if aff is None or int(inliers.sum()) < 18:
            raise RuntimeError(f'No reliable global background registration at frame {j}')
        m = np.eye(3); m[:2] = aff
        matrices.append(m)
        matches_log.append({'frame':j,'inliers':int(inliers.sum()),'plate_to_reference':m.tolist()})
    # Smooth only foreground registration parameters; no optical flow or plate warp.
    smoothed = []
    for j in range(120):
        a = np.mean(matrices[max(0,j-2):min(120,j+3)], axis=0)
        a[2] = [0,0,1]
        smoothed.append(a)
    items, log = [], []
    for j in indices:
        r = rec[j]; i = r['source_frame']; base = plates[j]
        original = fs[i]
        mask = cv2.imdecode(np.fromfile(str(old.WORK/'龙遮罩'/f'{i:04d}.png'),np.uint8),0)
        mask[old.berry_protection(original)>0] = 0
        alpha = cv2.GaussianBlur(mask.astype(np.float32)/255,(0,0),.65)
        s = r['scale']; px,py = r['pivot']
        shrink = np.array([[s,0,px*(1-s)],[0,s,py*(1-s)],[0,0,1]],np.float64)
        camera = np.linalg.inv(smoothed[j]) @ np.array(reg[i]['matrix'])
        transform = camera @ shrink
        wa = cv2.warpAffine(alpha,transform[:2],(w,h),flags=cv2.INTER_LINEAR)
        fg = cv2.warpAffine(original.astype(np.float32)*alpha[:,:,None],transform[:2],(w,h),flags=cv2.INTER_LINEAR)
        ground = camera @ np.array([px,r['ground_y'],1.0])
        camera_scale = float(np.hypot(camera[0,0],camera[1,0]))
        body_width = (r['mask_bbox'][2]-r['mask_bbox'][0])*s*camera_scale
        sh = np.zeros((h,w),np.float32)
        cv2.ellipse(sh,(int(ground[0]+12*camera_scale),int(ground[1]+7*camera_scale)),(max(16,int(body_width*.27)),max(4,int(7*camera_scale))),0,0,360,.20,-1)
        sh = cv2.GaussianBlur(sh,(0,0),4*camera_scale)
        result = np.clip(np.rint(fg+base.astype(np.float32)*(1-sh[:,:,None])*(1-wa[:,:,None])),0,255).astype(np.uint8)
        support = (wa>.0001)|(sh>.0001)
        result[~support] = base[~support]
        outside_diff = int(np.max(np.abs(result[~support].astype(np.int16)-base[~support].astype(np.int16))))
        assert outside_diff == 0
        name = '静态机位匹配预检' if preview else '合成原生帧01'
        view = result[crop_y:h-crop_y] if crop_y else result
        old.write_image(WORK/name/f'{j:04d}.png',view)
        if not preview:
            old.write_image(WORK/'原始底片对照帧'/f'{j:04d}.png',base[crop_y:h-crop_y] if crop_y else base)
        log.append({'output_frame':int(j),'source_frame':i,'scale':s,'camera_scale':camera_scale,'transform_foreground_only':transform.tolist(),'unmodified_base_fraction':float((~support).mean()),'outside_layer_pixel_max_diff':outside_diff})
        if j in [0,12,24,48,72,96,119]:
            pair=np.hstack((base,result));old.write_image(CHECK/f'{name}-对照-{j:04d}.jpg',pair)
            items.append((f'{j/24:.3f}s clean plate / layered composite',pair))
        if j%24 == 0:print('COMPOSITE',j,'inliers',matches_log[j]['inliers'],'background exact',outside_diff,flush=True)
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/('预检图层变换.json' if preview else '逐帧图层与底片不变性检查01.json')).write_text(json.dumps({'plate':str(plate_path),'plate_fps':fps,'frames':log,'registration':matches_log,'constraint':'No spatial resampling, donor averaging, local optical flow or hole filling is applied to the plate.'},ensure_ascii=False,indent=2),encoding='utf-8')
    old.overview(items,CHECK/('静态匹配预检总览01.jpg' if preview else '实际底片与分层合成总览01.jpg'),columns=2)
    if not preview:
        OUT.mkdir(parents=True,exist_ok=True)
        output=OUT/'无龙底片与独立小龙-五秒-24帧01.mp4'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate','24','-i',str(WORK/'合成原生帧01/%04d.png'),'-ss','1.5','-i',str(old.SOURCE),'-map','0:v:0','-map','1:a:0?','-t','5','-c:v','libx264','-preset','medium','-crf','17','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(output)],check=True)
        print('EXPORTED',output,flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--plate',type=Path,default=BASE)
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--inspect',action='store_true')
    args=parser.parse_args()
    if args.inspect:inspect_plate(args.plate)
    else:composite(args.plate,args.preview)
