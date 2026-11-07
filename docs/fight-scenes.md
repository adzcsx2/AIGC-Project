# 打斗戏工作流

短剧里的打斗戏通过 [短剧工作流](short-drama-workflow.md) 衔接：武指负责动作编排，
剧本分镜沿用统一角色与场景，缺少必要素材时先列 Midjourney 补图清单。
所有短剧镜头 YAML 带 materials_manifest/shot_id，素材检查通过后才进入 AutoDL 视频生成。

本项目已安装 [martial-arts-director-cy](../.agents/skills/martial-arts-director-cy/SKILL.md)。
来源为 [CY-CHENYUE/martial-arts-director-cy](https://github.com/CY-CHENYUE/martial-arts-director-cy)，
固定版本及许可见技能目录的 UPSTREAM.md 和 LICENSE。

## 如何使用

下一条消息起可以直接指定 `$martial-arts-director-cy`，也可以自然描述“武术指导”“打斗戏”
“武打分镜”“招式分解”。例如：

> 用武术指导 skill，为我的 Midjourney 角色图设计一段雨夜巷战。两名成年角色，
> 写实电影风格，徒手对打，15 秒。先给动作编排、分镜海报提示词和视频提示词，
> 再准备 AutoDL YAML。

可以提供角色图、武术流派、场景、对手、武器、画幅、时长和偏好的动作风格。
已有角色图时沿用人物与服装，按用户目标决定最终角色画面或白模预演。

## 与现有工具配合

1. **武术指导技能**：确定角色锚点、动作的起承转合、人物空间位置、镜头和节奏，
   输出分镜图提示词和配套视频提示词。它本身是文本策划技能。
2. **Midjourney**：用图像提示词制作人物图、关键帧或分镜海报，选定图片并保存本机。
   角色和场景图片由用户确定后作为视频输入。
3. **autodl-aigc 技能**：从真实工作流目录挑选模型，将视频提示词和素材路径填入 YAML，
   用 `validate` 或 `--dry-run` 检查参数和预算。
4. **视频生成**：在用户授权的模型、用途及预算内运行配置，保存 task_id、等待并下载结果。
   多段打斗可以逐镜头制作后剪辑；恢复等待不能重新提交生成任务。

可从 `examples/image-to-video.yaml`、`examples/images-audio-to-video.yaml`
或 `examples/first-last-frame.yaml` 起步。模型参数始终以 catalog/workflows.yaml
及运行前取得的实时 input_rules 为准，不能把技能里的时长建议直接当作所有模型的能力。

## 分镜海报与视频输入

上游技能提供将多宫格海报连同“参考图阅读协议”交给视频模型的方案。
这是一种提示词策略，不保证模型逐格完成所有动作、精确保留顺序或消除海报上的文字与网格。
需要更强控制时，可把分镜落实为若干独立镜头，每段集中在清楚的动作和运镜上，
提供对应角色/关键帧图片，再按镜头顺序剪辑。

本次仅安装技能并建立项目衔接，未创建或执行打斗戏生成任务。
