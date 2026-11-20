---
name: blender-video-original
description: 使用本机Blender制作静态尺寸/空间构图图、实际摄影机及按明确要求制作的简单几何运动白模；静态图交visual-assets转绘写实参考。用于构图校准、原创白模或工程修改，不默认精细建模；参考视频重建走blender-video-recreate。
license: MIT
---

# 本机 Blender 原创白模

当前新视频统一u30多图，不制作/提交白模视频；尺寸/空间关键参考图允许先做[静态白模构图→写实参考图](../../../docs/工作流/白模制作与验收.md#静态白模构图图与写实参考图)，静态工程由blender-video-original承接。本技能的运动白模/视频驱动细节仅供历史任务或用户另定用途，不是当前新视频默认；不自动切回titim。

Whitebox input must follow the [model-only guide contract](../../../docs/工作流/白模制作与验收.md#model-demonstration-only-environment-from-reference-images): demonstrate simple models, scale/space/orientation, motion and camera on a blank neutral canvas. Supply environment/appearance through separate reference images; no scene image plane or frozen photographic actor in ref_video. Check evaluated world rotations, including the active rotation mode/channel.

先按 `docs/skill-routing.md` 和根目录 `AGENTS.md` 承接本轮交付与确认状态。新视频的尺寸/空间关键参考可按静态专节制作构图图；运动白模仅按历史或明确要求的工程范围执行；优先执行 `D:\blender-5.3.0\blender.exe`。只询问或只写剧本不自动制作。不要求用户自行建模、绑骨或运行脚本。

静态构图任务先执行[静态专节](../../../docs/工作流/白模制作与验收.md#静态白模构图图与写实参考图)：读角色尺寸/当前style与分镜，用少量头/躯干/四足体块和必要同尺度环境占位，落实相机与真实单位，保存工程、PNG及实际投影/支撑测量；先验证一张转绘后再复用。交visual-assets转换成写实参考，u30只接通过的成图和必要身份等；不强制创建动画、运动速度/双版MP4或ref_video，不把工程尺寸通过当成转绘/成片通过。以下编号中动态步骤只在实际运动白模任务适用。

1. 复用已有文案、动作、时长、画幅、角色/场景图及工程；需写/补/改剧情时先参考 `cinematic-script-audit`，再使用动作/运镜技能。文案或打斗不足先交中文补全稿确认；完整明确或已确认版本不重复问。只有图片参考也可原创，不据此虚构精确三维模型。
2. 需要设计动作时由 `fight-scene-design` 补攻防；每次白模任务承接 `storyboard-camera` 的机位/角度、镜头路径/速度、焦距/视场、目标和切镜设计，并落实实际摄影机控制；已有设计复用。跨阶段状态归 `short-drama-workflow`，仅改工程不重走导演全流程。
3. 读 [共享制作与验收](../../../docs/工作流/白模制作与验收.md)，用Blender Python后台制作；只用以圆柱为主的简单几何占位，可用稳定纯色区分人物/物体。制作比例、朝向、位移/升降、接触锚点和摄影机，不做精细身体、关节步态或面部；细节由真实参考和英文提示词交视频模型完成。作品使用 `03-制作/制作计划/白模计划.yaml`，由 `project.yaml.whitebox_plan` 引用；摄影镜头与生成请求分别登记，时间不在多处手填。创作正文继续使用已有分镜，不另建冲突剧本。
4. 保存工程及真实哈希后，用 `tools/视频工具/白模.py` 在独立进程检查、导出审片版和送模版，接现有网页审片；检查比例、路径/高度、接触关系、实际相机、摄影覆盖和连续性。颜色导出能力按共享规范核实，当前灰度工具不冒称彩色送模。程序通过不代表细节表演、动态/送模可读性或用户验收通过；遇到问题查 [故障排查](../../../docs/工作流/白模故障排查.md)。服从本次规格，不套上游固定8秒、实验舱、慢镜或停顿。
   另按共享规范的[速度与真实物理时间](../../../docs/工作流/白模制作与验收.md#速度与真实物理时间)检查阶段秒数、实际位移与速度/加速度趋势、顶点/接触及受力依据，原速查看实际送模版；不能只验尺寸/最高点或为凑片长套缓入缓出，速度/物理未通过不放行生成。
5. 仅要工程/白模时到此交付；已要求后续换人物/场景时读 [替换交接](references/video-generation.md)，接 `video-retargeting` 与 `autodl-aigc`。白模规划不代表所有接口都有ref_video；用于规划或直接送模分别记录。

来源：[modengsir/blender-video-workflows](https://github.com/modengsir/blender-video-workflows) 原创入口，已适配本机与项目规则；版本、原文、许可及验证范围见 [UPSTREAM.md](UPSTREAM.md)。
