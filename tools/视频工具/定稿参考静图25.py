"""Reference stills06: connected photographic matte and continuous size repair."""
from pathlib import Path
import hashlib,json,math,runpy
from collections import deque
from PIL import Image,ImageDraw,ImageFilter,ImageChops

R=Path(__file__).resolve().parents[2];P=R/'projects/悬崖上的小气球'
M=runpy.run_path(str(R/'tools/视频工具/连续精修参考静图25.py'))
S=M['S'];style=M['style'];sha=M['sha'];warp=M['warp'];shadow=M['add_shadow']
O=P/'02-素材/镜头/固定果树单主体25/确定性精修09';W=P/'03-制作/静态精修/固定果树25-确定性09'
BOX={'RUN':(990,525,1205,630),'LOW':(945,545,1275,655),'BURY':(615,525,863,640),'TURN':(567,501,839,641)}

def component(points,w,h):
    pts=set(points);comps=[]
    while pts:
        seed=pts.pop();q=[seed];c=[seed]
        while q:
            x,y=q.pop()
            for a in [-1,0,1]:
                for b in [-1,0,1]:
                    n=x+a,y+b
                    if n in pts:pts.remove(n);q.append(n);c.append(n)
        comps.append(c)
    return comps
def matte(key):
    f=Image.open(S[key]).convert('RGB');b=BOX[key];im=f.crop(b);px=im.load();selected=[]
    envelope=Image.new('L',im.size);ed=ImageDraw.Draw(envelope)
    if key=='TURN':
        for poly in [ [(640,575),(654,547),(740,536),(773,550),(780,580),(798,619),(798,640),(663,640),(650,610)], [(760,543),(794,536),(820,548),(840,573),(840,605),(779,611),(750,582)] ]:
            ed.polygon([(x-b[0],y-b[1]) for x,y in poly],fill=255)
        tail=[(664,510),(615,520),(589,538),(581,560),(585,580),(603,594),(635,601),(669,600),(689,596)]
        for i,(a,z) in enumerate(zip(tail,tail[1:])):
            ed.line((a[0]-b[0],a[1]-b[1],z[0]-b[0],z[1]-b[1]),fill=255,width=8+i*3)
    else:
        points=M['POLY']['RUN' if key=='RUN' else key+'-WHOLE']
        ed.polygon([(x-b[0],y-b[1]) for x,y in points],fill=255)
        envelope=envelope.filter(ImageFilter.MaxFilter(5))
    ep=envelope.load()
    tips={'RUN':(1120,580,1157,603),'LOW':(1130,570,1162,598),'BURY':(831,525,863,546),'TURN':(645,501,675,520)}
    for y in range(im.height):
        for x in range(im.width):
            r,g,bb=px[x,y]
            ax,ay=x+b[0],y+b[1];tip=tips[key]
            strong=not(tip[0]<=ax<tip[2] and tip[1]<=ay<tip[3]) or r>g*1.25
            if ep[x,y] and strong and r>g*1.12+1 and r>bb*1.04+1:selected.append((x,y))
    parts=component(selected,*im.size);main=max(parts,key=len)
    mask=Image.new('L',im.size);mp=mask.load()
    for x,y in main:mp[x,y]=255
    # Fill only tiny enclosed eye/shadow holes, never the open spaces between legs.
    for c in component([(x,y) for y in range(im.height) for x in range(im.width) if mp[x,y]==0],*im.size):
        if len(c)<=48 and all(0<x<im.width-1 and 0<y<im.height-1 for x,y in c):
            for x,y in c:mp[x,y]=255
    mask=mask.filter(ImageFilter.GaussianBlur(.25));bb=mask.point(lambda a:255 if a>24 else 0).getbbox()
    out=im.convert('RGBA');out.putalpha(mask);out=out.crop(bb)
    return out,(b[0]+bb[0],b[1]+bb[1])
def region(im,origin,points):
    m=Image.new('L',im.size);ImageDraw.Draw(m).polygon([(x-origin[0],y-origin[1]) for x,y in points],fill=255)
    p=im.copy();p.putalpha(ImageChops.multiply(p.getchannel('A'),m));return p

def main():
    O.mkdir(parents=True,exist_ok=True);W.mkdir(parents=True,exist_ok=True)
    base=Image.open(S['ENV']).convert('RGBA');raw,origin=matte('RUN');k=79/raw.height
    stand=raw.resize((round(raw.width*k),79),Image.Resampling.LANCZOS)
    records={}
    for key in ['RUN','LOW','APEX','BURY','TURN']:
        st=style();photo=base.copy();layer=Image.new('RGBA',base.size)
        if key=='RUN':
            layer.alpha_composite(stand,(1008,532));shadow(photo,(1023,605,1128,615));params={'scale':k,'source_bbox':[origin[0],origin[1],origin[0]+raw.width,origin[1]+raw.height],'height_target':79}
        elif key=='APEX':
            skull=region(raw,origin,[(990,525),(1054,525),(1055,565),(1048,578),(1030,584),(990,586)])
            plus=region(raw,origin,[(990,525),(1055,525),(1055,565),(1066,577),(1069,592),(1057,597),(1038,586),(990,586)])
            skull=skull.resize(stand.size,Image.Resampling.LANCZOS);plus=plus.resize(stand.size,Image.Resampling.LANCZOS)
            core=stand.copy();core.putalpha(ImageChops.subtract(core.getchannel('A'),skull.getchannel('A')))
            torso=Image.new('RGBA',(stand.width+40,stand.height+40));torso.alpha_composite(core,(20,20))
            padded=Image.new('RGBA',torso.size);padded.alpha_composite(plus,(20,20))
            pivot=(20+(1060-origin[0])*k,20+(586-origin[1])*k)
            padded=padded.rotate(-7,Image.Resampling.BICUBIC,center=pivot,expand=False);torso.alpha_composite(padded)
            at=(897,422);layer.alpha_composite(torso,(at[0]-20,at[1]-20));shadow(photo,(923,605,1034,615),25)
            params={'master_torso_pixels_unchanged':True,'translation_px':[at[0]-1008,-110],'head_neck_rotation_deg':-7,'joint_pivot_source':[1060,586],'head_no_rescale':True,'gap_target_px':94,'padded_rotation_avoids_horn_clipping':True}
        else:
            rawpart,po=matte(key)
            if key=='LOW':
                xn=[(945,1003),(1025,1053),(1145,1110),(1275,1193)]
                syn=[(945,.52),(1024,.52),(1045,.40),(1135,.40),(1160,.65),(1275,.65)]
                an=[(945,645),(1024,645),(1045,650),(1135,650),(1160,642),(1275,642)];box=(1015,604,1124,616)
            elif key=='BURY':
                xn=[(615,645),(680,694),(780,752),(863,821)]
                syn=[(615,.72),(863,.72)];an=[(615,633),(863,633)];box=(652,603,770,617)
            else:
                xn=[(567,606),(655,676),(780,747),(839,799)]
                syn=[(567,.73),(760,.73),(780,.90),(839,.90)];an=[(567,635),(839,635)];box=(664,604,778,616)
            part,at=warp(rawpart,po,xn,syn,an);layer.alpha_composite(part,at);shadow(photo,box)
            params={'continuous_mesh_px':2,'x_landmarks':xn,'vertical_scale':syn,'source_ground_anchors':an,'output_ground_y':611,'purpose':'correct enlarged source anatomy, retaining already folded/pivoted joints and connected skin'}
        photo.alpha_composite(layer)
        if key=='BURY':
            # Photo blades over the nose at actual soft-tuft contact, no solid-earth burial.
            patch=base.crop((754,587,792,614));m=Image.new('L',patch.size)
            ImageDraw.Draw(m).polygon([(0,27),(3,18),(5,3),(8,22),(11,10),(13,26),(17,4),(20,22),(23,12),(26,25),(30,16),(34,23),(37,27)],fill=245)
            patch.putalpha(m.filter(ImageFilter.GaussianBlur(.25)));photo.alpha_composite(patch,(645,587))
        name={'RUN':'幼龙四足二十厘米-连通母图定标09.png','LOW':'幼龙低伏十厘米-连通轮廓校准09.png','APEX':'幼龙果下落空-原躯干与抬吻09.png','BURY':'幼龙埋草-连通体型与接触09.png','TURN':'幼龙原地转右-完整躯干校准09.png'}[key]
        f=O/name;photo.convert('RGB').save(f);layer.save(W/(key+'-参考工作层09.png'))
        b=layer.getchannel('A').point(lambda a:255 if a>32 else 0).getbbox()
        records[key]={'path':str(f),'sha256':sha(f),'alpha_bbox':b,'recipe':params,'style':st,'status':'NEEDS_ACTUAL_REVIEW','model_prompt':None}
    meta={'authorization':'06-记录/用户确认/参考静图确定性精修允许04.json','script_sha256':sha(__file__),'method':'Pillow connected photographic matte + continuous anatomical-region correction; static references only','sources':{q:{'path':str(f),'sha256':sha(f)} for q,f in S.items()},'base_plate':str(S['ENV']),'outputs':records,'limits':'2D reference calibration does not prove exact3D volume or native u30 motion. No video-layer composition; only integrated full reference frames may be submitted.'}
    (W/'连通精修参数09.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    (P/'06-记录/图片生成/固定果树单主体25-连通精修09.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'master_origin':origin,'master_scale':k,'outputs':{q:v['alpha_bbox'] for q,v in records.items()}},ensure_ascii=False))
if __name__=='__main__':main()
