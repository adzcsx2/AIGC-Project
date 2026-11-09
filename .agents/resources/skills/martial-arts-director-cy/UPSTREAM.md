# 来源与本项目安装记录

- 来源：https://github.com/CY-CHENYUE/martial-arts-director-cy
- 固定版本：`65c7c1dd35fcf4a01bfc1372ab506b60e2d0d26d`
- 安装日期：2026-11-07（Asia/Taipei）
- 许可：Apache-2.0，原始 LICENSE 随包保留。
- 安装位置：本项目 `.agents/resources/skills/martial-arts-director-cy/`，属于项目级技能。

使用 Codex 内置 skill-installer 的 install-skill-from-github.py，指定仓库根目录和以上版本安装。
原始 SKILL.md、README.md、references/ 及 LICENSE 保持原样。
本项目额外添加本文件和 agents/openai.yaml，项目衔接说明放在 docs/fight-scenes.md。
局部 .gitattributes 允许上游 SKILL.md 原有行尾空格，以保留其原始字节内容。

上游示例图、GIF 和 MP4 已随完整安装保存到 assets/。
它们服从项目既有的 assets/ 忽略规则，仅保留本地，避免将大体积示例媒体纳入 Git。
技能执行所需的四份 references 文档均纳入版本管理。

升级时先查看上游变更，在临时位置用安装器安装新版本，核对后更新上游文件及版本记录，
保留本项目的 agents/openai.yaml 和衔接说明；勿对已存在目标直接覆盖安装。
