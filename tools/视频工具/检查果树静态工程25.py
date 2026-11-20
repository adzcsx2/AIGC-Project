"""Read actual saved R25 blend files without rendering or modifying them."""
from pathlib import Path
import bpy,hashlib,json,math
from mathutils import Vector
P=Path(__file__).resolve().parents[2]/'projects/悬崖上的小气球'
G=P/'03-制作/静态构图/固定果树单主体25'
rows=[]
for f in sorted(G.glob('*02.blend')):
 bpy.ops.wm.open_mainfile(filepath=str(f))
 s=bpy.context.scene;bpy.context.view_layer.update()
 def pts(o):return [o.matrix_world@v.co for v in o.data.vertices]
 body=[o for o in s.objects if o.type=='MESH' and o.get('role')=='dragon']
 pp=[v for o in body for v in pts(o)]
 berry=bpy.data.objects.get('唯一浆果');bp=pts(berry)
 core={}
 for n in ['咕噜-固定体积躯干','咕噜-头','咕噜-吻']:
  o=bpy.data.objects.get(n)
  if o:
   core[n]={'mesh_sha256':hashlib.sha256(repr([tuple(v.co) for v in o.data.vertices]).encode()).hexdigest(),'world_scale_norms':[round(o.matrix_world.to_3x3().col[i].length,8) for i in range(3)]}
 row={'file':str(f),'blend_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'units':s.unit_settings.system,'unit_scale':s.unit_settings.scale_length,'body_min_z':min((v.z for v in pp),default=None),'body_max_z':max((v.z for v in pp),default=None),'core':core,'berry_bottom':min(v.z for v in bp),'berry_top':max(v.z for v in bp),'camera_lens':s.camera.data.lens,'camera_position':list(s.camera.location),'image_textures':sum(n.type=='TEX_IMAGE' for m in bpy.data.materials if m.use_nodes for n in m.node_tree.nodes),'actions':len(bpy.data.actions)}
 if json.loads(f.with_suffix('.json').read_text(encoding='utf-8'))['kind']=='APEX':
  mouth=bpy.data.objects.get('咕噜-吻');mp=pts(mouth);row['upper_muzzle_z']=max(v.z for v in mp);row['miss_gap_z']=row['berry_bottom']-row['upper_muzzle_z'];row['berry_x_inside_muzzle_span']=min(v.x for v in mp)<=0<=max(v.x for v in mp)
 rows.append(row)
assert all(r['units']=='METRIC' and r['unit_scale']==1 and r['actions']==0 and r['image_textures']==0 for r in rows)
for n in ['咕噜-固定体积躯干','咕噜-头','咕噜-吻']:
 vals=[r['core'][n] for r in rows if n in r['core']]
 assert all(v['mesh_sha256']==vals[0]['mesh_sha256'] and all(math.isclose(a,b,abs_tol=1e-6) for a,b in zip(v['world_scale_norms'],vals[0]['world_scale_norms'])) for v in vals),n
out={'status':'PASS_STATIC_CORE_AND_UNITS_ONLY','files':rows,'limits':'Saved metric gray geometry only. Does not validate photo transfer, exact character identity, speed or video.'}
f=P/'05-检查与验收/固定果树单主体25-实际Blender工程独立检查02.json';f.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print('R25_GEOMETRY_CHECK '+str(f),flush=True)
