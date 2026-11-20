"""Continuous anatomical-region correction of authorized reference stills only."""
from pathlib import Path
import hashlib,json,math,runpy
from PIL import Image,ImageDraw,ImageFilter,ImageChops
import yaml

R=Path(__file__).resolve().parents[2];P=R/'projects/悬崖上的小气球'
M=runpy.run_path(str(R/'tools/视频工具/精修参考静图25.py'))
S=M['SOURCES'];POLY=M['polys'];style=M['style'];sha=M['sha']
O=P/'02-素材/镜头/固定果树单主体25/确定性精修05';W=P/'03-制作/静态精修/固定果树25-确定性05'
POLY['LOW-WHOLE']=[(953,621),(957,611),(961,602),(970,591),(983,580),(994,577),(1001,572),(1014,567),(1020,566),(1017,574),(1010,581),(1023,577),(1024,569),(1038,558),(1064,551),(1080,550),(1101,553),(1120,562),(1135,572),(1152,582),(1148,586),(1139,584),(1133,582),(1138,593),(1146,605),(1157,614),(1174,621),(1199,629),(1229,632),(1265,633),(1267,636),(1253,640),(1225,642),(1197,643),(1173,640),(1154,638),(1150,646),(1135,650),(1101,649),(1080,647),(1072,647),(1052,645),(1033,645),(1024,643),(1009,645),(1002,639),(997,641),(976,639),(960,635),(953,629)]
POLY['BURY-WHOLE']=[(622,607),(624,596),(628,586),(632,579),(638,574),(640,565),(646,573),(654,565),(666,556),(669,558),(663,574),(674,570),(679,560),(691,553),(723,547),(751,549),(777,559),(786,572),(802,580),(828,580),(846,568),(849,548),(843,537),(837,534),(839,530),(850,536),(855,550),(854,570),(844,584),(823,596),(794,599),(782,610),(778,618),(767,625),(757,624),(750,625),(746,620),(753,612),(742,602),(726,611),(712,621),(704,630),(694,635),(681,632),(677,635),(672,631),(674,624),(687,616),(692,606),(679,606),(669,611),(658,615),(646,620),(637,622),(628,621),(623,616)]
POLY['TURN-WHOLE']=[(670,579),(663,562),(677,551),(703,545),(733,545),(757,552),(771,562),(765,573),(774,576),(779,568),(775,559),(771,554),(777,556),(788,566),(792,568),(791,558),(787,551),(789,549),(798,557),(810,563),(818,566),(822,574),(830,578),(832,585),(827,594),(814,598),(798,599),(785,599),(774,608),(784,619),(790,626),(785,634),(777,633),(772,634),(765,631),(755,620),(745,611),(731,611),(716,610),(699,610),(694,621),(699,628),(694,634),(685,635),(677,632),(674,626),(666,614),(656,605),(635,605),(606,601),(590,592),(578,580),(574,565),(578,547),(590,532),(611,520),(637,514),(662,509),(663,512),(641,519),(620,527),(603,539),(592,555),(592,568),(602,580),(624,587),(648,589),(661,586)]

def cut(key,poly):
    pts=POLY[poly];x0=min(x for x,y in pts);y0=min(y for x,y in pts);x1=max(x for x,y in pts)+1;y1=max(y for x,y in pts)+1
    im=Image.open(S[key]).convert('RGBA').crop((x0,y0,x1,y1));mask=Image.new('L',(im.width*4,im.height*4));ImageDraw.Draw(mask).polygon([((x-x0)*4,(y-y0)*4) for x,y in pts],fill=255)
    mask=mask.resize(im.size,Image.Resampling.LANCZOS);a=mask.load();pix=im.load()
    for y in range(im.height):
        for x in range(im.width):
            rr,gg,bb,_=pix[x,y]
            if gg>rr*1.10 and gg>bb*1.12:a[x,y]=0
    im.putalpha(mask);return im,(x0,y0)
def lerp(nodes,x):
    if x<=nodes[0][0]:return nodes[0][1]
    for (a,u),(b,v) in zip(nodes,nodes[1:]):
        if x<=b:return u+(v-u)*(x-a)/(b-a)
    return nodes[-1][1]
def warp(im,origin,xnodes,sy_nodes,anchor_nodes,ground=611):
    # Monotone continuous X remap + smoothly varying vertical scale around ground.
    # No detached head/neck patches; all skin boundaries remain connected.
    xmin=math.floor(xnodes[0][1]);xmax=math.ceil(xnodes[-1][1]);ymin=500;ymax=625
    inverse_nodes=[(b,a) for a,b in xnodes]
    def inv(x,y):
        sx=lerp(inverse_nodes,x);scale=lerp(sy_nodes,sx);anchor=lerp(anchor_nodes,sx)
        return sx-origin[0],(y-ground)/scale+anchor-origin[1]
    meshes=[]
    for y in range(ymin,ymax,2):
        for x in range(xmin,xmax,2):
            right=min(x+2,xmax);bottom=min(y+2,ymax)
            quad=(*inv(x,y),*inv(x,bottom),*inv(right,bottom),*inv(right,y))
            meshes.append(((x-xmin,y-ymin,right-xmin,bottom-ymin),quad))
    out=im.transform((xmax-xmin,ymax-ymin),Image.Transform.MESH,meshes,Image.Resampling.BICUBIC)
    return out,(xmin,ymin)
def add_shadow(im,box,alpha=42):
    sh=Image.new('RGBA',im.size);ImageDraw.Draw(sh).ellipse(box,fill=(28,30,18,alpha));im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(2)))

def main():
    O.mkdir(parents=True,exist_ok=True);W.mkdir(parents=True,exist_ok=True)
    auth=P/'06-记录/用户确认/参考静图确定性精修允许04.json'
    if not auth.exists():auth.write_text(json.dumps({'user_answer':'允许，只精修参考图（推荐）','scope':'deterministic reference stills only; final single-pass u30 video unchanged','question_item':'call_fd700641086c4decae4f41f4238d0cb8','source':'current explicit user reply'},ensure_ascii=False,indent=2),encoding='utf-8')
    base=Image.open(S['ENV']).convert('RGBA');stand,origin=cut('RUN','RUN');k=79/stand.height;stand=stand.resize((round(stand.width*k),79),Image.Resampling.LANCZOS)
    records={}
    for key in ['RUN','LOW','APEX','BURY','TURN']:
        st=style();photo=base.copy();layer=Image.new('RGBA',base.size)
        if key=='RUN':
            layer.alpha_composite(stand,(1008,532));add_shadow(photo,(1024,605,1125,615));params={'uniform_scale':k,'bbox_target':[1008,532,1008+stand.width,611]}
        elif key=='APEX':
            # The same head is rotated about its actual neck attachment; no new face/size.
            h,ho=cut('RUN','HEAD');hc=Image.new('RGBA',stand.size)
            h=h.resize((round(h.width*k),round(h.height*k)),Image.Resampling.LANCZOS)
            offset=(round((ho[0]-origin[0])*k),round((ho[1]-origin[1])*k));hc.alpha_composite(h,offset)
            torso=stand.copy();torso.putalpha(ImageChops.subtract(torso.getchannel('A'),hc.getchannel('A')))
            pivot=((1045-origin[0])*k,(574-origin[1])*k)
            hc=hc.rotate(-17,Image.Resampling.BICUBIC,center=pivot,expand=False)
            torso.alpha_composite(hc);layer.alpha_composite(torso,(903,422));add_shadow(photo,(928,605,1034,615),25)
            params={'same_master_body_pixels':True,'translation_px':[-105,-110],'same_master_head_rotation_deg':-17,'neck_pivot_source':[1045,574],'mouth_gap_design_px':94}
        else:
            part,po=cut(key,key+'-WHOLE')
            if key=='LOW':
                xn=[(953,1008),(1025,1053),(1145,1110),(1268,1189)]
                syn=[(953,.55),(1024,.55),(1045,.40),(1135,.40),(1160,.65),(1268,.65)]
                an=[(953,643),(1024,643),(1045,650),(1135,650),(1160,642),(1268,642)]
                box=(1015,604,1124,616)
            elif key=='BURY':
                xn=[(622,650),(680,694),(780,752),(856,815)]
                syn=[(622,.72),(856,.72)];an=[(622,633),(856,633)];box=(652,603,770,617)
            else:
                xn=[(574,612),(655,676),(780,747),(833,794)]
                syn=[(574,.73),(760,.73),(780,.90),(833,.90)];an=[(574,635),(833,635)];box=(664,604,778,616)
            warped,at=warp(part,po,xn,syn,an);layer.alpha_composite(warped,at);add_shadow(photo,box)
            params={'continuous_inverse_mesh_cell_px':2,'x_landmarks':xn,'vertical_scale_landmarks':syn,'source_ground_anchors':an,'output_ground_y':611,'purpose':'normalize enlarged generated anatomical regions while retaining existing folded/turned joints and connected skin'}
        photo.alpha_composite(layer)
        if key=='BURY':
            # Only already photographed thin grass blades, over the contact muzzle.
            patch=base.crop((754,587,787,613));m=Image.new('L',patch.size)
            ImageDraw.Draw(m).polygon([(0,26),(3,19),(5,7),(8,22),(11,13),(13,25),(17,5),(19,22),(22,13),(25,24),(29,17),(32,26)],fill=245)
            patch.putalpha(m.filter(ImageFilter.GaussianBlur(.25)));photo.alpha_composite(patch,(645,587))
        name={'RUN':'幼龙四足二十厘米-母图像素定标05.png','LOW':'幼龙低伏十厘米-连续头身校准05.png','APEX':'幼龙果下落空-同体量刚体位移05.png','BURY':'幼龙埋草-连续体型与接触校准05.png','TURN':'幼龙原地转右-连续体型校准05.png'}[key]
        dest=O/name;photo.convert('RGB').save(dest);layer.save(W/(key+'-仅参考工作层05.png'))
        b=layer.getchannel('A').point(lambda a:255 if a>32 else 0).getbbox()
        records[key]={'path':str(dest),'sha256':sha(dest),'alpha_bbox':b,'recipe':params,'style':st,'actual_model_prompt':None,'status':'NEEDS_VISUAL_REVIEW'}
    meta={'authorization':str(auth),'authorization_sha256':sha(auth),'tool':'Pillow deterministic still correction; no inference','base':str(S['ENV']),'base_sha256':sha(S['ENV']),'sources':{q:{'path':str(f),'sha256':sha(f)} for q,f in S.items()},'script_sha256':sha(__file__),'outputs':records,'limits':'2D reference-only correction, not3D reconstruction/volume proof or video compositing. Only complete integrated reference photos will be sent to u30 after actual review.'}
    f=W/'连续精修参数05.json';f.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    (P/'06-记录/图片生成/固定果树单主体25-确定性连续精修05.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({q:{'bbox':v['alpha_bbox'],'file':v['path']} for q,v in records.items()},ensure_ascii=False))
if __name__=='__main__':main()
