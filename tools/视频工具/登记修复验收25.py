"""Record observed repair evidence; FAIL/NOT_VERIFIED never become ready."""
from pathlib import Path
import hashlib,json

P=Path(__file__).resolve().parents[2]/'projects/悬崖上的小气球'
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
pack=json.loads((P/'03-制作/生成配置/固定果树单主体25修复03/制作包03.json').read_text(encoding='utf-8'))
observations={
 'ENV':('PASS','Re-viewed: no actor; two cottages left, mature tree right, one small sapling and one high red berry. New metric camera fitted to approximate photo root/crown/berry landmarks. This is staging consistency, not a recovered physical camera.'),
 'TREE':('PASS','Re-viewed complete one sapling, thin descending twig and one red berry, neutral photographic tree-design board. Canonical species/branch intent only; not submitted as a competing scene camera.'),
 'BERRY':('PASS','Re-viewed: one intact attached red sweet berry, intact sloping twig/pedicel, same left cottages/right mature tree and upper-left daylight. A visible closer insert; no actor or ground-level relocated fruit. Fine skin detail at insert distance is not comparable to the unresolved few-pixel texture in wide shot.'),
 'RUN':('PASS','Re-viewed: tiny left-facing four-paw juvenile at the root-depth lane, complete tail and wings, environment dominates. Approximate horn/paw envelope 80-86px on941px image versus78.5px metric-camera target; grass/pose measurement uncertainty is explicit. Approved juvenile family maintained. Not proof of exact 3D volume.'),
 'MIA':('PASS','Re-viewed: only Mia, same braid/cloak/linen/leather; low side-recline, separate planted support elbow/cheek hand and free hand on grass, full boots visible. No old low fruit/branch or animal. Natural skin/cloth and shared exterior light.'),
 'LOW':('FAIL','Actual attempt08 enlarged torso/whole animal relative to RUN and did not execute the intended supported cheek/head orientation. Horn envelope remains substantially above the approximately42px low target. Do not rescale the whole creature down and call it a joint-only posture fix.'),
 'APEX':('PASS','Re-viewed: muzzle directly below berry, visible approximately105-110px empty gap; whole animal airborne with no tree/fruit contact. Metric design gap94px under approximate camera, actual photo implies a clear miss of roughly25cm with projection uncertainty. Rounded juvenile retained. This is a soft pose/location reference; no claim of exact3D translation or motion speed.'),
 'BURY':('NOT_VERIFIED','Actual repair04 bends local grass around muzzle/chest; nose partly obscured, front paws brace, tail remains lifted, tuft stays left of berry/right of trunk. Contact improved. Comparable torso dimensions across RUN/BURY still need calibrated reference-only repair/measurement; silhouette height alone is insufficient.'),
 'TURN':('NOT_VERIFIED','Actual repair04 stays at the same pressed tuft and faces right on four paws with tense closed face. Position/direction repaired. Current torso/stance envelope versus original RUN still needs comparable-part scale verification; prior soft position PASS is not a complete physical-size PASS.'),
 'REACT':('PASS','Actual repair02 material/exposure inspected: restrained matte pink, irregular scales, moist gray-blue eyes, shaded belly/legs sharing grass exposure; pressed eyelids and down mouth corners, no smile. Macro framing about47-50percentH matches new deliberate closer camera design for the same20cm entity; no inferred giant size from image occupancy alone.'),
 'END':('PASS','Actual repair01 inspected: rear haunches contact damp pressed grass, both forepaws support chest, skull/neck and macro camera retained, no human upright sitting. Local rear/belly dirt, nose grass and right-facing closed tense face persist. Actual generating input was gray END05, preserved in request log; later END06 geometry is a separate corrected engineering reference, not retroactively substituted.')
}
assets={}
for key,(status,obs) in observations.items():
 f=Path(pack['assets'][key]);assets[key]={'status':status,'path':f.relative_to(P).as_posix(),'sha256':sha(f),'observed':obs,'evidence_method':'actual images visually inspected via view_image; approximate hand-read projection landmarks where stated'}
out={'status':'BLOCKED_CRITICAL_PHOTO_SCALE','scope':'actual R25 repair03 inputs; not movie acceptance','assets':assets,
 'independent_geometry':'05-检查与验收/固定果树单主体25-修复03-独立工程核对.json',
 'metric_check_result':'PASS_STATIC_COMPONENT_GEOMETRY: same rigid-component volumes, fixed-tail lengths, no animation/image textures, metric units. LOW max0.10077m; RUN/TURN/REACT/END max0.20m; APEX muzzle0.45m and fruit bottom0.70m; END torso contacts ground.',
 'required_followup':['Repair LOW joint pose without enlarged core','Calibrate comparable body parts in BURY/TURN against RUN','Recheck affected reference order/prompts and complete current actual-input cinematic audit'],
 'tool_choice_pending':'User question already sent: permit deterministic reference-STILL editing or continue imagegen. No answer yet; no approval inferred from elapsed time. Final video remains single-pass u30, no actor-layer compositing.',
 'video_submissions':0,'no_ready_override':True,'not_a_video_speed_or_volume_proof':True}
dest=P/'05-检查与验收/固定果树单主体25-修复03-实际图片验收.json';dest.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')

audit={'round':8,'scope':'All approved40s story/style, all selected photo references, actual metric06 engineering, all eight repair03 English drafts/configs, source-slot isolation and complete EDL',
 'basis':{'plan_sha256':pack['plan_sha256'],'style_sha256':pack['style_sha256'],'package_sha256_at_review':sha(P/'03-制作/生成配置/固定果树单主体25修复03/制作包03.json'),'actual_photo_acceptance_sha256':sha(dest)},
 'full_scope_review':[
  {'dimension':'story and information order','result':'PASS_DESIGN','evidence':'Same discovery/backsteps/run-under-fruit/upward miss/slip-roll/bury/tease/failed wing-flight/hurt reaction. No early cliff jump/eating/extra powers.'},
  {'dimension':'performance and voices','result':'PASS_DESIGN','evidence':'Mia stays low supported; eye/free-hand/shoulder/half-roll variations. Only her two approved17-word English lines in MIA-B; only MIA-A gets natural nonverbal laugh sample. Dragon requests and EDL omit all girl audio.'},
  {'dimension':'size and projection','result':'FAIL_ACTUAL_PHOTO','evidence':'Metric06 component volumes/20cm/10cm/45vs70 geometry PASS. Actual LOW08 enlarges core; BURY/TURN comparable torso scale not verified. New close47-50percentH is an explicitly different22mm macro camera, not an20cm contradiction.'},
  {'dimension':'space and contact','result':'PASS_DESIGN_WITH_PHOTO_LIMIT','evidence':'Fixed lateral depth and right-to-left run, muzzle under berry, landing left of berry/right of trunk, in-place right turn, pressed grass/nose dirt/rear mud persisted. Actual grass/rear support improved; dynamics still not generated.'},
  {'dimension':'native speed','result':'PASS_DESIGN_NOT_MEDIA_TESTED','evidence':'Short backsteps/scrape, run, brief0.5s ballistic hop and prompt land/roll; second5cm feet-clear interval0.25s. No slow motion/freeze/retiming. Native footage required to assess execution.'},
  {'dimension':'style and actual references','result':'PASS_APPLICABLE_STYLE_WITH_SCALE_FAIL','evidence':'Current style05/shared03 hashes unchanged; viewed exterior, girl, all corrected creature refs against previously viewed live-action benchmark. Macro roughness/exposure repaired. LOW failure remains a size/anatomy defect; style cannot cancel it.'},
  {'dimension':'input capability and bindings','result':'PASS_DRAFT_STRUCTURE','evidence':'Current real u30 GET:1-15s,9image/3audio,768p horizontal; nofps/ref_video/depth/mask. Drafts bind only visible actor board, real photo roles and appropriate voice slots; no Blender input sent to u30.'},
  {'dimension':'edit and continuity','result':'PASS_DESIGN','evidence':'11EDL ranges total40s, eight sources total40s, all source ranges nonoverlapping. Visible reaction cuts, same buried->extracted state across girl cut, rear-low continuity; no female J/L-cut onto dragon. Actual motion/seams/listening pending.'}
 ],
 'actual_repairs':['Rebuilt static camera/poses; removed opaque grass block; grounded rear hips; fixed tail component length changes','Created/inspected APEX04/BURY04/TURN04/REACT02/END01, preserving actual source hashes','Rewrote RUN initial-reference role and47cm route instead of treating stance image as backward-step endpoint','Recompiled all eight English drafts and single-actor bindings with current wide/macro projection values'],
 'unresolved':['LOW actual core/pose failure','BURY/TURN comparable-part scale verification'],
 'verdict':'NOT_CLEAN_FOR_VIDEO_SUBMISSION','paid_jobs_submitted':0}
ad=P/'05-检查与验收/固定果树单主体25-修复审计续轮08.json';ad.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'acceptance':str(dest),'audit':str(ad),'passed':[k for k,x in assets.items() if x['status']=='PASS'],'unresolved':[k for k,x in assets.items() if x['status']!='PASS']},ensure_ascii=False))
