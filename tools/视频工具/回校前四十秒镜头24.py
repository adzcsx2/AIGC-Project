"""Fit the design camera to the selected small-subject photographic composition.

This assumes the prescribed20cm proxy; it does NOT recover real3D size from RGB.
"""
from pathlib import Path
import json

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

R=Path(__file__).resolve().parents[2]
P=R/'projects/悬崖上的小气球'
C=P/'03-制作/生成配置/前四十秒电影重制24'
G=P/'03-制作/静态构图/前四十秒电影重制24'
t=json.loads((C/'RUN04-颜色包络与相机回校目标01.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=str(G/'小龙四足起跑-二十厘米与果高校准04.blend'))
s=bpy.context.scene;cam=s.camera
body=[o for o in s.objects if o.type=='MESH' and o.get('role')=='dragon']
def envelope():
    p=[world_to_camera_view(s,cam,o.matrix_world@v.co) for o in body for v in o.data.vertices]
    return dict(h=max(a.y for a in p)-min(a.y for a in p),x=(max(a.x for a in p)+min(a.x for a in p))/2,y=min(a.y for a in p))
old=envelope();cam.data.lens*=t['height_fraction']/old['h']
v=envelope();x0=v['x'];cam.data.shift_x=.001;dx=(envelope()['x']-x0)/.001;cam.data.shift_x=(t['body_center_x_fraction']-x0)/dx
v=envelope();y0=v['y'];cam.data.shift_y=.001;dy=(envelope()['y']-y0)/.001;cam.data.shift_y=(1-t['paw_baseline_fraction']-y0)/dy
def project(v):return world_to_camera_view(s,cam,Vector(v))
def solve2(position,axes,target):
    v=Vector(position)
    for _ in range(15):
        b=project(v);a=v.copy();a[axes[0]]+=.001;c=v.copy();c[axes[1]]+=.001
        ap,cp=project(a),project(c);j00=(ap.x-b.x)/.001;j10=(ap.y-b.y)/.001;j01=(cp.x-b.x)/.001;j11=(cp.y-b.y)/.001
        det=j00*j11-j01*j10;ex=target[0]-b.x;ey=target[1]-b.y
        v[axes[0]]+=(j11*ex-j01*ey)/det;v[axes[1]]+=(-j10*ex+j00*ey)/det
    return list(v)
# Screenshot coordinates are measured design anchors, not a recovered scene depth.
berry=solve2([-.25,0,.42],[0,2],[.473,1-.440])
sapling=solve2([-1.45,.20,0],[0,1],[.142,1-.726])
fit=dict(lens_mm=cam.data.lens,shift_x=cam.data.shift_x,shift_y=cam.data.shift_y,berry_center_m=berry,sapling_root_m=sapling,
         fitted_actor_projection=envelope(),target=t,assumption='Prescribed20cm proxy, fixed depth; camera and scene anchors refitted to selected small photographic composition. This does not measure real-world centimeters or establish hard AI geometry control.',
         pending_patch_alignment='Keep actor and high berry fixed; small wet turf and landing tuft will be aligned to the same projected ground row, not foreground tall clump.')
assert abs(envelope()['h']-t['height_fraction'])<1e-5
assert abs(envelope()['y']-(1-t['paw_baseline_fraction']))<1e-5
(C/'静态镜头回校参数02.json').write_text(json.dumps(fit,ensure_ascii=False,indent=2),encoding='utf-8')
print('DESIGN_CAMERA_FIT '+json.dumps(fit,ensure_ascii=False))
