# 2026-08-28 工单AI分析结果校验修复

## 问题背景

工单 INC00001894981（task_2044228725283840，prod 环境）AI 分析执行约 24 分钟后失败，错误码 `AI_WORKER_RESULT_INVALID`。

排查确认：AI Worker（codex）正常退出并产出了完整的分析结果，但结果中 `similar_cases` 字段为叙述字符串（"历史相似工单 INC00001789443…"），而输出 Schema 只允许数组类型，导致 JSON Schema 校验失败，整个结果被丢弃。同 Schema 中 `symptom`、`sop_suggestion` 等其他增强字段均为 `array/string` 双类型容忍，唯独 `similar_cases` 只允许 `array`。

## 修复内容

### Schema 放宽（服务端）

- `_build_result_schema` 中 `similar_cases` 类型从 `"array"` 放宽为 `["array", "string"]`，与其他增强字段保持一致。
- Schema 随任务下发给 Agent，落盘为任务工作区的 `result.schema.json`。

### 结果归一化兜底（服务端）

- `_normalize_analysis_result` 新增增强字段类型包装：`symptom`、`investigation_steps`、`prevention_actions`、`similar_cases`、`sop_suggestion`、`monitoring_suggestion` 若为字符串，统一包装为单元素数组，保证写回 RCA 结构化数据和前端展示时类型稳定；空字符串包装为空数组；数组输入保持不变。

### 失败诊断增强（服务端 + 客户端）

修复前失败日志中 `diagnostics: []` 为空，无法知道具体哪个字段违规，需要人工比对 result.json 与 schema。

- 服务端新增 `_collect_schema_violations`：按校验规则收集全部违规路径（如 `$.similar_cases: 期望 array，实际 string`），`_validate_analysis_result_schema` 改为其布尔包装，行为不变。校验失败时 FAIL 日志和 error_message 均包含违规明细（最多 10 条），error_message 会写入任务记录并在 Web 页面展示。
- 客户端（client_new）新增 `_collect_json_schema_violations`（与服务端同规则）：Worker 正常退出但结果不可用时，Agent 侧先做校验收集，违规明细以 `AI_WORKER_SCHEMA_VIOLATION` 诊断项随 `ai_analysis_error` 事件上报服务端；连 JSON 都解析不出时，以 `AI_WORKER_RESULT_UNPARSEABLE` 诊断项上报原始文本前 200 字符，便于判断是否为模型自由文本输出。
- 客户端新增 `_resolve_worker_result_text`：按 Provider 输出模式提取原始结果文本，供解析和诊断共用，避免重复实现。

## 涉及文件

- `server/modules/ticket/service/ai/ticket_ai_analysis_service.py` — Schema 放宽、归一化包装、违规收集与失败信息增强。
- `client_new/services/ticket_ai_analysis_service.py` — 校验违规收集、失败诊断上报、结果文本提取方法。
- `server/tests/test_ticket_ai_analysis_prompt.py` — 新增 3 个回归用例：similar_cases 字符串被接受、违规字段明细输出、归一化字符串包装。

## 验证结果

- 服务端 ruff 检查通过；`test_ticket_ai_analysis_prompt.py` 8 个用例全部通过。
- 客户端 `py_compile` 编译检查通过；违规收集逻辑用真实失败数据验证输出 `$.similar_cases: 期望 array，实际 string`。
- 用 INC00001894981 真实失败的 result.json 端到端验证：旧 Schema 精确报出违规字段；新 Schema 校验通过；归一化后 `similar_cases` 变为单元素数组。

## 注意事项

- 本次修复后重新发起分析会生成新 Schema（类型放宽），历史任务工作区的 `result.schema.json` 不回改。
- 服务端和客户端校验器为双份防线：Agent 侧先拦截并上报明细；即使 Agent 侧漏过，服务端仍会再次校验。
- 治理逻辑（业务语义）未变更，仅类型宽容度与失败信息可见性调整。
