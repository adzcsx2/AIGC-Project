"""Make the approved circle/stop/laugh/fly/catch/spin/nuzzle as two simple proxies."""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_tool_safety import read_json_bound, require_hash, save_checked
from whitebox_saved import load_saved, project_path, render_still_new, write_json_new


def clamp(x):
    return max(0.0, min(1.0, x))


def smooth(x):
    x = clamp(x)
    return x*x*(3-2*x)


def mix(a, b, x):
    return a+(b-a)*x


def radial(angle):
    return Vector((math.cos(angle), math.sin(angle), 0))


def horizontal_pose(angle):
    return Matrix((radial(angle), Vector((0, 0, -1)), Vector((-math.sin(angle), math.cos(angle), 0)))).transposed().to_quaternion()


def hermite(distance, speed, duration, u):
    u=clamp(u)
    return distance*(-2*u**3+3*u*u)+speed*duration*(u**3-2*u*u+u)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--config', required=True)
    a=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    p=Path(a.project).resolve();cp=project_path(p,a.config,exists=True);c,ch=read_json_bound(cp)
    src=project_path(p,c['source_blend'],exists=True);dst=project_path(p,c['output_blend'])
    report=project_path(p,c['report']);stills=project_path(p,c['stills'])
    for q in (dst,report,stills):
        if q.exists():raise FileExistsError(q)
    load_saved(bpy,str(src),c['source_sha256'])
    scene=bpy.context.scene;scene.frame_set(1);cam=scene.camera
    start_cam=cam.matrix_world.copy();start_lens=cam.data.lens
    start_pos=start_cam.translation.copy();start_q=start_cam.to_quaternion()
    camera_radius=math.hypot(start_pos.x,start_pos.y)
    start_angle=math.atan2(start_pos.y,start_pos.x)
    start_target=start_pos+(start_q@Vector((0,0,-1)))*camera_radius
    girl=bpy.data.objects['圆柱-女孩占位'];dragon=bpy.data.objects['圆柱-幼龙占位']
    for obj in (girl,dragon,cam):obj.animation_data_clear();obj.rotation_mode='QUATERNION'
    cam.data.animation_data_clear()
    tree=bpy.data.objects['巨树-主干'].evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=tree.to_mesh();bvh=BVHTree.FromPolygons([tree.matrix_world@v.co for v in mesh.vertices],[list(poly.vertices) for poly in mesh.polygons]);tree.to_mesh_clear()
    anchors={}
    for name in ('女孩-面颊参照','幼龙-面颊参照'):
        obj=bpy.data.objects.new(name,None);scene.collection.objects.link(obj);obj.empty_display_size=.025;anchors[name]=obj
    fps=24;scene.frame_start=1;scene.frame_end=600;scene.render.fps=fps
    g0=math.radians(-154);d0=math.radians(-113.89295434084238)
    gv=5.969026041820607/(119/24);dv=8.25/(119/24)
    stop=c['events']['girl_stop'];decel=c['events']['girl_decelerate']
    turn_end=c['events']['return_complete'];laugh_end=c['events']['laugh_end']
    fly_start=c['events']['fly_start'];catch=c['events']['catch'];settled=c['events']['settled']
    spin_end=c['events']['spin_end'];nuzzle_start=c['events']['nuzzle_start'];contact=c['events']['cheek_contact']
    g_stop=g0+gv*decel+gv*(stop-decel)/2
    d_wait=d0+dv*stop;d_final=d_wait+2*math.pi
    g_stop_pos=radial(g_stop)*.96
    face=radial(math.radians(175));side=Vector((-face.y,face.x,0))
    rows=[]

    def surface(angle):
        r=radial(angle);values=[]
        for z in (.52,.65,.78):
            hit,normal,poly,distance=bvh.ray_cast(r*3+Vector((0,0,z)),-r,5)
            if hit is None:raise ValueError('Missing actual trunk surface')
            values.append(hit.dot(r))
        return r*(max(values)+.131)+Vector((0,0,.65))

    launch_pos=surface(d_final)
    hold_root=radial(g_stop)*1.30
    hold_pos=hold_root+face*.30+Vector((0,0,.98))
    hold_angle=math.atan2(hold_pos.y,hold_pos.x)
    while hold_angle<d_final:hold_angle+=2*math.pi
    while hold_angle-d_final>math.pi:hold_angle-=2*math.pi

    for i in range(600):
        f=i+1;t=i/fps;scene.frame_set(f)
        if t<=decel:ga=g0+gv*t
        elif t<stop:
            u=(t-decel)/(stop-decel);ga=g0+gv*decel+gv*(stop-decel)*(u-u*u/2)
        else:ga=g_stop
        if t<stop:da=d0+dv*t
        elif t<turn_end:da=d_wait+hermite(2*math.pi,dv,turn_end-stop,(t-stop)/(turn_end-stop))
        else:da=d_final
        root=radial(ga)*.96
        approach=smooth((t-fly_start)/(catch-fly_start))
        if t>=fly_start:root=g_stop_pos.lerp(hold_root,approach)
        yaw=ga+math.pi/2
        welcome=smooth((t-laugh_end)/(catch-laugh_end))
        if t>=stop:yaw=mix(ga+math.pi/2,math.radians(175),welcome)
        spin=2*math.pi*smooth((t-settled)/(spin_end-settled))
        if t>=settled:yaw=math.radians(175)+spin
        current_face=Quaternion((0,0,1),spin)@face
        lean=0.0
        if turn_end<=t<laugh_end:
            u=smooth((t-turn_end)/.40)*smooth((laugh_end-t)/.35)
            lean=math.radians(15+3*math.sin((t-turn_end)*2*math.pi*2))*u
        n=smooth((t-nuzzle_start)/(contact-nuzzle_start))
        if t>=nuzzle_start:lean=math.radians(9)*n
        if turn_end<=t<laugh_end:
            look=(launch_pos-root);look.z=0;look.normalize()
        else:look=current_face
        axis=Vector((-look.y,look.x,0));qlean=Quaternion(axis,lean)
        sway=0.025*math.sin(2*math.pi*(t-contact)/1.85)*smooth((t-contact)/.35) if t>=contact else 0
        qroll=Quaternion(current_face, sway/.95)
        girl.rotation_quaternion=qroll@qlean@Quaternion((0,0,1),yaw)
        girl.location=root+(qroll@qlean)@Vector((0,0,.65))
        if t<fly_start:
            dragon.location=surface(da);dragon.rotation_quaternion=horizontal_pose(da)
        elif t<catch:
            u=clamp((t-fly_start)/(catch-fly_start));v=smooth(u)
            ang=mix(d_final,hold_angle,v)
            rr=mix(math.hypot(launch_pos.x,launch_pos.y),math.hypot(hold_pos.x,hold_pos.y),v)+.16*math.sin(math.pi*u)
            dragon.location=radial(ang)*rr+Vector((0,0,mix(.65,.98,v)+.28*math.sin(math.pi*u)))
            dragon.rotation_quaternion=horizontal_pose(d_final).slerp(Quaternion((0,0,1),math.radians(175)),v)
        else:
            dragon.location=root+current_face*.30+Vector((0,0,.98+.03*n))+side*sway*.55
            dragon.rotation_quaternion=Quaternion(current_face,sway/.7)@Quaternion((0,0,1),yaw)
        for obj in (girl,dragon):obj.keyframe_insert('location',frame=f);obj.keyframe_insert('rotation_quaternion',frame=f)
        girl_cheek=root+current_face*.22+side*sway+Vector((0,0,1.22-.06*n))
        dragon_cheek=root+current_face*.22+side*sway+Vector((0,0,1.11+.05*n))
        for name,point in [('女孩-面颊参照',girl_cheek),('幼龙-面颊参照',dragon_cheek)]:
            anchors[name].location=point;anchors[name].keyframe_insert('location',frame=f)

        # Motivated leftward travel while the chase ends, then a push toward affection.
        orbit=smooth((t-3.5)/4.0);ca=mix(start_angle,-math.pi,orbit)
        camera_pos=radial(ca)*camera_radius+Vector((0,0,start_pos.z))
        camera_target=start_target.lerp(Vector((0,0,.90)),orbit)
        together=smooth((t-laugh_end)/(settled-laugh_end))
        target2=root+current_face*.12+Vector((0,0,.82))
        camera_pos=camera_pos.lerp(target2+face*5.0+Vector((0,0,.48)),together)
        camera_target=camera_target.lerp(target2,together)
        close=smooth((t-spin_end)/(25-spin_end))
        near_target=root+face*.18+Vector((0,0,1.03))
        camera_pos=camera_pos.lerp(near_target+face*3.5+Vector((0,0,.27)),close)
        camera_target=camera_target.lerp(near_target,close)
        cam.location=camera_pos
        cam.rotation_quaternion=(camera_target-camera_pos).to_track_quat('-Z','Y')
        if t<=3.5:cam.location=start_pos;cam.rotation_quaternion=start_q
        cam.data.lens=mix(start_lens,50,close)
        cam.keyframe_insert('location',frame=f);cam.keyframe_insert('rotation_quaternion',frame=f);cam.data.keyframe_insert('lens',frame=f)
        bpy.context.view_layer.update()
        rows.append(dict(frame=i,seconds=t,girl_root=list(root),girl_angle=ga,dragon_angle=da,
                         girl_center=list(girl.location),dragon_center=list(dragon.location),spin_angle=spin,
                         cheek_distance=(girl_cheek-dragon_cheek).length,camera=list(cam.location)))
    for action in bpy.data.actions:
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:key.interpolation='LINEAR'
    scene.timeline_markers.clear()
    for name,value in c['events'].items():scene.timeline_markers.new(name,frame=round(value*24)+1)
    scene['本版用途']='两个圆柱表达完整25秒剧情；表情/四爪/翅膀/手臂由模型补全。面颊空节点仅表示接近目标。'
    scene.frame_set(1);stills.mkdir(parents=True)
    def validate():require_hash(cp,ch);require_hash(src,c['source_sha256'])
    dst.parent.mkdir(parents=True,exist_ok=True);digest=save_checked(bpy,dst,p,validate)
    write_json_new(report,dict(blend_sha256=digest,config_sha256=ch,source_sha256=c['source_sha256'],events=c['events'],rows=rows,limitation='Two spatial cylinders, no articulated face/limbs/wings; cheek empties are conceptual targets only.'),p)
    scene.render.resolution_percentage=50
    for f in [1,121,157,205,253,289,313,337,361,409,457,489,529,577,600]:
        scene.frame_set(f);render_still_new(bpy,stills/f'完整白模-帧{f:03d}.png',p)
    print(json.dumps({'blend':str(dst),'sha256':digest,'frames':600,'fps':24},ensure_ascii=False))


if __name__=='__main__':main()
