"""Check phase-specific framing/contact, then render the material-shaded performance."""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from project_tool_safety import read_json_bound, require_hash
from whitebox_saved import load_saved, project_path, render_still_new, sha, write_json_new


def main():
    ap=argparse.ArgumentParser()
    for key in ('project','blend','sha256','config','samples','version'): ap.add_argument('--'+key,required=True)
    ap.add_argument('--render',action='store_true')
    a=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    project=Path(a.project).resolve(); blend=project_path(project,a.blend,exists=True)
    cp=project_path(project,a.config,exists=True); sp=project_path(project,a.samples,exists=True)
    c,ch=read_json_bound(cp); sampledata,sh=read_json_bound(sp)
    out=project_path(project,f'05-检查与验收/飞扑贴脸核查-版本{a.version}.json')
    work=project_path(project,f'03-制作/中间数据/表演白模-版本{a.version}')
    if out.exists() or (a.render and work.exists()): raise FileExistsError('检查/导出版本已占用')
    load_saved(bpy,str(blend),a.sha256); scene=bpy.context.scene; camera=scene.camera
    fails=[]; feet={}; lengths={}; face_errors=[]; yaws=[]; head_heights=[]; margins=[]; wing_angles=[]
    for side in (-1,1): feet[side]={'previous':None,'was_planted':False,'max_slide':0.,'max_ground_error':0.}
    objects=list(bpy.data.objects['女孩-主体'].children_recursive)
    girl_geometry=[o for o in objects if o.type in {'MESH','CURVE'}]
    close_objects=[bpy.data.objects['女孩-头部控制'],bpy.data.objects['幼龙-主体'],bpy.data.objects['女孩-手控制--1'],bpy.data.objects['女孩-手控制-1']]
    close_geometry=list({o.name:o for root in close_objects for o in root.children_recursive if o.type in {'MESH','CURVE'}}.values())
    for i,sample in enumerate(sampledata['samples']):
        scene.frame_set(i+1); graph=bpy.context.evaluated_depsgraph_get(); t=i/c['fps']
        required=girl_geometry+close_geometry if t<=c['spin_end'] else close_geometry
        uv=[]
        for obj in required:
            obj=obj.evaluated_get(graph)
            uv.extend(world_to_camera_view(scene,camera,obj.matrix_world@Vector(p)) for p in obj.bound_box)
        margin=min(min(p.x,p.y,1-p.x,1-p.y) for p in uv); margins.append(margin)
        if margin<.015 or any(p.z<=camera.data.clip_start for p in uv):
            fails.append({'frame':i,'kind':'phase_framing','margin':margin})
        for side,field in [(-1,'left_planted'),(1,'right_planted')]:
            pt=bpy.data.objects[f'女孩-脚控制-{side}'].matrix_world@Vector((0,.025,-.045)); rec=feet[side]
            if sample[field]:
                rec['max_ground_error']=max(rec['max_ground_error'],abs(pt.z))
                if rec['was_planted']:rec['max_slide']=max(rec['max_slide'],(pt-rec['previous']).length)
            rec['previous']=pt.copy();rec['was_planted']=sample[field]
        for part,r,target in [('thigh',.059,.315),('shin',.045,.315),('upper',.045,.235),('lower',.034,.235)]:
            for side in (-1,1):
                value=(bpy.data.objects[f'女孩-{part}-{side}'].scale.z-r*.3)*2
                lengths.setdefault(part,[]).append(value)
                if abs(value-target)>.001:fails.append({'frame':i,'kind':'limb_stretch','part':part,'length':value})
        if t>=c['nuzzle_contact']:
            pa=bpy.data.objects['女孩-贴脸接触点'].matrix_world.translation
            pb=bpy.data.objects['幼龙-贴脸接触点'].matrix_world.translation
            error=(pa-pb).length;face_errors.append(error)
            if error>.004:fails.append({'frame':i,'kind':'cheek_contact','distance':error})
        axis=bpy.data.objects['女孩-torso'].matrix_world.to_3x3()@Vector((0,1,0))
        yaw=math.atan2(axis.y,axis.x)
        if yaws:
            while yaw-yaws[-1]>math.pi:yaw-=2*math.pi
            while yaw-yaws[-1]<-math.pi:yaw+=2*math.pi
        yaws.append(yaw)
        head_heights.append([bpy.data.objects['女孩-头部控制'].matrix_world.translation.z,bpy.data.objects['幼龙-头部'].matrix_world.translation.z])
        if c['jump_start']<=t<c['jump_end']:
            wing_angles.append(bpy.data.objects['幼龙-翼控制1'].rotation_quaternion.to_euler('XYZ').y)
    for rec in feet.values():
        del rec['previous'];del rec['was_planted']
        if max(rec.values())>.002:fails.append({'kind':'foot_contact','measurements':rec})
    start=math.ceil(c['settle_end']*c['fps']); end=math.ceil(c['spin_end']*c['fps'])
    turns=(yaws[end]-yaws[start])/(2*math.pi)
    if abs(turns-1)>.01:fails.append({'kind':'spin_turns','turns':turns})
    s=round(c['nuzzle_start']*c['fps']); e=math.ceil(c['nuzzle_contact']*c['fps'])
    head_change=[head_heights[e][j]-head_heights[s][j] for j in (0,1)]
    if not(head_change[0]<-.04 and head_change[1]>.035):fails.append({'kind':'head_direction','deltas':head_change})
    if max(wing_angles)-min(wing_angles)<1.:fails.append({'kind':'wing_motion_too_small'})
    for path,h in [(blend,a.sha256),(cp,ch),(sp,sh)]:require_hash(path,h)
    report=dict(source_sha256=a.sha256,config_sha256=ch,samples_sha256=sh,frames=c['frames'],failures=fails,
        phase_framing_min_margin=min(margins),feet=feet,limb_lengths={k:[min(v),max(v)] for k,v in lengths.items()},
        cheek_contact_max_error=max(face_errors),spin_turns=turns,spin_seconds=c['spin_end']-c['settle_end'],
        girl_head_vertical_change=head_change[0],dragon_head_vertical_change=head_change[1],
        wing_angle_range=[min(wing_angles),max(wing_angles)],dynamic_review='pending',
        limitations=['区分全身动作和贴脸近景的构图检查；未做全场精确碰撞或连续动态观感验收。'])
    if a.render and not fails:
        work.mkdir(parents=True)
        scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.color_type='MATERIAL'
        scene.display.shading.show_cavity=True;scene.display.shading.show_object_outline=False
        scene.render.resolution_percentage=50;scene.render.use_stamp=False
        for i in range(c['frames']):
            scene.frame_set(i+1);render_still_new(bpy,work/f'帧-{i:06d}.png',project)
        report['frames_directory']=str(work.relative_to(project))
    for path,h in [(blend,a.sha256),(cp,ch),(sp,sh)]:require_hash(path,h)
    write_json_new(out,report,project)
    print(json.dumps({'report':str(out),'failures':len(fails),'checks':{k:v for k,v in report.items() if k not in ('failures','limitations')}},ensure_ascii=False))
    if fails:raise SystemExit(1)


if __name__=='__main__':main()
