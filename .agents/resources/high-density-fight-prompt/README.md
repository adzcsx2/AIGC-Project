# 高密度打斗导演 · high-density-fight-prompt

根据参考图和创意要求，编排高密度、连续因果的打斗视频提示词。支持徒手战、武器战、机械战和巨物战。

## 输出

- 默认 15 秒、16:9、无对白和旁白。
- 中文导演稿与同一时间线的 MiniMax H3 Ref2VA 英文六段稿。
- 10 秒及以内使用短时长结构；支持明确指定的无停顿连续模式。
- 保留人物身份、装备、接触关系和逐镜状态；攻击、反制、位移与环境反馈连续。
- 每份最终提示词以 BUNNY 开始，这是本 skill 的提示词前缀约定。

## 安装与依赖

将本目录安装为 Codex skills 目录下的 `high-density-fight-prompt`，确保其根目录包含 `SKILL.md`。

生成英文 H3 稿还需单独安装 `h3-prompt-writing` skill，并确保其中包含 `SKILL.md` 与 `references/ref-en.txt`。本仓库不内嵌该依赖。

## 使用

上传参考图后输入：

```text
$high-density-fight-prompt 根据参考图生成15秒快节奏连续打斗提示词，保持人物面部与服装不变。
```

可补充时长、画幅、人物对应图片、武器与能力、胜负、声音，以及是否全程不停顿。只需要中文时明确说明“只要中文”。

## 文件

- `SKILL.md`：入口与工作流程。
- `agents/openai.yaml`：显示名称与默认调用提示。
- `references/15s-fight-directing-contract.md`：动作编排与连续性合同。
- `references/h3-ref2va-dual-output.md`：中英文同步编译合同。

本 skill 生成提示词，不直接渲染视频；实际生成效果取决于所用模型与参考素材。
