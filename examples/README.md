# 示例配置

这些是接口配置示例，不是生成授权，也不是已完成审计的作品方案。普通 MJ 图片由用户在官网手动生成；不启动 Discord 代理或执行 `mj run/change`。

先使用 `autodl models show WORKFLOW_ID` 阅读模型说明，准备素材，再运行 `autodl validate 配置路径`。
模型提示词正文统一英文；作品对白保留原语言，说明、素材路径及文件名使用中文，API 枚举保持原值。
生成前按当前作品完成素材确认、剧本与提示词审计。没有明确预算时省略 `max_cost_cny`；有上限时才填写或传 `--max-cost`。

首次使用这些通用示例时，在仓库根目录执行以下本地初始化；已有
`projects/工具验证/project.yaml` 时跳过。作品目录不随 Git 提供，校验不会自动创建入口。

```powershell
.\.venv\Scripts\python.exe tools/项目.py init 工具验证
autodl validate examples/text-to-video.yaml
```

| 配置 | 用途 | 需要准备的素材 |
|---|---|---|
| `text-to-video.yaml` | 1 秒文生视频样片 | 无 |
| `image-to-video.yaml` | u24 参考图生视频 | `人物/参考图片.png` |
| `images-audio-to-video.yaml` | u24 人物对白与音色参考 | `人物/参考图片.png`、`音频/参考音频.wav` |
| `first-last-frame.yaml` | 专用首尾帧过渡 | `衔接图/起始帧.png`、`衔接图/结束帧.png` |
| `motion-transfer.yaml` | Wan 专用动作迁移示例 | `人物/参考图片.png`、`参考原片/参考视频.mp4` |
| `character-replacement.yaml` | titim 单角色替换 | `人物/主角.png`、`参考原片/引导视频-原音轨.mp4` |
| `multi-character-replacement.yaml` | titim 多角色替换 | 两张人物图、`参考原片/引导视频-原音轨.mp4` |
| `text-to-speech.yaml` | 已有音色样本的语音生成 | `音频/参考音频.wav` |

表中素材路径均相对 `projects/工具验证/02-素材/`；示例 YAML 位于 `examples/`，因此写成 `../projects/工具验证/02-素材/...`。
用于真实作品时，将配置放到该作品的 `03-制作/生成配置/`，素材放在同作品 `02-素材/` 并更新相对路径。
作品配置可省略 `output_dir`，默认输出到该作品的 `04-输出/原始片段/<配置名>`；不能输出到另一作品或根 `outputs`。
也可以直接填写可公开访问的 HTTP(S) 素材 URL，或 MIME 正确的 Base64 data URL。
其余参数和费用以实时工作流信息为准。除文本样片外，其余示例需要自己的素材才能执行。

创建其他工作流的配置：

```powershell
autodl models template minimax_h3_zm_titim --output projects/我的作品/03-制作/生成配置/动作迁移.yaml
```

先创建作品的 `project.yaml`。模板按输出配置的位置生成同作品素材占位路径；占位文件不能作为已就绪素材。
多图中的角色关联、音频引用等提示词语法因工作流而异，查看目录中的 `instructions` 原始说明；提交前按实时规则校验。
白模换角默认 titim，普通参考图原创默认 u24；首尾帧和上述 Wan 示例展示专用接口，不自动替换当前作品已选路线。

仅当前剧本需要人物说话时准备已试听确认的声音样本；无台词或只有呼吸、吼声不要求配声。u24 音频参考不是结构化说话人 ID，也不保证精确复述音频；示例显式写出台词，正式作品替换为已确认对白，并绑定人物 ID 和音频哈希。IndexTTS2 的 `prompt_simple`需要已有样本，不能输入图片或音色文字。
新原创生成仅包含已确认对白，无对白镜头静音；不生成背景音乐、歌曲、哼唱或音乐点缀。后期音乐按完整剪辑时间线独立处理。声音规则见[人物与声音流程](../docs/工作流/character-voice.md)。

原片换角与动作迁移默认保留原音轨；明确要求静音时，先核对接口是否需要可提取的静音音轨，不例行移除音频流。见[视频换角工作流](../docs/工作流/video-retargeting.md)。H3 替换专用工作流使用简单主体映射，不套普通 H3 六段式。
短剧生产配置另外绑定 `materials_manifest`/`shot_id`；新清单使用 schema 2，人物音色参考路线按文档增加 `voice_policy`，不能移除绑定绕过素材或声音门槛。MJ 当前入口见[手动流程](../docs/工具与接口/midjourney-local.md)。
