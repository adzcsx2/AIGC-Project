# AutoDL AIGC

共享角色、不同服装三视图、声音、场景及其他可复用素材从 `projects/共享资产库/project.yaml` 进入；用 `tools/资产.py list --query <中文名>` 查真实路径，按版本导入作品并绑定角色。完整分类、唯一来源、命令与限制见 [共享资产流程](docs/工作流/asset-library.md)。既有作品路径保留，共享库更新不会自动改变已选版本。

作品从 `projects/<作品>/project.yaml` 进入；文件放置见 [目录规范](docs/规范/目录与命名规范.md)，本地剪辑、审片、水印和音乐使用 [统一视频工具](tools/视频工具/README.md)。

每个人物有独立YAML，`project.yaml.characters`为索引。名称可空，声音绑定人物；只有剧本需要人物说话才配置声音。无台词或仅非语言声不列配声待办；需要说话但缺声音时先完成独立工作，最后集中试听，确认后接续依赖步骤，见[人物与声音流程](docs/工作流/character-voice.md)。`tools/角色.py`可建档/列待试听清单；声音设计入口尚未接入，当前AutoDL可使用已有声音样本。

白模视频＋参考图复刻使用 `video-retargeting` 及已安装的 `clay-video-retargeting`：
先审计动作与目标身体，必要时修改引导副本，保留原声，生成后逐段检查。
人物参考板只做“正面特写＋正面全身无头＋背面全身”三个视图，不添加其他视角或运动格，使用
[character-reference-board](.agents/skills/character-reference-board/SKILL.md)。
该参考板明确生成请求可使用内置image_gen，优先于下文一般MJ默认；其他图片流程不变。
新出场人物、动物及其他生物先制作合格三视图，再制作含该角色的场景图，并将三视图实际传入后续生成API作身份参考；不能只把场景中临时生成的角色交API。流程见[新角色三视图前置与API绑定](docs/工作流/character-voice.md#新角色三视图前置与api绑定)。

Python + YAML 驱动 AutoDL ComfyUI 工作流，支持视频、语音生成及本地结果归档。

新原创视频默认只生成既有对白，不生成配乐；音乐按完整剪辑时间线单独制作、选择性混入，明确哪里有音乐、哪里留白，并让位对白。流程与当前功能边界见 [后期配乐](docs/工作流/music-postproduction.md)，配乐记录用 [YAML模板](templates/short-drama/配乐方案.yaml)。统一小工具已支持导入、器乐草稿和混音；专用AI音乐模型未接入；原片明确保声要求优先。

后续新人物、场景及配套视频未另定画风时，沿用用户认可的[中世纪写实风格规范](docs/视觉规范/中世纪写实风格规范.md)。其中保存实际基准图、角色与背景的风格分工、光线材质、摄影表演和出图检查；新人物使用自己的身份参考，已有作品明确风格优先。

直接描述需求即可，技能选择按 [自然语言路由表](docs/skill-routing.md)：单项工作直达专业技能，跨阶段制作由总导演组合调度；“继续”和选图确认承接当前进度，不重走全流程。

写、补、改剧本时必须先参考 [电影级剧本与生成前审计](.agents/skills/cinematic-script-audit/SKILL.md)，再使用动作与运镜等专业技能。默认 **16:9横屏，生成和剪辑默认24fps，最终成片自动补到60fps，不考虑平台UI安全区域**，用户明确要求及已确认规格优先。最终方案先总审计并修正、展示结论，之后才提醒/询问用户是否生成；不得等用户确认生成后才审计。审图后直接生成的任务同样提前审计，记录用 [生成前审计模板](templates/short-drama/电影级生成前审计.md)。

用户2026-11-12明确要求：以后新视频统一u30多图生成，不制作/提交白模。身份、身高参考和完整同框规则见 [导演流程](docs/工作流/director-workflow.md#u30多图身份身高与完整同框规则)。历史任务不重提。
按真实输入能力核实；必要输入不兼容时说明具体缺口和可行方案，不静默丢弃白模或伪造参数。已提交任务继续原ID等待/恢复，历史记录不改。

多片段采用最新 [剧本阶段预设计跨段切镜流程](docs/工作流/multi-segment-video.md)：助手审计分段方式和每段时长，
秒数按所选API当次实际范围、步长及剧情容量决定，无通用15秒或25秒上限；titim当前5–25整秒、u30当前1–15整秒，每次制作重新核验，不默认填满上限。
Codex先做按切镜设计所需的前出/后入图及必要端点，用户审图后直接生成全部片段、技术检查并合成。交付前逐一验收全部N−1个接缝，按已设计切镜/转场选择出入点并删除多余等待；旧片或明确连续例外再按版本04匹配运动并按需压短过渡，音画同步合成后自动补到60fps，最终接口也须复查；整体创作由用户验收。
有问题只重做指定段，用户认可后自动重合成。真正首尾帧需要对应入口；当前有
`minimax_h3_lightx2v` 与 `minimax_h3_b99_002`，u24的多图参数不等于首尾帧字段。

普通图片使用 Midjourney手动；已授权的参考板、衔接图与必要端点使用Codex内置image_gen。候选按适用流程展示，用户选定或确认后，
助手自动归档并执行已确认计划的下一必要步骤，包括准备下一张图片的英文提示词和手动挂图说明，不再重复询问是否继续。
只在需要用户选图、验收、决定创作分歧、不可兼容的模型选择或明确预算无法满足时停下；预算未给不构成缺口。不跳过未确认结果，不擅自重抽或扩大计划。
视频仍须先满足素材和实际模型输入条件。用户2026-11-08最新要求：明确提出生成即直接提交当前任务，不再单独查费或重复确认；未指定预算时不设预算参数。具体规则见 `AGENTS.md`。

视频会收费不再单独构成确认节点。当前蛇妖爬行修正已授权助手自行验收补图，不合格定向重做，合格后直接进入已要求的视频生成，详见`AGENTS.md`的补充授权。

**Discord 方案已按用户要求放弃。** 本项目代理和限速容器、专用镜像、网络及 Docker 部署文件已移除。
普通Midjourney图片提供英文提示词与参考图说明，由用户在官网手动生成；Codex专项图片按上文执行，不恢复Discord自动化提交。

所有模型提示词正文统一使用英文，包括图片、视频、编辑与负面提示词；
中文说明、剧本及素材中文命名继续保留。已提交配置保留原文作历史记录，新版本另写英文提示词。

## 安装

要求 Python 3.11+。本项目已经创建 `.venv`；在 PowerShell 中可直接调用虚拟环境的程序，
无需修改 PowerShell 执行策略：

```powershell
cd E:\AutoDL
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\autodl.exe models list
```

需要复现本次开发依赖版本时，可先执行
`.\.venv\Scripts\python.exe -m pip install -r requirements.lock`，再安装本项目。

以下示例的 `autodl` 均可替换为 `.\.venv\Scripts\autodl.exe`，或
`.\.venv\Scripts\python.exe -m autodl_video`。

## 密钥

读取优先级：环境变量 `AUTODL_API_KEY` / `AUTODL_APIKEY` / `AUTODL_TOKEN`，其次项目 `.env`。
支持标准 `AUTODL_API_KEY=...`、`autodl_apikey:...`（变量名不区分大小写），
也兼容一行裸 Token。解析不会修改 `.env`。
Token 必须属于 **ComfyUI 分组**；鉴权头是原始 `Authorization: Token`，不加 `Bearer`。
`.env`、作品目录 `projects/`、任务记录 `.autodl/` 均被 Git 忽略。

`projects/<作品>/02-素材/` 下的目录、图片、视频、音频统一使用中文名称，可带数字编号及版本号，扩展名保留真实格式。
例如 `projects/双精灵对决/02-素材/人物/角色-银发法师-全身.png`、`projects/双精灵对决/04-输出/原始片段/镜头01-双人对峙-版本01.mp4`。
模型 ID、API 字段和内部素材 ID 保留原值；具体约定见 `AGENTS.md`。

旧 Midjourney Python 代理代码和本地任务记录仅保留离线查阅，不再作为生成入口。
原账号配置仍在被忽略的根目录 `.env`，未输出或擅自变更凭据，也不再读取它们调用 Discord。
当前状态见 [Midjourney 手动流程与弃用记录](docs/工具与接口/midjourney-local.md)。

## 从 YAML 生成视频

首次使用通用示例时，先建立本机的“工具验证”作品入口；`projects/` 不随 Git 提供。
仅当 `projects/工具验证/project.yaml` 尚不存在时执行初始化，已有入口直接复用。
初始化只创建本地 YAML，不联网；离线校验也不会自动创建作品或读取密钥。

```powershell
.\.venv\Scripts\python.exe tools/项目.py init 工具验证
autodl run examples/text-to-video.yaml --dry-run
autodl run examples/text-to-video.yaml --max-cost 0.10
```

`run` 会真正提交收费任务；`validate` 和 `--dry-run` 只做离线校验，不联网、不读取 Token。
运行时先读取最新工作流规则和价格，再检查参数与预算，提交后保存 task_id，
轮询至完成并立即下载视频。URL 有有效期，勿只保存远程链接。

YAML 顶层字段：

| 字段 | 含义 |
|---|---|
| `workflow_id` | 必填，工作流 ID，不能仅使用显示名称 |
| `inputs` | 工作流的 API 参数；只将这部分作为 JSON Body 发送 |
| `output_dir` | 可选，默认当前作品的 `04-输出/原始片段/<配置名>`；通用示例归工具验证作品。显式相对路径相对仓库根目录 |
| `timeout` | 可选，等待秒数，默认 1800；超时不会取消远程任务 |
| `poll_interval` | 可选，查询间隔秒数，默认 3 |
| `max_cost_cny` | 可选，人民币预算，命令行 `--max-cost` 优先 |

`inputs` 的图片/音频/视频可以是 HTTP(S) URL、`data:MIME;base64,...`，或本地路径。
传给 `run` 或 Python `generate` 的配置路径相对当前工作目录，也可使用绝对路径。
**本地素材路径相对 YAML 所在目录**，也可使用 Windows 绝对路径；程序将文件转成带 MIME 的
Base64 data URL，仅随生成请求发送至 AutoDL，不需要额外图床。客户端单素材上限 100 MiB，
平台自身可能有更小限制。格式按各工作流的 `accept_types` 校验。

预算目前只支持可以按明确时长计算的 H3 工作流，使用公开价格较高的时段计算，货币单位为 CNY。
实际提交前重新获取价格；这是本地估算检查，平台没有提供服务端锁价/硬性费用上限字段。
按音频或输入视频长度计费的工作流无法仅凭配置可靠估价，指定预算时会拒绝提交。

## 全量模型目录及更新

```powershell
autodl models sync
autodl models sync --check
autodl models list --search 文生视频
autodl models list --search motion-transfer
autodl models show minimax_h3_lightx2v_no_pic
autodl models template indextts2-v1 --output examples/my-tts.yaml
```

`catalog/workflows.yaml` 保存全量模型和真实 `input_rules`、默认值、枚举、时长限制、
计费配置、输入/输出说明、原页面地址、更新时间和作者的使用说明；[简表](docs/工具与接口/models.md)方便浏览。
同步不需要 Token：读取网页使用的目录接口并逐一读取详情，全部成功后才原子替换目录。
失败不会清空旧目录。`--check` 只报告新增、变化和移除项，有差异返回 1，无差异返回 0。
同步刷新上游内容；`examples/`只放通用接口示例，作品的自定义调用参数保存到
`projects/<作品>/03-制作/生成配置/`，不要改写目录快照。

生成模板会填写实际默认值和必填素材路径；先替换提示词并提供素材，再执行校验。
多图、音画融合、首尾帧、动作迁移和语音示例见 [examples](examples/README.md)。
工作流同名也可能参数不同，始终按 ID 查阅。模型名称的“12 秒”等文字有时与
`input_rules` 不一致；校验依据服务端规则，并在需要时核对详情说明。

## 中断恢复

```powershell
autodl run examples/text-to-video.yaml --no-wait --max-cost 0.10
autodl task list
autodl task status TASK_ID
autodl task wait TASK_ID --timeout 1800
autodl task download TASK_ID
```

生成请求只发送一次。网络错误、服务器错误或无法解析的提交响应可能意味着任务已经创建，
程序不会自动重发 POST。此时查看 `.autodl/attempts/` 和 AutoDL「调用日志」；取得 task_id 后
使用 `task wait`，不要直接重新 `run`。有 task_id 的记录保存在 `.autodl/tasks/`。
恢复下载沿用任务所属作品的输出目录；指定`--output-dir`时也须位于同一作品内。
轮询和下载可以重新执行，不会创建新生成任务。下载失败时 `task download` 会重新查询结果 URL。

成功状态兼容 `SUCCESS` / `completed` / `SUCCEEDED`；排队与执行有超时退出，失败会明确报错。
下载使用独立无鉴权客户端，Token 不会发送至结果 CDN；文件流式落盘，空文件或错误文档会被拒绝。

## Python 调用

```python
from autodl_video import VideoProject

project = VideoProject(r"E:\AutoDL")
preview = project.generate("examples/text-to-video.yaml", dry_run=True)
print(preview)

# 真正提交任务：
result = project.generate("examples/text-to-video.yaml", max_cost_cny="0.10")
print(result["task_id"], result["files"])
```

底层客户端也可独立使用，适合接入自己的分镜或批处理程序：

```python
from pathlib import Path
from autodl_video import AutoDLClient
from autodl_video.config import load_token
from autodl_video.storage import download_results

with AutoDLClient(load_token(Path(r"E:\AutoDL"))) as client:
    task = client.submit(
        "minimax_h3_lightx2v_no_pic",
        {"prompt": "An orange cat walks along a street after the rain.", "duration": 1, "resolution": "480p横"},
    )
    # 立即保存 task["task_id"]；底层接口不提供 YAML 校验和预算检查。
    completed = client.wait(task["task_id"])
    paths = download_results(
        completed, Path("projects/工具验证/04-输出/原始片段/接口示例")
    )
```

模型推理在 AutoDL 执行，本机不需要 GPU 或 ComfyUI。本项目集成的是指定页面的工作流 API；
多段长视频可分别配置镜头生成，剪辑、配乐和拼接不属于这些工作流的统一 API。

## 导演与技能

文案、设计与已有媒体专项复审使用 [review](.agents/skills/review/SKILL.md)：默认做满5轮完整审计与范围内修订，最终无遗留问题、必需证据全部通过才放行，否则明确BLOCKED。每轮覆盖本次全部范围，涉及动作时独立审速度，已有白模/视频再核对尺寸、速度/物理、真实输入及状态稳定性；区分设计通过与实际测量，不因审计自动生成、修片或重抽。可说“审一下这个剧本并优化”“review这段决斗有没有被拉慢”，或使用 `$review`；“只审不改”保留原稿，生成前总审计仍由cinematic-script-audit负责。

已接入 [Acheng Director](https://github.com/AharaOoO/acheng-director-skill) 的故事、分镜、连续性和132个摄影示范，
当前技能及数量见 [安装清单](docs/installed-skills.yaml)，完整职责以技能路由表为准；历史重组数量不代表当前状态。
人物表演由[acting-prompt-writer](.agents/skills/acting-prompt-writer/SKILL.md)负责，只补原分镜中的可见演技，保留台词和大动作；镜头取景由storyboard-camera负责，招式变化由fight-scene-design负责，默认由总导演按需调用。重复入口仍作内部资料，原脚本和许可保留。
完整分工、来源和边界见 [导演规则](docs/工作流/director-workflow.md)、[接入记录](docs/工具与接口/acheng-integration.md)。

以后给故事/打斗想法即可：先补全中文文案让你确认，再自动拆镜，逐段审计运镜并检查整体变化，
列出缺少素材，交付英文图片/视频提示词。动作要求紧凑、迅速、有力，攻防交叠，避免回合制。
新视频按u30多图规则准备身份、尺度与完整镜头参考；先review再生图，实际输入复核/总审计通过后生成。

默认入口是 [short-drama-workflow](.agents/skills/short-drama-workflow/SKILL.md)；
摄影用 [storyboard-camera](.agents/skills/storyboard-camera/SKILL.md)，
打斗用 [fight-scene-design](.agents/skills/fight-scene-design/SKILL.md)，
资产用 [visual-assets](.agents/skills/visual-assets/SKILL.md)，
实际生成用 [autodl-aigc](.agents/skills/autodl-aigc/SKILL.md)。
人物板、原片复刻、白模预演和原片测量保留独立专项入口，见[技能路由表](docs/skill-routing.md)。

新清单使用schema 2，文案确认绑定剧本版本；修改后旧确认失效。
清单/模板/命令见 [短剧工作流](docs/工作流/short-drama-workflow.md)。历史schema 1与任务恢复保留兼容。
u24当前不读取参考视频，非白模原片需要复刻时会说明能力缺口，不能假称已经输入视频。

## 本机 Blender 与白模

已接入[blender-video-workflows](https://github.com/modengsir/blender-video-workflows)的两套技能：
[原创白模](.agents/skills/blender-video-original/SKILL.md)和[参考视频复刻白模](.agents/skills/blender-video-recreate/SKILL.md)。
以后直接说“用Blender做白模”“把这个视频复刻成三维白模”或“修改这个.blend”即可；助手优先调用
`D:\blender-5.3.0\blender.exe`，制作可编辑工程、动作、摄影机和白模视频。已验证版本为5.3.0 Release Candidate。

白模也可以先由其他视频工具生成；已有合格白模时直接接现有`video-retargeting`，用你选定的人物图、场景图替换，
由`autodl-aigc`核实titim的真实输入，不强制用Blender重做。视频外观转白不等于自动恢复可编辑三维工程。
来源、调用方式和本机验证见[Blender接入记录](docs/工具与接口/blender-integration.md)。

白模制作统一按 [制作与验收规范](docs/工作流/白模制作与验收.md)，作品入口用 `whitebox_plan` 指向 [白模计划](templates/whitebox-retargeting/白模计划.yaml)。`tools/视频工具/白模.py` 支持计划校验、独立重载工程检查、审片/送模两版预览、切点核验与网页审片交接。复用了VLM-Generation-Harness的方法并修正已发现的校验缺陷；上游原文仅作来源，不是新增执行规则。

用户2026-11-10确定：以后白模只用圆柱等简单几何占位，可用不同纯色区分人物/物体；白模控制比例、空间路径/高度、接触关系和摄影机，细节步态、肢体、表情与材质交视频模型提示词。现有 `storyboard-camera` 负责镜头设计，两个Blender技能把机位、角度、焦距、跟随路径/速度及切镜落实到工程。当前通用工具的送模分支为灰度，彩色送模须按共享规范使用实际支持的导出实现并核验，不能将带字审片版直接提交。

## 本地视频补帧

最终成片在剪辑、拼接及音轨完成后，自动调用项目技能 [补帧](.agents/skills/补帧/SKILL.md) 到60fps，无需再次提醒；单段、多段及替换后重合成都适用。生成和剪辑默认24fps；已有60fps成片核验复用，用户明确另定帧率或不补帧时遵从。中间素材和仅下载原始结果不自动处理。

也可在聊天中输入 `$补帧 双人对决.mp4`，
也可以说“把刚才的视频补到60帧”。助手定位视频后，使用本机RIFE v4.6/TensorRT补帧，
在原目录生成 `双人对决-补帧60帧.mp4`，保留原片、原声、速度和分辨率；重名自动加版本号。
容器按实际音轨和字幕格式选择：兼容音轨与mov_text字幕保留MP4，SRT/ASS字幕、附件或特殊音轨使用MKV；无法无损兼容的组合会在处理前说明，不静默丢轨。此流程在本地GPU执行，不使用AutoDL生成API。

```powershell
.\.venv\Scripts\python.exe 'tools\视频工具\补帧.py' 'projects\作品\04-输出\成片\双人对决.mp4'
```

## 开发验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=autodl_video --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip_audit
```

测试使用模拟 HTTP，不消耗额度。真实样片记录见 [验证记录](docs/验证记录/verification.md)。

来源：[工作流页面](https://autodl.art/large-model/comfyui)、
[官方 API 文档](https://autodl.art/docs/comfyui_api/)。
目录列表和详情是网页使用的接口，生成/查询接口则见官方文档；平台变更时需更新本项目适配。
各端点、状态及错误约定见 [API 适配说明](docs/工具与接口/api.md)。
