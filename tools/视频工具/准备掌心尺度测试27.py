"""Prepare the single authorized relative-scale test; no generation POST."""
from pathlib import Path
import copy
import hashlib
import json
import yaml

R = Path(__file__).resolve().parents[2]
P = R / 'projects/悬崖上的小气球'
C = P / '03-制作/生成配置/掌心相对尺度测试27'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


PROMPT = '''Image1 is SCENE, the location. Image2 is MIA, the girl identity. Image3 is GULU, the pink hatchling identity. Identity boards supply appearance and anatomy, not pose, studio lighting or display size. Only GULU appears; MIA remains offscreen. Reference labels never appear as text.

GULU is a truly palm-sized living hatchling: his compact head-and-torso could rest in a cupped human palm. This is a scale comparison, not a request to show a hand. Preserve his juvenile face, gray-blue eyes, short horns, four paws, folded wings and tail. The sapling is about ten times his natural four-paw horn height, with both rooted on the same ground plane. Keep that physical proportion throughout rising, running and jumping; straightening joints does not enlarge his head, torso or paws.

Begin belly-low with legs folded, facing LEFT. He promptly straightens onto four paws, scampers LEFT beneath the hanging berry and makes a brisk upward hop. His muzzle clearly misses the fruit with a visible air gap wider than his head. He falls promptly back to the grass, paws flexing under his weight and bending the blades. Finish with a short frustrated tail flick. Keep preparation short, the run quick and the hop-and-landing continuous; no hovering, slow descent or stretched recovery. Never touch, grab or perch on the twig.

Use the same sunny meadow: two timber-and-plaster cottages behind LEFT, a mature tree behind RIGHT and the curved dirt path. Preserve the slender sapling and its single high red berry. Use a scene-dominant side view showing the full sapling and tiny dragon together on the same ground depth; travel stays lateral, without approaching the lens.

Grounded medieval live-action fantasy with photoreal creature VFX, coherent upper-left daylight, contact shadows, irregular matte scales, supple joints, moist eyes, thin membranes, natural grass and soil. Restrained color, soft highlight roll-off and lens-appropriate detail; no cartoon, plastic toy, polished game render or HDR sharpness.

16:9. Silent: no speech, human voice, animal call, music or added effects. No text, ruler, hands or extra props.'''

PLAN = '''# 掌心相对尺度测试27：五秒方案

2026-11-15。按本轮明确授权，只生成一段5秒u30视频，检验熟悉物体类比和相对高度描述，不使用厘米、米或像素身高。

实际图片仍仅三张：场景SCENE、女孩MIA身份板、小龙GULU身份板，顺序不变；两个人物板只管身份。仅小龙出镜，女孩画外，不挂女孩音频，不新增手掌、尺子、道具、辅助图、白模或深度输入。

小龙是能由合拢手掌托住头身的掌心大小幼龙；尾翼不作为掌心体量比较。小树约为小龙自然四足角高的十倍，树根与龙脚处在同一深度。低伏来自屈肢贴草，起身不改变头/躯干尺寸。十倍为本次试验的相对描述，不更改人物主档，也不宣称与旧五倍关系构成严格单变量对照。

动作只取低伏→迅速四足起身→横向跑到果下→向上小跳没够到→自然迅速落地→短促受挫尾尖反应，不塞完整后退/刨地/滑滚剧情。果子始终挂在高处，嘴与果子间空隙比自己的头还宽，不抓枝或跳上树。短起手、快速跑动、及时落地，草叶因爪掌接触弯压，保持原速。

保留本片电影实拍风格及角色身份。景宽、树与小龙同时可见，运动横向且不走近镜头；不规定像素占比或细碎时间码。16:9横屏，真实u30选择768p横、5秒；没有fps字段则保留原生帧率，最终按默认补60fps，不变速。全段无对白、无音乐，音轨静音。

执行一次提交，不自动重抽。本方案的类比是否比厘米更有效，待实际视频比较；提示词正确不等于体型控制已通过。
'''


def main():
    C.mkdir(parents=True, exist_ok=True)
    pf = C / '掌心相对尺度-英文正文01.txt'
    assert not pf.exists(), 'Preserve the existing prepared test; inspect its records.'
    pf.write_text(PROMPT, encoding='utf-8')
    plan = P / '01-文档/需求与剧本/掌心相对尺度测试27-五秒方案01.md'
    plan.write_text(PLAN, encoding='utf-8')
    receipt = P / '06-记录/用户确认/掌心相对尺度测试27-五秒生成授权01.json'
    receipt.write_text(json.dumps({
        'client_date': '2026-11-15',
        'user_request': '我觉得你用具体的10厘米20厘米，视频可能识别不出来，你可能需要其他的形容词，不要用具体的数值了，直接用有参照物的词来控制身高看看，比如说手掌大小的小龙。然后果子树也用相对高度，比如说比小龙高10倍的果子树，或者其他参照物。你用这样试一下生成5秒的视频我看看',
        'scope': 'One5s u30 test, palm-size plus relative tree height, existing exact3images, normal physical speed; not another40s batch',
        'video_submissions_authorized': 1,
        'auto_rerolls': False,
        'style_preserved': True,
        'global_character_dimensions_changed': False,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    project = yaml.safe_load((P / 'project.yaml').read_text(encoding='utf-8'))
    style = P / project['documents']['style']
    style.read_text(encoding='utf-8')
    shared = R / 'docs/视觉规范/中世纪写实风格规范.md'
    shared.read_text(encoding='utf-8')
    old = yaml.safe_load((P / '素材清单-前四十秒三图输入26-执行02.yaml').read_text(encoding='utf-8'))
    ids = ['SCENE', 'CHAR-GIRL-THREEVIEW', 'CHAR-DRAGON-THREEVIEW']
    assets = {key: copy.deepcopy(old['assets'][key]) for key in ids}
    docs = copy.deepcopy(old['documents'])
    rel = plan.relative_to(P).as_posix()
    docs.update(script={'path': rel, 'state': 'ready'}, storyboard={'path': rel, 'state': 'ready'})
    manifest = {
        'schema_version': 2,
        'voice_policy': old['voice_policy'],
        'creative_confirmation': {'state': 'confirmed', 'script_sha256': sha(plan), 'confirmation_ref': receipt.relative_to(P).as_posix()},
        'documents': docs,
        'assets': assets,
        'shots': {'R27-PALM': {
            'speakers': [], 'voice_bindings': {}, 'required_assets': ids,
            'reference_bindings': {f'ref_image_{n}': key for n, key in enumerate(ids)},
            'authorization_ref': receipt.relative_to(P).as_posix(),
        }},
    }
    mf = P / '素材清单-掌心相对尺度测试27-执行01.yaml'
    mf.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False, width=110), encoding='utf-8')
    config = {
        'workflow_id': 'minimax_h3_zm_u30', 'materials_manifest': str(mf), 'shot_id': 'R27-PALM',
        'inputs': {**{f'ref_image_{n}': str(P / assets[key]['path']) for n, key in enumerate(ids)},
                   'prompt': PROMPT, 'duration': 5, 'resolution': '768p横', 'seed': 202611152603},
        'output_dir': str(P / '04-输出/原始片段/掌心相对尺度测试27'), 'timeout': 3600, 'poll_interval': 15,
    }
    cf = C / '掌心相对尺度-u30-执行01.yaml'
    cf.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False, width=110), encoding='utf-8')
    baseline = {
        'scope': 'One R27 prompt and5s test plan; all text/ref/contract/style/action/speed/contact/scale/language/camera/authority checks in every full round',
        'style': {'path': str(style), 'sha256': sha(style), 'shared_sha256': sha(shared)},
        'files': {str(f): sha(f) for f in (plan, pf, mf, cf)},
        'actual_references': {key: {'path': assets[key]['path'], 'sha256': sha(P / assets[key]['path'])} for key in ids},
        'rounds': [{
            'round': 1,
            'coverage': 'Full English prompt and Chinese plan, actual reference duties/style/identities, scale/comparison, camera/depth/axis, action capacity, normal speed/contact, silent language, actual configuration and single-test authorization',
            'finding': 'The English palm comparison says head-and-torso but omits the explicit tail/wings exclusion found in the Chinese plan. Make the comparison scope explicit. Same ground plane is paired with same-depth lateral framing; no foreground compensation is allowed.',
            'status': 'NEEDS_MINOR_TEXT_REPAIR',
        }],
    }
    review = P / '05-检查与验收/掌心相对尺度测试27-五轮与生成前审计01.json'
    review.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'draft': str(pf), 'words': len(PROMPT.split()), 'submissions': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
