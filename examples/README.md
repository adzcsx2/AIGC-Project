# 示例配置

先使用 `autodl models show WORKFLOW_ID` 阅读模型说明，准备素材，再运行 `autodl validate 配置路径`。

| 配置 | 用途 | 需要准备的素材 |
|---|---|---|
| `text-to-video.yaml` | 1 秒文生视频样片 | 无 |
| `image-to-video.yaml` | 参考图生视频 | `assets/reference.png` |
| `images-audio-to-video.yaml` | 图片和音频协同生成 | `assets/reference.png`、`assets/voice.wav` |
| `first-last-frame.yaml` | 首尾帧过渡 | `assets/first.png`、`assets/last.png` |
| `motion-transfer.yaml` | 动作迁移 | `assets/reference.png`、`assets/reference.mp4` |
| `character-replacement.yaml` | H3 单角色替换 | `assets/characters/HERO.png`、`assets/reference-silent.mp4` |
| `multi-character-replacement.yaml` | H3 多角色替换 | 两张角色图、`assets/reference-silent.mp4` |
| `text-to-speech.yaml` | 参考音色语音生成 | `assets/voice.wav` |

素材路径相对 YAML 所在位置；以上示例位于 `examples/`，因此使用 `../assets/`。
也可以直接填写可公开访问的 HTTP(S) 素材 URL，或 MIME 正确的 Base64 data URL。
其余参数和费用以实时工作流信息为准。除文本样片外，其余示例需要自己的素材才能执行。

创建其他工作流的配置：

```powershell
autodl models template minimax_h3_zm_titim --output examples/my-motion.yaml
```

多图中的角色关联、音频引用等提示词语法因工作流而异，查看目录中的 `instructions` 原始说明。
支持多个音频不等于自动完成配乐剪辑；具体生成能力由对应工作流决定。

换角与去音轨见 [视频换角工作流](../docs/video-retargeting.md)。H3 替换专用工作流使用简单提示词，
不套普通 H3 六段式。短剧镜头另外绑定 materials_manifest/shot_id 并通过素材检查。
