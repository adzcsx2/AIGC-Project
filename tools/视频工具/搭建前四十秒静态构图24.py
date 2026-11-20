"""Blender-only static composition renders; no motion guide or video is produced."""
from pathlib import Path
import hashlib
import json
import math
import sys

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / 'projects/悬崖上的小气球'
OUT = P / '03-制作/静态构图/前四十秒电影重制24'
OUT.mkdir(parents=True, exist_ok=True)
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
SELECT = ARGS or ['RUN', 'LOW', 'BURY', 'TURN', 'SIT', 'MIA', 'ENV']
NAMES = dict(TURN='小龙转向后-朝右四足二十厘米04', RUN='小龙四足起跑-二十厘米与果高校准04', LOW='小龙低伏-十厘米姿态04',
             BURY='小龙落草-埋头位置与物理支撑03', SIT='小龙朝右-低坐与四足尺度03',
             MIA='女孩侧躺-原支撑肘与活动空间04', ENV='无角色-灰岩草地两屋巨树构图03')

NAMES={k:v[:-2]+'05' for k,v in NAMES.items()}
FIT=json.loads((P/'03-制作/生成配置/前四十秒电影重制24/静态镜头回校参数02.json').read_text(encoding='utf-8'))
BX,BY,BZ=FIT['berry_center_m']
PX,PY,PZ=FIT['sapling_root_m']


def mat(name, gray):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (gray, gray, gray, 1)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (gray, gray, gray, 1)
    bsdf.inputs['Roughness'].default_value = .85
    return m


def finish(obj, name, material, role='environment'):
    obj.name = name
    obj.data.materials.append(material)
    obj['role'] = role
    return obj


def ball(name, center, radii, material, role='environment'):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, location=center)
    o = bpy.context.object
    o.scale = radii
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for poly in o.data.polygons:
        poly.use_smooth = True
    return finish(o, name, material, role)


def box(name, center, dimensions, material, role='environment'):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    o = bpy.context.object
    o.scale = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(o, name, material, role)


def link(name, start, end, radius, material, role='environment', tip=None):
    start, end = Vector(start), Vector(end)
    if tip is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=radius, depth=(end-start).length,
                                            location=(start+end)/2)
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=radius, radius2=tip,
                                        depth=(end-start).length, location=(start+end)/2)
    o = bpy.context.object
    o.rotation_euler = (end-start).to_track_quat('Z', 'Y').to_euler()
    return finish(o, name, material, role)


def scene_base():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.unit_settings.system = 'METRIC'
    s.unit_settings.scale_length = 1
    s.render.engine = 'CYCLES'
    s.cycles.device = 'CPU'
    s.cycles.samples = 12
    s.cycles.use_denoising = True
    s.render.resolution_x, s.render.resolution_y = 1344, 756
    s.render.resolution_percentage = 100
    s.render.image_settings.file_format = 'PNG'
    s.view_settings.view_transform = 'AgX'
    world = bpy.data.worlds.new('空白中性画布')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs[0].default_value = (.72,.72,.72,1)
    world.node_tree.nodes['Background'].inputs[1].default_value = .65
    s.world = world
    ground, actor, env, contact = mat('中性地面',.58), mat('主体灰白',.82), mat('环境量尺几何',.65), mat('接触区占位',.48)
    box('真实地面-非图片平面', (0,4,-.12), (16,16,.24), ground)
    box('平行跑道的岩沿', (0,-4.15,-1), (16,.30,2), env)
    # Inland landmarks establish a common world; all are untextured measuring stand-ins.
    for i,(x,y) in enumerate([(-2.4,8.6),(.4,9.4)]):
        box(f'木屋{i+1}-墙体量尺', (x,y,1.4), (2.6,2.2,2.8), env)
        roof = box(f'木屋{i+1}-屋顶占位', (x,y,3.0), (3.0,2.6,.5), env)
        roof.rotation_euler[1] = .05
        box(f'木屋{i+1}-一米八门高', (x,y-1.11,.9), (.75,.035,1.8), contact)
    link('巨树树干-直径约一米', (3.4,5.0,0), (3.4,5.0,5.0), .5, env)
    ball('巨树树冠-纯灰空间占位', (3.4,5.0,6.3), (4.0,3.6,2.3), env)
    # The berry lane is inland, parallel to the rim, never a cliff approach.
    link('浆果树干-跑道外侧', (PX,PY,0), (PX,PY,.95), .024, env)
    link('浆果枝条', (PX,PY,.66), (BX,BY,BZ+.045), .012, env)
    link('唯一果梗', (BX,BY,BZ+.045), (BX,BY,BZ+.015), .003, env)
    ball('唯一目标浆果-固定高位', (BX,BY,BZ), (.015,.015,.015), contact, 'berry')
    ball('浆果树叶量尺占位', (PX-.02,PY+.04,.85), (.24,.18,.22), env)
    box('暗湿草皮-滑点', (-.49,0,.002), (.20,.16,.004), contact)
    box('软草簇-落点', (-.82,.035,.037), (.26,.23,.074), ground, 'soft_grass')
    box('落点旁湿泥-第二次跌坐', (-.79,-.11,.001), (.23,.16,.002), contact)
    ld = bpy.data.lights.new('左上天空柔光','AREA')
    lo = bpy.data.objects.new('左上天空柔光',ld)
    s.collection.objects.link(lo)
    lo.location = (-3,-4,7)
    ld.energy, ld.shape, ld.size = 700,'DISK',6
    lo.rotation_euler = (Vector((0,0,0))-lo.location).to_track_quat('-Z','Y').to_euler()
    return s,actor


def dragon(material, pose):
    created=[]
    def B(name, c, rad, role='dragon'):
        o=ball(name,c,rad,material,role);created.append(o);return o
    def L(name,a,b,r,role='dragon',tip=None):
        o=link(name,a,b,r,material,role,tip);created.append(o);return o
    body_z=.10 if pose in ['RUN','TURN'] else (.052 if pose=='LOW' else (.072 if pose=='BURY' else .073))
    head_z=.135 if pose in ['RUN','TURN'] else (.05 if pose=='LOW' else (.065 if pose=='BURY' else .135))
    head_angle=0 if pose in ['RUN','TURN','SIT'] else (math.radians(45) if pose=='LOW' else math.radians(-30))
    B('咕噜-固定体积躯干',(0,0,body_z),(.10,.060,.045))
    # The head assembly articulates as a rigid unit; no whole-animal Z compression.
    headroot=bpy.data.objects.new('咕噜-头部姿态关节',None)
    bpy.context.scene.collection.objects.link(headroot)
    headroot.location=(-.115,0,head_z)
    headroot.rotation_euler[1]=head_angle
    parts=[B('咕噜-头',(0,0,0),(.05,.04,.035)),B('咕噜-吻',(-.045,0,-.005),(.028,.030,.020))]
    for sign in [-1,1]:
        parts.append(L('咕噜-角',(-.006,sign*.025,.032),(.020,sign*.025,.065),.007,tip=0))
    for o in parts:o.parent=headroot
    for x in [-.065,.065]:
        for y in [-.044,.044]:
            hipz=.087 if pose in ['RUN','TURN'] else (.043 if pose=='LOW' else .060)
            if pose=='SIT' and x>0:hipz=.035
            hip,foot=Vector((x,y,hipz)),Vector((x,y,.011))
            length=.045
            half=(hip-foot).length/2
            assert half < length
            knee=(hip+foot)/2+Vector((math.sqrt(length*length-half*half),0,0))
            L('咕噜-上肢段',hip,knee,.012)
            L('咕噜-下肢段',knee,foot,.011)
            B('咕噜-足掌',foot,(.025,.018,.011))
    for sign in [-1,1]:
        B('咕噜-原有折叠翼',(.025,sign*.057,body_z+.033),(.075,.012,.017),'dragon_wing')
    L('咕噜-尾根',(.08,0,body_z),(.19,0,.055),.018,'dragon_tail',tip=.010)
    L('咕噜-尾尖',(.19,0,.055),(.27,0,.022 if pose!='BURY' else .16),.010,'dragon_tail',tip=.002)
    root=bpy.data.objects.new('咕噜-整体位置与朝向',None)
    bpy.context.scene.collection.objects.link(root)
    for o in created:
        if o.parent is None:o.parent=root
    headroot.parent=root
    root.location.x = .58 if pose=='RUN' else (.40 if pose=='LOW' else -.80)
    if pose in ['SIT','TURN']:root.rotation_euler[2]=math.pi
    return root


def mia(material):
    # A neutral pose block, not a likeness reconstruction or an animated actor.
    x=2.05
    ball('米娅-侧躺躯干',(x,0,.16),(.30,.105,.105),material,'mia')
    ball('米娅-头',(x-.38,-.005,.26),(.09,.080,.100),material,'mia')
    link('米娅-原支撑上臂',(x-.25,-.03,.20),(x-.29,-.15,.035),.035,material,'mia')
    link('米娅-原支撑前臂',(x-.29,-.15,.035),(x-.43,-.055,.20),.03,material,'mia')
    link('米娅-空闲上臂',(x-.17,-.07,.21),(x-.10,-.20,.04),.03,material,'mia')
    link('米娅-空闲前臂',(x-.10,-.20,.04),(x-.32,-.19,.029),.026,material,'mia')
    for y in [-.045,.045]:
        link('米娅-腿',(x+.20,y,.115),(x+.58,y,.055),.045,material,'mia')
        ball('米娅-靴',(x+.65,y,.045),(.09,.045,.045),material,'mia')


def bounds(objects):
    pts=[o.matrix_world@v.co for o in objects for v in o.data.vertices]
    return dict(min=[min(p[i] for p in pts) for i in range(3)],max=[max(p[i] for p in pts) for i in range(3)])


def run(kind):
    s,material=scene_base()
    if kind in ['RUN','LOW','BURY','TURN','SIT']:dragon(material,kind)
    elif kind=='MIA':mia(material)
    data=bpy.data.cameras.new('真实透视摄影机')
    camera=bpy.data.objects.new('真实透视摄影机',data)
    s.collection.objects.link(camera)
    if kind=='ENV':loc,target,lens=(4,-8,3.8),(0,4,1.7),28
    elif kind=='MIA':loc,target,lens=(2.1,-2.8,.90),(2.1,0,.18),45
    elif kind=='LOW':loc,target,lens=(-.15,-4.6,1.5),(-.15,0,.22),35
    else:loc,target,lens=(-.15,-4.6,1.05),(-.15,0,.22),35
    camera.location=loc
    camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
    data.type='PERSP';data.lens=lens;data.sensor_width=36
    if kind not in ['MIA','ENV']:
        data.lens=FIT['lens_mm'];data.shift_x=FIT['shift_x'];data.shift_y=FIT['shift_y']
    s.camera=camera
    bpy.context.view_layer.update()
    actor=[o for o in s.objects if o.type=='MESH' and o.get('role','').startswith('dragon')]
    body=[o for o in actor if o.get('role')=='dragon']
    if kind=='MIA':body=[o for o in s.objects if o.type=='MESH' and o.get('role')=='mia']
    points=[world_to_camera_view(s,camera,o.matrix_world@v.co) for o in body for v in o.data.vertices]
    projection=None
    if points:
        projection=dict(x_min=min(p.x for p in points),x_max=max(p.x for p in points),y_min=min(p.y for p in points),y_max=max(p.y for p in points))
        projection['height_fraction']=projection['y_max']-projection['y_min']
        projection['width_fraction']=projection['x_max']-projection['x_min']
        assert 0<projection['x_min']<projection['x_max']<1,projection
        assert 0<projection['y_min']<projection['y_max']<1,projection
    metadata=dict(kind=kind,units='meters',actor_body_world_bounds=bounds(body) if body else None,
                  actor_including_wings_tail_bounds=bounds(actor) if actor else None,
                  projected_body_envelope=projection,camera=dict(position=loc,target=target,lens_mm=lens,projection='PERSP',sensor_width_mm=36,lens_after_calibration_mm=data.lens,shift_x=data.shift_x,shift_y=data.shift_y),
                  size_definition='GULU standing ground-to-highest horn20cm; low about10cm; tail/wings separate. MIA identity standing height130cm; pose block only.',
                  berry=dict(center_m=[BX,BY,BZ],radius_m=.015,bottom_m=BZ-.015),
                  first_jump_design=dict(ground_mouth_height_m=.150,body_translation_apex_m=.110,maximum_mouth_height_m=.260,clearance_below_berry_m=BZ-.015-.260),
                  rendered_size=[1344,756],motion_guide=False,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  limitation='Proxy geometry/camera dimensions and projection are measured; not actual dragon anatomy, imagegen preservation or dynamic/video validation.')
    if kind in ['RUN','TURN','SIT']:assert abs(metadata['actor_body_world_bounds']['max'][2]-.2)<1e-5,metadata
    if kind=='LOW':assert .09<metadata['actor_body_world_bounds']['max'][2]<.105,metadata
    path=OUT/NAMES[kind]
    s.render.filepath=str(path.with_suffix('.png'))
    bpy.ops.wm.save_as_mainfile(filepath=str(path.with_suffix('.blend')))
    metadata['blend_sha256']=hashlib.sha256(path.with_suffix('.blend').read_bytes()).hexdigest()
    bpy.ops.render.render(write_still=True)
    metadata['render_sha256']=hashlib.sha256(path.with_suffix('.png').read_bytes()).hexdigest()
    path.with_suffix('.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    print('STATIC_RESULT '+json.dumps(dict(kind=kind,projection=projection,body=metadata['actor_body_world_bounds'],png=str(path.with_suffix('.png'))),ensure_ascii=False))


for kind in SELECT:
    assert kind in NAMES,kind
    run(kind)
