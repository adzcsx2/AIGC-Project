# 短剧技能索引分析与本项目选型

分析与安装日期：2026-11-07。本项目需要“参考图或提示词风格 → Midjourney 资产提示词 →
剧本与分镜 → 检查并补齐图 → MiniMax 视频”，已有 AutoDL Python 客户端和武术指导技能。

## 索引提供什么

[Awesome Short Drama Skills](https://github.com/UnderleveledBuilder/awesome-short-drama-skills)
主要是策展索引，实际能力在它链接的源仓库。
本次读取的 [结构化索引](https://shortdramaskills.com/data.json) 标记更新日期为 2026-11-02，
共 99 条，包含 83 项技能/项目与 16 项平台。数量包含不同类型，并非 99 个可直接安装的标准技能。
索引自己的 `short-drama-skill-finder` 只负责匹配与检索。
因此本次既安装 finder，也从具体源仓库安装创作技能及其配套参考、脚本和模板。

## 实际安装

| 源仓库 | 本次安装技能 | 对本项目的作用 |
|---|---|---|
| [zenstory-ai/drama-skills](https://github.com/zenstory-ai/drama-skills) | `short-drama` | 项目初始化、阶段路由、创作资料管理 |
| 同上 | `short-drama-develop` | 想法开发、故事引擎、分集与钩子 |
| 同上 | `short-drama-write` | 单集剧本、动作与对白 |
| 同上 | `short-drama-assets` | 人物身份、造型、地点、道具与状态连续性 |
| 同上 | `short-drama-image-prompts` | 角色、场景、道具、关键帧图片提示词，交用户在 Midjourney 生成 |
| 同上 | `short-drama-storyboard` | 景别、机位、走位、冻结关键帧及参考图绑定 |
| 同上 | `short-drama-video-prompts` | 把分镜转为对应模型的视频提示词，包含 MiniMax H3 方言 |
| 同上 | `short-drama-review` | 剧本、连续性、分镜和提示词审校，按需使用 |
| [phileiny/h3-storyboard-skill](https://github.com/phileiny/h3-storyboard-skill) | `h3-storyboard` | H3 情绪表演、动作节拍密度与镜头设计补充 |
| [UnderleveledBuilder/awesome-short-drama-skills](https://github.com/UnderleveledBuilder/awesome-short-drama-skills) | `short-drama-skill-finder` | 今后按新增需求检索其他实际源仓库 |

合计安装 10 项外部技能，来自 3 个源仓库，其中 9 项负责实际创作。
另创建本项目 `short-drama-workflow`，把这组能力接到现有 `autodl-aigc`；
原有 `martial-arts-director-cy` 继续负责打斗动作。
完整文件位于 `.agents/skills/`，没有只复制技能名称或只装索引。

选择 zenstory 套件作为主线，是因为它的阶段拥有一致的五文档契约、区分身份与造型、
区分真实参考图与规划槽位，并把图片提示词与生成执行分开；这适合用户自己去 Midjourney 出图。
它在 README 声明支持 Codex，配套脚本为 Python，能与当前项目复用运行环境。
H3 补充指南侧重“怎么演、怎么拆镜”，与主线的提示词格式职责互补。

## 已核对但未安装的范围

- [eternityspring/shuohao-skills](https://github.com/eternityspring/shuohao-skills)：有角色、剧本和分镜能力，
  但采用另一套小说改编与结构化交付流程；部分角色参考/分镜阶段还直接调用其他图片生成链路。
  与现有主线大量重叠，因此本次不混入两套产物契约与生产执行方式。
- zenstory 的小说分析、对标视频拆解：当前需求是用户自己的创意与提示词风格，尚不需要这些专门入口。
- zenstory 的 `short-drama-produce`：本项目已有 AutoDL 任务记录、预算预检、轮询和下载，
  不另引入 provider/adapter 与凭据。上游路由提及它时，由项目衔接规则转到 `autodl-aigc`。
- zenstory 的后期剪辑阶段：本次要求到生成视频，尚未要求剪辑、配乐与成片封装，保留以后按需安装。
- 只针对 Seedance/Kling 等模型的专门技能，以及需要独立部署的平台：当前 MiniMax 路线已有匹配的提示词能力，
  不因索引收录就全部安装。

## 为用户要求做的衔接

1. 参考提示词只提炼画风和技术表达，再融入用户自己的人物需求；有真实图时以已查看的图锁定身份。
2. 每集五份 Markdown 是创作正文；额外 `materials.yaml` 只登记就绪、文件与输入绑定，不再复制剧情。
3. 上游默认可带 PLAN 槽位继续写视频提示词，但用户明确要求先补齐素材，因此本项目在缺图处停下，
   交付补图清单后等图，禁止暗中转文生视频。
4. 新增 Python 素材检查及 CLI `materials check`。短剧镜头 YAML 带 `materials_manifest` 与 `shot_id`，
   `run/validate` 会在网络与密钥加载前检查；实际媒体输入还必须与清单绑定一致。
5. H3 示例 production_profile 不是接口参数规范。时长、分辨率、媒体字段和预算以本项目 AutoDL 真实工作流规则为准。
   H3 指南的 PSNR、节拍数和样例成功率是作者的小样本观察，不能用作普适保证。
6. H3 补充指南提到另一个 `minimax-h3` 技能，其语法职责由已经安装的 H3 方言参考承担，
   不另引入本地 ComfyUI 服务依赖。

## 版本、许可与更新

- 索引固定提交：[9a1f686](https://github.com/UnderleveledBuilder/awesome-short-drama-skills/tree/9a1f686460c0a03cb0df40c3d2e55739568911dc)，CC0-1.0。
- zenstory 固定提交：[862ae46](https://github.com/zenstory-ai/drama-skills/tree/862ae46f36516f2b7d188da42e0e67365f7ddde6)，MIT。
- H3 固定提交：[ce732ba](https://github.com/phileiny/h3-storyboard-skill/tree/ce732bae6e05d2e4c4943e3e1fda2d515f9a2ff3)，MIT。

每个外部技能保留原始 SKILL.md、配套资源与来源记录，补齐源仓库根 LICENSE；
缺少 Codex 界面元数据的两个技能由本项目补充。精确目录与 SKILL.md 哈希见 `installed-skills.yaml`。
升级时先比较新提交的规则、引用和许可，再替换上游文件并验证本项目适配；不要覆盖用户作品和素材。
此安装请求没有建立定时自动更新任务。需要查新的索引或更新模型时，可直接让助手执行相应检索或 `models sync`。

操作说明见 [短剧工作流](short-drama-workflow.md)。安装验证使用离线测试，没有调用收费生成。
