"""Create a five-second spatial-only proxy from a saved performance scene."""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from whitebox_saved import load_saved, project_path, require_self_contained, render_still_new, sha, write_json_new
from project_tool_safety import read_json_bound, require_hash, save_checked


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--project',required=True);ap.add_argument('--config',required=True)
    a=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);p=Path(a.project).resolve()
    cp=project_path(p,a.config,exists=True);c,ch=read_json_bound(cp)
    source=project_path(p,c['source_blend'],exists=True);sp=project_path(p,c['source_samples'],exists=True)
    samples,sh=read_json_bound(sp);blend=project_path(p,c['output_blend']);stills=project_path(p,c['stills']);report=project_path(p,c['report'])
    for out in (blend,stills,report):
        if out.exists() or out.is_symlink():raise FileExistsError(out)
    load_saved(bpy,str(source),c['source_sha256']);scene=bpy.context.scene;cam=scene.camera
    rows=[]
    for i in range(c['frames']):
        j=c['source_start_frame']+i;scene.frame_set(j+1)
        row=samples['samples'][j]
        rows.append(dict(source_frame=j,girl_root=row['girl_root'],dragon_matrix=[list(r) for r in bpy.data.objects['幼龙-主体'].matrix_world],camera_matrix=[list(r) for r in cam.matrix_world],camera_lens=cam.data.lens))
    removed=set()
    for name in ('女孩-主体','幼龙-主体'):
        root=bpy.data.objects[name];removed.update(o.name for o in [root,*root.children_recursive])
    for name in sorted(removed):
        obj=bpy.data.objects.get(name)
        if obj:bpy.data.objects.remove(obj,do_unlink=True)
    cam.animation_data_clear();cam.data.animation_data_clear()
    cylinders=[]
    for name,radius,height,gray in [('圆柱-女孩占位',.145,1.30,.78),('圆柱-幼龙占位',.10,.38,.28)]:
        bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=radius,depth=height)
        obj=bpy.context.object;obj.name=name;obj.rotation_mode='QUATERNION'
        mat=bpy.data.materials.new(name+'-中性灰');mat.diffuse_color=(gray,gray,gray,1);obj.data.materials.append(mat)
        for face in obj.data.polygons:face.use_smooth=len(face.vertices)==4
        cylinders.append(obj)
    from mathutils import Matrix
    for i,row in enumerate(rows):
        frame=i+1;girl,dragon=cylinders
        girl.location=Vector(row['girl_root'])+Vector((0,0,.65))
        dragon.location=Matrix(row['dragon_matrix']).translation
        # Both shapes intentionally omit limbs, gait, faces and wing motion.
        for obj in cylinders:obj.keyframe_insert('location',frame=frame)
        cm=Matrix(row['camera_matrix']);cam.location=cm.translation;cam.rotation_mode='QUATERNION';cam.rotation_quaternion=cm.to_quaternion()
        cam.keyframe_insert('location',frame=frame);cam.keyframe_insert('rotation_quaternion',frame=frame)
        cam.data.lens=row['camera_lens'];cam.data.keyframe_insert('lens',frame=frame)
    for action in bpy.data.actions:
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:key.interpolation='LINEAR'
    scene.frame_start=1;scene.frame_end=c['frames'];scene.render.fps=24
    scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.color_type='MATERIAL'
    scene.display.shading.show_cavity=True;scene.display.shading.show_object_outline=False
    scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB';scene.render.use_stamp=False
    scene.timeline_markers.clear();scene['圆柱测试用途']='仅控制位置、绕行路线、距离、遮挡与相机；步态由生成模型补足，不把圆柱平移当成人体动画。'
    def validate():
        require_hash(cp,ch);require_hash(source,c['source_sha256']);require_hash(sp,sh)
    blend.parent.mkdir(parents=True,exist_ok=True);stills.mkdir(parents=True)
    scene.frame_set(1);require_self_contained(bpy);save_checked(bpy,blend,p,validate)
    write_json_new(report,dict(source_blend_sha256=c['source_sha256'],config_sha256=ch,samples_sha256=sh,source_start_seconds=c['source_start_frame']/24,frames=c['frames'],fps=24,removed_character_geometry=len(removed),cylinder_objects=[o.name for o in cylinders],rows=rows),p)
    scene.render.resolution_percentage=50
    for f in [1,25,49,73,97,120]:
        scene.frame_set(f);render_still_new(bpy,stills/f'圆柱测试-帧{f:03d}.png',p)
    validate();print(json.dumps(dict(blend=str(blend),sha256=sha(blend),frames=c['frames']),ensure_ascii=False))


if __name__=='__main__':main()
