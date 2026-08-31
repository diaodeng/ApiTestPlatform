# 2026-08-31 工单AI分析结果未转义引号修复

## 问题背景

工单 INC00001904725 第二次分析失败（task_2045268316707840，prod 环境，Agent 日志 2026-08-31 17:28）。此前 2026-08-28 已修复 `similar_cases` 的 Schema 类型放宽问题，本次为同一工单的新失败原因。

注意：本次任务的 Provider 为 `openai_com`（`https://api-ai.dmall.com/v1`，模型 `deepseek-v4-flash`），与上次失败的 `shuidi` Provider 不同。

## 问题现象

- Worker（codex）正常退出（return_code=0，耗时 440 秒）并产出了内容完整的 `result.json`。
- 任务失败，错误码 `AI_WORKER_RESULT_INVALID`，诊断项 `AI_WORKER_RESULT_UNPARSEABLE`，附带的原始文本预览以 ` ```json ` 开头。
- 分析结果未写回工单，页面显示"AI Worker 已正常退出，但结果无法解析或未通过 JSON Schema 校验"。

## 根因

`result.json` 虽然带 ` ```json ` 围栏（该情况已有围栏剥离兜底），但剥离后内容仍不是合法 JSON：`root_cause` 字符串值内部输出了未转义的英文双引号（`停留在"恢复中"（Pending）状态`），`json.loads` 在第 7 行第 113 列报 `Expecting ',' delimiter`。deepseek-v4-flash 模型即使收到 `--output-schema` 约束也没有遵守 JSON 字符串转义规则。

## 修复内容

### 未转义引号修复兜底（Agent 客户端 client_new）

- 新增 `_repair_unescaped_quotes`：对已剥离围栏的 JSON 文本做一次结构化扫描——处于字符串内部、且后面不紧跟 `, } ] :` 结构符的引号，判定为值内部未转义引号，补 `\"` 转义；修复结果必须能通过 `json.loads` 且为 dict 才被采纳。
- `_extract_json_from_text` 在常规解析（围栏剥离、花括号截取）全部失败后调用该兜底，修复成功才返回结果，否则保持返回 `None` 的原行为。

### 提示词约束（服务端 + 客户端）

- 两端分析提示词第 5 条新增：JSON 字符串值内部的英文双引号必须写成 `\"` 转义；引用中文术语使用中文引号（“”）。从源头减少模型输出非法 JSON 的概率。

### 数据流确认

- Agent 端 `_parse_worker_output`：直接解析失败后走 `_extract_json_from_text`，修复后的结果仍会经过 Schema 校验（`accept_candidate`），校验防线未被绕过。
- 服务端 `_read_json_file` 仅读取服务端自产的 `context.json`，不读 Worker 结果文件，无需同步修改。

## 涉及文件

- `client_new/services/ticket_ai_analysis_service.py` — `_repair_unescaped_quotes` 新增、`_extract_json_from_text` 兜底接入、提示词约束。
- `server/modules/ticket/service/ai/ticket_ai_analysis_service.py` — 提示词约束。
- `client_new/tests/test_ticket_ai_json_quote_repair.py` — 新增 5 个回归用例。

## 验证结果

- 用 INC00001904725 真实失败的 `result.json` 端到端验证：`_parse_worker_output` 完整链路解析成功（14 个字段），`root_cause` 中 `停留在"恢复中"（Pending）状态` 被正确保留，且通过该任务的真实 Schema 校验。
- client_new 新增 5 个回归用例全部通过；既有 27 个 AI 相关测试全部通过。
- client_new `py_compile` 通过；server `ruff check` 通过；server `test_ticket_ai_analysis_prompt.py` 5 个用例通过。

## 注意事项

- 修复生效需要更新并重启本机 Agent（client_new）；服务端提示词变更在下次部署后对新生成的 prompt 生效。
- 修复只处理"字符串值内部未转义引号"这一类可确定性修复的损坏；其他形式的 JSON 损坏（截断、缺括号等）仍会按原逻辑失败并上报诊断。
- 该工单的分析内容（root_cause 等）当时已完成但被丢弃，修复部署后在页面对该工单重新发起 AI 分析即可（重试会复用工作区，若工作区 result.json 仍非法则会重新启动 Worker）。
