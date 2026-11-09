---
name: storyboard-camera
description: 把已确认的故事或动作稿拆成连续分镜，逐小段选择并审计运镜，检查全片节奏、空间连续性与镜头变化，交付适合实际MiniMax入口的英文视频提示词。用于分镜、运镜选择、镜头审计和视频提示词定稿；原片复刻保留源镜头。
---

# 分镜与摄影

先读 `AGENTS.md` 和 `docs/director-workflow.md`（路径均相对项目根）。文案缺动作/因果时先交
`fight-scene-design`或`short-drama-workflow`补全并让用户确认，不提前写最终分镜和提示词。

## 拆镜与选择

1. 按叙事信息、动作相位和时长拆小段，记录段首/段尾位置、朝向、运动趋势、接触、道具、伤势、环境。
2. 选景别、机位高度、焦段倾向、镜头路径/速度/目标和焦点；说明此段要看清什么、为何适合这个运镜。
   有真正取舍时列替代方案和舍弃原因，避免只堆“震撼、电影感”。每段一个主导摄影意图。
3. 从 [摄影选择表](references/运镜选择与审计.md) 定位真实示范；必要时观看相关示范而非一次加载132段。
4. 审计全片是否长期同侧、同景别、同速度或每镜都环绕；服务叙事地改变远近、高低、方向和前后景。
   静止镜头可用于让关键接触可读；不为凑数量强行切镜或牺牲轴线、距离闭合。
5. 写入 `分镜.md`，采用 `templates/short-drama/运镜审计.md`。逐段通过之后，再检查整体节奏与总时长。
   原创15秒连续戏份可含内部机位变化，但不拆成多段静态首帧短视频；源片复刻不添加新镜头。

## 模型提示词

- 全部新提示词用英文，中文需求自动译入；台词/字幕保持作品指定语言，协议引用标记不翻译。
- 无白模原创用u24，按实际图序绑定；参考内部 `short-drama-video-prompts/references/minimax-h3.md` 和
  Acheng `references/70-minimax-h3-compiler.md`、`111-h3-final-format-pass-v4.md`，不是全部无差别套模板。
- 白模用titim，保留源片，省略prompt或只写简短英文主体映射/必要动作例外；不套长H3分段格式。
- 上游2200–2900词不等于接口限制；由 `autodl-aigc` 校验真实字符上限、时长与媒体槽位。
- 写前实际看参考；写后再审计角色朝向/左右手、攻击启动与反馈、持续伤势、光照、场景锚点、动作留白，
  清除冲突静态模板。逐段审计不能因写了“continuous”就通过。

## 按需阅读

内部源根为 `.agents/resources/`：
- `acheng-director/references/decisions/shots.md`、`20-storyboard-compiler.md`、`21-genre-camera-capacity.md`：镜头职责与容量。
- `acheng-director/references/80-continuity-ledger.md`：状态连续性。
- `skills/short-drama-storyboard/references/`：拆镜与执行字段；不采用碎片化生成默认。
- `skills/h3-storyboard/SKILL.md`：身体/关节动作表达；经验不是所有模型的禁令。
- `skills/short-drama-review/references/`：本阶段核查，自动执行，不要求用户另点“审计”。

缺图/设定交回总导演列最小缺口；摄影技能不自行调用生成API。
