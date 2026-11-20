"""Pure primitive guide: fixed 20 cm body ball, unfolding pose from 20 to 40 cm."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from project_tool_safety import save_checked
from whitebox_saved import render_still_new,write_json_new
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'projects/悬崖上的小气球'
DEST=P/'03-制作/三维工程/姿态高度对照12-球体低伏起身01.blend'

def make(name,kind,size,loc,color,parent):
 if kind=='sphere':bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12)
 elif kind=='cylinder':bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=1,depth=2)
 else:bpy.ops.mesh.primitive_cube_add(size=2)
 o=bpy.context.object;o.name=name;o.dimensions=size
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 o.location=loc;o.color=color;o.parent=parent
 return o

def link(o,a,b,frame):
 a,b=Vector(a),Vector(b);o.location=(a+b)/2
 o.rotation_mode='QUATERNION';o.rotation_quaternion=(b-a).to_track_quat('Z','Y')
 o.keyframe_insert('location',frame=frame);o.keyframe_insert('rotation_quaternion',frame=frame)

def main():
 bpy.ops.wm.read_factory_settings(use_empty=True)
 s=bpy.context.scene;s.frame_start=1;s.frame_end=120;s.render.fps=24;s.render.fps_base=1
 s.render.resolution_x=1280;s.render.resolution_y=720;s.render.resolution_percentage=100
 s.render.engine='BLENDER_WORKBENCH';s.display.shading.light='FLAT';s.display.shading.color_type='OBJECT'
 s.display.shading.background_type='WORLD';s.display.shading.show_shadows=False;s.display.shading.show_cavity=False
 s.world=bpy.data.worlds.new('空白中性背景');s.world.color=(0.38,0.38,0.38)
 roots={}
 for name in ['MIA-ROOT','GULU-ROOT']:
  roots[name]=bpy.data.objects.new(name,None);s.collection.objects.link(roots[name])
 blue=(0.08,0.32,0.78,1);orange=(0.92,0.52,0.12,1)
 girl=make('MIA-body-cylinder','cylinder',(0.24,0.24,1.1),(-0.72,0,0.12),blue,roots['MIA-ROOT'])
 girl.rotation_euler[1]=math.pi/2
 make('MIA-head-end-marker','cube',(0.2,0.18,0.18),(-0.07,0,0.15),blue,roots['MIA-ROOT'])
 base=0.52
 body=make('GULU-20cm-body-ball','sphere',(0.2,0.2,0.2),(base,0,0.1),orange,roots['GULU-ROOT'])
 head=make('GULU-head-marker','sphere',(0.12,0.12,0.12),(base+0.15,0,0.14),orange,roots['GULU-ROOT'])
 length=math.hypot(0.15,0.04)
 neck=make('GULU-neck-link','cylinder',(0.018,0.018,length),(0,0,0),orange,roots['GULU-ROOT'])
 legs=[]
 for i,(dx,dy) in enumerate([(-0.065,-0.065),(-0.065,0.065),(0.065,-0.065),(0.065,0.065)]):
  foot=(base+dx,dy,0.02)
  make(f'GULU-paw-contact-{i}','cylinder',(0.03,0.03,0.02),(foot[0],foot[1],0.01),orange,roots['GULU-ROOT'])
  upper=make(f'GULU-leg-{i}-upper','cylinder',(0.012,0.012,0.085),(0,0,0),orange,roots['GULU-ROOT'])
  lower=make(f'GULU-leg-{i}-lower','cylinder',(0.012,0.012,0.085),(0,0,0),orange,roots['GULU-ROOT'])
  legs.append((dx,dy,foot,upper,lower))
 theta0=math.asin(0.04/length);theta1=math.asin(0.14/length)
 for frame in range(1,121):
  t=(frame-1)/24;u=max(0,min(1,(t-1.2)/0.6));q=u*u*(3-2*u)
  z=0.1+0.1*q;theta=theta0+(theta1-theta0)*q
  center=(base,0,z);headloc=(base+length*math.cos(theta),0,z+length*math.sin(theta))
  body.location=center;head.location=headloc
  body.keyframe_insert('location',frame=frame);head.keyframe_insert('location',frame=frame)
  link(neck,center,headloc,frame)
  for dx,dy,foot,upper,lower in legs:
   hip=Vector((base+dx,dy,z-0.03));f=Vector(foot);mid=(hip+f)/2
   side=1 if dy>0 else -1
   knee=mid+Vector((0,side*math.sqrt(0.085**2-((hip-f).length/2)**2),0))
   link(upper,hip,knee,frame);link(lower,knee,f,frame)
 # Dense frame keys with linear interpolation avoid overshoot between evaluated frames.
 for o in s.objects:
  if o.animation_data and o.animation_data.action:
   for layer in o.animation_data.action.layers:
    for strip in layer.strips:
     for bag in strip.channelbags:
      for curve in bag.fcurves:
       for key in curve.keyframe_points:key.interpolation='LINEAR'
 camdata=bpy.data.cameras.new('固定比尺机位');cam=bpy.data.objects.new('Camera-fixed',camdata);s.collection.objects.link(cam)
 cam.location=(-0.05,-6,0.6);target=Vector((-0.05,0,0.35))
 cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();camdata.type='ORTHO';camdata.ortho_scale=2.8
 camdata.lens=50;camdata.clip_start=0.01;camdata.clip_end=100;s.camera=cam
 marker=s.timeline_markers.new('POSE-CONTROL12',frame=1);marker.camera=cam
 s.frame_set(1)
 style=P/'01-文档/视觉设定/视觉设定-版本03-场景候选登记.md';digest=hashlib.sha256(style.read_bytes()).hexdigest()
 def validate():
  assert hashlib.sha256(style.read_bytes()).hexdigest()==digest
  assert len(bpy.data.images)==0
 saved=save_checked(bpy,DEST,P,validate)
 info={'blend':DEST.relative_to(P).as_posix(),'sha256':saved,'body_sphere_diameter_m':0.2,'head_marker_diameter_m':0.12,'crouched_height_m':0.2,'standing_height_m':0.4,'normal_rise_seconds':[1.2,1.8],'girl_span_m':1.3,'model_only':True,'camera':{'name':cam.name,'type':camdata.type,'location':list(cam.location),'target':list(target),'ortho_scale':camdata.ortho_scale,'motion':'fixed'},'mechanism':'constant-size body ball and head; fixed-length neck and two-link primitive leg supports unfold; planted paw anchors; no scaling or root travel'}
 write_json_new(P/'05-检查与验收/姿态高度对照12-白模构建01.json',info,P)
 still=P/'05-检查与验收/姿态高度对照12-白模首帧01.png';render_still_new(bpy,still,P)
 print(json.dumps(info,ensure_ascii=False))

if __name__=='__main__':main()
