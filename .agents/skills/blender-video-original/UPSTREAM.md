# 来源与本地适配

- 上游：https://github.com/modengsir/blender-video-workflows
- 固定提交：`8dbcdc4b7d1f1d8b701e8de6e9258b63d63a5afb`
- 原路径：`skills/blender-video-original/`
- 许可：MIT；完整版权与条款见本目录 `LICENSE`。
- 未修改源码快照：`../../resources/blender-video-workflows/`（相对本技能目录），只作追溯，不是当前执行规则。
- 接入日期：2026-11-09。
- 本地适配：本机Blender优先；中文素材名、英文模型提示词与二次审计；复用文案确认；区分原视频/白模/三维工程；接续titim人物与场景参考；移除上游自动科幻风、固定8秒/慢运镜/末尾停顿、默认追加付费重试及默认助手成片创作审计。
- 验证：上游只有结构记录，未宣称端到端通过；本地结果见项目根目录 `docs/工具与接口/blender-integration.md`。

## 补充方法来源（2026-11-10）

VLM-Generation-Harness固定提交 `2c64ed4ddcbc6f002e3afd15c7c7492ddd0ae0ca`，MIT；原文和哈希见 `../../resources/vlm-generation-harness/SOURCE.json`。吸收空间/时间与参考职责、双版本预览、排错方法；执行以共享白模规范为准，不直接运行上游检查器。
