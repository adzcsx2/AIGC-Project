# 共享资产库与作品版本绑定

## Strict board correction and existing-project migration — 2026-11-11

The current shared 人物 folder contains only two reviewed, exact-three-view boards:
MEDIEVAL-GIRL-BOARD@05 and PINK-DRAGON-BOARD@04. Character master revision 03 adds
`language: en`; revision 02 stays frozen for historical bindings. Character speech language
follows [人物与声音流程](character-voice.md#角色说话语言), including translation of requested lines.
Old six/five-view sheets and the original single face image are source evidence under
99-历史/旧人物来源; they are not current board candidates. New identity-board registration,
character look selection and production readiness validate the current layout contract and its
hash-bound inspection record. The program verifies the record; actual image inspection remains
necessary and is not inferred from PNG headers or a passing unit test.

`tools/刷新共享三视图.py` consumes explicit image and review files. It does not generate visual
approvals. `tools/迁移现有项目资产.py` consolidates the explicitly selected inputs of existing
projects, preserving submitted manifests and creating sibling migration manifests. Unselected
branches retain their explicit selection state. Original local input paths remain project-owned
aliases to versioned library bytes; their presence does not mean they are disposable duplicates.
Character sources imported from unrelated older works are archived sources, not newly approved boards.

To check unnecessary images, use `tools/资产清理.py plan <new-plan.json>`. It considers historical
branches, task receipts, escaped/URL-encoded references and source tools. Only unreferenced exact
duplicates qualify; numbered sequences and unique images are protected. Apply requires a new
JSON journal, revalidates references under project/manifest locks, and hashes/deletes the same
Windows file handle. Other systems fail closed for deletion. The current scan found zero additional
unreferenced duplicates; the three obsolete active-library aliases were removed after archival.

The two old one-shot balloon preparation scripts are retired at their CLI entry points; they
must not recreate old manifests or reference the old boards for new submissions. Continue from
the current project.yaml selection and create new configs with its current input bindings.

用户2026-11-11批准实施。资产库入口是 `projects/共享资产库/project.yaml`，其
`project_type: asset_library` 与 `asset_catalog: 资产索引.yaml` 指向专用目录。
资产库不是待拍作品，不要求虚构剧本、分镜或生成授权。公共工具是 `tools/资产.py`。

## 先找素材，再制作

1. 先读目标作品 `project.yaml`，沿其当前 `materials_manifest` 和 `characters` 查找。
2. 跨作品找角色/场景/声音时，用 `tools/资产.py list --query <中文名或标签>`。
   返回全局ID、每个明确版本及真实绝对路径。不得按同名、修改时间猜同一身份或“最新版”。
3. `show <ID> --revision <版本>` 查文件用途/来源/验收依据；角色主档加 `--entity`。
   实看参考/实际试听等原门槛仍适用。库内有文件不代表该文件已被接受或适合当前镜头。
4. 用 `import` 将明确版本归档到本作品，锁定ID、版本、SHA-256与本地路径。
   已有同字节本地文件直接复用；跨作品旧引用在本作品建立只读媒体路径。
5. 角色用 `bind-character` 明确选择主档版本、造型ID、人物板和可选声线。
   再运行 `check --project`；正式生产仍运行现有materials检查、实际接口校验和创作审计。

```powershell
.venv/Scripts/python.exe tools/资产.py list --query 中世纪小女孩
.venv/Scripts/python.exe tools/资产.py show MEDIEVAL-GIRL --revision 01 --entity
.venv/Scripts/python.exe tools/资产.py check --project projects/悬崖上的小气球/project.yaml
.venv/Scripts/python.exe tools/资产.py uses MEDIEVAL-GIRL
```

`uses`列出各作品明确选中的当前清单/人物及受影响镜头，未选择的历史分支不冒充当前。
读不到的作品明确列在issues，不静默忽略。当前未绑定共享库的旧作品仍按原契约读取。

## 唯一来源与路径

| 数据 | 唯一维护位置 |
|---|---|
| 共享实体及各媒体版本目录 | 资产库的资产索引.yaml；索引含文件元数据，不另建平行状态表 |
| 长期角色身份、性格、造型与声线选项 | 资产库01-文档/角色的不可覆盖版本YAML |
| 地点空间/道具属性 | 资产库01-文档/场景、道具的版本YAML |
| 本作品选择了哪个角色/造型/声线 | 本作品角色YAML的library_binding；仍由project.characters索引 |
| 本作品当前人物称呼、说话用途、剧情能力 | 本作品角色YAML；对白仍以剧本为准 |
| 本作品媒体是否可用及真实API槽位 | 本作品当前materials.yaml；library_ref固定共享文件版本 |
| 当前作品的视觉风格 | project.documents.style；materials.documents.style引用同文件 |
| 实际音乐入出点/音量/对白避让 | 现有配乐方案；不写回公共曲目 |

资产库内路径相对资产库根目录。作品人物档案和快照路径相对作品根；materials中的path
仍相对清单目录。library_ref/library_binding里的library是相对作品根的来源入口，仅用于
追溯，不在生成时动态读取“最新”。来源provenance采用明确的 `path_base: repository`。

同一名称可以属于不同全局ID；同一角色在作品里的CHAR-GIRL等局部ID保留。
建立全局映射必须有来源/已确认复用关系，不能仅凭同名或脸相似自动合并。
角色的新名字不触发新身份，也不自动把名字写入台词。

本作品保存带哈希的主档快照 `01-文档/角色/共享版本/`，它是某次使用的冻结依据，
不能直接编辑。运行时characters()合并此快照的固定attributes和本作品剧情属性，
返回resolved_look与style_reference。长期appearance/personality等不在两处同时维护；
迁移前摘要保留在registration_history，只作来源。

## 分类与角色变体

分类是用途，media_type是image/audio/video/document/project，二者分别登记。

| category | 范围 |
|---|---|
| character | 人物、动物、怪物的身份图、角色板 |
| wardrobe | 服装、配饰与造型组件 |
| scene | 地点、环境及具体视图 |
| prop | 道具、武器、家具与载具 |
| voice | 人物音色样本、候选和语言版本 |
| dialogue | 具体台词、旁白、对白底轨 |
| ambience | 环境底声、风雨与室内空间声 |
| sfx | 动作拟音、碰撞、液体、呼吸与生物叫声 |
| music | 曲目、主题、编配及独立分轨 |
| motion | 动作原片、简单白模工程与引导 |
| camera | 机位与摄影参考 |
| compositing | 遮罩、深度、法线、透明特效、贴图 |
| graphics | 字幕、字体、包装、水印 |
| footage | 可复用原始片段与成片版本 |

角色主档沿用 `templates/asset-library/共享角色.yaml`：身份、固定外观、性格、身体结构、
尺寸依据、可见表演习惯、不可变特征、风格引用、来源。未知保持null，不补造已确认事实。
每套造型在looks下有独立ID、服装/发型/配饰和board资产版本；换装不换全局身份。
Same-outfit edits create a new asset revision. Every newly registered identity_board and active
character-look binding requires the exact three-view layout plus hash-bound visual inspection
evidence. Old sheets and original face sources belong in 99-历史, with their original bytes preserved.
They remain historical sources and cannot pass the current board gate merely because they were
previously accepted. Animal and dragon boards follow the same three-view rule.

一部作品跨镜换装时，在已锁定主档版本中登记各look，并导入对应人物板；每镜可以用
`character_looks: {CHAR-GIRL: {look_id: winter, board_asset_id: CHAR-GIRL-WINTER}}`
选择。不填则沿用人物library_binding的默认造型。实际reference_bindings必须传入对应
人物板；选择造型不会自动修改镜头或把另一个造型的板当作正确输入。

voice_profiles收录真实样本及原始确认范围；角色仍只在当前剧本需要说话时配声。
bind-character不会选择随机声线、复制approval或自动确认。选定样本必须与人物voice、
materials音频及真实API槽位一致。跨作品沿用确认须有同一全局身份、同一字节样本和
原确认适用依据；改绑定人物/文件则按人物流程处理。情绪参考不新建声音身份。

湿衣、泥污、伤势、手持物和剧情能力属于作品连续性；场景昼夜/天气可以是地点变体，
不同机位属于同地点views。风格与角色身份分开，原风格引用不会覆盖新作品明确风格。
资产相关性或库内存在不等于API能接收：身份、环境、端点、动作、声音按真实槽位绑定。

## 登记、更新与导入

先用 `templates/asset-library/资产登记.yaml` 准备元数据，再登记真实文件：

```powershell
.venv/Scripts/python.exe tools/资产.py init
.venv/Scripts/python.exe tools/资产.py register <源文件> --spec <资产登记.yaml>
.venv/Scripts/python.exe tools/资产.py register-entity <共享角色版本.yaml>
.venv/Scripts/python.exe tools/资产.py import <作品/project.yaml> --asset <资产ID> --revision 01 --local-id <本地ID>
.venv/Scripts/python.exe tools/资产.py bind-character <作品/project.yaml> --character CHAR-GIRL --entity MEDIEVAL-GIRL --revision 01 --look blue-cloak --board-asset CHAR-GIRL
```

参数是示意，占位符不能直接执行。新建角色仍先用tools/角色.py init建立作品角色，
再导入素材与绑定。`--voice-profile`与`--voice-asset`只选择已存在声线及已配置的本地声音。

登记必须有用途和来源；SHA-256、大小由工具核对，review默认unreviewed。
新导入默认provided；已有素材保留原本ready/provided/rejected和确认依据。
技术检查、实看/试听、用户选定、当前镜头可用分别记录，不设万能approved。
不同版本禁止原地覆盖；更换本地已锁定素材版本须用新的本地asset ID，再明确调整镜头。
角色绑定只允许同一全局身份的明确版本/造型选择；换成另一个角色建立新角色档案。

文件名含中文语义、稳定ID和版本以避免同名不同身份冲突。完整SHA-256相同可共享物理
字节，不据相似度删除文件。同磁盘优先硬链接，跨磁盘独占复制；所有共享链接视为只读，
处理必须另存。工具拒绝覆盖不同内容，索引登记失败只撤回本次创建且未被替换的文件。
进程强停后同内容可恢复登记，不把遗留文件自动标已确认。

生成前materials检查library_ref哈希；runner在编码前捕获版本，再核对实际请求data URL
字节，防止校验后文件被替换。提交记录保存asset_pins。没有library_ref的旧配置与已有
task_id恢复保持原契约。library check只检查文件/哈希，不证明三视图内容或接口效果。
工程/文档可入库、检索并在相应制作计划引用；当前import只接收现有生产清单支持的
图片/音频/视频，不能把.blend当API媒体字段。

## 备份与迁移

projects被Git忽略。迁移前在本作品99-历史记录原配置字节和哈希，06-记录保存迁移结果；
这些记录和硬链接都不是异地备份。独立备份应包含共享库、所有作品使用快照、元数据和
媒体实际内容；恢复后运行library/project check核验。当前不自动配置云盘或定时备份。
废弃版本先标记录并查uses，不自动删媒体。原任务配置、用户确认原文、已提交任务和
已接受成片不因接入资产库重写或重生成。
