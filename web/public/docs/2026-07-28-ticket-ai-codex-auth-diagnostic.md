# 工单 AI Codex 鉴权故障诊断增强

## 结论

工单 AI Agent 在 Codex Worker 执行失败时，现会记录实际 Provider、模型、基础地址和 API Key 的脱敏指纹。若 Worker 输出命中 `401`、`Unauthorized` 或 `Invalid token`，Agent 会额外以同一认证信息调用 `GET /models`，用于区分“认证确实无效”和“仅 Responses 请求链路异常”。

## 诊断范围与安全边界

- 仅在 Worker 未返回可解析结果时写入失败诊断；正常任务不增加外部请求。
- 仅 Codex Worker 命中 401 特征时执行探测，探测接口固定为 OpenAI 兼容的 `GET {base_url}/models`。
- 探测不调用模型推理、不创建分析结果，也不重试原 Worker。
- 日志和任务失败结果只包含 `api_key_present`、`api_key_length`、`api_key_sha256_16` 及 key 来源，不输出 API Key 明文。
- Codex 的实际 key 优先按任务级 `.codex_home/auth.json` 解析；基础地址优先按任务级 `config.toml` 解析，确保诊断与 CLI 实际优先级一致。

## 诊断字段

| 字段 | 说明 |
| --- | --- |
| `provider_type` / `provider_code` | 当前 AI Worker 类型和业务 Provider 编码 |
| `worker_model` | 本次执行指定的模型 |
| `base_url` | 从任务级 Codex 配置解析出的实际请求地址 |
| `api_key_source` | `auth.json.OPENAI_API_KEY` 或环境变量来源 |
| `api_key_*` | 是否存在、长度和 SHA-256 前 16 位的脱敏指纹 |
| `auth_probe_*` | `/models` 探测状态、HTTP 状态码和上游请求 ID |

## 排障判读

- Worker 401 且 `auth_probe_http_status=401`：该地址当前拒绝同一把 key，优先检查 Provider key 权限、有效期或网关配置。
- Worker 401 且 `auth_probe_http_status=200`：key 在探测时有效，优先携带 Worker 原始 request ID、探测 request ID 和时间范围请 Provider 排查 Responses 链路的瞬态认证、缓存或策略问题。
- `auth_probe=failed`：网络、TLS、代理或 Provider 不支持 `/models`，不能据此判定 key 有效性；保留 Worker 原始错误继续排查。

## 验证

- 单元测试覆盖：任务级 `auth.json` 优先级、密钥脱敏、401 特征匹配，以及 `/models` 探测的请求头和结果归一化。
- 测试不访问真实 Provider，也不会写入任何真实密钥。

## 回滚

如需停止额外诊断，可移除 `TicketAiAnalysisService` 中 Worker 失败分支对 `_build_worker_auth_diagnostic` 和 `_probe_codex_authentication` 的调用。回滚后不会影响正常 Codex 执行，但 401 将再次只保留 CLI 原始错误，无法自动区分 token 无效与接口链路异常。
