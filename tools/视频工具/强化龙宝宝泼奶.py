"""Strengthen the existing, approved spill with baked editable geometry."""

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from whitebox_saved import load_saved, project_path, render_still_new, sha, write_json_new
from project_tool_safety import save_checked, require_hash
from 制作龙宝宝睡醒舔奶 import h, mesh_obj, smooth


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True)
    ap.add_argument('--source', required=True)
    ap.add_argument('--version', required=True)
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
    project = Path(args.project).resolve()
    source = project_path(project, args.source, exists=True)
    digest = sha(source)
    scene = load_saved(bpy, source, digest)
    out = project_path(project, f'03-制作/三维工程/龙宝宝-睡醒舔奶-白模{args.version}.blend')
    record = project_path(project, f'05-检查与验收/睡醒舔奶-泼奶强化{args.version}.json')
    pictures = project_path(project, f'05-检查与验收/睡醒舔奶-泼奶强化{args.version}')
    if any(x.exists() for x in (out, record, pictures)):
        raise FileExistsError('Version already exists')
    head = bpy.data.objects['控制-头部']
    milkmat = bpy.data.materials['牛奶']
    # Two staggered connected lobes leave the bowl, rather than sparse unrelated dots.
    sheets = []
    for j in range(2):
        nu, nv = 14, 5
        faces = [(u*nv+v, (u+1)*nv+v, (u+1)*nv+v+1, u*nv+v+1)
                 for u in range(nu-1) for v in range(nv-1)]
        ob = mesh_obj(f'牛奶-涌出奶浪{j}', [(0, 0, -.5)]*(nu*nv), faces, milkmat)
        solid = ob.modifiers.new('奶浪厚度', 'SOLIDIFY')
        solid.thickness = .012
        sheets.append(ob)
    tongue = bpy.data.objects['幼龙-可卷舌网格']
    bowl = bpy.data.objects['道具-浅奶碗']
    milk = bpy.data.objects['奶面']
    film = h.sphere('牛奶-舌尖薄奶膜', (.032,.025,.008),milkmat)
    bridge = h.tube('牛奶-舔起的奶丝', [(0,0,-.5)]*6,.012,milkmat)
    if bridge.data.splines[0].type != 'BEZIER':
        raise ValueError('Expected editable Bezier milk bridge')
    ripplemat = bpy.data.materials.new('牛奶-涟漪明暗')
    ripplemat.diffuse_color=(.71,.75,.72,1)
    ripplemat.use_nodes=True
    ripplemat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.71,.75,.72,1)
    ripplemat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.26
    ripples=[]
    for i in range(2):
        bpy.ops.mesh.primitive_torus_add(major_radius=1,minor_radius=.018,major_segments=48,minor_segments=8)
        ob=bpy.context.object;ob.name=f'牛奶-触舌涟漪{i}'
        ob.data.materials.append(ripplemat);ripples.append(ob)
    lick_starts=[10.6,11.3,12,12.7,13.4,20.55,21.25,21.95,22.65,23.35,24.1,24.95]
    # Launch points are frozen at launch; airborne milk does not keep following the head.
    launches = []
    for i in range(48):
        shake = i >= 20
        start = (15.07+(i%10)*.015) if not shake else ((18.23 if i < 34 else 19.13)+(i%7)*.014)
        scene.frame_set(round(start*24)+1)
        matrix = head.matrix_world.copy()
        target = matrix @ Vector(((-.10 if i%2 else .10), -.25, .14))
        if shake:
            origin = matrix @ Vector((((i%5)-2)*.055, -.28, .10+(i%3)*.025))
            velocity = Vector(((-1 if i%2 else 1)*(.65+i%3*.13), -1.15-i%4*.12, .42+i%3*.10))
            life = .65
        else:
            origin = Vector((.88+((i%4)-1.5)*.04, -.10+((i%5)-2)*.03, .16))
            flight = .20+(i%4)*.012
            velocity = (target-origin-Vector((0, 0, -2.7*flight*flight)))/flight
            life = flight
        launches.append((start, origin, velocity, life, shake))
    for ob in list(bpy.data.objects):
        if ob.name.startswith('牛奶-飞溅'):
            bpy.data.objects.remove(ob, do_unlink=True)
    drops = [h.sphere(f'牛奶-飞溅{i:02d}', (.025,.025,.04), milkmat) for i in range(48)]
    stains = [bpy.data.objects[f'幼龙-脸上奶渍{i:02d}'] for i in range(7)]
    for ob in stains:
        ob.animation_data_clear()
    evidence = []
    for f in range(1, 769):
        t = (f-1)/24
        scene.frame_set(f)
        matrix = head.matrix_world.copy()
        phase = next(((t-start)/.54 for start in lick_starts if 0 <= (t-start)/.54 <= 1),-1)
        evaluated=tongue.evaluated_get(bpy.context.evaluated_depsgraph_get())
        tip=sum((evaluated.matrix_world @ vertex.co for vertex in list(evaluated.data.vertices)[-12:]),Vector())/12
        surface=(bowl.matrix_world @ Vector((0,0,milk.location.z+.008)))
        contact=Vector((tip.x,tip.y,surface.z))
        lifting=.38<phase<.93 and t<25.75
        h.pose(film,tip+Vector((0,0,.009)),scale=(.033,.026,.010) if lifting else (.00001,)*3,frame=f)
        for i,point in enumerate(bridge.data.splines[0].bezier_points):
            u=i/5
            pos=contact.lerp(tip+Vector((0,0,.010)),u)
            pos.y+=.012*math.sin(math.pi*u)
            point.co=pos if lifting and tip.z>surface.z else Vector((0,0,-.5))
            point.handle_left_type='AUTO';point.handle_right_type='AUTO'
            point.keyframe_insert('co',frame=f)
        for i,ob in enumerate(ripples):
            age=(phase-.28-i*.13)/.70
            visible=0<age<1 and t<25.75
            radius=.018+.12*max(0,age)
            h.pose(ob,contact+Vector((0,0,.002+i*.001)),scale=(radius,radius,.10*(1-age)) if visible else (.00001,)*3,frame=f)
        for j, ob in enumerate(sheets):
            start, hit, end = 15.045+j*.045, 15.35+j*.045, 15.66+j*.045
            active = start < t < end
            if active:
                front = smooth(start, hit, t)
                back = smooth(hit-.075, end, t)
                origin = Vector((.90, -.28+j*.055, .16))
                target = matrix @ Vector(((-.15 if j else -.09), -.25, .14))
                for vertex in ob.data.vertices:
                    u, v = divmod(vertex.index, 5)
                    along = back+(front-back)*u/13
                    width = (v/4-.5)*(.25+.12*along)
                    point = origin.lerp(target, along)+Vector((width,0,.30*math.sin(math.pi*along)))
                    point.z += .018*math.sin(v*1.8+u*.9+t*20)*math.sin(math.pi*along)
                    vertex.co = point
                    vertex.keyframe_insert('co', frame=f)
            elif f == 1 or round(start*24) <= f <= round(start*24)+1 or round(end*24)+1 <= f <= round(end*24)+3:
                for vertex in ob.data.vertices:
                    vertex.co = (0,0,-.5)
                    vertex.keyframe_insert('co', frame=f)
        for i, ob in enumerate(stains):
            wet = smooth(15.25+i*.006,15.43+i*.006,t)
            wet *= 1-.34*smooth(18.23,18.80,t)-.30*smooth(19.13,19.70,t)
            # Residual nose/forehead marks remain after the two ejections.
            ob.scale = (.09*wet, .009*wet, (.11 if i < 2 else .082)*wet)
            ob.keyframe_insert('scale',frame=f)
        for i,(ob, launch) in enumerate(zip(drops, launches)):
            start,origin,velocity,life,shake = launch
            dt=t-start
            visible=0 <= dt <= life
            point=origin+velocity*max(0,dt)+Vector((0,0,-2.7*max(0,dt)**2))
            if point.z < .015:
                visible=False
            h.pose(ob,point,scale=(.020,.020,.043) if visible else (.00001,)*3,frame=f)
        if f in [361,365,368,371,374,378,383,391,413,440,446,462,469,480,503,754]:
            evidence.append({'frame':f,'seconds':t,'head_matrix':[list(row) for row in matrix],
                             'visible_flying_drops':sum(1 for ob in drops if ob.scale.x>.001),
                             'face_milk_scale':list(stains[0].scale)})
    scene.frame_set(1)
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    out.parent.mkdir(parents=True,exist_ok=True)
    save_checked(bpy,out,project,lambda:require_hash(source,digest))
    write_json_new(record,{'source':str(source.relative_to(project)),'source_sha256':digest,
                          'blend':str(out.relative_to(project)),'sha256':sha(out),
                          'samples':evidence,'new_objects':[o.name for o in sheets+drops+[film,bridge,*ripples]],
                          'method':'Baked mesh surge and fixed-origin ballistic drops; not fluid simulation',
                          'dynamic_review':'pending'},project)
    pictures.mkdir(parents=True)
    scene.render.engine='BLENDER_EEVEE'
    scene.render.resolution_percentage=100
    for f in [262,265,270,276,280,365,368,371,374,378,383,413,440,446,462,469,503,510,754]:
        scene.frame_set(f)
        render_still_new(bpy,pictures/f'帧{f:04d}.png',project)
    print('milk-surge version saved')


if __name__=='__main__':
    main()
