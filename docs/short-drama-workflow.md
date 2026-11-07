# Midjourney 素材到 MiniMax 视频

在本项目中说“用短剧工作流”，或显式使用 `$short-drama-workflow`。
你可以先给角色图，也可以给参考提示词、自己的角色要求及故事想法。
助手会提炼风格、写角色和场景图片提示词，再完成剧本与分镜。
你去 Midjourney 生成缺少的图，放回项目后由助手查看、登记；必要素材齐备后才进入视频提示词和生成。
单独只要人物提示词或剧本也可以，不要求先跑完整流程。

已有原视频、希望换成自己的角色时使用 [视频换角工作流](video-retargeting.md)，
按需拆镜与去音轨；H3 替换专用工作流使用简单主体映射提示词，不套普通图生视频的六段式。

## 文件与状态

每集创作正文采用上游的五份 Markdown：`剧本.md`、`视觉设定.md`、`分镜.md`、
`图片提示词.md`、`视频提示词.md`。另保留用户需求 `需求.md`。
`materials.yaml` 是生产清单，不复制整份剧本和分镜。可从 `templates/short-drama/` 复制两个 YAML 到剧集目录。

- `documents` 必须登记 `brief/style/script/storyboard`，分别指向需求、视觉设定、剧本、分镜。
  同一份视觉设定可以拥有画风与人物设定，不必再造一份重复画风文档。
- `assets` 以稳定 ID 登记 `character/scene/prop/keyframe/audio/video`。
  `required` 默认 true；`path` 是相对清单的本地路径；`prompt` 可存补图提示词或正文定位。
- 状态：`missing` 待补，`provided` 有文件待检查，`ready` 已查看并符合本镜需求。
  提示词、计划槽位和假路径不能标成已就绪。新增人物/场景或改镜头后，重新检查受影响素材。
- `shots` 的 `required_assets` 列镜头依赖；`reference_bindings` 列实际 API 媒体字段到素材 ID 的映射。
  例如 `ref_image_0: CHAR-01`、`ref_image_1: SCENE-01`。
  首尾帧模式可以依赖角色、场景，但实际只绑定起始/结束关键帧，不要求把每个资产都发给接口。

```powershell
.\.venv\Scripts\python.exe -m autodl_video materials check projects/我的短剧/剧集/EP001/materials.yaml
.\.venv\Scripts\python.exe -m autodl_video validate projects/我的短剧/剧集/EP001/SHOT-01.yaml
```

清单检查完全离线：退出码 0 为齐备，1 为缺文档/缺图/待检查并输出缺口清单，2 为格式错误。
指定 `--shot SHOT-01` 核对镜头 ID；仍检查同一清单内所有必要素材，满足“补齐后才开始生成”的要求。
不相关作品放在不同清单。未使用且明确 `required: false` 的可选素材不阻断，镜头依赖或输入绑定引用它后就必须就绪。

镜头 YAML 的 `materials_manifest` 相对该 YAML；`shot_id` 必须存在于清单。
两个字段必须一起提供。`run` 与 `validate` 会先做素材检查，再校验实际媒体字段、类型、路径，
正式提交前还会根据最新模型规则复核。缺图时在读取密钥和网络访问前拒绝执行。
已有独立演示 YAML 不强制绑定短剧清单；以后此工作流编写的短剧配置一律绑定清单。
底层 `AutoDLClient.submit()` 是底层接口，不包含这层检查；短剧生产使用 `VideoProject.generate` 或 CLI `run`。

Python 能验证声明、文件存在、非空和常见图片文件头，以及是否把登记的图绑到实际输入。
人物相似、构图、风格和图像完整性仍需助手实际看图；不能只运行检查命令就宣布视觉验收完成。
不要在图像被替换后沿用旧的 ready 状态。

## 视频生成

素材齐备后，读取 `short-drama-video-prompts/references/minimax-h3.md` 编写对应模式的完整提示词。
参考模式的各段正文放进同一次请求，不拆成多次生成。
图片编号按实际输入顺序对应：`<Picture 1>` 是 `ref_image_0`。
模型 ID、时长、分辨率、参考图/音频数量以 AutoDL 实际规则为准；上游方言示例时长不是接口限制。

```powershell
.\.venv\Scripts\python.exe -m autodl_video models list --search minimax
.\.venv\Scripts\python.exe -m autodl_video models show minimax_h3_lightx2v_v5_15s
# 在本次镜头与预算已获用户授权、离线校验通过后运行：
.\.venv\Scripts\python.exe -m autodl_video run projects/我的短剧/剧集/EP001/SHOT-01.yaml --max-cost 0.25
```

模板里的 5 秒、480p、0.25 元是示例，并非用户已授权的生成参数或对价格的保证。
用户要求决定实际镜头与预算；正式请求使用最新公开详情估算。保存任务记录、等待并下载由现有客户端处理。
多镜头分别生成；本次没有安装另一套 provider，也没有自动调用 Midjourney 或其他图片平台。

具体安装源与取舍见 [技能分析](short-drama-skills-analysis.md)。
