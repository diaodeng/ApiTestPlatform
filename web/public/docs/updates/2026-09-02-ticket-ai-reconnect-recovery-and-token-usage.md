---
title: AI分析断链恢复与Token真实消耗记录
---

# AI分析断链恢复与Token真实消耗记录

## 变更日期

2026-09-02

## 变更概述

解决工单 AI 分析在“服务端重启 / 网络断连”场景下的三类问题：

1. **重启后结果丢失**：服务端重启期间 Agent 已执行完成的任务，此前会被直接标记为“服务重启中断失败”，Agent 的执行结果永久滞留在本地工作区。现在 Agent 会把断连期间完成的响应记入本地“待补交清单”，重连成功后自动补交；服务端对没有等待者的迟到响应不再丢弃，而是写入 Redis 结果缓存（保留 24 小时）。服务启动恢复时检测到迟到结果的任务会重新排队并直接写回成功，不再重复调用 Agent。
2. **失败任务 token 显示为空**：Worker 失败、超时、结果无效时模型调用可能已经发生并产生真实消耗，此前这些路径不解析 token，审计记录为空。现在所有失败路径都会尽力从 Codex JSONL 事件流、Claude modelUsage、结果文件、工作区落盘文件中提取已消耗 token，如实写入审计记录。
3. **缓存命中 token 丢失**：Agent 命中本地 `result.json` 缓存直接返回时，此前 `token_usage` 固定为空。现在会从结果 payload、落盘 stdout 事件流中恢复 token 一并返回。

同时修复：AI 分析成功写回的消息/RCA/快照创建者归属任务提交人（此前为 system）；Agent 请求 request_id 写入审计载荷，迟到结果补全、重试对账可按 request_id 关联。

## 用户可见变化

- 服务发布重启后，重启前正在执行的 AI 分析任务：只要 Agent 在重启期间执行完成，任务最终会显示成功（状态描述为“分析成功（恢复服务重启前的执行结果）”），token 如实入库，不需要人工重试。
- 失败的 AI 分析任务在 AI 执行审计中可以看到真实的 token 消耗（如有），不再是空值；确实没有任何凭据时仍为空，表示“消耗未知”而不是 0。
- AI 分析结果消息、RCA、快照的创建者显示为实际提交人。
- Agent 配置页新增“断线重连”开关和“低频间隔”输入框：开启后，高频重试次数用尽仍连不上服务端时，按低频间隔（默认 300 秒）持续重连，直到手动停止。不开启时行为与原来一致。

## 涉及文件

- `client_new/server/agent_server.py`：新增断连待补交清单（`storage/data/pending_response_deliveries.json`）；响应回传失败自动入清单，连接建立后自动补交；永续重连逻辑。
- `client_new/model/config.py`：新增 `retry_forever`、`retry_forever_interval` 配置。
- `client_new/ui/pages/agent_page.py`：Agent 页面新增“断线重连”开关与低频间隔配置项。
- `client_new/services/agent_client_service.py`：传递永续重连配置。
- `client_new/services/ticket_ai_analysis_service.py`：新增 `_parse_failure_token_usage`（失败路径 token 提取）、`_recover_token_usage_from_workspace`（从工作区落盘文件恢复）；缓存命中恢复 token；失败/超时/异常返回携带 `token_usage`；Claude 解析支持接受失败结果报文（仅失败提取路径）。
- `server/module_qtr/controller/agent_controller.py`：孤儿响应分片不再丢弃，攒齐后写入 Redis 结果缓存（`_stash_orphan_response_chunk`）。
- `server/modules/ticket/service/ai/ticket_ai_analysis_service.py`：
  - `resume_pending_tasks` 启动恢复时检测迟到结果缓存，命中任务重新排队而非标记失败；
  - `_load_recovered_agent_response` / `_process_recovered_success` 读取缓存并完成成功写回；
  - 业务失败、结果不可解析路径提取 token 计入审计；
  - request_id 写入审计请求载荷；
  - `_persist_success_result` 写回创建者归属提交人（`_submission_user_placeholder`）。

## 行为边界

- 迟到结果缓存保留 24 小时（与调度侧结果缓存一致），过期后任务仍按“服务重启中断”处理。
- 只有“传输成功且业务成功”的迟到响应才会被恢复写回；失败结果的缓存记录不会被误用。
- 启动恢复按审计 payload 中的 requestId 定位缓存，因此本变更之前的存量任务（审计中没有 requestId）无法自动恢复，仍按中断处理。
- 失败路径 token 提取是“尽力而为”：有明确协议格式的数据（JSONL turn、modelUsage、内嵌 usage）才计入，不从任意文本猜测。
- 待补交清单按 request_id 去重，服务端按同一 request_id 幂等接收；清单上限 200 条，超出丢弃最旧记录。
- “断线重连”开关默认关闭，升级后行为不变；需要最终自愈能力的部署环境建议开启。

## 注意事项

- 服务端与 Agent 都升级后，重启恢复链路才完整：只升级服务端时，Agent 补交机制缺失，迟到结果依赖 Agent 重连窗口内的正常回传；只升级 Agent 时，服务端仍会把孤儿响应丢弃，恢复链路不生效。
- AI 执行审计页面中，恢复写回的任务响应来源为缓存，`command_line` 显示为 `agent:recovered`，可据此识别恢复任务。
