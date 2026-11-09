---
name: short-drama-workflow
description: 本项目短剧与视频创作的总导演入口，接收故事、文案或打斗想法，补全文案并取得确认，再调度分镜运镜审计、视觉素材、英文提示词及AutoDL制作；需要跨阶段创作或整理缺口时默认使用。
---

# 总导演流程

先读根目录 `AGENTS.md` 与 `docs/director-workflow.md`；清单与命令见 `docs/short-drama-workflow.md`。
所有路径相对项目根。这里负责阶段交接，具体摄影、资产、API各只有一个入口。

1. 查当前作品的用户需求、已确认文案和已有素材，区分原创与源片复刻；有源片交 `video-retargeting`。
2. 文案/动作不足时先主动写中文补全稿，保留用户人物、意图、结果和风格；打斗交 `fight-scene-design`。
   写清新增细节、时长与真实缺口，先取得用户确认，再开始正式分镜/提示词/制作。
   不边等确认边制作；完整明确或已确认版本不重复问。确认元数据见新schema 2清单。
3. 确认后 `storyboard-camera` 自动拆镜、逐小段选镜并审计整体多样性。动作/摄影必须可读、连续。
4. `visual-assets` 检查资产与缺口，按镜头准备英文图片提示词；多视角板走 `character-reference-board`。
   需用户补充时给用途、影响镜段、提示词、中文保存名；素材全部真实就绪才进入视频。
5. `storyboard-camera` 编写并二次审计英文视频提示词，`autodl-aigc` 校验配置、按已授权范围执行与恢复。
   白模→titim，非白模→u24；u24不读取参考视频，依赖该能力时先说明缺口。
6. 实看返回图/视频，用户确认节点通过后同轮归档与推进；条件齐全的多图提示词批量交付。
   未授权视频重抽、新剧情或工具变更不自动进行。

## 按需取内部资料

- `.agents/resources/skills/short-drama-develop/references/`：短故事结构与时间容量。
- `.agents/resources/skills/short-drama-write/references/`：场次、戏剧动作和对白；正文拥有权是 `剧本.md`。
- `.agents/resources/skills/short-drama/`：原项目管理脚本与模板仍可用；初始化时显式指定英文prompt_language。
- `.agents/resources/acheng-director/references/11-story-architecture.md`、`10-scriptwriter-engine.md`：故事推进。
- `.agents/resources/acheng-director/references/80-continuity-ledger.md`：状态和因果。
- `.agents/resources/skills/short-drama-review/references/`：按当前阶段自动审计；不读完整资料包才开始。

内部源文件的旧语言/工具/强制版式不覆盖本项目。五份Markdown为创作正文，materials为状态绑定；
Acheng production.json只从已确认文档派生，不能形成双份互相冲突的剧本。
本技能无需白模；可选白模空间/摄影预演交 `huashu-seedance`，不承诺任意复杂动作自动建模。
