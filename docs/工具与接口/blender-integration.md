# Blender 本机接入与白模工作流

当前操作唯一依据为 [白模制作与验收](../工作流/白模制作与验收.md)，问题按 [故障排查](../工作流/白模故障排查.md) 定位。本页保留环境、来源和验证范围。

用户于2026-11-09要求将[blender-video-workflows](https://github.com/modengsir/blender-video-workflows)接入本项目，并优先使用本机Blender处理三维与白模需求。

## 已接入的入口

| 本轮目标 | 入口与执行方式 |
|---|---|
| 按文字/已确认分镜做白模、三维场景、动画或修改工程 | [blender-video-original](../../.agents/skills/blender-video-original/SKILL.md)，优先本机Blender |
| 根据原视频重建/修正可编辑三维白模 | [blender-video-recreate](../../.agents/skills/blender-video-recreate/SKILL.md)，实看原片再制作/对比 |
| 已有其他工具生成的白模，换成自己的人物与场景 | [video-retargeting](../../.agents/skills/video-retargeting/SKILL.md)，无需先重建Blender工程 |

自然语言即可触发，不需要用户每次输入技能名称。两套新技能允许自动发现，项目唯一职责路由见[skill-routing.md](../skill-routing.md)。

本机程序为`D:\blender-5.3.0\blender.exe`。适合本地建模、骨骼/约束、动画、摄影机与空间预演、白模渲染、已有`.blend`修改，以及已建场景的深度/法线/遮罩输出。默认由助手用Blender Python后台操作；需要界面审视时再用可用Computer Use工具。

已有白模→实际检查→绑定选定人物图、场景图→`autodl-aigc`核实titim→按已明确要求提交。人物/场景映射和API槽位按真实能力处理，不虚构独立场景字段。保留源片、音轨、旧版与任务来源。仅要求工程/白模/提示词时就在该阶段交付。

## 来源与适配

- 固定上游[提交8dbcdc4](https://github.com/modengsir/blender-video-workflows/commit/8dbcdc4b7d1f1d8b701e8de6e9258b63d63a5afb)，完整11个文件保存在`.agents/resources/blender-video-workflows/`，`SOURCE.json`记录原始Git blob哈希，MIT许可及版权保留。
- `.agents/skills/`中的两个入口为本地适配版，保留三维白模制作、动作接触检查与可编辑工程交付，接续本项目人物/场景替换。
- 不沿用上游自动科幻风、固定8秒、缓慢运镜/末尾停顿、默认追加付费重试或默认助手逐段审查模型成片。项目文案确认、英文模型提示词与二次审计、素材中文名及一次提交规则继续适用。
- 新白模优先本机Blender；`huashu-seedance`保留明确指定的旧scene.json/照片拟合流程，不强制迁移旧工程。
- 上游是工作流指令，不包含Blender插件、预制人体骨骼库或自动动捕模型。其他工具生成的白模外观视频不自动变成可编辑三维工程，单目重建的遮挡/隐藏结构仍需估计。

## 2026-11-09实际验证

- 本机`--version`：`Blender 5.3.0 Release Candidate`，构建哈希`f78a5e153839`。
- 后台`bpy`执行成功；插入并求值两帧位置关键帧；保存中文名`.blend`后重新打开，动画值正确。
- 用`BLENDER_EEVEE`实际渲染96×64 PNG成功，文件非空。验证在临时目录进行并自动清理，未修改用户配置或已有工程。
- 两个新技能和本次调整的huashu-seedance、video-retargeting、short-drama-workflow均通过官方`quick_validate.py`。Windows需以Python的`-X utf8`运行，避免系统GBK解码中文UTF-8技能文件失败。

这些验证证明本机后台建场景、关键帧、工程读写与基础渲染可用。本次未制作具体作品、未提交收费视频，也未将复杂动作或完整AI换角链路标为端到端验收通过。

## VLM方法融合（2026-11-10）

后续制作范围已按用户2026-11-10的圆柱方案选择收窄为简单几何占位，具体见 [共享规范](../工作流/白模制作与验收.md)。本页下述Rigify可探测等是能力/来源记录，不是精细建模或骨骼动画的默认许可；圆柱代理平移用于给模型提供路径，不声称等于真实身体动作。摄影由storyboard-camera设计、Blender实际落实，纯色可区分主体；通用送模工具当前仍为灰度分支，能力与规则偏好分开记录。

- 审计固定版本 `7ohnson/VLM-Generation-Harness@2c64ed4ddcbc6f002e3afd15c7c7492ddd0ae0ca`。24份必要文本文件存入 `.agents/resources/vlm-generation-harness/`，保留MIT许可；`SOURCE.json`记录每个文件的Git blob SHA-1及SHA-256，未复制演示媒体。原文不是可调用技能，也不被运行时import。
- 吸收输入职责、统一时间轴、先测量后渲染、双版本预览、独立重建及按症状排错。运行代码在 `tools/视频工具/白模.py`、`whitebox_core.py`、`whitebox_blender.py` 维护；现有两个技能共享规范。
- 修正上游切点重复匹配/附近多切漏报、忽略解码失败、按名称漏掉墙体/误算隐藏对象等问题。使用实际相机与求值后网格，不用固定36mm/16:9公式当任意工程的实测。
- 不沿用中文关键词检查、固定15节长prompt、超过6秒必拆、30秒通用上限、默认付费重试或静态人形平移替代连续动作。角色结构、原片动作、英文提示词、titim简短映射及声音规则继续服从当前项目。
- 本机5.3 RC已探测到Rigify模块，可设置Workbench与EEVEE。无需新增MCP或插件；MCP若未来确有交互需要，再按实际授权和配置评估。当前不修改用户偏好。
- 详细审计取舍见 [融合记录](../维护记录/VLM白模融合审计-20261110.md)；本地技术验证与生成模型效果严格分开。
