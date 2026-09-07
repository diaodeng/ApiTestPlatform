# 2026-09-05 - 补齐工单处理案例人工确认 UI 入口

## 变更背景

工单相似处理案例的后端能力已完整（草稿自动生成、状态接口 `POST /ticket/{id}/similarity-case/status`、案例向量索引），但前端没有任何页面调用案例状态接口，案例只能停留在草稿状态，无法人工确认为已验证（verified）或驳回（rejected），导致"处理案例相似"召回长期只有草稿级可信度，确认链路断头。

## 变更内容

### 1. 后端：轻量概览透出当前工单案例摘要

- `server/modules/ticket/entity/vo/ticket_read_vo.py`：`TicketSummaryModel` 新增 `similarityCase` 字段（新模型 `TicketSimilarityCaseSummaryModel`），白名单字段：案例状态、来源、版本、可复用标记、根因/方案/证据/排查/验证摘要、确认与驳回人和时间、驳回原因、向量索引状态与错误。
- `server/modules/ticket/service/core/ticket_read_service.py`：`get_summary` 组装链路新增 `_attach_similarity_case`，读取当前工单案例记录；无案例时返回 `{ caseStatus: "none" }`。

### 2. 前端：相似面板新增"当前工单案例"区块

- `web/src/views/ticket/components/detail-shared/TicketSimilarPanel.vue`：
  - "处理案例相似"卡片顶部新增当前工单案例区块：状态标签（草稿/已验证/已驳回/未形成案例）、版本、确认人/驳回人、根因与方案摘要、向量索引状态说明（pending/ready/failed/skipped 文案化）。
  - 新增操作按钮（均受 `ticket:similarity:case` 权限控制，通过 `allowCaseAction` 控制显示）：确认案例（根因+方案+证据/验证不完整时禁用）、回退草稿（仅已验证状态显示）、驳回案例（需要填写驳回原因）。
- `web/src/views/ticket/components/detail-tabs/TicketDetailOverviewTab.vue`：转发新 props 和 `case-action` 事件。
- `web/src/views/ticket/components/TicketDetailWithList.vue`（工单列表详情弹窗，主要操作入口）：
  - 实现 `handleCaseAction`：驳回需填写原因（window.prompt），操作前二次确认，成功后同时刷新概览与相似结果（后端在状态变更时已失效相似缓存）。
- `web/src/views/ticket/components/TicketDetailView.vue`（独立只读详情页）：仅展示案例状态信息，不提供写操作，与页面只读定位一致。

## 交互说明

- 确认案例按钮在校验不通过时禁用，并提示"确认案例需要根因、解决方案以及证据或验证方式"。
- 案例状态变化后自动刷新概览与相似工单，用户无需手动刷新。
- 权限：操作按钮走 `v-hasPermi="['ticket:similarity:case']"`，与后端接口权限一致；未授权用户在确认/驳回按钮处不可见（回退草稿同理）。

## 验证

- 后端：改动文件 `ruff check` 通过；Pydantic 模型 camelCase 序列化单测验证通过（含 `caseStatus/verifiedBy` 别名输出）。
- 前端：`npm run build:prod` 通过。
- 未在浏览器端实际点击验证（需部署环境），剩余风险：`window.prompt` 驳回原因输入为原生弹窗，样式与 Element Plus 对话框不一致，后续可升级为 ElMessageBox.prompt。
