from pathlib import Path
import hashlib
import json
import datetime
import shutil
import yaml

if __name__ == "__main__":
    raise SystemExit("Historical preparer retired: read project.yaml and its current manifest.")

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / 'projects/悬崖上的小气球'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write_new(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8', newline='\n') as f:
        f.write(text)

def dump(p, d):
    write_new(p, yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=110))

receipt = ROOT / '06-记录/用户确认/前五段视频试制授权-20261111.json'
write_new(receipt, json.dumps({
    'recorded_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'user_message': '你先做前面5段视频，我看下效果',
    'scope': ['CLIFF-01','CLIFF-02','CLIFF-03','CLIFF-04','CLIFF-05'],
    'planned_durations_seconds': [10,13,15,13,15],
    'authorization': '当前制作计划前5个生成单元各一次提交；沿用刚展示的崖顶总览、既定人物与已选声音制作试片。',
    'scene_acceptance_scope': '允许当前SCENE-CLIFF用于本批试制，不记录成全片美术无条件认可，不推定另外两张新景获接受。',
    'not_authorized': '第6至13单元、付费重抽或无关任务',
},ensure_ascii=False,indent=2))

# Preserve the exact state to which the earlier whitebox bundle was bound.
history = ROOT / '99-历史/前五段试制前状态-20261111'
history.mkdir(parents=True, exist_ok=False)
for name in ('project.yaml','materials.yaml'):
    shutil.copyfile(ROOT/name, history/name)

m_path=ROOT/'materials.yaml'
m=yaml.safe_load(m_path.read_text(encoding='utf-8'))
m['assets']['SCENE-CLIFF'].update({
    'state':'ready', 'user_review':'accepted_for_first_five_trial',
    'acceptance_ref':receipt.relative_to(ROOT).as_posix(),
    'review_basis':'用户在本批三图展示后要求先做前5段，按当前总览用于该批试制；细节仍由实际视频检验。',
    'purpose':'environment_reference',
})
# Future shots still explicitly require these assets; this batch does not use them.
for aid in ('SCENE-VALLEY','SCENE-AERIAL'):
    m['assets'][aid]['required']=False
m_path.write_text(yaml.safe_dump(m,allow_unicode=True,sort_keys=False,width=110),encoding='utf-8')

style = '''Maintain the approved medieval live-action fantasy look throughout every shot and close-up. The baby dragon is a living photoreal cinematic VFX creature, with fine irregular pink scales, flexible skin folds, wet gray-blue eyes and tongue, thin wing membranes, believable soft tissue, weight and contact shadows. Preserve the referenced juvenile design and its four separate legs, two dorsal wings and one continuous tail; three short claws per foot. No extra limbs, red recoloring, changing eye color, adult growth, plastic figurine, cartoon-film or game-cutscene rendering. The girl's real skin, chestnut braid, gray-blue wool cloak with its existing fastening and worn hem, linen clothing, dark trousers and worn leather boots retain the reference identity, age appearance, materials and coherent natural exposure. Identity boards describe anatomy and clothing only: do not copy their neutral background, panel layout, standing poses or multiple copies of a character. One dragon exists; when the girl is shown there is only one girl. No titles, subtitles, captions, black bars or watermark. Fill a horizontal 16:9 frame with natural optical perspective and motivated depth of field.'''
space = '''Use the supplied cliff environment as the same continuous location in every shot: one main broad deciduous tree inland to the right, exactly two modest timber-and-plaster cottages on stone bases farther inland to the left, a curving dirt path behind the action, a connected grassy plateau with small-scale grass blades and local soft earth, and the rough layered gray-limestone rim on the valley side. The plateau remains attached to the inland hillside, never a floating island. Preserve the houses' relative near/far order through the camera change. No new buildings, railings, bell props or bystanders. Valley mist stays below the rim; distant wooded hills and pale blue sky retain the reference horizon. Thin-cloud-filtered daylight comes from high above the valley side, slightly left in the establishing view; shadows extend inland. Keep that world light direction and neutral warm daylight through angle changes. A mild breeze moves grass, leaves, loose hairs and the cloak edge in the same valley-to-inland direction. The small berry shrub stays safely inland, left of the main tree; select one ripe red berry on its outward-facing fork as the fixed target at about 0.9 m above the soil. Other background fruit need not disappear; the narrative target never changes branch or is picked. The girl starts on grass nearer the valley than the dragon, both several metres inland; the berry and both failed takeoffs remain inland of them. The dragon's head-and-trunk length is about 35 cm, total length about 55 cm including its tail, seated height about 30 cm; its body is small enough for the girl to cradle in both forearms, far below her knee when she stands at roughly 1.3 m. These are scale anchors, not an extra carrying action. Preserve that same physical size, not the equal panel sizes of separate reference boards.'''
sound = '''Audio: no background music, score, songs, humming, musical stings or narration. Only the explicitly scripted dialogue/vocalizations and restrained story sounds listed below are allowed; do not add words. No subtitles. Keep natural spatial perspective. Any continuous soft wind may carry through the editorial cut; do not insert a musical ending, fade to black or frozen end card.'''

prompts={}
prompts[1] = '''Reference mapping: ref_image_0 is the girl's identity and clothing board; ref_image_1 is the pink baby dragon's identity/anatomy board; ref_image_2 is the cliff environment. Compose a single live-action scene, never show the boards themselves.
'''+style+'\n'+space+'''
Duration 10 seconds. This is the beginning of the story; both characters and the ground are clean. The girl rests on her side, comfortably propped by an elbow, looking at her companion with a relaxed mouth and unhurried breathing. Her elbow and cloak press the grass down; the dragon's belly and folded legs compress the adjacent blades. Its two wings are folded naturally against its back without changing their underlying size.
0.0-6.0: A 28 mm relationship wide shot begins low over the inland grass with the girl and dragon together, then moves smoothly backward and upward toward the valley to reveal the near rock rim, the safe inland running space, the berry shrub and the same tree and cottages behind them. Do not teleport or reposition either character during this camera move. Both full bodies occupy a modest portion of the wide frame, with visible ground between them, full head/foot/tail room and room for the environment reveal. The dragon notices the berry near the end: its eyes fix on that branch and its head rises, curiosity sharpening into appetite; the girl remains resting.
6.0-8.0: An explicit straight cut to a fixed 70 mm insert of the designated ripe berry on the same shrub. Its stem visibly connects it to the twig. The breeze bends the twig and leaves slightly; the berry moves with its stem, never floats or detaches. The blurred tree/path retain the correct background relation.
8.0-10.0: An explicit eyeline cut to a fixed 65 mm low close shot of the dragon's head, chest and front paws, facing the shrub inland. It opens its wet eyes wider, licks its own lips once with real tongue-to-lip contact leaving a small wet trace, then plants its forepaws, folds the foreleg joints under load and pushes its chest up from the grass. The grass rebounds where its chest lifts and remains depressed beneath the loaded paws. End as it begins shifting its weight backward, still looking at the berry. This last movement motivates the next unit's cut from close-up to a low full-body view; do not hold a finished pose. No berry is eaten, no flight and no fall yet.
'''+sound+''' Allowed sound here: soft wind and leaf movement only. No human speech, dragon speech or added human vocalization.'''

prompts[2] = '''Reference mapping: ref_image_0 is only the pink baby dragon's identity/anatomy board; ref_image_1 is the cliff environment. The girl remains at her established resting spot outside this shot; do not introduce a different person.
'''+style+'\n'+space+'''
Duration 13 seconds, continuing after the berry has attracted the dragon. Begin immediately in a visibly different low full-body camera angle, already facing the same berry inland; do not repeat the earlier discovery or show a reference-board pose. Its body starts clean.
0.0-3.0: In a 45 mm low lateral three-quarter full-body view, the dragon takes exactly three small backward steps away from the shrub while keeping its head and gaze on the designated berry. Each paw contacts and bears weight on the grass before the next transfer; its tail follows its body. It lowers its chest and scrapes one hind paw through soft earth, pulling a little soil backward and leaving a short shallow furrow. Its eyes narrow with earnest determination and its shoulders load forward.
3.0-8.0: It drives forward toward the shrub, hind legs extending against the ground and both dorsal wings flapping rapidly but ineffectively. The camera tracks laterally with the whole animal, leaving forward travel space and full head, feet, folded-wing and tail margin. Its right hind paw lands on a small damp grassy patch and visibly slides backward under load; the grass bends with the skid. Its heavy front tips down and its eyes open in surprise. Both wings fold back before shoulder contact. The soft body makes one short sideways tumble along the grass, with continuous forward displacement and a single tail trailing from the pelvis; do not twist open wings against the ground or loop through repeated somersaults.
8.0-10.0: In the same uninterrupted view it lands muzzle and front chest first into a thick soft grass clump at the inland end of the attempted run. The blades part and flatten exactly where the muzzle/chest press, loose earth shifts slightly and a few grass fragments adhere to its nose. Its belly settles with a small soft-tissue rebound, while its short tail remains visible above the grass. Show the contact and the resulting flattened patch before cutting. The berry remains on its branch beyond reach. No drop over the cliff and no injury.
10.0-13.0: A visible cut to a fixed 75 mm insert of the same compressed grass clump and the dragon's single raised tail. The tail droops, then makes a small unhappy side-to-side wag while the face stays buried and the chest breathes. The pressed blades do not reset. End on this frustrated movement, ready to cut to the girl's first laugh in the next unit. Do not extract the head or make the dragon fly in this unit.
'''+sound+''' Allowed sounds: soft wind, small wing flutters, the restrained soft grass landing described in the story. No dialogue or laughter yet. Avoid added pain cries or exaggerated impact explosions.'''

prompts[3] = '''Reference mapping: ref_image_0 is the girl's identity/clothing board; ref_image_1 is the dragon's identity/anatomy board; ref_image_2 is the same cliff environment. ref_audio_0 is the user-selected voice timbre for this girl only. Use that same sweet youthful voice for the Mandarin dialogue and laughter below. The audio sample's English sentences are reference material, not the words to reproduce; do not speak them, translate this script, or assign its voice to the dragon. The dragon has no spoken words.
'''+style+'\n'+space+'''
Duration 15 seconds. Make a clearly visible new shot of the girl after the preceding tail insert. She is still at her original resting patch, looking toward the same inland grass clump where the dragon has fallen. The dragon's muzzle/front chest are initially in that flattened clump, with a few grass bits and tiny dirt flecks on its nose.
0.0-9.0: Fixed 50 mm medium shot, low enough to read her face and upper body, with space for her existing side-roll rather than cropping the action. She tries to hold a smile when she sees the tail, then breaks into a clear open laugh. Her eyes crease, shoulders bounce, and both hands clutch her abdomen. She rolls once onto her side on the grass, compressing it under her shoulder and cloak, then props herself on her left elbow with her right hand still over her belly. Her braid and heavy wool follow the roll with weight; grass under the elbow remains pressed. She catches her breath and speaks toward the dragon, amused and familiar rather than deliberately cruel. Her lips form only the quoted words. The laugh starts immediately; allow about two seconds for laugh/breath and begin the sentence by about 2.0 seconds, naturally continuing it across the internal edit if needed.
Exact original utterances, spoken once in order, with their original punctuation and no narrator: “噗哈哈哈哈哈！” “咕噜，你飞得真高啊，足足有一只蚂蚱那么高呢！你那是翅膀还是蒲扇呀？”
9.0-15.0: A visible cut to a 70 mm low dragon reaction close shot, making a small motivated push closer. The same girl's sentence continues offscreen and finishes by about 13.0 seconds, at a readable natural cadence, without cutting off a syllable or digitally accelerating speech. In response to her first teasing clause, the dragon presses its forepaws into the grass and lifts its dirty face out of the same clump; the blades part at its cheeks, some recover and a few remain bent. It first searches her face as if expecting praise, then registers that she is laughing at it. Its wet eyes widen, lower jaw draws tight and wing roots tense. Preserve the nose grass/dirt and the flattened landing area. Hold enough time for the hurt look to deepen after the complete line; do not reset to a neutral pose or begin a new takeoff yet. The next request visibly cuts from this hurt close-up to a full-body ground-reference shot in the same place.
'''+sound+''' Allowed sounds: the exact girl's laughter, breathing between her existing phrases, quoted Mandarin dialogue and soft wind. No dragon human voice, new lines, music or unrelated effects.'''

prompts[4] = '''Reference mapping: ref_image_0 is only the same pink juvenile dragon's identity/anatomy board; ref_image_1 is the same cliff environment. The girl stays offscreen at her existing nearby resting patch. No voice sample or human speech belongs to this unit.
'''+style+'\n'+space+'''
Duration 13 seconds. Begin with a visible cut to a fixed 55 mm low lateral full-body shot of the dragon in its previous inland landing patch, with the shrub beyond it, the same small grass fragments/dirt on its nose and a visible ground reference beneath all four paws. Its gaze briefly remains on the offscreen girl, hurt turning to stubborn resolve. Keep the entire body, folded/opening wing envelope, tail, every paw and a band of surrounding ground visible, with generous head and foot room. Use this constant ground-level comparison to read the tiny takeoff; do not raise the camera in sympathy or scale the creature up.
0.0-3.0: It exhales two thin gray wisps with a couple of dim short-lived ember specks from its nostrils, directed toward clear air, not a flame jet or propulsion. It sets its forepaws wider and takes one effortful inhalation. The chest/belly expand only modestly with breathing, the neck and wing roots tighten and the claws press grass/soil down. Keep its exact normal juvenile proportions; no balloon-shaped transformation, swelling body, huge belly or new wing structure.
3.0-6.5: Still intent on proving itself, it flaps the same wings rapidly from its back joints while its four legs lighten. The grass beneath responds to the nearby air and recovers as the paws leave. It wobbles up only about five centimetres, roughly one short claw's ground clearance, with a visible small gap below its lowest paw. This lift comes from wingbeats, not inflated-body buoyancy. For one readable instant its wet eyes brighten and its mouth lifts proudly.
6.5-9.5: The held breath escapes, chest/belly return to their earlier size, shoulders lose coordination and wingbeats falter. It folds the wings safely and drops onto its rump in the adjacent soft muddy part of the same patch. Show the rump actually reaching the mud, the local shallow depression forming under that pressure, a small amount of mud pushed outward, and a modest belly/neck rebound that settles under its weight. Avoid a crater, huge splash, weightless bounce or cut hiding the contact. Retain damp mud on the rump/lower belly and the depression after settling; the berry is untouched and remains beyond reach.
9.5-11.0: The fixed full-body view holds the settled consequence, the two wings folded again and feet braced. Its brief proud expression has collapsed into embarrassment.
11.0-13.0: A visible cut to a fixed 75 mm closer dragon face/front-chest reaction. Its eyes dip, then cautiously look toward the girl for approval; its jaw remains tight and its breathing shallow from exertion. Carry the nose grass/dirt and lower-body mud into all later shots even when the mud is outside this close crop. End on that expectant, embarrassed look; the next unit cuts to the girl laughing again. Do not start her second dialogue here.
'''+sound+''' Allowed sounds: wing flutters, the existing short frustrated exhalation and restrained soft muddy landing, with soft wind. No speech, added squeals, laughter, music or explosive fire sound.'''

prompts[5] = '''Reference mapping: ref_image_0 is the same girl's identity/clothing board; ref_image_1 is the same dragon identity/anatomy board; ref_image_2 is the same cliff environment. ref_audio_0 is only this girl's selected voice timbre. Keep that sweet youthful voice in the exact Mandarin dialogue and laughter below; do not reproduce the sample's English words. The dragon only has the existing nonverbal growl, never a human voice or new spoken line.
'''+style+'\n'+space+'''
Duration 15 seconds, ending the requested five-unit preview before the cliff run. Begin with an explicit new angle on the girl after the preceding embarrassed dragon close-up. The girl remains supported on her left elbow in her original grass patch. The dragon remains in the same inland muddy sitting spot, with nose grass/dirt, damp rump/lower-belly mud and the shallow depression left by the fall.
0.0-9.0: A fixed 50 mm medium shot includes the girl's face, torso and hands. Her second laugh is larger, bringing actual laugh tears to her eyes. She bends at the waist, her left elbow staying visibly loaded against compressed grass and her right hand clutching her abdomen, then the right index finger briefly points toward the dragon. Her shoulders shake with the laugh; she catches a breath and tries to compose herself, but her mouth keeps curling with amusement. Her braid and wool retain weight and the existing grass-contact state. She believes she is making a familiar joke, unaware of the hurt. Start the short laugh immediately and enter the complete spoken lines by about 1.5 seconds; use a natural childlike cadence, clear consonants and short breaths without speeding up the audio.
Exact original utterances, once in this order and with no additions: “哈哈哈哈！哎哟我的肚子……” “好啦好啦，小肥龙，承认吧，你其实是一只伪装成龙的胖蜥蜴对不对？”
9.0-15.0: A visible cut to a 70 mm low close/medium dragon reaction shot with a small motivated push, showing the head, shoulders, wing roots and enough torso to read a turn. The girl's existing line continues offscreen; complete it by about 12.5 seconds. At first the dragon raises its gaze toward her in hopeful expectation. The exact words “胖蜥蜴” trigger the change: its gaze fixes, the jaw clenches, its cheeks/nostrils tense without human facial distortion and the same gray-blue eyes widen in anger. Do not change them to gold. Only after the entire question ends, it gives the short milk-toothed, nonverbal angry growl “嗷呜”, then plants its paws and pivots its body away from the girl toward the valley side. The wet grass bends under its loaded forepaws as it turns, the muddy rump lifts out of the existing depression, and its single tail follows that turn with weight; the mud and grass traces remain on it. End on this determined departure initiation with enough time to read the hurt underneath the anger. The subsequent unit would make a visible cut to a side/rear full-body running angle; do not run to the rim, jump or reveal later flying in this unit, and do not freeze or fade at the end.
'''+sound+''' Allowed sounds: the quoted girl's laughter, existing breaths/quoted Mandarin lines, the one short nonverbal dragon growl and soft wind. No extra words, repeat dialogue, musical sting or narration.'''

names=['晒太阳与发现浆果','冲刺滑倒滚草','第一次笑与调侃','鼓肚子与短暂离地','第二次调侃与恼怒']
durations=[10,13,15,13,15]
config_dir=ROOT/'03-制作/生成配置/前五段试制01'
docs=['# 前五段视频英文提示词与审计\n\n版本01｜2026-11-11｜起草后复核定稿；只覆盖CLIFF-01至05，每段一次提交。中文对白逐字保留。\n',
'''## 中文执行依据与范围

依已确认剧本与分镜02：开场发现浆果→冲刺滚草→第一次笑与调侃→五厘米试飞跌泥→第二次调侃与恼怒。时长10/13/15/13/15秒，共66秒。四个内部段界分别为脸近景→低位全身、尾部→女孩中景、受挫脸→地面参照全身、跌坐反应→女孩中景。01/02留在同一浆果朝向，03/04/05延续草屑、泥痕和支撑；06尚未授权，不在05中奔崖。

当前风格03是唯一风格来源。采用用户刚展示后要求试制的崖顶总览；不把向下/回望图或白模灰度图混入API。现有身份板分别作为实际图像输入，板的背景、布局和静止姿势不继承。u30没有硬端点/视频/fps字段，摄影和尺寸是文本控制，非精确轨迹保证。输出选择真实枚举768p横，实际像素和原生帧率下载后探测。

总览可见多颗小红果；本次明确一颗固定外向分叉上的熟果为目标，其余是背景果，不虚构树上只有一颗果、实测距离或旧图像素精度。浆果始终挂枝。场地坐标与主体体量沿用已有白模，局部细节由英文正文执行和返回片实测。03/05的声样绑定米娅，英文样本不改变中文对白。两段各15秒，分别分配约11秒/11秒完成文字与气口、余下容纳笑与反应；真实口播是否完整由成片听音核验，不另开收费TTS试读。

本批是无配乐效果试片，保留剧本已有对白及明确的风/扑翼/落草落泥/非语言声；后期不铺音乐遮盖模型原声。全片可选音乐意图仍在已确认规划中，留待完整剪辑时再校准，不在这5段中启动作曲或第6—13段。
''']
for n,prompt in prompts.items():
    sid=f'CLIFF-{n:02d}'
    shot=m['shots'][sid]
    inputs={'duration':durations[n-1], 'resolution':'768p横', 'seed':202611110100+n, 'prompt':prompt}
    for slot,aid in shot['reference_bindings'].items():
        inputs[slot]='../../../'+m['assets'][aid]['path']
    config={
        'workflow_id':'minimax_h3_zm_u30','materials_manifest':'../../../materials.yaml','shot_id':sid,
        'inputs':inputs,
        'output_dir':f'projects/悬崖上的小气球/04-输出/原始片段/前五段试制01/片段{n:02d}-{names[n-1]}',
        'timeout':3600,'poll_interval':15,
    }
    cfg=config_dir/f'片段{n:02d}-{names[n-1]}-版本01.yaml'
    dump(cfg,config)
    docs += [f'\n## {sid}：{names[n-1]}（{durations[n-1]}秒）\n\n配置：`{cfg.relative_to(ROOT).as_posix()}`\n\n```text\n{prompt}\n```\n']

docs.append('''
## 提示词迭代审计记录

| 轮次 | 实际检查与发现 | 已落实修改/结论 |
|---|---|---|
| 起草检查 | 旧场景检查中的“唯一目标果”未锁定、旧稿缺实际声样映射；旧文字可能误导红龙/金眼、气球变形或多视图复制 | 本版每段定义同一指定分叉熟果、不要求清除背景果；03/05明确ref_audio_0仅映射米娅、说原中文；各段统一粉色灰蓝眼幼体、适度呼吸和板的身份职责 |
| 逐项二次复核 | 对照当前剧本、摄影、真实图序和u30字段：检查表情递进、倾听反应、左右手支撑、足/土/草/泥反馈、镜头留白、莓果不摘与状态残留 | 已具体写入五段实际英文正文；草丛/泥地接触在切镜前完成。女孩左肘承重、右手指向，回身动作不要求同时腾空。无硬端点/fps/视频伪字段，无新角色/台词/音乐 |
| 全局复核 | 四处段界前后状态、05对06的出口、时长容量及英文正文/YAML逐字一致性 | 已核对。全部适用文本项通过；镜头/口型/声线/材质/尺寸与动态物理的真实结果未产生，留作实测，不冒称模型保证 |

定稿来源为本文件五个英文代码块，与各配置inputs.prompt完全一致。电影级总审计另留版本证据；本记录不代替正式视频实测或用户认可。
''')
prompt_doc=ROOT/'01-文档/提示词/前五段视频-英文提示词与审计-版本01.md'
write_new(prompt_doc,'\n'.join(docs))

p_path=ROOT/'project.yaml'
p=yaml.safe_load(p_path.read_text(encoding='utf-8'))
p['current']={
 'stage':'first_five_trial', 'version':'前五段试制01',
 'next_step':'按本批生成记录核对CLIFF-01至05任务/输出，交用户审看效果；不提交第6至13段。',
 'issues':['当前SCENE-CLIFF仅按本轮要求用于前5段试制；另外两张环境图仍待审。',
           '米娅已选声音用于03/05；中文对白、音色保持及口型由实际返回片核验。',
           '白模04几何/摄影复用，当前状态文件变更后重新独立检查；动态与听音结论不由技术检查代替。']}
p['documents']['first_five_authorization']=receipt.relative_to(ROOT).as_posix()
p['documents']['video_prompts']=prompt_doc.relative_to(ROOT).as_posix()
p['documents']['pre_generation_audit']='05-检查与验收/电影级生成前审计-前五段试制01.md'
p['documents']['generation_batch']='06-记录/视频生成/前五段试制01-任务与结果.json'
p['whitebox_evidence']='05-检查与验收/白模-版本前五段试制01/白模检查包.json'
p_path.write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=110),encoding='utf-8')

pins=[]
for f in [prompt_doc,m_path,ROOT/p['documents']['script'],ROOT/p['documents']['style'],ROOT/p['documents']['storyboard'],*config_dir.glob('*.yaml')]:
    pins.append({'path':f.relative_to(ROOT).as_posix(),'sha256':sha(f)})
for aid in ['CHAR-GIRL','CHAR-DRAGON','SCENE-CLIFF','VOICE-GIRL']:
    f=ROOT/m['assets'][aid]['path']
    assert sha(f)==m['assets'][aid]['sha256'],aid
    pins.append({'asset_id':aid,'path':f.relative_to(ROOT).as_posix(),'sha256':sha(f)})
write_new(ROOT/'06-记录/视频生成/前五段试制01-输入锁定.json',json.dumps(pins,ensure_ascii=False,indent=2))
print(json.dumps({'configs':[str(f) for f in config_dir.glob('*.yaml')],'prompt_lengths':{k:len(v) for k,v in prompts.items()},'pins':len(pins)},ensure_ascii=False))
