# 内部资料层

此目录不作为日常技能发现入口；可调用入口统一在 `.agents/skills/` 的9个技能。
当前规则见根 `AGENTS.md`、`docs/director-workflow.md`，来源见 `docs/installed-skills.yaml`。

- `acheng-director/`：固定提交完整原文、脚本、模板、132个视频与许可，保持上游原样。
- `skills/`：12个重复入口及其脚本、模板与参考，已转为内部按需资料，相对链接随迁移修复。
  旧SKILL里的中文提示词、提供商、审批和制作流程只是历史，不再作为当前调度入口。
  脚本依赖同目录资源，不能仅复制脚本而遗漏assets/references。

来源文档保留原语言，新交付正文遵守当前英文提示词规则。
完整重组前备份在 `docs/archive/技能重组-20261109-实施前/`，该目录及大型媒体按gitignore保存在本机。
