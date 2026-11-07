# Midjourney 本机接入与 Python 调用

最新状态：首次法师定妆已真实提交一次，任务进入执行后 Discord 凭据无法继续通过鉴权
（连接关闭 4003，频道读取 HTTP 401）。本地结果尚未取回，等待用户更新凭据后恢复已有任务。
不要重复创建该任务；生成与确认记录见 `projects/elf-duel/剧集/EP001/生成确认.md`。

记录日期：2026-11-07。用户已提供官方 Bot 的 `/info`，Discord 已能识别有效的 Midjourney 会员。
账号信息及当时的额度快照已按用户要求保存到根目录 `.env`，使用中文注释，具体账号标识不写入本文件。
快照不是实时额度查询，也不是 API 凭据。Discord 用户凭据、服务器和文字频道 ID 已登记到本机 `.env`，
独立代理密钥已生成，Docker 代理已运行。只读联调确认：启动时有 1 个可用 Discord 账号，
带代理密钥查询返回 HTTP 200，不带密钥返回 HTTP 401；官方 Discord API 读取文字频道成功，
频道所属服务器与配置一致。具体账号与频道标识只保存在本机。
Python `MidjourneyClient` / `MidjourneyProject` 和 CLI `autodl mj` 已接入，
生成与恢复协议经过模拟测试，YAML 示例通过离线校验；首次真实创建请求已被接收，
但图片结果尚未取回，不能视为完成出图验收；新版参数兼容性也尚未全面验证。

## 先完成账号准备

1. 注册并验证自己的 Discord 账号。
2. 登录**已经付费的 Midjourney 官网账号**，进入 Account Settings → Connected Accounts，
   连接这个 Discord 账号。现有会员可用于官网和 Discord，无需再次购买订阅。
   若已有 Discord 账号曾生成过 MJ 图片，官网账号合并可能受限制；不要先创建第二份订阅。
3. 在 Discord 创建一个自己的服务器，例如「双精灵工坊」，建文字频道「素材生成」。
   这里的服务器是 Discord 内的工作空间，不需要租用云主机，也不需要部署 Discord 服务端。
4. 从 Midjourney 官方服务器的成员列表或 Discord App Directory 找到官方 Midjourney Bot，
   点 Add App，选择自己的服务器并授权。无需自己开发或注册一个替代 MJ 的 Bot。
5. 在「素材生成」里输入 `/info`，确认官方 Bot 能识别自己的订阅。
   这一步只检查账号信息，不需要用 `/imagine` 消耗生成额度。
6. Discord 用户设置 → Advanced → Developer Mode 开启后，
   右击服务器图标复制 Server ID，右击文字频道复制 Channel ID。
   可以把这两个数字 ID 告诉助手；账号密码和 Token 留在本机。

官方说明：[账号关联](https://docs.midjourney.com/hc/en-us/articles/33390994570509-Logging-In-Connecting-Accounts)、
[添加官方 Bot](https://docs.midjourney.com/hc/en-us/articles/32637946450445-Add-Midjourney-to-Your-Discord-Server)、
[Discord ID 获取](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID)、
[/info 等命令](https://docs.midjourney.com/hc/en-us/articles/32894521590669-Discord-Command-List)。

## 后端的最小范围

目标调用链：用户提出生图需求 → 助手操作本项目 Python → 本机 MJ 代理 → Discord/Midjourney。
自建 Discord 服务器本身不提供 MJ API 地址。代理接通后，本项目拟使用的地址是
`http://127.0.0.1:6013`，仅允许本机访问。

不需要部署 Dooy 的 Vue 网页、Node 中转或额外 FastAPI 服务。
Dooy/chatgpt-web-midjourney-proxy 的 MJ 部分依赖另一个 MJ_SERVER；
它的 `/mjapi` 路由只是转发，并不自行完成 Discord 接入。
本项目可直接调用底层代理的 `/mj/submit/imagine` 与 `/mj/task/{id}/fetch`。

部署使用 [novicezk/midjourney-proxy](https://github.com/novicezk/midjourney-proxy) 上游文档中的
`2.6.3` 镜像版本。这是非官方代理，依赖 **Discord 用户凭据**，不是自建 Bot Token；
官网订阅也不会提供这个代理的 API Key。
官方对未经许可的自动化有使用限制，关联 Discord 并不等于获得官方 API 授权。
当前已实测账号连接、频道访问和只读查询；出图及 V8/多图参考兼容性尚未实测。
本客户端通过 `base64Array` 上传普通图片提示，不等于 V8 编辑器的 Attach 身份绑定功能。

来源：[Docker 部署](https://github.com/novicezk/midjourney-proxy/blob/main/docs/docker-start.md)、
[配置字段](https://github.com/novicezk/midjourney-proxy/blob/main/docs/config.md)、
[API 协议](https://github.com/novicezk/midjourney-proxy/blob/main/docs/api.md)、
[MJ 使用规则](https://docs.midjourney.com/hc/en-us/articles/32013696484109-Community-Guidelines)。

## 本机配置与联调入口

配置统一保存在项目根目录 `.env`。用户已明确授权在原文件中增加 Midjourney 信息，
已有 AutoDL 内容保持原样；追加后验证了 AutoDL Token 的读取结果不变。
说明、套餐和状态使用中文注释，程序和 Docker 使用的变量名保留英文。
`deploy/midjourney/env.example` 列出连接字段；根目录 `.env` 已完成本机配置。
`MJ_SERVER` 为本机代理根地址，默认 `http://127.0.0.1:6013`。
本地 Python 只向代理发送 `mj-api-secret` 鉴权头；Discord 用户凭据由代理用于连接 Discord。
不得用空白模板覆盖原 `.env`，也不要把 `/info` 中的 UUID 当作服务器或频道的数字 ID。
根目录 `.env` 已被 Git 忽略，不提交其中的账号信息或凭据。
`MJ_API_SECRET` 是给本机代理设置的鉴权密钥，不是向 MJ 官网申请的密钥。

### 填写 Discord 用户凭据（仅本机）

上游的[参数获取说明](https://github.com/novicezk/midjourney-proxy/blob/main/docs/discord-params.md)
要求使用 Discord 网页请求中的用户鉴权值。

1. 在 Chrome 打开 Discord 网页版，登录已关联 Midjourney 的账号，进入自己的文字频道。
2. 按 `F12` 打开开发者工具，选择「网络 / Network」。
3. 刷新 Discord 页面，在网络面板筛选框输入 `messages`，选择对应的消息请求。
4. 打开「标头 / Headers」，在「请求标头 / Request Headers」找到 `authorization`。
5. 只复制它的值，填写到本机根目录 `.env` 的 `MJ_DISCORD_USER_TOKEN=` 后面。
   不复制字段名，也不添加 `Bearer` 前缀。凭据仅保存在本机，不粘贴到聊天里。
6. 保存文件后告诉助手「已填好」，再检查配置、启动代理并验证连接。

以上用户凭据不是 Midjourney `/info` 的用户 ID，也不是自己的 Discord Bot Token。

账号准备好并在本机完成配置后，助手可执行以下命令。用户不需要自己维护网站或操作后台。

```powershell
cd E:\AutoDL
# 只校验配置，不连接账号、不提交任务；--quiet 避免将展开后的凭据打印出来。
docker compose --env-file .env -f deploy/midjourney/compose.yaml config --quiet
# Docker 引擎运行后启动代理；建立 Discord 连接，不会自行发起生图。
docker compose --env-file .env -f deploy/midjourney/compose.yaml up -d
```

参数缺失时 Compose 会拒绝启动。不要直接执行不带 `--quiet` 的 `compose config` 并转贴输出，
展开后的配置含凭据。容器信息和日志也可能包含私人账号信息。

首次启动遇到镜像内旧版 Java 的 cgroup 探测崩溃，已在 Compose 中覆盖 `JAVA_OPTS`：
禁用自动容器探测，堆上限 512 MiB、容器内存上限 1 GiB、CPU 线程数按 2 配置，并移除默认远程 JMX。
此调整已通过容器运行和 HTTP 查询验证。参数含义参考
[Java 17 官方说明](https://docs.oracle.com/en/java/javase/17/docs/specs/man/java.html)。

## Python 和命令行

只读检查不会生图，离线校验也不读取任何密钥：

```powershell
.\.venv\Scripts\python.exe -m autodl_video mj doctor
.\.venv\Scripts\python.exe -m autodl_video mj validate examples/双精灵-法师生图.yaml
.\.venv\Scripts\python.exe -m autodl_video mj run examples/双精灵-法师生图.yaml --dry-run
```

`doctor` 验证本机 API 鉴权，不单独证明 Discord 实时在线；账号连接需结合初始化日志判断。
YAML 支持 `prompt`、`reference_images`、`output_dir`、`timeout`、`poll_interval`。
参考图片路径相对 YAML，图片可为 PNG/JPEG/WebP 本地文件或 Base64 data URL。
不接受普通图片 URL 填入 `reference_images`，因为该后端字段要求 Base64。
输出目录相对项目根目录，默认 `outputs/midjourney`；目录和素材说明使用中文。
这些字段名与协议键保持英文，供程序稳定读取。

下列创建命令会消耗会员额度，只在用户指定提示词、参考图片和次数后执行：

```powershell
# 每次 run 创建一条 imagine 任务；--no-wait 保存任务 ID 后返回。
.\.venv\Scripts\python.exe -m autodl_video mj run examples/双精灵-法师生图.yaml --no-wait
# 替换任务 ID；U1～U4 选图，V1～V4 变体，R 重新生成，均为额外任务。
.\.venv\Scripts\python.exe -m autodl_video mj change TASK_ID U2 --no-wait
```

查询和恢复只读已有任务，不重新提交：

```powershell
.\.venv\Scripts\python.exe -m autodl_video mj list
.\.venv\Scripts\python.exe -m autodl_video mj status TASK_ID
.\.venv\Scripts\python.exe -m autodl_video mj wait TASK_ID
.\.venv\Scripts\python.exe -m autodl_video mj download TASK_ID
```

任务记录位于 `.autodl/midjourney/tasks/`，创建尝试位于 `.autodl/midjourney/attempts/`。
提交 POST 只发送一次；网络错误、重定向、服务端错误或提交响应不明确时记录 `UNCERTAIN`，
先核对 Discord 历史，不自动重发。`state` 是关联标记，不是服务端幂等键。
结果下载使用独立、无鉴权的 HTTP 客户端，代理密钥不发送给图片 CDN。
原始文件留在 `outputs/`，审核后按中文名称归档至 `assets/双精灵对决/`；
不直接将任务 ID 文件名下载进 `assets/`。生成或放大不自动将素材标为 ready。

```python
from autodl_video import MidjourneyProject

project = MidjourneyProject(r"E:\AutoDL")
preview = project.generate("examples/双精灵-法师生图.yaml", dry_run=True)
print(preview)
# 用户授权后，移除 dry_run=True 才会提交生成。
```

会员分钟消耗没有在此代理的提交协议中提供可靠预估或硬性上限；本客户端不把它当作 AutoDL 人民币预算。
一次 run 不自动批量出图或继续 U/V/R，避免将选图和重抽隐含在同一次调用里。

当前模板使用上游默认内存任务存储，**重启代理会丢失其任务记录**。
运行期间保留任务 ID；中断后先核对 Discord 历史，不能因为查不到任务就自动重新生成。
本机客户端已保存任务 ID，但不能重建代理丢失的任务内容；
若需要代理重启后继续通过代理查询，可再启用上游支持的 Redis 持久化方案。

通过只读连接检查后，再按用户明确指定的提示词、参考图和生成数量做出图联调。
成图仍归档至 `assets/双精灵对决/`，沿用项目中文命名与视频阶段素材检查规则。
