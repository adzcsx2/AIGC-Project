---
name: huashu-seedance
description: 使用已安装scene.json引擎制作本地白模空间与运镜预演，进行几何体检、照片空间拟合、抽帧和构图检查。用于需要白模参考或验证摄影路径的任务；不负责调用Seedance，不把简单几何预演当精细打斗动画或动捕。
license: MIT
---

# 白模空间与摄影预演

先读 `AGENTS.md` 与 `docs/director-workflow.md`。无白模也可用原创分镜/u24，不强制先做白模。
先复用已确认时长、画幅、动作草案和分镜；确缺关键信息才问，不重复套三问问卷。
文案不足先补全文案取得确认，复杂攻防由 `fight-scene-design` 设计。

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
- 输出实际检查合格后按中文素材名归档，由 `video-retargeting`绑定，`autodl-aigc`用titim执行。
  保留原轨；没有音轨时是否需补全静音AAC由实际工作流决定。
- 原 `references/prompt-spec.md` 和作者经验仅属Seedance源资料，不是AutoDL接口契约。
  不调用未配置服务或把图片默认切到Seedream；图片仍走本项目授权工具。

来源与许可保留于 `UPSTREAM.md`、`LICENSE`及原references，原入口备份在docs/archive技能重组目录。
