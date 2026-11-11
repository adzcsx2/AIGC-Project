# 来源与本地适配

审计日期：2026-11-08。由用户明确指定的两个本地目录提供，源目录未修改。

1. `C:/Users/long/Documents/xwechat_files/wxid_m6ioxcdaxxq221_8751/msg/file/2026-11/martial-arts-director-cy`
   与项目现有 `../martial-arts-director-cy` 的 SKILL、README、LICENSE及四份参考正文按行比较一致。
   现有来源为 https://github.com/CY-CHENYUE/martial-arts-director-cy ，固定提交
   `65c7c1dd35fcf4a01bfc1372ab506b60e2d0d26d`，Apache-2.0。继续使用原安装及许可，不重复安装或覆写原文。
2. `C:/Users/long/Documents/xwechat_files/wxid_m6ioxcdaxxq221_8751/msg/file/2026-11/3D-anime-redfruit-pipeline/3d-anime-redfruit-pipeline`
   十份文本/脚本以原始字节存于 `references/upstream/3d-anime-redfruit-pipeline/`；排除两份 `__pycache__` 缓存。
   交付包没有 LICENSE、远程地址或版本号，未推断为开源许可。当前仅按用户要求本地整合，未发布或上传第三方。

逐文件SHA256及本地测试结果见 `references/来源指纹与校验.json`。原始脚本只归档供审计追溯，
不自动执行、不作为AutoDL生成门禁；正文方法经本技能两份适配参考后使用。
详细缺陷、覆盖规则和验证范围见根目录 `docs/维护记录/技能审计-武指与三维制作流程.md`。

## 高密度打斗导演方法（2026-11-09）

用户指定 https://github.com/lj350201364/high-density-fight-prompt ，重点为 `references/15s-fight-directing-contract.md`。
固定提交 `d0316da6edfc37034c35479613669e07251e4571`，五份上游文本原样存于 `.agents/resources/high-density-fight-prompt/`，只作内部来源，不注册重复技能。
该版本没有LICENSE，未推断授权类型；本次仅本地整合。文件指纹见该目录的 `来源记录.json`。
采用方法和冲突裁决见 `docs/维护记录/技能审计-高密度打斗融合.md`，执行正文为本技能 `references/高密度打斗导演合同.md`。
