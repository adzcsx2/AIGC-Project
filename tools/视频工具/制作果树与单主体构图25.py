"""Metric static studies for the authorized R25; no motion guide is created."""
from pathlib import Path
import ast
import hashlib
import json
import math
import sys
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'projects/悬崖上的小气球'
OUT=P/'03-制作/静态构图/固定果树单主体25'
OUT.mkdir(parents=True,exist_ok=True)
# Reuse only geometric helper functions. Never execute the historical driver,
# its camera fitting, its output setup, or its rendering loop.
OLD=ROOT/'tools/视频工具/搭建前四十秒静态构图24.py'
tree=ast.parse(OLD.read_text(encoding='utf-8'))
names={'mat','finish','ball','box','link','dragon','mia','bounds'}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),str(OLD),'exec'))
SELECT=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else ['TREE','ENV','LOW','RUN','APEX','BURY','TURN','SIT','REACT','END','MIA']
NAMES={'TREE':'果树定型-整树一米与单果七十厘米01','ENV':'固定果树与草地-无角色母图构图01','LOW':'同机位-小龙低伏十厘米01','RUN':'同机位-小龙四足二十厘米01','APEX':'同机位-嘴高四十五厘米仍够不到01','BURY':'同机位-落草埋头与固定树形01','TURN':'同机位-拔头后朝右二十厘米01','SIT':'同机位-跌坐与泥草接触01','REACT':'近景切镜-原地朝右受挫01','END':'近景切镜-后躯低坐与失落01','MIA':'女孩单独侧躺-树在画外01'}
NAMES={k:v[:-2]+'02' for k,v in NAMES.items()}

def plant(material,contact):
    link('果树-主干',(-.9,0,0),(-.80,0,.86),.014,material,tip=.006)
    link('果树-上部枝',(-.84,0,.65),(-.90,0,.98),.005,material,tip=.002)
    link('果树-斜生挂果枝A',(-.80,0,.80),(-.46,0,.85),.005,material,tip=.003)
    link('果树-斜生挂果枝B',(-.46,0,.85),(0,0,.76),.003,material,tip=.0015)
    link('唯一果梗',(0,0,.76),(0,0,.730),.0015,material)
    ball('唯一浆果',(0,0,.715),(.015,.015,.015),contact,'berry')
    ball('树冠顶部一米',(-.88,0,.90),(.17,.075,.10),material,'plant_crown')
    ball('树冠次枝',(-.65,.005,.87),(.14,.06,.10),material,'plant_crown')

def base(kind):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s=bpy.context.scene;s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
    s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=12;s.cycles.use_denoising=True
    s.render.resolution_x,s.render.resolution_y=1344,756;s.render.resolution_percentage=100
    s.render.image_settings.file_format='PNG';s.view_settings.view_transform='AgX'
    w=bpy.data.worlds.new('中性灰画布');w.use_nodes=True
    w.node_tree.nodes['Background'].inputs[0].default_value=(.7,.7,.7,1);w.node_tree.nodes['Background'].inputs[1].default_value=.7;s.world=w
    ground,actor,env,contact=mat('地面灰',.58),mat('主体灰白',.82),mat('场景量尺灰',.65),mat('接触区灰',.4)
    box('实际地面',(0,4,-.12),(16,16,.24),ground)
    plant(env,contact)
    if kind!='TREE':
        for i,(x,y) in enumerate([(-2.4,8.6),(.4,9.4)]):
            box(f'远处木屋{i+1}',(x,y,1.4),(2.6,2.2,2.8),env)
            box(f'木屋{i+1}屋顶',(x,y,3.0),(3,2.6,.5),env)
        link('远处巨树',(3.4,5,0),(3.4,5,5),.5,env)
        ball('远处巨树冠',(3.4,5,6.3),(4,3.6,2.3),env)
        box('湿滑草皮',(.18,0,.001),(.26,.14,.002),contact)
        box('同深度软草簇',(-.35,0,.025),(.24,.18,.050),ground,'soft_grass')
        box('软泥落点',(-.35,0,.001),(.26,.18,.002),contact)
    l=bpy.data.lights.new('左上自然天空光','AREA');o=bpy.data.objects.new('左上自然天空光',l);s.collection.objects.link(o)
    o.location=(-3,-4,7);o.rotation_euler=(Vector((0,0,0))-o.location).to_track_quat('-Z','Y').to_euler();l.energy=700;l.size=6
    return s,actor

def run(kind):
    s,material=base(kind)
    if kind in ['LOW','RUN','APEX','BURY','TURN','SIT','REACT','END']:
        pose={'APEX':'RUN','REACT':'TURN','END':'SIT'}.get(kind,kind)
        root=dragon(material,pose)
        if pose=='BURY':
            tip=bpy.data.objects['咕噜-尾尖'];a=Vector((.19,0,.055));direction=Vector((.08,0,.105)).normalized()
            fixed_length=Vector((.08,0,-.033)).length
            tip.scale.z*=fixed_length/Vector((.08,0,.105)).length
            tip.location=(a+a+direction*fixed_length)/2
        # The muzzle, not the torso center, is under the berry at the apex.
        root.location=(.62 if kind=='LOW' else (.8 if kind=='RUN' else (.18 if kind=='APEX' else -.35)),0,.30 if kind=='APEX' else 0)
    if kind=='MIA':mia(material)
    camera_data=bpy.data.cameras.new('固定真实透视机位');camera=bpy.data.objects.new('固定真实透视机位',camera_data);s.collection.objects.link(camera)
    loc,target,lens=(-.15,-4.6,1.05),(-.15,0,.25),35
    if kind=='TREE':loc,target,lens=(-.45,-2.7,.75),(-.45,0,.50),48
    if kind in ['REACT','END']:loc,target,lens=(-.35,-4.6,1.05),(-.35,0,.10),85
    if kind=='MIA':loc,target,lens=(2.1,-3,.85),(2.1,0,.18),45
    camera.location=loc;camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler();camera_data.lens=lens;camera_data.sensor_width=36;s.camera=camera
    bpy.context.view_layer.update()
    body=[o for o in s.objects if o.type=='MESH' and o.get('role')=='dragon']
    pts=[world_to_camera_view(s,camera,o.matrix_world@v.co) for o in body for v in o.data.vertices]
    projection={'xmin':min(p.x for p in pts),'xmax':max(p.x for p in pts),'top':1-max(p.y for p in pts),'bottom':1-min(p.y for p in pts),'height':max(p.y for p in pts)-min(p.y for p in pts)} if pts else None
    berry=world_to_camera_view(s,camera,Vector((0,0,.715)))
    ground=world_to_camera_view(s,camera,Vector((0,0,0)))
    record={'kind':kind,'meter_units':True,'camera':{'position':loc,'target':target,'lens_mm':lens,'sensor_mm':36},'body_bounds':bounds(body) if body else None,'projection':projection,'scene_dimensions':{'tree_highest_m':1,'tree_root':[-.9,0,0],'berry_center':[0,0,.715],'berry_bottom_m':.70,'berry_diameter_m':.03,'lowest_hanging_branch_m':.76,'dragon_ground_depth_y':0,'stand_height_m':.20,'low_height_m':.1025,'first_jump_body_translation_m':.30,'mouth_apex_max_m':.45,'miss_gap_min_m':.25,'jump_root_x_m':.18,'wet_patch_x_m':.18},'berry_projection':{'x':berry.x,'top':1-berry.y,'ground_top':1-ground.y},'pose_body_meshes_same':'fixed component builder; independent check required','no_animation':True,'not_u30_media':True,'helper_sha256':hashlib.sha256(OLD.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'limits':'Metric design and projection only; AI photo transfer and video still require actual checks.'}
    if kind in ['RUN','TURN','REACT','SIT','END']:assert abs(record['body_bounds']['max'][2]-.2)<1e-5
    if kind=='APEX':assert abs(record['body_bounds']['max'][2]-.5)<1e-5
    if kind=='LOW':assert .09<record['body_bounds']['max'][2]<.105
    path=OUT/NAMES[kind];s.render.filepath=str(path.with_suffix('.png'))
    bpy.ops.wm.save_as_mainfile(filepath=str(path.with_suffix('.blend')));bpy.ops.render.render(write_still=True)
    record['blend_sha256']=hashlib.sha256(path.with_suffix('.blend').read_bytes()).hexdigest();record['png_sha256']=hashlib.sha256(path.with_suffix('.png').read_bytes()).hexdigest()
    path.with_suffix('.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print('R25_STATIC '+json.dumps({'kind':kind,'projection':projection,'berry':record['berry_projection']},ensure_ascii=False),flush=True)

for kind in SELECT:run(kind)
