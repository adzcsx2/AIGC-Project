# 短剧制作与清单

只有剧本要求人物说话才配置声音；无台词/非语言声不列配声待办。人物身份、显示名、声音选择与试听队列见 [人物与声音流程](character-voice.md)。新人物用 `templates/short-drama/角色.yaml` 并登记到project.yaml；新的声音参考镜头按该文填写voice_policy、speakers与voice_bindings，历史提交不改。

入口为 `short-drama-workflow`，完整规则见 [导演规则](director-workflow.md)。
本页用于跨阶段生产和清单；单项需求先按 [技能路由](../skill-routing.md) 直达专业入口，尤其已有task_id的恢复不重新创建剧本/分镜或刷新创作确认。
写剧本前必须参考 [`cinematic-script-audit`](../../.agents/skills/cinematic-script-audit/SKILL.md)，再细化动作与运镜。未特别说明时为16:9横屏，生成和剪辑默认24fps，最终成片自动补到60fps，不考虑平台UI安全区域，动作构图余量保留。
文案或动作不足时，先补全中文文案并取得确认，再做正式分镜、逐段运镜审计、英文提示词和素材制作。
新视频默认先完成简单白模预演，已有合格白模可复用，用户明确另定流程时记录例外，见 [白模制作与验收](白模制作与验收.md#默认先做白模)。有白模视频默认实际交titim，没有白模视频才默认u30；按此路由无需逐次询问接口，用户明确另定时遵从，真实输入不兼容时按导演流程解决。
多片段的新默认见 [衔接图制作规则](multi-segment-video.md)：先审计分段和时长，Codex生成边界图、用户审图后直接生成全批并合成。有白模默认titim并实际上传，无白模才默认u30；每个独立请求边界从剧本/提示词预设计可见切镜/转场，连续速度链尽量留在所选API允许时长内的同一次生成；真正首尾用途另核实，不当作边界速度保证。

## 文档与版本

五份Markdown拥有创作正文：`剧本.md`、`视觉设定.md`、`分镜.md`、`图片提示词.md`、`视频提示词.md`。
另有 `需求.md` 保存用户要求。materials只登记状态和实际绑定。Acheng production.json如需编译，
只能从当前文档派生并记录源哈希，正文变化后重新派生，不能双向独立维护。

新作品复制 `templates/short-drama/` 下的清单、镜头与人物YAML模板，白模用 `templates/whitebox-retargeting/`。
所有示例素材未就绪，不能直接改ready绕过查看和确认。一个SHOT-ID代表一次计划生成，时长按内容与实际接口确定；模板中的15秒仅为示例，
内部小段在分镜中按 [运镜审计模板](../../templates/short-drama/运镜审计.md)逐段审核，不机械拆成碎片请求。

## schema 2确认记录

```yaml
schema_version: 2
creative_confirmation:
  state: pending
  script_sha256: ""
  confirmation_ref: ""
```

补全文案交用户确认后，记录真实确认消息/时间/版本位置，将state设confirmed，并记录该版剧本SHA-256。
用户本来就提供完整明确版本时可引用其指令，无须另问。文案确认不自动授权未要求的生成；
“生成”也不代表用户接受尚未看到的补全剧情。

```powershell
(Get-FileHash -LiteralPath 'projects/我的短剧/01-文档/需求与剧本/剧本.md' -Algorithm SHA256).Hash.ToLowerInvariant()
```

哈希放清单，不写进剧本本身。剧本改变即使旧确认失效，应说明变化并取得适用确认，不悄悄刷新哈希。
程序在网络/凭据读取前检查状态、非空记录、版本哈希与素材，但不能证明聊天真实性或判断摄影美感。
schema 1仅保留历史兼容；新任务不能降级、移除materials绑定或直接调用submit绕过。

## 素材与绑定

- documents登记brief/style/script/storyboard，指向真实需求、视觉设定、剧本和分镜。
- assets使用稳定ID，kind为character/scene/prop/keyframe/audio/video；作品目录和文件名用中文。
  required默认true，path相对清单；prompt可存英文补图正文或正文文档定位。
- missing=待补，provided=有文件待查看/确认，ready=实际查看且通过当前节点。
  一般候选由用户选定；明确授权助手验收的参考板等例外按AGENTS执行。图变更须重查。
- shots包含required_assets和reference_bindings；后者覆盖实际输入的全部图像/音频/视频字段。
  不要求所有资产都上传，但实际绑定图不能错，白模不能仅登记而没有输入。

```powershell
.venv/Scripts/python.exe -m autodl_video materials check projects/我的短剧/materials.yaml
.venv/Scripts/python.exe -m autodl_video validate projects/我的短剧/03-制作/生成配置/镜头01.yaml
.venv/Scripts/python.exe -m autodl_video run projects/我的短剧/03-制作/生成配置/镜头01.yaml --dry-run
```

退出码0=通过，1=待确认/缺素材/待检查，2=格式错误。--shot检查该镜头声音依赖，并保留同清单视觉素材前置检查；新voice_policy下其他镜头待试听的角色声音不阻断本镜头。
不相关作品用不同清单；required=false且未用的资产不阻断，实际依赖或绑定后必须就绪。
materials_manifest相对镜头YAML，与shot_id成对。独立历史演示和task_id恢复保留原用法。
机械检查验证文件和绑定，不能替代实际看图、摄影审计与成片验收。

## 提交与交付

先用 [电影级生成前审计模板](../../templates/short-drama/电影级生成前审计.md) 审查最终方案并修正，**在提醒/询问用户是否生成之前展示审计结论**，不得等用户说确定生成才审计。审图后直接生成的计划提前到最终审图材料交付前完成；确认后仅核对当前版本与已审版本一致、素材和接口参数有效。总审计属于助手工作流要求，本次未新增客户端schema字段或自动审美校验能力。

正文全英文，说明与命名中文，对白字幕按作品需求。普通图片按MJ手动；已授权参考板及多片段衔接图/必要端点按Codex内置image_gen流程。
通过真实工作流规则核对字段、长度和枚举；源skill字数/时长不是API契约。

```powershell
.venv/Scripts/python.exe -m autodl_video models show minimax_h3_zm_u24
.venv/Scripts/python.exe -m autodl_video models show minimax_h3_zm_titim
# 仅在用户已明确请求当前生成、文案确认与素材检查通过后执行：
.venv/Scripts/python.exe -m autodl_video run projects/我的短剧/03-制作/生成配置/镜头01.yaml
```

未指定预算时不加max_cost_cny/--max-cost；有明确上限遵守。一次请求只提交一次，保留task_id并恢复查询，
不自动重抽。多片段图片确认后直接生成全部计划片段；下载后做必要技术检查，并依据 [多片段规则](multi-segment-video.md) 的切镜/转场设计逐一选出入点、删多余等待；旧片或明确连续例外才按版本04匹配运动并按需压短过渡，音画同步合成后自动调用 `补帧` 到60fps；验收全部N−1个接缝的源端、实际合成及最终补帧结果。单段成片与替换后重合成同样执行，已是60fps核验复用，用户另定规格时遵从。其余身份、动作、特效仍由用户审整体成片，SUCCESS或接缝通过不等于整体创作验收。片段映射、实际时间范围、裁切区间、版本和task_id保留；用户认可指定段替换版后自动重合成并复查新版接口。
分段方式和秒数由生成前审计决定，不机械固定15秒，也不把内部切镜全拆成单独请求；原片复刻按源片长度、动作和原声。

新模板落位：materials.yaml置作品根目录，shot.yaml置03-制作/生成配置，路径基准已按此设置；正文按目录规范归01-文档。先读project.yaml恢复当前版本。
