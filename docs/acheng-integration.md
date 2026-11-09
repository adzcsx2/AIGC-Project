# Acheng接入与迁移记录

2026-11-09，用户确认重组方案后接入。新规则见 [导演规则](director-workflow.md)。

## 固定来源

- 上游：[AharaOoO/acheng-director-skill](https://github.com/AharaOoO/acheng-director-skill/tree/287b5ac27c3790c665029eb4fdf94628070b2ac8)。
- 提交：`287b5ac27c3790c665029eb4fdf94628070b2ac8`，上游metadata版本4.3.9。
- 完整安装位置：`.agents/resources/acheng-director/`，924个文件，包括132个示范MP4。
- 原ZIP SHA-256：`e9695082b099174e6e60027aedaac41c0951a5f3db0edc6dbc99215b9265dae3`。
- 安装记录：`.autodl/install/acheng-install.json`。从GitHub该固定提交只读下载ZIP可恢复，
  解包去掉最外层目录，保留原目录、媒体、LICENSE、NOTICE与第三方许可。

脚本适用Apache-2.0，作者创作文本/指南/示例采用CC BY-NC-ND 4.0，第三方资料各有许可。
参见原 [许可范围](../.agents/resources/acheng-director/LICENSE-SCOPE.md) 与
[第三方摄影库许可](../.agents/resources/acheng-director/references/sources/licenses/camera-moves-whitebox-LICENSE.txt)。
本次保留源码原文，项目适配规则独立编写；没有发布或推送，不将整个包标为Apache，也不作商业改编授权保证。

## 接入方式

总导演读故事和连续性；摄影入口读shots、镜头容量、摄影库与H3格式；视觉入口沿用本项目素材流程。
逐段审计摄影并检查全片变化。上游入口没有装入自动发现目录，避免产生第二个总导演。
132个视频是选镜示例，不是定制打斗白模。需要白模时使用huashu本地引擎；
没有通用3D动捕或精细双人打斗骨骼求解，不把简单几何移动称作完整动作制作。

## 编译器用法与边界

production.json为可选派生文件。按上游schema从已确认的五份Markdown映射，旁存源路径和SHA-256；
原稿变更即失效。不为通过上游表单虚构ready素材、用户确认或视觉审查结果。
下面只执行离线编译，不生成视频：

```powershell
.venv/Scripts/python.exe .agents/resources/acheng-director/scripts/compile_h3.py --help
.venv/Scripts/python.exe .agents/resources/acheng-director/scripts/compile_h3.py projects/作品名/派生/production.json --out projects/作品名/派生/H3草稿 --draft
```

生产卡字段按固定源码的schema/examples读取，不是任意故事都能直接编译。
--draft允许草稿，退出2可表示源合同未通过，不能称可提交，也不能捏造通过标记。
最终英文prompt写进视频提示词文档并与YAML正文一致；编译报告不授权提交。
源长提示词、四视角、风格母图等要求不是AutoDL接口契约，已有合格参考板不因此重做。
u24按实际字符上限适配；titim用简短映射或省略prompt，不调用长格式编译器。

## 去重结果

19个原入口重组为9个。12个旧入口完整迁到 `.agents/resources/skills/`，新增storyboard-camera与visual-assets。
用户3D资料、武指、H3表演、故事/编剧、资产/提示词、审计和维护索引仍保留，由对应单一入口调度。
原脚本及许可没有删除；原入口与重要规则备份在 `docs/archive/技能重组-20261109-实施前/`。
active/internal状态、对应入口、源版本和SKILL指纹见 [installed-skills.yaml](installed-skills.yaml)。

## 验证范围

本次不新建付费视频；u24的ref_video拒绝测试来自此前用户明确要求的兼容性验证。
机械校验只证明结构和代码行为，不代表完整白模已渲染或视频生成质量必然符合要求。

2026-11-09本机实际验证结果：

| 检查 | 结果 |
|---|---|
| 项目完整pytest（含schema 1/2、未确认阻断、变更失效、媒体绑定和任务恢复） | 185 passed |
| Ruff与git diff --check | 通过 |
| pip-audit（本机虚拟环境，跳过本项目editable包，独立缓存） | 未发现已知依赖漏洞 |
| 九个入口的skill-creator quick_validate | 全部通过 |
| 九份UI元数据、当前项目/技能Markdown链接、清单指纹 | 通过 |
| Acheng原ZIP与安装文件逐字节SHA-256比对 | 924个源文件一致，132个MP4存在 |
| Acheng scripts/test_*.py | 89项通过 |
| 迁移后short-drama/develop/write及保留breakdown的selftest | 分别17/5/8/11项通过 |
| compile_h3.py上游01-mecha示例，--draft | 成功写出1段编译包，没有模型调用 |
| huashu多机位切换模板probe | 无红色几何问题；本次未做完整视频渲染或视觉验收 |

项目测试使用 `.autodl/test-tmp/` 独立临时目录并禁用旧pytest缓存；技能验证设置PYTHONUTF8=1，
以避开本机旧缓存权限和系统GBK默认读取问题。没有修改用户凭据或全局Python设置。
依赖审计结果文件为 `.autodl/install/依赖审计-技能重组.json`。

规则走读同时核对：简略“A打B，15秒”停在中文补全稿等待确认；完整已确认文案自动进入逐段摄影审计；
无白模原创走u24；有白模走titim；非白模原片强制动作继承时提示u24能力缺口；剧本修改使旧确认失效。
这些是流程/静态核对，不冒充新的生成样片测试。
