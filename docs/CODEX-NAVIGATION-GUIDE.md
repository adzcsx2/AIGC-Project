# Codex项目导航

找共用角色/造型/声音/场景：先读目标作品project.yaml，再读 [共享资产流程](工作流/asset-library.md)。统一入口 `projects/共享资产库/project.yaml`，查找命令 `tools/资产.py list --query <中文名>`；接续作品先执行 `tools/资产.py check --project <作品/project.yaml>`，沿本地materials路径使用，不猜原作品位置或浮动最新版本。

人物YAML、language说话语言（默认en）、对白翻译、音色与集中试听：先读 [人物与声音流程](工作流/character-voice.md)，再读作品project.yaml.characters；工具入口为 `tools/角色.py`。

先按本次目标选入口，路径均相对仓库根目录。

| 工作 | 主要位置 |
|---|---|
| 自然语言选技能、组合和继续当前阶段 | `docs/skill-routing.md`；当前硬性规则 `AGENTS.md` |
| 可调用技能 | `.agents/skills/<name>/SKILL.md` 与 `agents/openai.yaml` |
| 文案、剧本、分镜、摄影与动作设计的五轮完整审计、修订和放行 | `.agents/skills/review/SKILL.md`；具体职责见 `docs/skill-routing.md`，按当前作品及适用专业标准取证 |
| 人物视图标准与用户排版参考图 | `.agents/skills/character-reference-board/references/版式与三视图.md`；只做正面特写、正面全身无头、背面全身 |
| 新人物、动物等先三视图再入场景/API | `docs/工作流/character-voice.md`「新角色三视图前置与API绑定」；实际传入三视图身份参考，不能仅传场景临时角色 |
| 剧本必读基准、生成提醒前总审计 | `.agents/skills/cinematic-script-audit/SKILL.md`；`templates/short-drama/电影级生成前审计.md` |
| 跨阶段导演/多片段 | `docs/工作流/director-workflow.md`、`docs/工作流/multi-segment-video.md` |
| 对白生成、后期配乐/留白、音乐制作与混音需求 | `docs/工作流/music-postproduction.md`；`templates/short-drama/配乐方案.yaml`；音乐小工具按当前规划/实际能力区分 |
| 创作确认、素材清单与参数绑定 | `docs/工作流/short-drama-workflow.md`、`templates/short-drama/` |
| 当前作品正文、进度、片段版本 | `projects/<作品>/project.yaml`；先看 production_selection 与当前问题，再读已选文档；last_accepted_delivery 单列最近确认交付，不等于新制作分支 |
| 用户认可的中世纪实拍风格、新人物沿用 | `docs/视觉规范/中世纪写实风格规范.md`；内含实际基准图、可变身份与场景检查 |
| 每个作品的风格入口、逐请求继承与防漂移 | 作品 `project.yaml.documents.style`；`docs/工作流/director-workflow.md`「项目风格与防漂移」；`templates/short-drama/视觉设定.md` |
| AutoDL客户端、参数校验、恢复下载 | `src/autodl_video/`；测试在 `tests/`，配置在 `pyproject.toml` |
| 工作流规则快照 | `catalog/workflows.yaml`；按公开详情/同步更新，不直接手改生成目录 |
| 已提交任务及原始结果 | `.autodl/tasks/`、`.autodl/attempts/`、`projects/<作品>/04-输出/`；已有task_id恢复，不重提 |
| 原视频动作复刻与普通图片工具规则 | `docs/工作流/video-retargeting.md`、`docs/工具与接口/midjourney-local.md` |
| 本机Blender、原创/视频复刻白模及人物场景替换衔接 | `docs/工具与接口/blender-integration.md`；`.agents/skills/blender-video-original/`、`.agents/skills/blender-video-recreate/` |
| 圆柱等简单白模、纯色身份标签、摄影机位置/角度/路径控制 | `docs/工作流/白模制作与验收.md`；`storyboard-camera`设计镜头，两个Blender技能落实实际摄影机；不精细建模 |
| 内部来源与历史 | `.agents/resources/`按需取方法；`docs/archive/`仅恢复/追溯，不作当前入口 |

改技能职责时同步路由表、对应description和UI元数据；改生成客户端时运行对应模拟HTTP测试与ruff。只改规则/文案不伪装为已验证视频效果。不要输出或改写根目录`.env`，也不为导航补建账号、远程仓库或生成任务。

统一工具：`tools/视频工具/README.md`；目录规则：`docs/规范/目录与命名规范.md`。

白模任务：先读作品 `project.yaml.whitebox_plan`，再读 [白模制作与验收](工作流/白模制作与验收.md)。检查工具 `tools/视频工具/白模.py`；异常按 [故障排查](工作流/白模故障排查.md)。上游原文只在追溯或升级时读取。
