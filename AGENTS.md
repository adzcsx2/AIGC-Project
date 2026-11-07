# AutoDL AIGC 项目

这是 Python + YAML 的 AutoDL ComfyUI 集成项目。先读 `README.md`。

## 素材中文命名（用户要求）

- 项目根目录 `assets/` 下的作品目录、子目录及素材文件统一用中文语义命名，
  图片、视频、音频及后续新增素材均适用。保留 `assets` 根目录名称及真实扩展名。
- 名称要体现内容与用途，可加数字编号、版本号；例如 `双精灵对决/角色-银发法师-全身.png`、
  `镜头01-双人对峙.png`、`视频/镜头01-双人对峙-版本02.mp4`。
  不再用 character、HERO、CHAR-A、SHOT-01、reference 等英文代号作为素材文件名。
- 提示词交付时提供的建议保存名、素材清单、YAML 媒体路径、自动创建的示例路径也必须遵守。
  模型 ID、API 参数键、内部资产/镜头 ID、task_id 不翻译，不与文件名混用。
- 改名同步更新实际文件和所有本地引用，保留真实图片/视频格式，不覆盖已有文件或其他版本。
  上游下载的原始任务输出可保留在 `outputs/` 供恢复；归档进 `assets/` 时改为中文名称并保留任务来源。
- 此规则针对制作素材；`.agents/skills/` 内第三方技能的程序资源与原始模板保留原文，
  从它们复制或生成本项目素材时应用中文命名。

## 提示词语言（用户要求）

- 所有新编写、修改、交付或提交给模型的 prompt 提示词正文统一使用英文，包括图片、视频、
  局部编辑、角色替换、动作迁移及负面提示词；聊天使用中文不改变此规则。
- 中文需求先整理为英文提示词；可复制正文、YAML 的 prompt 字段及实际 API 请求保持一致。
  用途说明、剧本、分镜说明、规则文档与素材目录/文件名继续使用中文。
- API 字段、模型 ID、参数枚举与引用标记保持协议要求的原值；语音台词、字幕等需要出现在作品中的
  中文内容按作品需求保留，用英文指令描述，不把对白或 API 枚举误当成需要翻译的提示词。
- 用户提供的原始提示词、已提交任务配置及上游资料保留原文作为历史来源，不篡改执行记录；
  再次使用时另建英文版本。第三方技能默认语言与本规则不一致时，制作本项目提示词以本规则为准。

## 创作与开发

- 用户指定本项目所有图片生成统一使用 Midjourney，走现有 `autodl mj`；不自动切换其他生图服务。
- 每次图片或视频生成必须有用户对本次用途与范围的明确授权；用户直接要求生成某张图即为该次授权，
  不重复索要同一授权。生成后展示结果并停下，须等用户确认或提出修改，才能进入下一步。
  不自动选图放大、重抽、做变体、补其他角度、生成下一角色/场景或推进视频。批量仅限用户明确授权的范围。
  助手检查合格也不能替代用户确认；未经用户确认的成图保持待确认，不能标 ready 或用于下游生成。
- 跨阶段短剧创作默认使用 `.agents/skills/short-drama-workflow/SKILL.md`，
  按角色/风格提示词 → 剧本分镜 → 补齐素材 → MiniMax 图生视频衔接。
  用户要求生图时使用 `autodl mj`；也可提供提示词供用户手动生成。
  生成后看图、中文归档，取得用户确认后再进行素材就绪检查与下一步。
- 原视频换角、去音轨、动作迁移和白模/深度路线判断使用
  `.agents/skills/video-retargeting/SKILL.md`。原片测量与抽帧用 short-drama-breakdown，
  白模预演用 huashu-seedance；不能声称已部署任意原视频到深度或3D动捕。
- H3 专用角色替换工作流 minimax_h3_zm_titi/titim 省略提示词或用简单主体映射，
  不套普通 H3 六段式。具体输入、声音与时长边界见 `docs/video-retargeting.md`。
- 原创作能力来自已安装的 zenstory-ai/drama-skills 九项技能，H3 表演补充来自
  phileiny/h3-storyboard-skill；具体来源、版本及取舍见 `docs/short-drama-skills-analysis.md`。
  需要哪个阶段就读对应 skill；不要求把全部技能、全部参考一次读入。
- 用户明确要求必要素材满足后才进入视频生成。缺图时给出用途、影响镜头、提示词与保存路径，
  不把 PLAN 槽位或提示词当现成图片，不自动改走文生视频。
  实际查看图并确认符合需求后才标 ready；改图或改分镜时重新检查受影响状态。
- 所有短剧生产 YAML 必须带 `materials_manifest` 与 `shot_id`，使用 CLI `validate/run`
  或 `VideoProject.generate`。素材检查与媒体绑定检查由 Python 执行，缺图不提交。
  五份 Markdown 拥有创作正文，materials.yaml 只登记生产就绪与文件绑定。
- 上游路由提及的 short-drama-produce 未安装，真实生成由本项目 autodl-aigc 接管；
  未安装的小说拆解、后期剪辑阶段仅在用户确有需要时扩展。

- 对 AutoDL 模型选择、参数解释、目录更新和生成请求，使用
  `.agents/skills/autodl-aigc/SKILL.md`；不要凭记忆编造工作流 ID 或参数。
- 对打斗戏、武术指导、武打分镜、动作编排和动作分解海报，使用
  `.agents/skills/martial-arts-director-cy/SKILL.md`，并读 `docs/fight-scenes.md` 衔接本项目。
  武指技能负责分镜及图像/视频提示词；API 配置和执行交给 autodl-aigc。
  用户已有 Midjourney 角色图时，以该图锁定人物、服装和风格，用户需求优先于模板默认值。
- 项目入口为 `.venv/Scripts/python.exe -m autodl_video`（Windows）或安装后的 `autodl`。
- Midjourney 本机代理已启动，Discord 账号初始化、频道读取与本机 API 鉴权已通过只读联调；
  已完成一次真实图片提交与结果恢复；该轮未通过用户验收，新版本参考参数尚未全面验证。
  使用 `docs/midjourney-local.md` 与
  Python `MidjourneyProject` / CLI `autodl mj`，不增加网页后台。
  用户要求本机账号信息与凭据统一保存到项目根目录 `.env`，能用中文的说明与状态使用中文，
  程序读取的环境变量名和 API 参数保留原文。保留现有 AutoDL 内容及密钥，不输出或提交 `.env`。
  Midjourney `/info` 中的 UUID 不能替代 Discord 服务器 ID、文字频道 ID 或用户凭据。
  `mj doctor` 为只读检查，`mj validate` / `mj run --dry-run` 为离线校验；
  `mj run` / `mj change` 会消耗会员额度，按用户明确授权的提示词、图片及次数执行。
  创建请求不自动重试；记录位于 `.autodl/midjourney/`，已有 ID 用 `mj wait/download` 恢复。
- `catalog/workflows.yaml` 是上游工作流规则及说明的本地快照，使用 `models sync` 更新，
  不直接手改生成目录。查询价格/最新模型时先同步或读取对应公开详情。
- `.env` 及环境变量中的 Token 不得输出、写入示例、提交 Git 或发送给结果下载域名。
  保留用户现有 `.env` 格式；只在内存中兼容裸 Token。
- `run` 会提交收费任务。执行用户授权的模型、用途和预算；无生成授权时使用 dry-run。
  样片初始化时的一次性授权不延伸到未来的其他生成任务。
- 生成 POST 不自动重试；不确定是否创建任务时查 `.autodl/attempts/` 和平台调用日志。
  已有 task_id 使用 `task wait/download` 恢复，不重新生成。
- 自定义输入放在单独的 YAML 配置里。素材相对 YAML 目录，输出相对项目目录。
- 修改客户端、动态 schema、计费或恢复逻辑时，运行对应模拟 HTTP 测试和 ruff。
  提交前运行完整 pytest、pip-audit，并检查 Git 中没有密钥。
- 本仓库只建立本地 Git；远程创建、推送和发布需要用户明确要求。
