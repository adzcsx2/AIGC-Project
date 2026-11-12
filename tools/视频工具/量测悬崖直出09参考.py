"""Static reference diagnostics only; never edits any production media."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'.autodl/video-edit-runtime'),str(ROOT/'.autodl/dragon-edit-deps'),str(ROOT/'.autodl/video-edit-models/mobile-sam/vendor/MobileSAM-master')]
import cv2,numpy as np,torch
from mobile_sam import sam_model_registry,SamPredictor
from PIL import Image,ImageDraw
P=ROOT/'projects/悬崖上的小气球'
pack=json.loads((P/'03-制作/制作计划/正式五段直出09/制作包05-实际输入.json').read_text('utf-8'))
torch.set_num_threads(6)
model=sam_model_registry['vit_t'](checkpoint=str(ROOT/'.autodl/video-edit-models/mobile-sam/vendor/MobileSAM-master/weights/mobile_sam.pt')).to('cuda').eval()
pred=SamPredictor(model)
items=[('R08-START',[1080,450,1380,670],[1220,570]),('R08-STOP',[190,450,480,675],[330,580]),
       ('R09-REST',[1080,500,1410,665],[1240,590]),('R09-MISS',[190,400,480,610],[330,530]),
       ('R09-LAND',[185,510,510,685],[350,610]),('R09-READY',[180,450,530,665],[365,580])]
out=P/'05-检查与验收/正式五段直出09/参考尺度';out.mkdir(parents=True,exist_ok=True)
values=[];sheet=Image.new('RGB',(1000,len(items)*240),'#19202a');draw=ImageDraw.Draw(sheet)
with torch.inference_mode():
 for i,(aid,box,point) in enumerate(items):
    path=P/pack['sources'][aid];im=np.asarray(Image.open(path).convert('RGB'))
    pred.set_image(im);mask,s,_=pred.predict(point_coords=np.array([point]),point_labels=np.array([1]),box=np.array(box),multimask_output=False)
    y,x=np.where(mask[0]);bbox=[int(x.min()),int(y.min()),int(x.max()),int(y.max())]
    values.append(dict(id=aid,path=str(path.relative_to(P)),bbox=bbox,height_px=bbox[3]-bbox[1]+1,width_px=bbox[2]-bbox[0]+1,score=float(s[0]),note='Human ROI + SAM outer silhouette, pose/projection proxy only; not3Dcm/volume. Wing/tail/neck articulation changes outer width/height.'))
    a=Image.fromarray(im);roi=(max(0,box[0]-20),max(0,box[1]-25),min(im.shape[1],box[2]+20),min(im.shape[0],box[3]+20));crop=a.crop(roi)
    sheet.paste(crop,(10,i*240));draw.text((480,i*240+15),aid+'\n'+str(bbox)+'\nH='+str(values[-1]['height_px'])+' W='+str(values[-1]['width_px']),fill='white')
sheet.save(out/'各姿态原像素对照01.jpg',quality=94)
(out/'原始轮廓量测01.json').write_text(json.dumps(values,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(values,ensure_ascii=False),flush=True)
