# 大师镜头原生多切编配

## 先约束，后切镜

每个外层镜号内部建立：

```yaml
MASTER_SHOTS_CONSTRAINT_PACKET:
  dramatic_goal: 本镜前后可观察的状态变化
  audience_viewpoint: 观众依附谁、知道多少、何时转移
  information_order: 必须依次看见的故事点
  relationship_change: 力量/关系的可见变化
  spatial_geography: 轴线、方向、距离、高低、入口出口和地标
  action_anchors: 起势、目标、接触/闪避、受力、恢复
  subject_and_attention: 每拍主体、牵引动作和注意力终点
  lens_distance_height: 景别、焦段、物理距离和高度约束
  camera_motion: 每个切镜的牵引、起点、终点和收益
  editing_interface: 动作、视线、形状、声桥或特效切点
  continuity: 人物、武器、伤势、光源、能力和环境限制
  selected_strategies: 0至3项
  hard_stops: 当前镜号禁止事项
  validation: 回放时必须读到的证据
```

再建立：

```yaml
INTERNAL_SHOT_COVERAGE_MAP:
  - shot: 1
    function: 空间/关系/攻击/接触证据/能力变化/反应/钩子之一
    information_gain: 本镜新增加什么
    physical_camera: 机位、距离、高度、焦段
    subject: 当前主体与目标点
    entrance_exit: 从何状态切入、以何状态切出
    dialogue_mode: SYNC/OS-CONTINUE/无
    vfx_phase: 当前阶段和跨镜遗留
```

没有新信息、表演或动作证据的内部镜头不进入覆盖图。

## 14个核心决策入口

根据问题选择1个主要决策，独立问题再补1—2个：

| 决策入口 | 管辖问题 |
|---|---|
| dramatic-goal-shot-chain | 戏剧变化到故事点与镜头链 |
| audience-viewpoint-control | 观众依附、知情差和视点转移 |
| distance-lens-height-relations | 距离、焦段、高度与权力关系 |
| subject-driven-camera-feedback | 演员动作触发摄影机启动停止 |
| movement-reveal-attention-transfer | 移动、揭示和注意力交接 |
| occlusion-delayed-reveal | 遮挡、威胁和延迟揭示 |
| depth-staging-relational-change | 纵深、站位与关系变化 |
| axis-spatial-continuity | 轴线、方向与空间连续 |
| visual-contrast-power-psychology | 力量和心理状态视觉化 |
| reaction-before-reveal | 反应先于答案或危险 |
| action-transition-editing-interface | 动作、遮挡、形状和切点接口 |
| low-budget-optical-illusion | 安全、预算与透视借位 |
| narrative-justified-camera-movement | 运镜动机、停止点与稀缺性 |
| rehearsal-playback-continuity-loop | 排练、焦点、走位与回放验证 |

若需要完整52技巧候选，完整读取同级可用的 `master-shots-orchestrator/references/MASTER_SHOTS_ROUTING_MATRIX.md`，只读取通过允许条件的0—3个技巧文件。不得因“对话、打斗、追逐、镜面”等场景名词直接选择同名技巧。

## 原生多镜高频策略

| 目标 | 常用候选 | 允许条件 |
|---|---|---|
| 快慢变化 | motion-pacing、editing-rhythm-control | 加速、冲击、停顿与恢复节点明确 |
| 删除重复覆盖 | cutting-economy、story-point-first | 故事点与必要动作已锁定 |
| 动作切点 | action-transition-editing-interface、seamless-transition | 尾态与首态有可验证动作/形状接口 |
| 演员牵引摄影机 | actor-driven-camera、camera-motion-motivation | 主体动作提供起止点 |
| 双向碰撞 | reverse-tension-motion | 相反方向运动在明确节点汇合 |
| 压迫与反转 | power-visualization、power-proximity | 面积、高度、距离或站位可比较 |
| 信息揭示 | attention-guidance、reaction-before-reveal | 注意力起点、终点和揭示时机明确 |
| 稀缺高潮 | scarcity-discipline | 已定义唯一高潮并限制其他镜头强度 |

异能＋玄幻场景可追加以下条件策略，但仅在原文存在对应能力时启用：

| 目标 | 可选策略 | 允许条件 |
|---|---|---|
| 展示法相体积 | 低机位仰拍、半环绕或受控orbit | 法相需要展示体积、遮挡、投影或与角色绑定；轴线和目标点可验证 |
| 展示能量生命周期 | 媒介特写、阶段匹配切 | 能量有明确征兆、聚集、释放、接触和遗留，不能跳段 |
| 展示兵器重量 | 侧向跟移、接触特写、材质反馈切 | 刃面核心、包裹、拖尾和环境反馈至少有可读证据 |
| 展示双层合击 | 全景换气→接触近景 | 角色与法相同步动作且主结果只有一个 |

最多3项且作用不能重复；基础机位已足够时允许零技巧。

## 真实切镜标准

相邻内部镜头至少改变以下一项并产生叙事收益：

- 物理机位或观察方向；
- 景别与主体尺度；
- 摄影机高度/角度；
- 焦段行为与空间关系；
- 观众视点或信息权限；
- 主体、目标点或动作证据。

只改变焦点、轻微摇移、同义改写或画面清晰区，不算真实切镜。相邻镜头的机位、景别、焦段、高度和功能全部相同时必须合并。

## 多镜覆盖顺序

战斗常用覆盖：

1. 空间或双人关系；
2. 攻击承诺和来向；
3. 武器/法术接触证据；
4. 能力或优势变化；
5. 身体、表情和环境受力；
6. 反转、追击或下一镜钩子。

根据剧情删减，不机械凑满最低六镜；战斗至少六镜，复杂但仍可读时可到11—12镜。一个内部镜头只承担一个主信息区和必要反应区。

## 机位与焦段

- 24—32mm：空间、群战、巨物和高速路线；
- 35—50mm：双人动作、走位和环境平衡；
- 65—85mm：表情、手势、武器接触和压缩隔离；
- 100mm以上：远距观察，必须保留方向参照。

焦段不能代替物理机位。高低角度必须有力量、关系或信息比较。高速跟拍在接触前停止或稳定；撞击只允许一次受控反馈；慢动作只用于唯一峰值。

## 轴线与切点

- 先建立画左/画右、中心线、目标点和地标；
- 越轴只有在中性机位、可见走位或关系秩序变化时允许；
- 切点优先落在挥击承诺、接触、受力、转身、遮挡、落地、视线或特效阶段变化；
- 台词跨镜优先使用自然停顿和关键词声桥，不让画面切点截断字音；
- 接触前的运动镜头必须在目标点可读前稳定；
- 每个内部镜头尾帧记录位置、姿态、视线、握持、武器轨迹、伤势、光源、特效阶段和运动趋势。

## 拆分回退

即使主交付为原生多镜，每个内部镜头也必须独立可生成：首帧继承清楚、单一主动作、明确尾态、方向一致、声轨片段唯一。第六节列出累计切点；平台失败时沿切点分别生成并按原顺序剪辑，不改动作、对白和镜头设计。

## 硬判停

出现以下情况退回更简单方案：技巧只能解释为“高级/电影感”；切镜没有信息增量；机位变化破坏轴线、口型、接触点或身份；同一效果有更简单覆盖；无法定义切入切出状态；6—12切同时叠加过多主体、动作和特效导致平台负载失控。
