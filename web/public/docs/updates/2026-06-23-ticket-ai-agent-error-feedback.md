# 2026-06-23 工单 AI Agent 异常反馈修复

## 背景

发起工单 AI 分析时，如果指定 Agent 未连接服务端或连接异常，后台任务会失败并记录 `error_message`，但页面提交后只看到“任务已提交”。部分接口异常对象还会被前端直接展示成 `{}`，导致无法判断真实失败原因。

## 变更

1. `TicketAiAnalysisService.create_analysis_task_services` 在创建任务前校验实际解析到的 Agent 是否在线。
2. 指定 Agent 未连接时，接口直接返回 `Agent[xxx]未连接服务端，请先启动本地 Agent 并确认连接正常`，不再创建必然失败的后台任务。
3. 工单页提交或重试 AI 分析后，会短轮询本次任务终态；若后台快速失败，立即弹出任务 `errorMessage`。
4. 前端全局请求拦截器新增错误文案归一化，优先读取 `msg/message/errorMessage/detail`，避免对象型异常显示成 `{}`。
5. AI 分析提交与重试接口改为页面局部处理错误提示，避免和全局拦截器重复弹窗。

## 影响范围

- 手工发起 AI 分析。
- AI 分析任务重试。
- 全局接口错误提示展示。

## 回滚建议

如需回滚，仅恢复 `server/modules/ticket/service/ticket_ai_analysis_service.py`、`web/src/views/ticket/index.vue` 和 `web/src/utils/request.js` 本次改动即可；数据库结构未变化。
