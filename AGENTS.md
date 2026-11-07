# AutoDL AIGC 项目

这是 Python + YAML 的 AutoDL ComfyUI 集成项目。先读 `README.md`。

- 跨阶段短剧创作默认使用 `.agents/skills/short-drama-workflow/SKILL.md`，
  按角色/风格提示词 → 剧本分镜 → 补齐素材 → MiniMax 图生视频衔接。
  用户去 Midjourney 生成图；助手提供可复制提示词并检查回传图。
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
