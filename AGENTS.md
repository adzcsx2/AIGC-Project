# AutoDL AIGC 项目

这是 Python + YAML 的 AutoDL ComfyUI 集成项目。先读 `README.md`。

- 对 AutoDL 模型选择、参数解释、目录更新和生成请求，使用
  `.agents/skills/autodl-aigc/SKILL.md`；不要凭记忆编造工作流 ID 或参数。
- 项目入口为 `.venv/Scripts/python.exe -m autodl_video`（Windows）或安装后的 `autodl`。
- `catalog/workflows.yaml` 是上游工作流规则及说明的本地快照，使用 `models sync` 更新，
  不直接手改生成目录。查询价格/最新模型时先同步或读取对应公开详情。
- `.env` 及环境变量中的 Token 不得输出、写入示例、提交 Git 或发送给结果下载域名。
  保留用户现有 `.env` 格式；只在内存中兼容裸 Token。
- `run` 会提交收费任务。执行用户授权的模型、用途和预算；无生成授权时使用 dry-run。
  样片初始化时的一次性授权不延伸到未来的其他生成任务。
- 生成 POST 不自动重试；不确定是否创建任务时查 `.autodl/attempts/` 和平台调用日志。
  已有 task_id 使用 `task wait/download` 恢复，不重新生成。
- 自定义输入放在单独的 YAML 配置里。素材相对 YAML 目录，输出相对项目目录。
- 修改客户端、动态 schema、计费或恢复逻辑时，运行对应模拟 HTTP 测试和 ruff。
  提交前运行完整 pytest、pip-audit，并检查 Git 中没有密钥。
- 本仓库只建立本地 Git；远程创建、推送和发布需要用户明确要求。
