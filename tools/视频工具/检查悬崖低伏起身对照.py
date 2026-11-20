"""Independent evaluated-scene measurements; no media generation or API call."""
import hashlib,json,math
from pathlib import Path
import bpy
from mathutils import Vector
P=Path('E:/AutoDL/projects/悬崖上的小气球')
s=bpy.context.scene;rows=[];reference=None;camera=None
for frame in range(1,121):
 s.frame_set(frame);g=bpy.context.evaluated_depsgraph_get();parts=[o for o in s.objects if o.name.startswith('GULU-') and o.type=='MESH']
 signatures=[];points=[]
 for o in parts:
  e=o.evaluated_get(g);mesh=e.to_mesh()
  coords=[tuple(v.co) for v in mesh.vertices];signatures.append((o.name,hashlib.sha256(json.dumps(coords).encode()).hexdigest(),tuple(o.scale)))
  points.extend(e.matrix_world@v.co for v in mesh.vertices);e.to_mesh_clear()
  assert max(abs(a-1) for a in o.scale)<1e-6
 if reference is None:reference=signatures
 assert signatures==reference,'Primitive geometry or scale changed'
 body=s.objects['GULU-20cm-body-ball'];head=s.objects['GULU-head-marker']
 assert abs(body.location.x-0.52)<1e-6 and abs(body.location.y)<1e-6
 assert (head.location-body.location).length>0
 assert abs((head.location-body.location).length-math.hypot(0.15,0.04))<1e-6
 assert head.location.x>body.location.x
 for o in parts:
  if o.name.startswith('GULU-leg-'):
   e=o.evaluated_get(g);dist=(e.matrix_world@Vector((0,0,0.0425))-e.matrix_world@Vector((0,0,-0.0425))).length
   assert abs(dist-0.085)<1e-6
  if o.name.startswith('GULU-paw-contact-'):
   assert abs(o.location.z-0.01)<1e-6
 state=[v for row in s.camera.matrix_world for v in row]+[s.camera.data.ortho_scale]
 if camera is None:camera=state
 assert state==camera
 low=min(v.z for v in points);high=max(v.z for v in points)
 assert abs(low)<1e-6
 rows.append({'frame':frame,'seconds':(frame-1)/24,'whole_height_m':high-low,'body_center_z':body.location.z,'head_center_z':head.location.z,'lowest_paw_z':low})
assert abs(rows[0]['whole_height_m']-0.2)<1e-6
assert abs(rows[-1]['whole_height_m']-0.4)<1e-6
assert len(bpy.data.images)==0
result={'source_blend':bpy.data.filepath,'source_sha256':hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),'frames_measured':120,'checks_passed':True,'rest_height_m':rows[0]['whole_height_m'],'stand_height_m':rows[-1]['whole_height_m'],'body_diameter_m':list(s.objects['GULU-20cm-body-ball'].dimensions),'constant_primitive_geometry_and_scale':True,'fixed_neck_and_leg_link_lengths':True,'planted_feet':True,'fixed_camera':True,'images_count':0,'max_body_vertical_speed_mps':max(abs(b['body_center_z']-a['body_center_z'])*24 for a,b in zip(rows,rows[1:])),'max_head_vertical_speed_mps':max(abs(b['head_center_z']-a['head_center_z'])*24 for a,b in zip(rows,rows[1:])),'mechanism':'supported joint unfolding, not flight; body and head envelopes do not scale','samples':rows}
out=P/'05-检查与验收/姿态高度对照12-独立几何与速度02.json';assert not out.exists();out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='samples'},ensure_ascii=False))
