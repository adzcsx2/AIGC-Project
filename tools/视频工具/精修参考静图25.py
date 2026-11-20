"""User-authorized deterministic edits of reference STILLS only; never video."""
from pathlib import Path
import hashlib,json,math
from PIL import Image,ImageDraw,ImageFilter,ImageOps,ImageChops
import yaml

R=Path(__file__).resolve().parents[2];P=R/'projects/悬崖上的小气球'
A=P/'02-素材/镜头/固定果树单主体25';O=A/'确定性精修04'
W=P/'03-制作/静态精修/固定果树25-确定性04'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def style():
    d=yaml.safe_load((P/'project.yaml').read_text(encoding='utf-8'));f=P/d['documents']['style']
    f.read_text(encoding='utf-8');g=R/'docs/视觉规范/中世纪写实风格规范.md';g.read_text(encoding='utf-8')
    return {'path':str(f),'sha256':sha(f),'shared_sha256':sha(g)}

SOURCES={'RUN':A/'小龙四足二十厘米-固定果树尺度母图06.png',
 'ENV':A/'固定果树-草地无角色电影母图02.png',
 'LOW':A/'修复03/幼龙侧卧晒太阳-原体量十厘米低位08.png',
 'BURY':A/'修复03/幼龙落草接触-原体量与压倒草叶04.png',
 'TURN':A/'修复03/幼龙原落点转右-四足二十厘米04.png'}
OUTNAMES={'RUN':'幼龙四足二十厘米-共同底图与尺寸精修04.png',
 'LOW':'幼龙低伏十厘米-关节姿态与头身精修04.png',
 'APEX':'幼龙腾空落空-同一体量与果下气隙精修04.png',
 'BURY':'幼龙埋草-同体量与固定落点精修04.png',
 'TURN':'幼龙拔头转右-原地与同体量精修04.png'}
polys={
 'RUN':[(1005,561),(1010,550),(1018,549),(1023,541),(1027,544),(1033,539),(1034,533),(1038,537),(1046,535),(1051,530),(1050,540),(1043,550),(1048,549),(1045,559),(1052,557),(1047,566),(1052,566),(1058,555),(1064,548),(1089,547),(1112,557),(1123,570),(1134,585),(1147,594),(1153,600),(1170,605),(1198,609),(1197,612),(1176,614),(1143,613),(1113,606),(1114,616),(1112,621),(1104,620),(1097,622),(1092,619),(1096,608),(1085,594),(1078,601),(1067,614),(1066,621),(1060,626),(1053,624),(1044,626),(1037,624),(1039,620),(1045,614),(1052,602),(1054,594),(1045,592),(1035,610),(1029,617),(1012,617),(1013,613),(1021,609),(1027,594),(1030,582),(1010,581),(1001,575),(996,573),(996,569),(1002,566)],
 'HEAD':[(996,569),(1005,564),(1008,557),(1011,550),(1018,549),(1023,541),(1028,544),(1033,539),(1034,533),(1038,537),(1046,535),(1051,530),(1050,541),(1042,550),(1048,549),(1044,558),(1052,556),(1047,565),(1051,567),(1045,573),(1040,575),(1031,580),(1020,582),(1007,581),(1000,576),(996,574)],
 'LOW-BODY':[(1024,593),(1037,584),(1060,581),(1082,582),(1106,589),(1125,604),(1143,615),(1155,629),(1157,639),(1149,646),(1133,650),(1103,649),(1084,646),(1077,647),(1066,644),(1055,646),(1040,642),(1023,642),(1013,644),(1005,639),(1006,630),(1017,625),(1025,620),(1020,611)],
 'LOW-WING':[(1024,584),(1027,571),(1041,558),(1067,552),(1083,550),(1107,554),(1127,564),(1145,575),(1153,583),(1147,587),(1124,578),(1102,574),(1083,576),(1062,584),(1037,597),(1026,599)],
 'TAIL':[(1098,592),(1114,598),(1138,605),(1167,608),(1198,609),(1198,612),(1177,614),(1147,613),(1128,610),(1110,605),(1098,602)],
 'BURY-BODY':[(672,581),(677,564),(691,553),(723,547),(751,549),(777,559),(786,572),(802,580),(828,580),(846,568),(849,548),(843,537),(837,534),(839,530),(850,536),(855,550),(854,570),(844,584),(823,596),(794,599),(782,610),(778,618),(767,625),(757,624),(750,625),(746,620),(753,612),(742,602),(726,611),(712,621),(704,630),(694,635),(681,632),(677,635),(672,631),(674,624),(687,616),(692,606),(679,606),(669,599)],
 'TURN-BODY':[(670,579),(663,562),(677,551),(703,545),(733,545),(757,552),(771,562),(765,573),(773,581),(784,586),(784,600),(774,608),(784,619),(790,626),(785,634),(777,633),(772,634),(765,631),(755,620),(745,611),(731,611),(716,610),(699,610),(694,621),(699,628),(694,634),(685,635),(677,632),(674,626),(666,614),(656,605),(635,605),(606,601),(590,592),(578,580),(574,565),(578,547),(590,532),(611,520),(637,514),(662,509),(663,512),(641,519),(620,527),(603,539),(592,555),(592,568),(602,580),(624,587),(648,589),(661,586)]
}

def cut(key,polykey):
    im=Image.open(SOURCES[key]).convert('RGBA');pts=polys[polykey]
    x0=min(x for x,y in pts)-2;y0=min(y for x,y in pts)-2;x1=max(x for x,y in pts)+3;y1=max(y for x,y in pts)+3
    im=im.crop((x0,y0,x1,y1));m=Image.new('L',(im.width*4,im.height*4));ImageDraw.Draw(m).polygon([((x-x0)*4,(y-y0)*4) for x,y in pts],fill=255)
    m=m.resize(im.size,Image.Resampling.LANCZOS)
    inside=m.filter(ImageFilter.MinFilter(5));pix=im.load();alpha=m.load();ins=inside.load()
    # Remove green only along the polygon perimeter, preserving interior blue eyes.
    for y in range(im.height):
        for x in range(im.width):
            rr,gg,bb,_=pix[x,y]
            if ins[x,y]<180 and gg>rr*1.08 and gg>bb*1.15:alpha[x,y]=0
    im.putalpha(m);return trim(im)
def trim(im):
    b=im.getchannel('A').point(lambda a:255 if a>8 else 0).getbbox()
    return im.crop(b) if b else im
def resize(im,sx,sy=None):return im.resize((max(1,round(im.width*sx)),max(1,round(im.height*(sy if sy is not None else sx)))),Image.Resampling.LANCZOS)
def rotate(im,a):return trim(im.rotate(a,Image.Resampling.BICUBIC,expand=True))
def draw(im,part,xy):im.alpha_composite(part,(round(xy[0]),round(xy[1])))
def shadow(im,box,opacity=48):
    l=Image.new('RGBA',im.size);ImageDraw.Draw(l).ellipse(box,fill=(30,30,18,opacity));im.alpha_composite(l.filter(ImageFilter.GaussianBlur(2)))
def grass_contact(im,headx,ground=611):
    # Unmodified real blades copied from the same base photograph, not painted CG grass.
    base=Image.open(SOURCES['ENV']).convert('RGBA')
    patch=base.crop((744,579,800,612));m=Image.new('L',patch.size)
    ImageDraw.Draw(m).polygon([(0,33),(4,24),(7,15),(12,29),(15,8),(18,27),(22,16),(25,30),(30,11),(33,26),(37,17),(41,31),(45,22),(50,25),(55,33)],fill=220)
    patch.putalpha(m.filter(ImageFilter.GaussianBlur(.35)))
    draw(im,patch,(headx-14,ground-29))

def main():
    O.mkdir(parents=True,exist_ok=True);W.mkdir(parents=True,exist_ok=True)
    base=Image.open(SOURCES['ENV']).convert('RGBA');log=[]
    stand_raw=cut('RUN','RUN');scale=79/stand_raw.height;stand=resize(stand_raw,scale)
    head=resize(cut('RUN','HEAD'),scale)
    # Head is the same rigid photographed patch in all wide references, not regenerated.
    head.save(W/'同一头部-校准原始像素.png')
    records={}
    for key in ['RUN','LOW','APEX','BURY','TURN']:
        st=style();im=base.copy();layer=Image.new('RGBA',base.size)
        if key=='RUN':
            draw(layer,stand,(1008,532));shadow(im,(1024,603,1132,616),42)
            recipe={'whole_source_scale':scale,'top_left':[1008,532],'body_height_target_px':79,'purpose':'standing20cm calibration'}
        elif key=='LOW':
            body=resize(cut('LOW','LOW-BODY'),.63,.45)
            wing=resize(cut('LOW','LOW-WING'),.56)
            tail=resize(cut('RUN','TAIL'),scale)
            lowhead=rotate(head,-17)
            draw(layer,tail,(1098,599));draw(layer,body,(1030,579));draw(layer,wing,(1056,570));draw(layer,lowhead,(1008,611-lowhead.height))
            shadow(im,(1014,603,1132,617),45)
            recipe={'head_source':'same RUN head patch','head_rotation_degrees':-17,'head_scale':1,'folded_body_source':'LOW08 existing folded limbs','body_patch_correction':[.63,.45],'wing_patch_scale':.56,'height_target_px':41,'purpose':'repair erroneous enlarged folded body; no uniform scaling of whole animal into a low pose'}
        elif key=='APEX':
            draw(layer,stand,(903,412));shadow(im,(929,605,1035,616),27)
            recipe={'same_standing_pixels':True,'whole_body_translation_from_RUN':[-105,-120],'nose_under_berry_x':904,'upper_lip_target_y':442,'empty_gap_target_px':94,'purpose':'same-size rigid displacement, not enlarged torso or branch contact'}
        elif key=='BURY':
            body=resize(cut('BURY','BURY-BODY'),.65)
            draw(layer,body,(682,546));down=rotate(head,23);draw(layer,down,(650,611-down.height))
            shadow(im,(652,602,769,618),48)
            recipe={'head_source':'same RUN head patch','head_rotation_degrees':23,'head_scale':1,'body_patch_scale':.65,'body_center_target_px':[717,588],'ground_y':611,'grass_occlusion':True,'purpose':'same-scale folded/shoulder-low body at left-of-berry right-of-trunk tuft'}
        else:
            body=resize(cut('TURN','TURN-BODY'),.65)
            draw(layer,body,(621,532));right=ImageOps.mirror(head);draw(layer,right,(742,532))
            # A source neck bridges the unchanged head to the calibrated body at the same depth.
            neck=resize(cut('RUN','HEAD'),scale)
            shadow(im,(660,603,773,617),44)
            recipe={'head_source':'same RUN head patch mirrored for right-facing reference','head_scale':1,'body_patch_scale':.65,'head_top_y':532,'ground_y':611,'purpose':'in-place right-facing aftermath, same core reference size'}
        im.alpha_composite(layer)
        if key=='BURY':grass_contact(im,655)
        if key=='TURN':grass_contact(im,659)
        dest=O/OUTNAMES[key];im.convert('RGB').save(dest)
        layer.save(W/(key+'-参考精修工作层.png'))
        bbox=layer.getchannel('A').point(lambda a:255 if a>32 else 0).getbbox()
        records[key]={'path':str(dest),'sha256':sha(dest),'alpha_bbox':bbox,'recipe':recipe,'style':st,'status':'ACTUAL_RESULT_NEEDS_REVIEW'}
        # No prompt is sent to a model during this deterministic operation.
        log.append({'id':key,**records[key],'tool':'Pillow deterministic reference-still edit','actual_model_prompt':None})
    meta={'scope':'User explicitly allowed deterministic editing of reference STILLS only','video_layers_or_retiming':False,'base_plate':str(SOURCES['ENV']),'base_sha256':sha(SOURCES['ENV']),'sources':{k:{'path':str(v),'sha256':sha(v)} for k,v in SOURCES.items()},'outputs':records,'limitations':'2D reference calibration and photographic patch articulation, not a recovered3D model or guaranteed u30 volume. Individual working layers NEVER sent to u30; only full integrated references after review.'}
    (W/'确定性精修参数04.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    (P/'06-记录/图片生成/固定果树单主体25-确定性静图精修04.json').write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'outputs':[{'id':k,'bbox':v['alpha_bbox']} for k,v in records.items()],'work':str(W)},ensure_ascii=False))
if __name__=='__main__':main()
