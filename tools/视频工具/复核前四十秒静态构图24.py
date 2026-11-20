"""Independently reopen the selected .blend files and measure actual saved geometry."""
from pathlib import Path
import hashlib
import json

import bpy
from bpy_extras.object_utils import world_to_camera_view

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'projects/悬崖上的小气球'
package=json.loads((P/'03-制作/生成配置/前四十秒电影重制24/制作包01.json').read_text(encoding='utf-8'))
result=[]
mesh_dimensions={}
for key,png in package['assets'].items():
    if not key.startswith('CLAY-'):continue
    file=Path(png).with_suffix('.blend')
    metadata=json.loads(Path(png).with_suffix('.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(file.read_bytes()).hexdigest()==metadata['blend_sha256']
    assert hashlib.sha256(Path(png).read_bytes()).hexdigest()==metadata['render_sha256']
    bpy.ops.wm.open_mainfile(filepath=str(file))
    s=bpy.context.scene
    bpy.context.view_layer.update()
    assert s.unit_settings.system=='METRIC' and s.unit_settings.scale_length==1
    assert s.camera.data.type=='PERSP'
    assert not any(o.type=='FONT' or o.animation_data for o in s.objects)
    assert not any(n.type=='TEX_IMAGE' for m in bpy.data.materials if m.use_nodes for n in m.node_tree.nodes)
    body=[o for o in s.objects if o.type=='MESH' and o.get('role') in ['dragon','mia']]
    paws=[o for o in body if o.name.startswith('咕噜-足掌')]
    pts=[o.matrix_world@v.co for o in body for v in o.data.vertices]
    low=min((p.z for p in pts),default=None)
    high=max((p.z for p in pts),default=None)
    if pts:assert low>=-1e-6,(key,low)
    if key in ['CLAY-RUN','CLAY-TURN','CLAY-SIT']:assert abs(high-.2)<1e-5,(key,high)
    if key=='CLAY-LOW':assert .09<high<.105,(key,high)
    if key.startswith('CLAY-') and key not in ['CLAY-MIA','CLAY-ENV']:
        assert len(paws)==4,(key,len(paws))
        for paw in paws:assert abs(min((paw.matrix_world@v.co).z for v in paw.data.vertices))<1e-6
        for part in ['咕噜-固定体积躯干','咕噜-头','咕噜-吻']:
            o=s.objects[part]
            shape=tuple(round(n,7) for v in o.data.vertices for n in v.co)
            if part in mesh_dimensions:assert mesh_dimensions[part]==shape,(key,part)
            else:mesh_dimensions[part]=shape
    projected=[world_to_camera_view(s,s.camera,p) for p in pts]
    envelope=None
    if projected:
        envelope=dict(height_fraction=max(p.y for p in projected)-min(p.y for p in projected),width_fraction=max(p.x for p in projected)-min(p.x for p in projected))
        assert abs(envelope['height_fraction']-metadata['projected_body_envelope']['height_fraction'])<1e-6
    berry=s.objects['唯一目标浆果-固定高位']
    berry_low=min((berry.matrix_world@v.co).z for v in berry.data.vertices)
    assert abs(berry_low-metadata['berry']['bottom_m'])<1e-6
    if key=='CLAY-TURN':assert abs(s.objects['咕噜-整体位置与朝向'].location.x+.8)<1e-6
    if key=='CLAY-ENV':assert not body
    anchors={}
    for name in ['唯一目标浆果-固定高位','软草簇-落点','暗湿草皮-滑点']:
        pp=world_to_camera_view(s,s.camera,s.objects[name].location);anchors[name]={'x':pp.x,'y_from_top':1-pp.y}
    result.append(dict(anchors=anchors,asset=key,file=str(file),geometry_min_z_m=low,geometry_max_z_m=high,projection=envelope,berry_bottom_m=berry_low,feet_supported=len(paws),status='PASS_STATIC_GEOMETRY_ONLY'))
out=dict(stage='static_geometry_before_image_conversion',files=result,component_shape_equality='same local body/head/muzzle geometry across5 postures',camera_and_units='actual saved scene independently reopened',no_photo_planes_or_motion='PASS',first_jump_clearance_design='Mouth upper edge15cm +11cm body translation=26cm; fixed berry bottom follows fitted design geometry; no video measurement',limits='No AI photoreal conversion or video motion/size/style validated by these checks.')
f=P/'05-检查与验收/前四十秒电影重制24-静态白模独立复核01.json'
f.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print('INDEPENDENT_STATIC_CHECK '+json.dumps(out,ensure_ascii=False))
