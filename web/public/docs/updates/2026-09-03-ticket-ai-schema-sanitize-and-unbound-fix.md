# 2026-09-03 工单AI分析结果schema清洗与失败分支崩溃修复

## 问题背景

工单 INC00001920244 第二次分析失败（task_2046322511408128，prod 环境，Agent 日志 2026-09-03 17:19）。此前 2026-08-28 已放宽 `similar_cases` 类型、2026-08-31 已修复未转义引号问题，本次为同一系列（deepseek-v4-flash 不遵守输出约束）的新失败形态。

本次任务 Provider 为 `shuidi`（`https://ai-router.dmall.com/v1`，模型 `deepseek-v4-flash-0731`）。

## 问题现象

- Worker（codex）正常退出（return_code=0，耗时 742 秒）并产出了内容完整的 `result.json`（根因、证据、修复建议完整）。
- Agent 端任务失败，错误码 `AI_WORKER_RESULT_INVALID`，诊断项 `AI_WORKER_SCHEMA_VIOLATION`：
  - `$.ticket_no`、`$.merchant_name`、`$.version`、`$.root_cause_type` 为 additionalProperties 不允许的额外字段；
  - `$.evidence[0..5]` 期望 string，实际 object。
- 随后 Agent 抛出 `UnboundLocalError: cannot access local variable 'invalid_result_token_usage'`，错误码被覆盖为 `AI_WORKER_EXECUTION_ERROR`，失败原因被二次异常掩盖。

## 根因

1. **Schema 违规**：deepseek-v4-flash 经 ai-router 中转时，codex 的 `--output-schema` 未真正约束模型输出。模型在 schema 外自行附加了工单号、商家名、版本号、根因分类字段，并把每条证据写成了 `{source, content}` 对象数组（与提示词要求的"字符串数组"不符）。结果内容本身质量完好，仅结构不符合约定。
2. **UnboundLocalError**：`client_new/services/ticket_ai_analysis_service.py` 的"结果无效"分支中，`invalid_result_token_usage` 在第 3648 行才赋值，而第 3639 行 `report_task_span` 已先使用该变量，任何走到该分支的任务都会触发 `UnboundLocalError`，导致真实失败原因（schema 违规）被二次异常覆盖。

## 修复内容

### 结果清洗（schema 校验前的保守归一化）

新增纯函数清洗逻辑，在 schema 校验前执行，只处理"模型真实意图明确"的结构偏差：

1. 剔除 `additionalProperties=False` 时 schema 之外的额外字段（如 ticket_no）；
2. evidence 元素为 `{source, content}` 对象时拼接为 `"source: content"` 字符串；
3. evidence 元素为其他非字符串类型（数字、null 等）时 JSON 序列化为字符串，保留信息。

清洗动作会写入日志（如 `$.ticket_no: 已剔除 schema 外额外字段`），便于审计。清洗后仍需通过完整 schema 校验，校验防线未被绕过；明显非法的结果依旧按原逻辑失败并上报诊断。

### UnboundLocalError 修复

Agent 端"结果无效"分支调整为：先提取 `invalid_result_token_usage`，再上报可观测 span，最后返回失败结果，消除"先使用后赋值"。

### 提示词约束加固（服务端 + Agent 端）

两端分析提示词第 6 条新增：

- 除 schema 字段外禁止输出任何其他字段（明确点名 ticket_no、merchant_name、version、root_cause_type）；
- evidence 必须是字符串数组，每条格式为"来源文件路径:行号: 证据内容摘要"，禁止写成 `{source, content}` 对象。

## 涉及文件

- `client_new/services/ticket_ai_result_schema_service.py` — 新增，Agent 端结果清洗服务（`TicketAiResultSchemaService`）。
- `client_new/services/ticket_ai_analysis_service.py` — UnboundLocalError 修复；`_parse_worker_output.accept_candidate` 与 `_load_cached_result` 在校验前接入清洗；提示词约束。
- `server/modules/ticket/util/ticket_ai_result_schema_util.py` — 新增，服务端结果清洗 util（`TicketAiResultSchemaUtil`，与 Agent 端同规则）。
- `server/modules/ticket/service/ai/ticket_ai_analysis_service.py` — Agent 回传结果在 `_validate_analysis_result_schema` 前接入清洗；提示词约束。
- `client_new/tests/test_ticket_ai_result_schema_sanitize.py` — 新增 6 个回归用例。

## 数据流确认

- Agent 端清洗发生在 `_parse_worker_output` 的 `accept_candidate` 内，清洗后仍走 `_validate_json_schema`，防线未被绕过；缓存命中路径（`_load_cached_result`）同样先清洗再校验，历史无效结果可被挽救复用。
- 服务端清洗发生在 Agent 回传解析之后、`_normalize_analysis_result` 与 schema 校验之前；服务端 `additionalProperties` 校验规则与 Agent 端一致，两端清洗规则完全相同。
- 清洗仅影响内存中的结果对象，不回写工作区的 `result.json` 原始文件（原始输出保留供审计）。

## 验证结果

- 用 INC00001920244 真实失败的 `result.json` 验证：清洗前 12 条 schema 违规（与线上日志一致），清洗后 0 条违规，`_parse_worker_output` 完整链路解析成功，`ticket_no` 等额外字段被剔除，evidence 全部转为字符串。
- 边界用例通过：仅 content 无 source、数字/None 元素、已合规结果（零清洗动作）、schema 要求对象时不误清洗。
- client_new 新增 6 个回归用例全部通过；既有 AI 相关测试（引号修复、失败契约、鉴权诊断、token 用量、可观测、Codex 配置、任务取消、锁心跳）全部通过。
- server `ruff check`（新增 util + 主服务文件）通过；server 既有提示词测试 5 个用例通过；client_new 新增文件 ruff 通过（主服务文件 72 个违规均为存量问题，stash 基线对比确认非本次引入）。

## 注意事项

- 修复生效需要更新并重启本机 Agent（client_new）；服务端清洗与提示词变更在下次部署后生效。
- 清洗是兜底而非豁免：模型输出的内容性错误（根因错误、证据不实等）不会被清洗掩盖；清洗动作有日志可审计。
- 若后续 ai-router 修复了 `--output-schema` 透传问题，模型输出会天然合规，清洗逻辑自动成为无操作（零清洗动作）。
