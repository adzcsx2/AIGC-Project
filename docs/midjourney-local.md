# Midjourney 本机接入准备

记录日期：2026-11-07。当前只有 Midjourney 官网会员，用户正在创建并关联 Discord。
现有 Python/AutoDL 视频功能照常使用；本次只准备本地代理部署模板，没有新增 MJ Python 客户端，
没有登录 Discord、启动代理或提交生成任务。Docker 客户端已安装，检查时 Docker 引擎没有运行。

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

模板使用 [novicezk/midjourney-proxy](https://github.com/novicezk/midjourney-proxy) 上游文档中的
`2.6.3` 镜像版本。这是非官方代理，依赖 **Discord 用户凭据**，不是自建 Bot Token；
官网订阅也不会提供这个代理的 API Key。
官方对未经许可的自动化有使用限制，关联 Discord 并不等于获得官方 API 授权。
当前协议、出图及 V8/多图参考兼容性均待账号接通后实测；此模板不表示已验证可用。

来源：[Docker 部署](https://github.com/novicezk/midjourney-proxy/blob/main/docs/docker-start.md)、
[配置字段](https://github.com/novicezk/midjourney-proxy/blob/main/docs/config.md)、
[API 协议](https://github.com/novicezk/midjourney-proxy/blob/main/docs/api.md)、
[MJ 使用规则](https://docs.midjourney.com/hc/en-us/articles/32013696484109-Community-Guidelines)。

## 本机配置与联调入口

`deploy/midjourney/env.example` 是空白模板。后续将其复制为同目录 `env.local`，
填写服务器 ID、文字频道 ID、Discord 用户凭据和独立的本地代理密钥。
`env.local` 已被 Git 忽略；不要改动存有 AutoDL Token 的项目根目录 `.env`。
`MJ_API_SECRET` 是给本机代理设置的鉴权密钥，不是向 MJ 官网申请的密钥。

账号准备好并在本机完成配置后，助手可执行以下命令。用户不需要自己维护网站或操作后台。

```powershell
cd E:\AutoDL
# 只校验配置，不连接账号、不提交任务；--quiet 避免将展开后的凭据打印出来。
docker compose --env-file deploy/midjourney/env.local -f deploy/midjourney/compose.yaml config --quiet
# Docker 引擎运行后启动代理；建立 Discord 连接，不会自行发起生图。
docker compose --env-file deploy/midjourney/env.local -f deploy/midjourney/compose.yaml up -d
```

参数缺失时 Compose 会拒绝启动。不要直接执行不带 `--quiet` 的 `compose config` 并转贴输出，
展开后的配置含凭据。容器信息和日志也可能包含私人账号信息。

当前模板使用上游默认内存任务存储，**重启代理会丢失其任务记录**。
运行期间保留任务 ID；中断后先核对 Discord 历史，不能因为查不到任务就自动重新生成。
后续接入 Python 时沿用现有一次提交、轮询恢复、独立无鉴权下载的做法；
若需要代理重启后继续查询，可再启用上游支持的 Redis 持久化方案。

通过只读连接检查后，再按用户明确指定的提示词、参考图和生成数量做出图联调。
成图仍归档至 `assets/双精灵对决/`，沿用项目中文命名与视频阶段素材检查规则。
