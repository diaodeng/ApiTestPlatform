# 2026-06-11 工单汇总数据源与自动分类工具增强

## 变更目标

1. 工单汇总通知支持统计数据源切换（本地 / 飞书多维表格）。
2. 汇总统计支持 AI 解读，并允许自定义提示词编码。
3. 同步配置页增加自动分类工具：一键统计未归类、按策略批量重归类、强制全量重归类。

## 后端改动

- `server/modules/ticket/service/ticket_sync_notify_service.py`
  - 新增汇总数据源归一化：`_normalize_summary_data_source`。
  - 新增汇总配置校验：`_validate_summary_report_config`。
  - 汇总统计拆分为两条数据链路：
    - `_collect_ticket_summary_from_local`（本地工单）
    - `_collect_ticket_summary_from_bitable`（飞书多维表格）
  - 新增汇总 AI 解读能力：
    - `_build_summary_ai_user_prompt`
    - `_build_summary_ai_text`
  - `run_ticket_summary_report` 支持：
    - `dataSource=local/bitable`
    - `aiEnabled/aiProviderCode/aiPromptCode`
    - 模板变量 `${data_source}` `${ai_summary}`
    - 配置缺失时返回 `skipped + skipReason`。

- `server/modules/ticket/service/ticket_sync_service.py`
  - 继续复用已扩展的 `summaryReport` 字段归一化（含 `dataSource`、多维字段、AI 字段）。

- `server/modules/ticket/controller/ticket_controller.py`
  - 继续复用已新增接口：
    - `GET /ticket/sync/auto-category/stats`
    - `POST /ticket/sync/auto-category/reclassify`

## 前端改动

- `web/src/views/ticket/syncAutomation/index.vue`
  - 汇总统计配置新增：
    - 数据源选择（本地 / 多维表格）
    - 多维字段配置（`appToken/tableId/viewId/filterFormula/statusField/categoryField/priorityField/bitableTimeField/pageSize`）
    - AI 配置（`aiEnabled/aiProviderCode/aiPromptCode`）
  - 新增“自动分类管理”卡片：
    - 一键统计未归类工单
    - 按当前策略批量重归类（AI/正则）
    - 强制重归类全部工单
  - 批量重归类支持正则规则 JSON 编辑（`pattern/category/flags`）。

- `web/src/api/ticket/ticket.js`
  - 新增 `getTicketSyncAutoCategoryStats`。

## 兼容性说明

1. 旧配置不含新字段时，后端会回填默认值，不影响已上线配置读取。
2. 未开启 AI 解读或未配置 AI 参数时，汇总仍可发送，`ai_summary` 自动回退为跳过说明文本。
3. 多维表格模式必须配置 `appId/appSecret + appToken/tableId`，否则执行结果返回 `skipped`。
