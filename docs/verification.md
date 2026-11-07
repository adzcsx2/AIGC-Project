# 验证记录

日期：2026-11-07（Asia/Taipei）。环境：Windows、Python 3.13.5。

| 检查 | 结果 |
|---|---|
| 真实公开目录同步 | 27 个工作流，逐一取得结构化 input_rules |
| 二次同步检查 | 无新增、移除或参数变化，`models sync --check` 退出 0 |
| 全量模板离线校验 | 27/27 通过；媒体占位路径替换为示例 URL，未提交推理 |
| 文生视频示例预览 | 通过，1 秒、480p 横屏，按最高时段估算 ¥0.04 |
| pytest | 101 项通过，整体覆盖率 88.69%（要求至少 80%） |
| ruff check / format | 通过 |
| skill-creator quick_validate | 通过（Windows 使用 Python `-X utf8`） |
| pip-audit | 未发现已知漏洞；仅升级了本项目虚拟环境的 pip |
| 真实样片生成 | 尚未通过：正确读取令牌后，只读接口返回 HTTP 403，缺少 ComfyUI 权限 |

样片使用 `examples/text-to-video.yaml`，用户批准预算 ¥0.10。
初次提交返回 `Invalid authentication credentials`（401）。后续定位到用户 `.env`
为 `autodl_apikey:...`，旧解析器错误地把整行作为 Token，已修正并加入格式回归测试。
目前支持大小写变量名、冒号、等号及一行裸 Token，始终不修改用户 `.env`。

修正后，通过正式 CLI 对全零任务 ID 做只读查询，返回 HTTP 403：
`This token does not have permission to access ComfyUI APIs`。
这是令牌缺少 ComfyUI API 权限，不能继续归因为密钥无效。
没有再次发送生成 POST，也没有取得 task_id；视频生成和下载链路尚未通过线上验收。

待本机 `.env` 更新为有效 ComfyUI 分组令牌后，在已授权范围内继续：

```powershell
.\.venv\Scripts\autodl.exe run examples/text-to-video.yaml --max-cost 0.10
```

若已得到 task_id 但等待中断，使用 `task wait TASK_ID`，不要重新提交。
实际生成、CDN 下载和视频可播放性的线上验收需要在有效凭证下完成。

自动化测试已覆盖：收费 POST 不重试、408/5xx/连接中断的状态不确定处理、
鉴权错误信息脱敏、离线模式不读密钥不联网、实时涨价拦截、YAML 类型/范围/格式、
任务状态与恢复、目录失败保留旧文件、下载跳转不带 Token、部分文件清理。
