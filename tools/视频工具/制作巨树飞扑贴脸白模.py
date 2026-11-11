"""Revise the giant-tree performance without changing the earlier authoring tool."""
import argparse
import bisect
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import 制作巨树互动白模 as base
from project_tool_safety import read_json_bound, require_hash, save_checked
from whitebox_saved import project_path, render_still_new, require_self_contained, sha, write_json_new

Z = Vector((0, 0, 1))
smooth, pose, joint, segment, basis = base.smooth, base.pose, base.joint, base.segment, base.basis


def retimed_timeline(c):
    """Retain original blocking, accelerating only the planted-foot spin."""
    p, yaw, angle, phase, feet, planted = base.timeline(c)
    result = ([], [], [], [], {-1: [], 1: []}, {-1: [], 1: []})
    for i in range(c['frames']):
        t = i / c['fps']
        if t < c['settle_end']:
            old = t
        elif t < c['spin_end']:
            old = 19.2 + (t - c['settle_end']) * 4 / (c['spin_end'] - c['settle_end'])
        else:
            old = 23.2 + (t - c['spin_end']) * 1.8 / (25 - c['spin_end'])
        f = min(c['frames'] - 1, old * c['fps'])
        a, b = int(f), min(c['frames'] - 1, int(f) + 1)
        u = f - a
        result[0].append(p[a].lerp(p[b], u))
        for out, values in zip(result[1:4], (yaw, angle, phase)):
            out.append(values[a] * (1-u) + values[b] * u)
        for side in (-1, 1):
            result[4][side].append((feet[side][a][0].lerp(feet[side][b][0], u),
                                    feet[side][a][1].slerp(feet[side][b][1], u)))
            result[5][side].append(planted[side][a] and (u < 1e-6 or planted[side][b]))
    return result


def add_face_controls(g, d):
    dark = bpy.data.materials['面部细节']
    clay = bpy.data.materials['女孩-白模']
    g['smile'] = bpy.data.objects['女孩-微笑'].data.splines[0]
    g['mouth'] = base.sphere('女孩-笑口', (.025,.003,.001), dark, g['head'], (0,.101,-.053))
    for side in (-1, 1):
        g['eye',side] = bpy.data.objects[f'女孩-眼{side}']
        _, g['lid',side] = base.tube(f'女孩-笑眼弧{side}',
            [(side*.043+x,.102,.035) for x in (-.018,0,.018)], [.001]*3, dark, g['head'])
        g['cheek',side] = base.sphere(f'女孩-笑肌{side}', (.023,.004,.015), clay, g['head'], (side*.061,.087,-.008))
        d['eye',side] = bpy.data.objects[f'幼龙-眼球{side}']
    d['neck'] = base.sphere('幼龙-短颈', (.054,.058,.048), bpy.data.materials['幼龙-白模'], d['root'], (0,.105,.033))
    g['cheek_anchor'] = base.empty('女孩-贴脸接触点', g['head'])
    d['cheek_anchor'] = base.empty('幼龙-贴脸接触点', d['head'])


def face_expression(g, d, happy, affection, frame):
    for side in (-1, 1):
        pose(g['eye',side], (side*.043,.096,.035), scale=(.016,.009,.013*(1-.85*happy)), frame=frame)
        for j, point in enumerate(g['lid',side].bezier_points):
            x = side*.043 + (j-1)*.018
            z = .035 + (.008 if j==1 else -.001)*happy
            point.co = (x, .103*math.sqrt(max(.1,1-(x/.115)**2-(z/.145)**2))+.007, z)
            point.radius = .0003+.0025*happy
            point.keyframe_insert('co', frame=frame); point.keyframe_insert('radius', frame=frame)
        pose(g['cheek',side], (side*.061,.087,-.008+.005*happy), scale=(.023,.003+.003*happy,.015), frame=frame)
        pose(d['eye',side], (side*.061,.065,.024), scale=(.018,.012,.022*(1-.65*affection)), frame=frame)
    for j, point in enumerate(g['smile'].bezier_points):
        x = (j-1)*(.031+.013*happy)
        z = (-.047+.017*happy) if j!=1 else -.053-.005*happy
        point.co = (x,.103*math.sqrt(max(.1,1-(x/.115)**2-(z/.145)**2))+.005,z)
        point.keyframe_insert('co',frame=frame)
    pose(g['mouth'], (0,.101,-.052), scale=(.025+.007*happy,.003,.001+.010*happy), frame=frame)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--project',required=True)
    ap.add_argument('--version',required=True); ap.add_argument('--config',required=True)
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    if not args.version or not all(x.isalnum() or x in '-_' for x in args.version): raise ValueError('版本无效')
    project=Path(args.project).resolve(); config=project_path(project,args.config,exists=True)
    c, digest=read_json_bound(config)
    source_code={Path(base.__file__).resolve():sha(base.__file__),Path(__file__).resolve():sha(__file__)}
    blend=project_path(project,f'03-制作/三维工程/巨树互动白模-版本{args.version}.blend')
    stills=project_path(project,f'05-检查与验收/白模关键帧-版本{args.version}')
    report=project_path(project,f'05-检查与验收/白模动作采样-版本{args.version}.json')
    for path in (blend,stills,report):
        if path.exists() or path.is_symlink(): raise FileExistsError(path)
    blend.parent.mkdir(parents=True,exist_ok=True); stills.mkdir(parents=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for brush in list(bpy.data.brushes): bpy.data.brushes.remove(brush)
    scene=bpy.context.scene; scene.render.engine='BLENDER_WORKBENCH'
    scene.render.resolution_x=c['width']; scene.render.resolution_y=c['height']; scene.render.resolution_percentage=100
    scene.render.fps=c['fps']; scene.frame_start=1; scene.frame_end=c['frames']
    scene.render.image_settings.file_format='PNG'; scene.render.image_settings.color_mode='RGB'
    scene.render.use_overwrite=False; scene.world=bpy.data.worlds.new('白模世界'); scene.world.color=(.7,.7,.7)
    scene.view_settings.view_transform='Standard'; scene.display.shading.color_type='MATERIAL'
    scene.display.shading.light='STUDIO'; scene.display.shading.show_shadows=True
    scene.display.shading.show_cavity=True; scene.display.shading.show_object_outline=False
    base.build_set(c); g=base.build_girl(); d=base.build_dragon(); add_face_controls(g,d)
    bpy.ops.object.camera_add(); cam=bpy.context.object; cam.name='摄影机-连续观察'
    cam.data.lens=c['camera_lens']; cam.data.clip_end=100; scene.camera=cam
    positions,yaws,angles,phases,feet,grounded=retimed_timeline(c)
    rate=c['fps']; samples=[]; lastq=None; grip_phase=[0.]; grip_states={}
    for k in range(1,c['frames']): grip_phase.append(grip_phase[-1]+abs(angles[k]-angles[k-1])*.65/.11)
    for i in range(c['frames']):
        t=i/rate; frame=i+1; root=positions[i]; yaw=yaws[i]; q=Quaternion(Z,yaw-math.pi/2)
        forward=q@Vector((0,1,0)); right=q@Vector((1,0,0))
        crouch=.055*smooth((t-15.8))*(1-smooth((t-18.4)/.8))
        absorb=.065*math.exp(-((t-18.55)/.20)**2)
        moving=(positions[min(i+1,c['frames']-1)]-positions[max(0,i-1)]).length>.008
        bob=.013*math.sin(phases[i]*4*math.pi) if moving else .002*math.sin(t*3)
        pelvis=root+Z*(.64-crouch-absorb+bob)
        for side in (-1,1):
            ankle=feet[side][i][0]; offset=pelvis+right*side*.084-ankle
            horizontal=offset.x**2+offset.y**2
            if horizontal>=.626**2: raise ValueError(f'步幅过大: {frame}')
            pelvis.z=min(pelvis.z,ankle.z+math.sqrt(.626**2-horizontal))
        affection=smooth((t-c['nuzzle_start'])/(c['nuzzle_contact']-c['nuzzle_start']))
        rub_u=max(0,min(1,(t-c['nuzzle_contact'])/(24.85-c['nuzzle_contact'])))
        rub=math.sin(2*math.pi*rub_u)*math.sin(math.pi*rub_u)
        torso=pelvis+Z*.235+forward*.014
        head=pelvis+Z*.535+forward*.018 + affection*(forward*.04-right*.03-Z*.065) + right*(.012*rub)
        a=angles[i]; normal=Vector((math.sin(a),-math.cos(a),0)); tangent=Vector((math.cos(a),math.sin(a),0))
        preload=.035*math.sin(math.pi*smooth((t-(c['jump_start']-.3))/.3)) if t<c['jump_start'] else 0
        climbpos=normal*.80+Z*(.72+.025*math.sin(t*3.2)-preload); climbq=basis(Z+tangent*.15,normal)
        heldpos=pelvis+forward*(.27-.07*affection)+right*(.07*affection)+Z*(.29+.02*affection)
        heldq=basis(-right,Z)
        if t<c['jump_start']: dp,dq=climbpos,climbq
        elif t<c['jump_end']:
            u=(t-c['jump_start'])/(c['jump_end']-c['jump_start'])
            aa=angles[round(c['jump_start']*rate)]
            origin=Vector((math.sin(aa),-math.cos(aa),0))*.80+Z*(.72+.025*math.sin(c['jump_start']*3.2))
            dp=origin.lerp(heldpos,smooth(u))+Z*(.19*math.sin(math.pi*u)+.012*math.sin(6*math.pi*u)*math.sin(math.pi*u))
            flight_q=basis(heldpos-origin,Z)
            dq=climbq.slerp(flight_q,smooth(u/.20))
            dq=dq.slerp(heldq,smooth((u-.72)/.28))
        else: dp,dq=heldpos,heldq
        if lastq is not None and dq.dot(lastq)<0: dq.negate()
        lastq=dq.copy(); pose(d['root'],dp,dq,frame=frame)
        flight=smooth((t-(c['jump_start']-.13))/.13)*(1-smooth((t-(c['jump_end']-.1))/.28))
        flap=math.cos(2*math.pi*3.2*(t-c['jump_start']))
        for side in (-1,1):
            for end,yy in (('fore',.065),('hind',-.085)):
                anchor=Vector((side*.063,yy,0))
                if t<c['jump_start']:
                    offset=(0 if end=='fore' else .5)+(side+1)*.25
                    phase=grip_phase[i]+offset; cycle=math.floor(phase); phase-=cycle; key=(end,side)
                    def grip_surface(k):
                        angle=angles[k]+side*.10
                        return Vector((.654*math.sin(angle),-.654*math.cos(angle),.72+.025*math.sin(k/rate*3.2)+yy))
                    if key not in grip_states or grip_states[key][0]!=cycle: grip_states[key]=(cycle,grip_surface(i))
                    plant=grip_states[key][1]
                    if phase<.45: world_grip=plant
                    else:
                        k=min(c['frames']-1,bisect.bisect_left(grip_phase,cycle+1-offset),round(c['jump_start']*rate))
                        swing=(phase-.45)/.55
                        world_grip=plant.lerp(grip_surface(k),smooth(swing))+normal*(.018*math.sin(math.pi*swing))
                    grip=dq.inverted()@(world_grip-dp)
                elif t<c['jump_end']:
                    u=(t-c['jump_start'])/(c['jump_end']-c['jump_start'])
                    grip=Vector((side*.075,yy+(.035 if end=='fore' else -.025),-.095-.035*math.sin(u*math.pi)))
                else: grip=Vector((side*.067,yy+(.015 if end=='fore' else 0),-.085))
                elbow=joint(anchor,grip,Vector((side,0,.15)),.095)
                segment(d[end,'upper',side],anchor,elbow,.025,frame); segment(d[end,'lower',side],elbow,grip,.017,frame)
                pose(d[end,'foot',side],grip,Quaternion((1,0,0),-.35),frame=frame)
            folded=smooth((t-(c['jump_end']-.10))/.35)
            wing_angle=side*((1-flight)*(1-folded)*.07*math.sin(t*2)+flight*(.15+.95*flap)+folded*1.05)
            wing_q=Quaternion((0,1,0),wing_angle)@Quaternion(Z,-side*.8*folded)
            pose(d['wing',side],(side*.055,.025,.055),wing_q,
                 scale=(1+flight-.15*folded,1+.28*flight-.15*folded,1),frame=frame)
        for k,point in enumerate(d['tail'].bezier_points):
            u=k/3; point.co=(.045*u*u+.025*math.sin(t*3-u*2)*u,-.12-.19*u,-.055*u)
            point.keyframe_insert('co',frame=frame)
        look=(dp-head).normalized(); lookyaw=math.atan2(look.y,look.x)
        while lookyaw-yaw>math.pi: lookyaw-=2*math.pi
        while lookyaw-yaw< -math.pi: lookyaw+=2*math.pi
        lookyaw=yaw+max(-1.15,min(1.15,lookyaw-yaw))
        old_hq=basis(Vector((math.cos(lookyaw),math.sin(lookyaw),max(-.75,min(.1,look.z)))))
        cuddle_hq=basis(Vector((math.cos(yaw-.50+.05*rub),math.sin(yaw-.50+.05*rub),-.25)))
        hq=old_hq.slerp(cuddle_hq,affection)
        pose(g['head'],head,hq,frame=frame)
        cheekx=-.067+.017*rub; cheekz=-.025
        cheeky=.103*math.sqrt(1-(cheekx/.115)**2-(cheekz/.145)**2)
        ga=Vector((cheekx,cheeky,cheekz)); da=Vector((-.075,.025,.015))
        dhq=Quaternion((1,0,0),(1-affection)*.06*math.sin(t*2.2)+affection*(.65+.06*rub))
        target_head=head+hq@ga-(dq@dhq)@da
        dhp=Vector((0,.145,.038)).lerp(dq.inverted()@(target_head-dp),affection)
        pose(d['head'],dhp,dhq,frame=frame)
        segment(d['neck'],Vector((0,.095,.028)),dhp,.050,frame)
        pose(g['cheek_anchor'],ga,frame=frame); pose(d['cheek_anchor'],da,frame=frame)
        happy=.08+.60*smooth((t-c['jump_end'])/.65)+.30*affection
        face_expression(g,d,happy,affection,frame)
        pose(g['pelvis'],pelvis,q,frame=frame); pose(g['torso'],torso,q,frame=frame)
        segment(g['neck'],torso+Z*.17,head-Z*.11,.045,frame)
        pose(g['cloak'],torso+Z*.11-forward*.015,q@Quaternion((1,0,0),.04*math.sin(phases[i]*2*math.pi)),frame=frame)
        pose(g['bag'],pelvis+right*.18-forward*.025-Z*.025,q,frame=frame)
        support=[]
        for side in (-1,1):
            foot,fq=feet[side][i]; hip=pelvis+right*side*.084; knee=joint(hip,foot,forward,.315)
            segment(g['thigh',side],hip,knee,.059,frame); segment(g['shin',side],knee,foot,.045,frame)
            pose(g['foot',side],foot,fq,frame=frame)
            ground=foot+fq@Vector((0,.025,0)); ground.z=0; pose(g['ground',side],ground,frame=frame)
            shoulder=torso+Z*.12+right*side*.148
            if t<15.8:
                swing=.10*math.sin(phases[i]*2*math.pi+side*math.pi/2)
                hand=pelvis+right*side*.21+forward*(.15+swing)+Z*(.13-.04*math.cos(phases[i]*2*math.pi))
            else:
                openhand=pelvis+right*side*.20+forward*.35+Z*.28
                belly=dp+dq@Vector((0,-.065 if side==1 else .065,-.071))
                hand=openhand.lerp(belly-Z*.024,smooth((t-(c['jump_end']-.35))/.35))
                support.append((hand+Z*.024-belly).length)
            elbow=joint(shoulder,hand,right*side-forward*.15,.235)
            segment(g['upper',side],shoulder,elbow,.045,frame); segment(g['lower',side],elbow,hand,.034,frame)
            pose(g['hand',side],hand,q,frame=frame)
        cp=base.sample(c['camera_keys'],t,cubic=False); cl=Vector(cp[:3]); target=Vector(cp[3:])
        pose(cam,cl,(target-cl).to_track_quat('-Z','Y'),frame=frame)
        cheek_error=(head+hq@ga-(dp+dq@(dhp+dhq@da))).length
        samples.append(dict(frame=frame,time=t,girl_root=list(root),girl_yaw=yaw,dragon_root=list(dp),
            left_planted=grounded[-1][i],right_planted=grounded[1][i],support_errors=support,
            girl_head=list(head),dragon_head=list(dp+dq@dhp),cheek_contact_error=cheek_error,
            happiness=happy,affection=affection,wing_flight_envelope=flight,wing_flap=flap))
    for action in bpy.data.actions:
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points: key.interpolation='LINEAR'
    for name,sec in [('原片动作',0),('新增承接',14.875),('扑腾飞入怀中',c['jump_start']),('双臂接住',c['jump_end']),('加快转圈',c['settle_end']),('低头伸颈靠近',c['nuzzle_start']),('幸福笑着贴脸蹭',c['nuzzle_contact'])]:
        scene.timeline_markers.new(name,frame=round(sec*rate)+1)
    scene['制作说明']='用户指定修订：扑翼飞扑、3秒转一圈、低头伸颈贴脸磨蹭与幸福笑；非动捕。'
    scene['来源动作配置SHA256']=digest
    def validate():
        require_hash(config,digest)
        for path,h in source_code.items(): require_hash(path,h)
    scene.frame_set(1); require_self_contained(bpy); save_checked(bpy,blend,project,validate)
    write_json_new(report,dict(config_sha256=digest,implementation={str(k):v for k,v in source_code.items()},samples=samples,dynamic_review='pending'),project)
    scene.render.resolution_percentage=50
    for sec in c['still_times']:
        frame=min(c['frames'],round(sec*rate)+1); scene.frame_set(frame)
        render_still_new(bpy,stills/f'关键帧-{frame:04d}.png',project)
    validate()
    print(json.dumps(dict(blend=str(blend),sha256=sha(blend),stills=str(stills),samples=str(report)),ensure_ascii=False))


if __name__=='__main__':
    main()
