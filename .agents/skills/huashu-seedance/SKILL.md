---
name: huashu-seedance
description: 继续明确指定的huashu旧scene.json几何预演或照片拟合流程。保留现有引擎与模板；新Blender/白模制作优先本机Blender技能，不调用Seedance云API，不把几何移动当动捕或精细骨骼打斗。
license: MIT
---

# 白模空间与摄影预演

当前新视频统一u30多图，不制作/提交白模；见[当前导演规则](../../../docs/工作流/director-workflow.md#u30多图身份身高与完整同框规则)。本技能的白模/视频驱动细节仅供历史任务恢复或用户以后明确另定用途，不是当前新视频默认；不自动切回titim。

用户2026-11-09指定本机Blender优先：新的三维白模/运镜预演交`blender-video-original`，参考视频重建交`blender-video-recreate`；本入口承接明确指定的旧scene.json或照片拟合任务，不自动迁移已有工程。

先读根规则与导演流程；当前新视频走u30无白模，本技能只承接用户明确指定的旧流程。
先复用已确认时长、画幅、动作草案和分镜；确缺关键信息才问，不重复套三问问卷。
需写/补/改文案时先参考 `cinematic-script-audit`；文案不足先补全取得确认，再由 `fight-scene-design` 细化复杂攻防。仅改既有工程不重启创作流程。

## 本地引擎

按需读 `references/scene-spec.md`、`camera-rig.md`、`whitemodel.md`，从 `templates/scenes/` 建scene.json。
`engine/`原源码保留。以下命令在作品工作目录执行，示例路径应替换为真实文件：

```powershell
node E:/AutoDL/.agents/skills/huashu-seedance/engine/probe.mjs scene.json
node E:/AutoDL/.agents/skills/huashu-seedance/engine/build.mjs scene.json
npx hyperframes@0.7.107 lint
npx hyperframes@0.7.107 render --quality draft --output 白模预演.mp4
node E:/AutoDL/.agents/skills/huashu-seedance/engine/frames.mjs 白模预演.mp4 scene.json
```

渲染需Hyperframes和浏览器运行时；只有实际渲染成功并看过结果才称白模已完成。
probe零红之后仍须查看可疑时段和完整动作，检查双人遮挡、占画比例、空间、路径与切镜。
可用 `engine/preview.mjs scene.json 0,7.5,15` 检查画面和机位数值是否一致。
照片拟合按 `references/photo-to-whitemodel.md` 用 `engine/photo_grid.py`，其OpenCV依赖按需准备。

## 交给制作

- 这套引擎负责简单几何、空间和摄影预演；没有通用人体骨骼打斗/任意原片动捕执行端。
  不把推移几何体称作已经实现拳脚接触。复杂动作缺口须明确指出。
- Acheng132示范可帮助选镜，不是用户角色的完整动作片；源Blender生成脚本没有随该库提供。
- `engine/make_prompt.mjs`产物只作测量与源方言资料，不能把其中文/Seedance标记直接交给MiniMax。
  由 `storyboard-camera` 按真实引导改成英文；titim只作简短主体映射与必要例外。
- 输出实际检查合格后按中文素材名归档；仅预演任务到此交付。用户已有明确白模复刻生成请求时才交 `video-retargeting`绑定、`autodl-aigc`核实titim执行，不把本地预演自动扩成收费视频。
  保留原轨；没有音轨时是否需补全静音AAC由实际工作流决定。
- 原 `references/prompt-spec.md` 和作者经验仅属Seedance源资料，不是AutoDL接口契约。
  不调用未配置服务或把图片默认切到Seedream；图片仍走本项目授权工具。

来源与许可保留于 `UPSTREAM.md`、`LICENSE`及原references，原入口备份在docs/archive技能重组目录。
