# API 适配说明

服务地址：`https://autodl.art`。生成和结果查询见
[官方说明](https://autodl.art/docs/comfyui_api/)。

| 方法 | 路径 | 用途 | 鉴权 | 自动重试 |
|---|---|---|---|---|
| POST | `/api/v1/comfyui/workflows` | 网页目录查询，Body 为 page_size/page_index | 无 | 是，只读查询 |
| GET | `/api/v1/comfyui/workflows/{workflow_id}` | 网页工作流详情、input_rules、价格、说明 | 无 | 是 |
| POST | `/api/v1/comfyui/comfyui_workflow/{workflow_id}` | 提交生成任务 | 原始 Token | 否 |
| GET | `/api/v1/comfyui/comfyui_workflow/result/{task_id}` | 查询状态与结果 | 原始 Token | 是 |

目录的 `result_total` 用于验证分页完整性，详情必须包含匹配的 uuid 和 input_rules。
目录与详情是网页内部使用的公开接口，并非官方承诺稳定的模型发现协议。
失败时保留旧目录；结构变化需更新客户端。

发送 `inputs` 作为 JSON Body，YAML 的 workflow_id/output_dir/预算不发送。
必填、数值范围、类型、文本长度和枚举均按工作流实时 input_rules 校验。
媒体枚举填写 `options[].label`，不能把其内部 `values` 节点映射当作参数值发送。
`default_local_path:` 表示服务端占位默认资源，不能用来代替用户必须提供的素材。

官方总文档使用 `QUEUED`、`RUNNING`、`SUCCESS`、`FAILED`；网页输出示例使用 `completed`。
客户端统一大小写，并兼容 `SUCCEEDED`、`ERROR`、`CANCELLED/CANCELED` 等状态。
未知状态停止等待并保留记录，避免把错误当作成功或无限轮询。

成功 `results` 支持 URL 字符串列表，或含 `url/type/file_type` 的对象列表。
HTTPS 结果通过无 Token 的独立客户端流式下载，保存为任务 ID + 序号，避免采用远程文件名。
每个输出默认最多 2 GiB，可在 Python `download_results(..., max_bytes=...)` 中调整。

已观察到的鉴权拒绝响应与正常业务 envelope 不同：

```json
{"error":{"message":"Invalid authentication credentials","type":"invalid_request_error"}}
```

客户端会显示这个嵌套错误并给出 Token 分组提示，不打印 Token。
401/403 应核对 Token 有效性、ComfyUI 分组和权限；程序不创建或更改凭证。
本机 `.env` 的 `autodl_apikey:...` 已兼容，发送前会去除变量名前缀。
正确提取令牌后已观察到 HTTP 403，错误类型为 `permission_denied`，
消息为 `This token does not have permission to access ComfyUI APIs`，表示缺少该接口权限。
HTTP 408、5xx、连接中断及无法解析的成功提交响应都按“可能已提交”处理，不自动再发生成请求。

H3 公开计费字段 `price=40` 对应页面显示的 ¥0.040/秒；估价取高峰/空闲价格较大值，
乘以明确时长并换算成人民币。该检查不提供平台锁价保证。
语音及按输入视频时长计费的模型需另外知道实际时长，本版本不编造预算估计。
