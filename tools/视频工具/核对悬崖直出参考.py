"""Measure inspected dragon silhouettes in static calibration references only."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'.autodl/video-edit-runtime'),str(ROOT/'.autodl/dragon-edit-deps'),str(ROOT/'.autodl/video-edit-models/mobile-sam/vendor/MobileSAM-master')]
import cv2,numpy as np,torch
from mobile_sam import sam_model_registry,SamPredictor
P=ROOT/'projects/悬崖上的小气球'

def main():
    torch.set_num_threads(6)
    model=sam_model_registry['vit_t'](checkpoint=str(ROOT/'.autodl/video-edit-models/mobile-sam/vendor/MobileSAM-master/weights/mobile_sam.pt'))
    model.to('cuda').eval();pred=SamPredictor(model)
    values=[]
    names=sys.argv[1:] or ['起点A-小体型四足-校准02.png','果下B-同尺度四足-校准候选02.png']
    with torch.inference_mode():
        for name in names:
            path=P/'02-素材/镜头/一次直出08'/name;im=cv2.imdecode(np.fromfile(str(path),np.uint8),1)
            is_a=name.startswith('起点')
            x0,x1=(1000,1450) if is_a else (190,590)
            crop=im[400:710,x0:x1]
            box=np.array([70,50,380,270]) if is_a else np.array([10,55,310,250])
            point=np.array([[200,180]]) if is_a else np.array([[140,180]])
            pred.set_image(cv2.cvtColor(crop,cv2.COLOR_BGR2RGB));m,s,_=pred.predict(point_coords=point,point_labels=np.array([1]),box=box,multimask_output=False)
            y,x=np.where(m[0]);bbox=[int(x.min()+x0),int(y.min()+400),int(x.max()+x0),int(y.max()+400)]
            value={'path':str(path.relative_to(P)).replace('\\','/'),'dimensions':[im.shape[1],im.shape[0]],'bbox':bbox,'height_px':bbox[3]-bbox[1]+1,'width_px':bbox[2]-bbox[0]+1,'height_fraction':(bbox[3]-bbox[1]+1)/im.shape[0],'mask_score':float(s[0]),'method':'human_inspected_roi_MobileSAM_silhouette; pose/projection proxy, not3Dcm'}
            values.append(value)
            display=im.copy();cv2.rectangle(display,(bbox[0],bbox[1]),(bbox[2],bbox[3]),(0,255,30),2)
            out=P/'05-检查与验收/一次直出08/参考尺寸'/('核对-'+path.stem+'.jpg');out.parent.mkdir(parents=True,exist_ok=True);cv2.imencode('.jpg',display)[1].tofile(str(out))
    dest=P/'05-检查与验收/一次直出08/参考尺寸/实际参考轮廓量测01.json';dest.write_text(json.dumps(values,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(values,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
