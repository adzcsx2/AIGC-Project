# 验证记录

日期：2026-11-07（Asia/Taipei）。环境：Windows、Python 3.13.5。

| 检查 | 结果 |
|---|---|
| 真实公开目录同步 | 27 个工作流，逐一取得结构化 input_rules |
| 二次同步检查 | 无新增、移除或参数变化，`models sync --check` 退出 0 |
| 全量模板离线校验 | 27/27 通过；媒体占位路径替换为示例 URL，未提交推理 |
| 文生视频示例预览 | 通过，1 秒、480p 横屏，按最高时段估算 ¥0.04 |
| pytest | 96 项通过，整体覆盖率 88.59%（要求至少 80%） |
| ruff check / format | 通过 |
| skill-creator quick_validate | 通过（Windows 使用 Python `-X utf8`） |
| pip-audit | 未发现已知漏洞；仅升级了本项目虚拟环境的 pip |
| 真实样片生成 | 尚未通过：AutoDL 返回 HTTP 401 鉴权拒绝，未取得 task_id |

样片使用 `examples/text-to-video.yaml`，用户批准预算 ¥0.10。
返回错误为 `Invalid authentication credentials`；只读任务查询也返回同样的 401。
原始 Token 鉴权、Bearer 形式的只读诊断及同站 www 地址均不能通过，未改动用户 `.env`。
没有重试生成 POST，不能把本次鉴权拒绝当作已经验证了视频生成链路。

待本机 `.env` 更新为有效 ComfyUI 分组令牌后，在已授权范围内继续：

```powershell
.\.venv\Scripts\autodl.exe run examples/text-to-video.yaml --max-cost 0.10
```

若已得到 task_id 但等待中断，使用 `task wait TASK_ID`，不要重新提交。
实际生成、CDN 下载和视频可播放性的线上验收需要在有效凭证下完成。

自动化测试已覆盖：收费 POST 不重试、408/5xx/连接中断的状态不确定处理、
鉴权错误信息脱敏、离线模式不读密钥不联网、实时涨价拦截、YAML 类型/范围/格式、
任务状态与恢复、目录失败保留旧文件、下载跳转不带 Token、部分文件清理。
