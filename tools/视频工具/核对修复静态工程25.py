"""Inspect saved R25 repair studies independently; never render or change them."""
from pathlib import Path
import hashlib,json,math
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

P=Path(__file__).resolve().parents[2]/'projects/悬崖上的小气球'
G=P/'03-制作/静态构图/固定果树单主体25'
rows=[]
for f in sorted(G.glob('*06.blend')):
    bpy.ops.wm.open_mainfile(filepath=str(f))
    s=bpy.context.scene;bpy.context.view_layer.update()
    def points(o):return [o.matrix_world@v.co for v in o.data.vertices]
    def volume(o):
        o.data.calc_loop_triangles()
        vs=o.data.vertices
        local=sum(vs[t.vertices[0]].co.dot(vs[t.vertices[1]].co.cross(vs[t.vertices[2]].co)) for t in o.data.loop_triangles)/6
        return abs(local*o.matrix_world.to_3x3().determinant())
    actors=[o for o in s.objects if o.type=='MESH' and str(o.get('role','')).startswith('dragon')]
    body=[o for o in actors if o.get('role')=='dragon']
    pp=[v for o in body for v in points(o)]
    parts={o.name:{'volume_m3':volume(o),'min_z':min(v.z for v in points(o)),'max_z':max(v.z for v in points(o))} for o in actors}
    meta=json.loads(f.with_suffix('.json').read_text(encoding='utf-8'))
    kind=meta['kind'];berry=points(bpy.data.objects['唯一浆果'])
    projection=[world_to_camera_view(s,s.camera,v) for v in pp]
    row={'kind':kind,'file':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),
         'units':s.unit_settings.system,'unit_scale':s.unit_settings.scale_length,
         'max_z':max(v.z for v in pp),'min_z':min(v.z for v in pp),'parts':parts,
         'projected_height':max(v.y for v in projection)-min(v.y for v in projection),
         'camera':{'position':list(s.camera.location),'lens_mm':s.camera.data.lens},
         'image_textures':sum(n.type=='TEX_IMAGE' for m in bpy.data.materials if m.use_nodes for n in m.node_tree.nodes),
         'actions':len(bpy.data.actions),'opaque_tuft_box':bpy.data.objects.get('草丛落点') is not None}
    if kind=='APEX':
        mouth=points(bpy.data.objects['咕噜-吻'])
        row.update(mouth_top=max(v.z for v in mouth),berry_bottom=min(v.z for v in berry),
                   gap=min(v.z for v in berry)-max(v.z for v in mouth),
                   mouth_under_berry=min(v.x for v in mouth)<=0<=max(v.x for v in mouth))
    rows.append(row)

assert {r['kind'] for r in rows}=={'RUN','LOW','APEX','BURY','TURN','REACT','END'}
issues=[];reference=next(r for r in rows if r['kind']=='RUN')
for row in rows:
    if not(row['units']=='METRIC' and row['unit_scale']==1 and row['actions']==0 and row['image_textures']==0 and not row['opaque_tuft_box']):issues.append((row['kind'],'scene_contract'))
    if row['parts'].keys()!=reference['parts'].keys():issues.append((row['kind'],'part_set'))
    if any(p['min_z']<-.002 for p in row['parts'].values()):issues.append((row['kind'],'ground_penetration'))
    for name,p in row['parts'].items():
        v0=reference['parts'][name]['volume_m3']
        if not math.isclose(p['volume_m3'],v0,rel_tol=2e-5,abs_tol=1e-12):issues.append((row['kind'],name,'component_volume',p['volume_m3'],v0))
    target=.10 if row['kind']=='LOW' else (.50 if row['kind']=='APEX' else (.14 if row['kind']=='BURY' else .20))
    if row['kind']!='BURY' and abs(row['max_z']-target)>.005:issues.append((row['kind'],'body_height',row['max_z']))
    if row['kind']=='APEX' and not (math.isclose(row['gap'],.25,abs_tol=1e-5) and row['mouth_under_berry']):issues.append(('APEX','miss_geometry'))
    if row['kind']=='END' and abs(row['parts']['咕噜-固定体积躯干']['min_z'])>.003:issues.append(('END','rear_contact'))
out={'status':'PASS_STATIC_COMPONENT_GEOMETRY' if not issues else 'FAIL_STATIC_GEOMETRY','issues':issues,'files':rows,
     'limits':'Rigid component volumes, world heights, support and saved-camera projections only. Overlapping component sums are not an occupied-union volume. This does not establish photo anatomy/scale transfer, real video motion, speed or u30 hard control.'}
dest=P/'05-检查与验收/固定果树单主体25-修复03-独立工程核对.json'
dest.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':out['status'],'issues':issues,'kinds':[{'kind':r['kind'],'height_m':r['max_z'],'projected_h':r['projected_height']} for r in rows],'output':str(dest)},ensure_ascii=False),flush=True)
assert not issues,issues
