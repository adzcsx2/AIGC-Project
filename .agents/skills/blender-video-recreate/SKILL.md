---
name: blender-video-recreate
description: 读取参考视频，用本机Blender以圆柱等简单几何重建比例、空间轨迹、接触时序及实际摄影机，交视频模型完成身体表演。用于复刻或修正白模，不做精细建模或自动动捕；已有合格白模直接换角走video-retargeting。
license: MIT
---

# 参考视频复刻三维白模

当前新视频统一u30多图，不制作/提交白模；见[当前导演规则](../../../docs/工作流/director-workflow.md#u30多图身份身高与完整同框规则)。本技能的白模/视频驱动细节仅供历史任务恢复或用户以后明确另定用途，不是当前新视频默认；不自动切回titim。

Whitebox input must follow the [model-only guide contract](../../../docs/工作流/白模制作与验收.md#model-demonstration-only-environment-from-reference-images): demonstrate simple models, scale/space/orientation, motion and camera on a blank neutral canvas. Supply environment/appearance through separate reference images; no scene image plane or frozen photographic actor in ref_video. Check evaluated world rotations, including the active rotation mode/channel.

新视频制作默认先做简单白模；按 [共享规范](../../../docs/工作流/白模制作与验收.md#默认先做白模) 区分合格已有白模复用、用户明确例外及纯文件处理。源片动作/摄影保留要求由预演对照验证，不为默认流程重做已认可旧片。

先读 `docs/skill-routing.md` 与根目录 `AGENTS.md`。源片可来自其他视频工具或用户已有视频；需三维复刻/修正时优先用 `D:\blender-5.3.0\blender.exe`。已有合格白模且只换人物、场景时，直接交 `video-retargeting`，不额外制作白模。

1. 实际读取原片，确定片段与需保留的动作、运镜、声音。链接不可读时尝试可用工具，仍不可读则说明具体缺口，不从标题编造动作。只借风格不走复刻。
2. 用 `short-drama-breakdown` 按需探测时长、帧率、画幅，抽首尾、接触、遮挡、出入画及运动代表帧。记录占比、朝向、左右手、路径、接触点、镜头及事件时间，区分观察与隐藏部分的估计。
3. 读 [本机制作](references/blender-production.md)，只用以圆柱为主的简单几何占位匹配主体比例、透视、布局、位移/高度及接触关系，可用稳定纯色区分主体；不恢复精细身体、骨骼步态或表情。承接 `storyboard-camera` 对原机位/角度、镜头路径/速度、焦距/视场、目标和切点的设计，做成实际摄影机控制，未知值注明估计。保持原切镜、节奏、因果与原声，不新增招式/镜头；参考与英文提示词承担自然身体表演。修正只在本次范围另存副本。
4. 按 [共享制作与验收](../../../docs/工作流/白模制作与验收.md) 建作品 `03-制作/制作计划/白模计划.yaml` 并由project.yaml引用，保留源片事件时间对应关系。保存工程和真实哈希后用 `tools/视频工具/白模.py` 独立重载检查、导出审片/送模两版；通过网页对比源片与完整预览，检查比例、方向、距离闭合、支撑接触、事件及运镜。实际证据记入 `05-检查与验收/`；静态采样不代表动态通过。问题按 [故障排查](../../../docs/工作流/白模故障排查.md) 定位。
   同时按[速度与真实物理时间](../../../docs/工作流/白模制作与验收.md#速度与真实物理时间)核对源片→白模的真实时钟、阶段速度/加速度和受力/接触；保留原片明确特殊速度，原创适配部分默认正常速度。实际送模版原速复核，不能凭几何/最高点通过或把短促动作拉满片长。
5. 输出真实可编辑 `.blend` 和合格白模视频。单目视频不能唯一恢复三维；本技能不自带动捕、相机反解模型或插件，不把灰度滤镜/二维合成称为三维重建。
6. 仅需白模时到此交付。已要求换角/场景时读 [替换交接](references/video-generation.md)，绑定用户选定人物、场景及真实白模，接 `video-retargeting` / `autodl-aigc`。保留源片、原声；模型视频技术检查和用户审片独立记录。

来源：[modengsir/blender-video-workflows](https://github.com/modengsir/blender-video-workflows) 复刻入口，已适配本机与项目规则；版本、原文、许可及验证范围见 [UPSTREAM.md](UPSTREAM.md)。
