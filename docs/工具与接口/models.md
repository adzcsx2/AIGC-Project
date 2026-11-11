# AutoDL 工作流目录

同步时间：2026-11-07T08:22:05+00:00

由 `autodl models sync` 生成。参数以 `catalog/workflows.yaml` 的 input_rules 为准。
价格和目录接口属于网页使用的接口，平台调整时可能需要更新适配。

| 工作流 ID | 名称 | 分类 | 必填项 |
|---|---|---|---|
| `indextts2-v1` | indextts2 | text-to-speech | emo_control_method, prompt_simple, prompt_text |
| `minimax_h3_801` | H3九图15s(无字幕版) | reference-to-video | prompt, ref_image_0 |
| `minimax_h3_802` | H3九图15s(画质增强版) | reference-to-video | prompt |
| `minimax_h3_803` | H3九图三音15s(画质增强版) | reference-to-video | prompt |
| `minimax_h3_804` | H3九图15s(多模式版) | reference-to-video | prompt |
| `minimax_h3_805` | H3九图三音15s(多模式版) | reference-to-video | prompt |
| `minimax_h3_b99_001` | H3文生视频 | text-to-video | prompt |
| `minimax_h3_b99_002` | H3首尾帧生成视频 | first-last-frame | first_frame, last_frame, prompt |
| `minimax_h3_b99_003_12s` | H3多图生视频12秒 | reference-to-video | prompt, ref_image_0 |
| `minimax_h3_image_audio_to_video` | H3图生视频-音频同步(自动对口型) | lip-sync | ref_audio_0, ref_image_0 |
| `minimax_h3_image_audio_to_video_v2` | H3多图多音频生视频 | reference-to-video | prompt |
| `minimax_h3_image_audio_to_video_v2_15s` | H3多图多音频生视频15秒 | reference-to-video | prompt |
| `minimax_h3_lightx2v` | H3首尾帧生成视频 | first-last-frame | first_frame, last_frame, prompt |
| `minimax_h3_lightx2v_no_pic` | H3文生视频 | text-to-video | prompt |
| `minimax_h3_lightx2v_v5` | H3多图参考生视频 | reference-to-video | prompt, ref_image_0 |
| `minimax_h3_lightx2v_v5_15s` | H3多图生视频15秒 | reference-to-video | prompt, ref_image_0 |
| `minimax_h3_z0901` | H3文生视频（高质量创意直出） | text-to-video | prompt |
| `minimax_h3_z0902` | H3六图生视频（多图一致性创作） | reference-to-video | prompt, ref_image_0 |
| `minimax_h3_z0903` | H3六图三音频生视频（高质量音画融合） | reference-to-video | prompt, ref_audio_0, ref_image_0 |
| `minimax_h3_zm_nono` | H3多图多音频生视频(影视画质) | reference-to-video | prompt, ref_image_0 |
| `minimax_h3_zm_titi` | H3全自动角色动迁替换 | motion-transfer | ref_image, ref_video |
| `minimax_h3_zm_titim` | H3全自动多角色动迁替换 | motion-transfer | ref_image_0, ref_video |
| `minimax_h3_zm_u08` | H3多图多音频生视频(高速版) | reference-to-video | prompt, ref_image_0 |
| `minimax_h3_zm_u22` | H3多图多音频生视频(短剧带货版) | reference-to-video | prompt, ref_image_0 |
| `minimax_h3_zm_u24` | H3多图多音频生视频(升级画质) | reference-to-video | prompt, ref_image_0 |
| `minimax_h3_zm_u30` | H3多图多音频生视频(超清画质) | reference-to-video | prompt, ref_image_0 |
| `wan2.2animate-v4-motion_retargeting` | 动作迁移 | motion-transfer | ref_image, ref_video |

查看单个工作流的参数、选项和使用说明：

```powershell
autodl models show minimax_h3_lightx2v_no_pic
```
