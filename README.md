# AutoDL AIGC

Python + YAML 驱动 AutoDL ComfyUI 工作流，支持视频、语音生成及本地结果归档。

项目图片生成统一使用 Midjourney。每次图片或视频生成后先展示结果，
必须取得用户确认才能执行下一步；不自动放大、重抽、生成下一角色或继续视频。
用户直接要求本次生成即为该次授权，不重复确认同一请求。具体规则见 `AGENTS.md`。

## 安装

要求 Python 3.11+。本项目已经创建 `.venv`；在 PowerShell 中可直接调用虚拟环境的程序，
无需修改 PowerShell 执行策略：

```powershell
cd E:\AutoDL
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\autodl.exe models list
```

需要复现本次开发依赖版本时，可先执行
`.\.venv\Scripts\python.exe -m pip install -r requirements.lock`，再安装本项目。

以下示例的 `autodl` 均可替换为 `.\.venv\Scripts\autodl.exe`，或
`.\.venv\Scripts\python.exe -m autodl_video`。

## 密钥

读取优先级：环境变量 `AUTODL_API_KEY` / `AUTODL_APIKEY` / `AUTODL_TOKEN`，其次项目 `.env`。
支持标准 `AUTODL_API_KEY=...`、`autodl_apikey:...`（变量名不区分大小写），
也兼容一行裸 Token。解析不会修改 `.env`。
Token 必须属于 **ComfyUI 分组**；鉴权头是原始 `Authorization: Token`，不加 `Bearer`。
`.env`、素材目录 `assets/`、任务记录 `.autodl/` 和输出 `outputs/` 均被 Git 忽略。

`assets/` 下的目录、图片、视频、音频统一使用中文名称，可带数字编号及版本号，扩展名保留真实格式。
例如 `assets/双精灵对决/角色-银发法师-全身.png`、`assets/双精灵对决/视频/镜头01-双人对峙-版本01.mp4`。
模型 ID、API 字段和内部素材 ID 保留原值；具体约定见 `AGENTS.md`。

Midjourney 本机代理已通过 Discord 账号初始化、频道读取及 API 鉴权检查，
可用 Python `MidjourneyProject` 或 `autodl mj` 提交 YAML、选图、查询和恢复任务。
账号及连接配置按用户要求保存在根目录 `.env`，说明使用中文。
命令、限制与示例见 [Midjourney 本机接入](docs/midjourney-local.md)；实际出图尚未验证。

## 从 YAML 生成视频

```powershell
autodl run examples/text-to-video.yaml --dry-run
autodl run examples/text-to-video.yaml --max-cost 0.10
```

`run` 会真正提交收费任务；`validate` 和 `--dry-run` 只做离线校验，不联网、不读取 Token。
运行时先读取最新工作流规则和价格，再检查参数与预算，提交后保存 task_id，
轮询至完成并立即下载视频。URL 有有效期，勿只保存远程链接。

YAML 顶层字段：

| 字段 | 含义 |
|---|---|
| `workflow_id` | 必填，工作流 ID，不能仅使用显示名称 |
| `inputs` | 工作流的 API 参数；只将这部分作为 JSON Body 发送 |
| `output_dir` | 可选，默认 `outputs`，相对项目根目录 |
| `timeout` | 可选，等待秒数，默认 1800；超时不会取消远程任务 |
| `poll_interval` | 可选，查询间隔秒数，默认 3 |
| `max_cost_cny` | 可选，人民币预算，命令行 `--max-cost` 优先 |

`inputs` 的图片/音频/视频可以是 HTTP(S) URL、`data:MIME;base64,...`，或本地路径。
传给 `run` 或 Python `generate` 的配置路径相对当前工作目录，也可使用绝对路径。
**本地素材路径相对 YAML 所在目录**，也可使用 Windows 绝对路径；程序将文件转成带 MIME 的
Base64 data URL，仅随生成请求发送至 AutoDL，不需要额外图床。客户端单素材上限 100 MiB，
平台自身可能有更小限制。格式按各工作流的 `accept_types` 校验。

预算目前只支持可以按明确时长计算的 H3 工作流，使用公开价格较高的时段计算，货币单位为 CNY。
实际提交前重新获取价格；这是本地估算检查，平台没有提供服务端锁价/硬性费用上限字段。
按音频或输入视频长度计费的工作流无法仅凭配置可靠估价，指定预算时会拒绝提交。

## 全量模型目录及更新

```powershell
autodl models sync
autodl models sync --check
autodl models list --search 文生视频
autodl models list --search motion-transfer
autodl models show minimax_h3_lightx2v_no_pic
autodl models template indextts2-v1 --output examples/my-tts.yaml
```

`catalog/workflows.yaml` 保存全量模型和真实 `input_rules`、默认值、枚举、时长限制、
计费配置、输入/输出说明、原页面地址、更新时间和作者的使用说明；[简表](docs/models.md)方便浏览。
同步不需要 Token：读取网页使用的目录接口并逐一读取详情，全部成功后才原子替换目录。
失败不会清空旧目录。`--check` 只报告新增、变化和移除项，有差异返回 1，无差异返回 0。
同步刷新上游内容，自定义调用参数请放在 `examples/` 或自己的配置中。

生成模板会填写实际默认值和必填素材路径；先替换提示词并提供素材，再执行校验。
多图、音画融合、首尾帧、动作迁移和语音示例见 [examples](examples/README.md)。
工作流同名也可能参数不同，始终按 ID 查阅。模型名称的“12 秒”等文字有时与
`input_rules` 不一致；校验依据服务端规则，并在需要时核对详情说明。

## 中断恢复

```powershell
autodl run examples/text-to-video.yaml --no-wait --max-cost 0.10
autodl task list
autodl task status TASK_ID
autodl task wait TASK_ID --timeout 1800
autodl task download TASK_ID --output-dir outputs/recovered
```

生成请求只发送一次。网络错误、服务器错误或无法解析的提交响应可能意味着任务已经创建，
程序不会自动重发 POST。此时查看 `.autodl/attempts/` 和 AutoDL「调用日志」；取得 task_id 后
使用 `task wait`，不要直接重新 `run`。有 task_id 的记录保存在 `.autodl/tasks/`。
轮询和下载可以重新执行，不会创建新生成任务。下载失败时 `task download` 会重新查询结果 URL。

成功状态兼容 `SUCCESS` / `completed` / `SUCCEEDED`；排队与执行有超时退出，失败会明确报错。
下载使用独立无鉴权客户端，Token 不会发送至结果 CDN；文件流式落盘，空文件或错误文档会被拒绝。

## Python 调用

```python
from autodl_video import VideoProject

project = VideoProject(r"E:\AutoDL")
preview = project.generate("examples/text-to-video.yaml", dry_run=True)
print(preview)

# 真正提交任务：
result = project.generate("examples/text-to-video.yaml", max_cost_cny="0.10")
print(result["task_id"], result["files"])
```

底层客户端也可独立使用，适合接入自己的分镜或批处理程序：

```python
from pathlib import Path
from autodl_video import AutoDLClient
from autodl_video.config import load_token
from autodl_video.storage import download_results

with AutoDLClient(load_token(Path(r"E:\AutoDL"))) as client:
    task = client.submit(
        "minimax_h3_lightx2v_no_pic",
        {"prompt": "一只橘猫走过雨后的街道", "duration": 1, "resolution": "480p横"},
    )
    # 立即保存 task["task_id"]；底层接口不提供 YAML 校验和预算检查。
    completed = client.wait(task["task_id"])
    paths = download_results(completed, Path("outputs"))
```

模型推理在 AutoDL 执行，本机不需要 GPU 或 ComfyUI。本项目集成的是指定页面的工作流 API；
多段长视频可分别配置镜头生成，剪辑、配乐和拼接不属于这些工作流的统一 API。

## 项目 skill

`.agents/skills/autodl-aigc/SKILL.md` 提供模型选择、更新目录、编写配置、生成和恢复的操作指导。
在此项目里可以直接提问“哪个模型支持首尾帧”“更新模型目录”“帮我用参考图生成视频”。
项目 `AGENTS.md` 要求回答参数和价格时查阅目录，不依赖记忆猜测。

已安装 [martial-arts-director-cy 武术指导技能](.agents/skills/martial-arts-director-cy/SKILL.md)，
用于打斗戏动作编排、人物锚定、多宫格分镜及配套视频提示词。
可以直接说“用武术指导 skill，给这张角色图设计一段雨夜打斗戏”。
与 Midjourney 和 AutoDL 的配合方式见 [打斗戏工作流](docs/fight-scenes.md)。

## 短剧制作工作流

已按 [Awesome Short Drama Skills 索引](https://github.com/UnderleveledBuilder/awesome-short-drama-skills)
安装实际源仓库的 12 项技能，并增加本项目的 `$short-drama-workflow`、`$video-retargeting` 衔接技能。
现在可以直接说“按这段提示词的画风设计我的角色”“把这个想法写成剧本和分镜”。
缺角色图、场景图或关键帧时会列出补图清单和 Midjourney 提示词；你补齐图片后才进入 MiniMax 视频生成。
完整流程、清单检查和 YAML 用法见 [短剧工作流](docs/short-drama-workflow.md)，
安装来源与取舍见 [技能分析](docs/short-drama-skills-analysis.md)。

原视频去音轨、截片、用自己的角色替换原片人物或迁移动作，使用
[视频换角工作流](docs/video-retargeting.md)。已补装原片拆镜与白模预演引擎；
任意原片到深度或3D动捕目前没有部署执行端，详情见该文的能力表。

```powershell
.\.venv\Scripts\python.exe -m autodl_video materials check projects/我的短剧/剧集/EP001/materials.yaml
```

## 开发验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=autodl_video --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip_audit
```

测试使用模拟 HTTP，不消耗额度。真实样片记录见 [验证记录](docs/verification.md)。

来源：[工作流页面](https://autodl.art/large-model/comfyui)、
[官方 API 文档](https://autodl.art/docs/comfyui_api/)。
目录列表和详情是网页使用的接口，生成/查询接口则见官方文档；平台变更时需更新本项目适配。
各端点、状态及错误约定见 [API 适配说明](docs/api.md)。
