# 原视频换角、动作迁移与白模/深度参考

本项目可以准备静音引导片，并通过已接入的 AutoDL 工作流，把自己的人物图用于原视频角色替换或动作迁移。
“先转白模/深度再重绘”需要区分具体控制信号；安装提示词技能本身不会部署深度模型。
在项目里直接说“用视频换角工作流”，或使用 `$video-retargeting`。

## 能力与接入状态

| 需求 | 实际能力 | 当前状态 |
|---|---|---|
| 去音轨、截片 | 本地 FFmpeg/ffprobe，新增 media inspect/prepare | 已实现，本地测试，不上传素材 |
| 原片切点、镜长、代表帧 | 新装 short-drama-breakdown，来自 zenstory-ai/drama-skills | 原脚本与参考完整安装 |
| 原片人物换成自己的角色 | 现有 H3 单/多角色替换 API | 公开参数与说明已核对，本次未做收费生成验收 |
| 自己角色模仿视频动作 | 现有 Wan 动作迁移 API | 已有示例与客户端支持，不保证原片背景不变 |
| 自搭白模、照片反解空间、控制运镜 | 新装 huashu-seedance，来自 alchaincyf/seedance-skill | 引擎与模板已安装，渲视频需 Hyperframes 和浏览器运行时 |
| 任意原片自动转白模外观视频 | 需要视频转绘后端和对应工作流 | 当前没有相应 AutoDL 工作流契约 |
| 原片自动恢复3D人体/相机再渲白模 | 需要动捕、人体/相机重建及3D渲染 | 不在所安装白模引擎的自动能力范围内 |
| 提取深度/骨架/遮罩后受控重绘 | 预处理模型 + 能消费该控制的视频模型 | 候选已核对，未部署深度推理/VACE 控制执行端 |

本次安装的是源仓库实际代码，保留原文、脚本、引擎、参考与模板，固定版本见各技能 UPSTREAM.md 和 installed-skills.yaml。
原有武术指导的白模部分负责动作设计、分解海报与提示词，不执行原片深度估计或动捕。

## 现有 API 换角路线

路径：**原片 → 查看与拆镜 → 去音轨副本 → 自己的角色图 → H3 换角 → 检查交付**。
不需要为了换人先制作白模或深度参考。

2026-11-07 读取了以下公开工作流详情，参数与计费规则均与现有目录一致：

| 工作流 | 必要输入 | 用途 |
|---|---|---|
| minimax_h3_zm_titi | ref_image、ref_video | 单角色替换 |
| minimax_h3_zm_titim | ref_image_0、ref_video；其余角色图按需 | 多角色替换，最多9张图 |
| wan2.2animate-v4-motion_retargeting | ref_image、ref_video | 动作迁移 |

来源：[H3 单角色详情](https://autodl.art/api/v1/comfyui/workflows/minimax_h3_zm_titi)、
[H3 多角色详情](https://autodl.art/api/v1/comfyui/workflows/minimax_h3_zm_titim)、
[Wan 动作迁移详情](https://autodl.art/api/v1/comfyui/workflows/wan2.2animate-v4-motion_retargeting)。

H3 替换当前声明 5–25 整秒、768p 横/竖。通常无需 prompt，需指定人物时用简短说明，
如“图1换左边穿黑甲的人，图2换右边的人，保留手中的剑”。
**替换专用工作流已内置提示词，不套普通 H3 六段式。**
多角色图依次对应 ref_image_0..8；未提供的可选字段省略，不复制平台的空白图默认值。
多人交叉、切镜、脸过小会影响识别；身份、动作、镜头和场景都需逐段检查。

上游检测类型的文字有冲突：正文说一次一种，文末又列逗号分隔多类别示例。
当前稳妥用一种明确英文类别，如 person。人物具体映射放 prompt，不把“左边的人”写成检测类别。
上游说明 H3 会保留引导片原声。只要动作时先去音轨；需要对白/口型时先决定声音方案。
无音轨输入不保证生成结果绝对无声，最终仍需检查，需要时再输出无声副本。
参考片短于输出时长时尾部可能自由发挥，不默认循环、变速、补帧或扩时。
画幅尽量与原片一致，横竖切换可能裁掉人物和关键物品。

```powershell
.\.venv\Scripts\python.exe -m autodl_video media inspect assets/source.mp4
# 去音轨，保留原视频，目标文件已存在时拒绝覆盖
.\.venv\Scripts\python.exe -m autodl_video media prepare assets/source.mp4 --output assets/reference-silent.mp4
# 第12秒起准确截5秒，截片重新编码
.\.venv\Scripts\python.exe -m autodl_video media prepare assets/source.mp4 --output assets/SHOT-01-silent.mp4 --start 12 --duration 5
# 填写自己的图和视频后离线校验
.\.venv\Scripts\python.exe -m autodl_video validate examples/character-replacement.yaml
```

另有 examples/multi-character-replacement.yaml；例中的时长、提示词和预算是演示值，不是付费授权。
正式运行前按实际片段和最新详情确定参数与预算。
Wan 按输入视频长度计费，当前客户端没有可靠预算估算；不能添加未声明的 duration/prompt/depth 字段。

短剧换角镜头沿用素材门槛，清单 assets 可增加：

```yaml
VIDEO-01:
  kind: video
  required: true
  path: assets/SHOT-01-silent.mp4
  state: provided
```

实际看完并确认正确后才改 ready。单角色镜头的 reference_bindings 例如
`{ref_image: CHAR-01, ref_video: VIDEO-01}`，字段、类型、文件必须与 YAML 一致。
没有脚本创作需求的独立换角不必伪造剧本，但仍先看素材、核对人物映射并 validate。
收费生成由现有客户端提交、保存 ID、轮询与下载。

## 白模、深度和姿态的区别

- 白模预演：简化几何与人物占位体表达空间、摄影机路径和节奏，新装引擎按 scene.json 设计。
- 白模外观转绘：让视频呈现无纹理白色人物的外观，通常是生成式编辑，不等于得到可编辑3D模型。
- 深度视频：每帧表达远近结构的估计，去色/灰度滤镜不具有这种含义。
- 姿态和遮罩：分别记录关节运动和重绘区域，仍需兼容的生成模型与输入契约。

核对过的官方候选：

- [Video Depth Anything](https://github.com/DepthAnything/Video-Depth-Anything)：视频深度估计，需其权重与推理依赖。
- [VACE](https://github.com/ali-vilab/VACE)：参考、视频转视频、遮罩编辑，需部署实际模型及预处理链路。
- [Wan Animate 预处理说明](https://github.com/Wan-Video/Wan2.2/blob/main/wan/modules/animate/preprocess/UserGuider.md)：
  animation 产出 face/pose，replacement 另有背景与遮罩；不代表所有任务都先转深度。

本次没有下载这些 GPU 模型，也没有把候选声明为可调用的 AutoDL 端点。
当前27个工作流没有独立 depth/pose/mask 控制参数，要闭合此路线需新的真实执行端。

## 白模技能边界

huashu-seedance 主要面向 Seedance 的参考视频与提示词，已安装引擎可在工作目录运行：

```powershell
node E:/AutoDL/.agents/skills/huashu-seedance/engine/probe.mjs scene.json
node E:/AutoDL/.agents/skills/huashu-seedance/engine/build.mjs scene.json
node E:/AutoDL/.agents/skills/huashu-seedance/engine/make_prompt.mjs scene.json
```

渲视频另需 hyperframes@0.7.107 和浏览器运行时，照片叠网格需 opencv-python。
引擎不能从任意实拍视频自动得到人体关节和场景。Seedance 的 @白模1 语法不是 H3 的 API 参数。
简化白模也不一定被 H3 的主体检测识别，不能承诺随意接入即可换角。
索引中的 VideoClaw 有云端动作迁移，但要另一套平台与供应商凭据；已有 AutoDL 可完成该任务，
这次用原片拆解和白模引擎补充能力，没有部署第二套视频平台。
