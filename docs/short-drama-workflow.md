# 短剧制作与清单

入口为 `short-drama-workflow`，完整规则见 [导演规则](director-workflow.md)。
文案或动作不足时，先补全中文文案并取得确认，再做正式分镜、逐段运镜审计、英文提示词和素材制作。
没有白模可直接做原创视频；需要预演时用本地引擎。白模用titim，非白模用u24；u24不能读取视频。

## 文档与版本

五份Markdown拥有创作正文：`剧本.md`、`视觉设定.md`、`分镜.md`、`图片提示词.md`、`视频提示词.md`。
另有 `需求.md` 保存用户要求。materials只登记状态和实际绑定。Acheng production.json如需编译，
只能从当前文档派生并记录源哈希，正文变化后重新派生，不能双向独立维护。

新作品复制 `templates/short-drama/` 下两个YAML，白模用 `templates/whitebox-retargeting/`。
所有示例素材未就绪，不能直接改ready绕过查看和确认。一个SHOT-ID可以代表一次连续15秒生成，
内部小段在分镜中按 [运镜审计模板](../templates/short-drama/运镜审计.md)逐段审核，不机械拆成碎片请求。

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
(Get-FileHash -LiteralPath 'projects/我的短剧/剧本.md' -Algorithm SHA256).Hash.ToLowerInvariant()
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
.venv/Scripts/python.exe -m autodl_video validate projects/我的短剧/镜头01.yaml
.venv/Scripts/python.exe -m autodl_video run projects/我的短剧/镜头01.yaml --dry-run
```

退出码0=通过，1=待确认/缺素材/待检查，2=格式错误。--shot只核对镜头ID，仍检查同清单所有必要素材。
不相关作品用不同清单；required=false且未用的资产不阻断，实际依赖或绑定后必须就绪。
materials_manifest相对镜头YAML，与shot_id成对。独立历史演示和task_id恢复保留原用法。
机械检查验证文件和绑定，不能替代实际看图、摄影审计与成片验收。

## 提交与交付

正文全英文，说明与命名中文，对白字幕按作品需求。图片按MJ手动或已授权参考板流程。
通过真实工作流规则核对字段、长度和枚举；源skill字数/时长不是API契约。

```powershell
.venv/Scripts/python.exe -m autodl_video models show minimax_h3_zm_u24
.venv/Scripts/python.exe -m autodl_video models show minimax_h3_zm_titim
# 仅在用户已明确请求当前生成、文案确认与素材检查通过后执行：
.venv/Scripts/python.exe -m autodl_video run projects/我的短剧/镜头01.yaml
```

未指定预算时不加max_cost_cny/--max-cost；有明确上限遵守。一次请求只提交一次，保留task_id并恢复查询，
不自动重抽。返回后检查完整解码、声音、时长、身份、动作和连续性，SUCCESS不等于创作验收。
已确认15秒原创连续戏份保持一次连续多机位生成；原片复刻按源片长度、动作和原声，不套15秒模板。
