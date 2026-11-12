"""Bind inspected R08 images; preserve original prompts and submitted histories."""
from pathlib import Path
import hashlib,json,yaml
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'projects/悬崖上的小气球'

def main():
    packet=json.loads((P/'03-制作/制作计划/一次直出08/制作包02-审定文本.json').read_text(encoding='utf-8'))
    mp=P/'素材清单-三视图更新01-资产归位01.yaml';m=yaml.safe_load(mp.read_text(encoding='utf-8'))
    actual={'R08-START':'02-素材/镜头/一次直出08/起点A-小体型四足-校准02.png','R08-STOP':'02-素材/镜头/一次直出08/果下B-同尺度四足-校准03.png'}
    for k,rel in actual.items():
        f=P/rel;digest=hashlib.sha256(f.read_bytes()).hexdigest()
        m['assets'][k]={'kind':'scene','required':False,'path':rel,'state':'ready','sha256':digest,'dimensions':list(Image.open(f).size),'purpose':'complete_scene_scale_and_pose_reference','usage':'startA' if k=='R08-START' else 'later_stopB_same_actor_same_scale_not_hard_lastframe','review_basis':'实看与同姿态轮廓量测A159/B160px、足底差1px；非3D体积证明','user_review':'assistant_checked_for_current_authorized_test_not_individually_user_accepted','generation_record':'06-记录/图片生成/一次直出08-实际请求与筛选01.json'}
        packet['sources'][k]=str(f.resolve())
    ids=packet['common_asset_ids']+list(actual)
    sid='CLIFF-02-U30-ONEPASS08';bindings={f'ref_image_{i}':k for i,k in enumerate(ids)}
    m['shots'][sid]={'speakers':[],'required_assets':ids,'reference_bindings':bindings,'purpose':'一次同框五秒奔跑、稳定体型与脚草物理测试；无跳跃/分层','authorization_ref':'06-记录/用户确认/一次直出08-继续五秒奔跑测试-20261112.json'}
    mp.write_text(yaml.safe_dump(m,allow_unicode=True,sort_keys=False,width=100),encoding='utf-8')
    inputs={'prompt':packet['video_prompt'],'duration':5,'resolution':packet['resolution']}
    pins={}
    for field,aid in bindings.items():
        f=(P/m['assets'][aid]['path']).resolve();inputs[field]=str(f);pins[field]={'id':aid,'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
    config={'workflow_id':'minimax_h3_zm_u30','materials_manifest':'../../../素材清单-三视图更新01-资产归位01.yaml','shot_id':sid,'inputs':inputs,'output_dir':str((P/'04-输出/原始片段/一次直出08').resolve()),'timeout':1800,'poll_interval':10}
    cp=P/'03-制作/生成配置/一次直出08/同框奔跑与真实踩草-五秒01.yaml';cp.parent.mkdir(parents=True,exist_ok=True);cp.write_text(yaml.safe_dump(config,allow_unicode=True,sort_keys=False,width=100),encoding='utf-8')
    packet.update(reference_bindings=bindings,actual_input_pins=pins,config_path=str(cp.relative_to(P)).replace('\\','/'),config_sha256=hashlib.sha256(cp.read_bytes()).hexdigest(),review_state='ACTUAL_IMAGES_INSPECTED_TOTAL_AUDIT_PENDING')
    out=P/'03-制作/制作计划/一次直出08/制作包03-实际输入.json';out.write_text(json.dumps(packet,ensure_ascii=False,indent=2),encoding='utf-8')
    hist=P/'06-记录/图片生成/一次直出08-实际请求与筛选01.json';history=json.loads(hist.read_text(encoding='utf-8'))
    for req in history['requests']:
        f=P/req['result'];req['result_sha256']=hashlib.sha256(f.read_bytes()).hexdigest();req['result_dimensions']=list(Image.open(f).size)
    hist.write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CONFIG',packet['config_path'],packet['config_sha256']);print('BINDINGS',json.dumps(bindings));print('All seven actual media files pinned; no paid generation submitted here.')

if __name__=='__main__':main()
