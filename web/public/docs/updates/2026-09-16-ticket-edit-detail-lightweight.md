# 2026-09-16 - 工单编辑弹窗打开慢治理（轻量编辑详情接口）

## 问题现象

工单列表点击"编辑"后弹窗迟迟不出现：前端 `handleUpdate` 调用旧全量详情接口 `GET /ticket/{ticket_id}`，等接口返回后才打开弹窗。该接口除了工单本体，还会同步执行相似工单检索（向量缺失时同步外呼 Embedding API、全量向量表扫描、候选逐条补查约 300 条小 SQL）、全量消息流和全量 ACR 快照，而这些数据编辑表单一个都不用，属于纯浪费。日志拉取管理页选择工单预填参数时也走的同一个重接口。

## 变更内容

- 后端新增轻量编辑详情接口 `GET /ticket/{ticket_id}/edit-detail`（权限沿用 `ticket:ticket:query`）：
  - 只返回编辑表单需要的字段：工单本体、项目/模块业务码、四类版本 ID 与展示名、处理人、问题分类、工单类型、`tags`、`categoryName`、`problemPatternVerified`、`extraData`（编辑弹窗从中还原日志拉取/自动翻译配置）、`originalDescription`/`aiTranslation`，以及最近一次日志拉取摘要（供日志拉取管理页预填兜底）。
  - 不读取消息、快照、相似工单、AI 提示词分层、AI Token 统计。
  - 全部 BIGINT 主键与关联 ID（工单、项目、模块、分类、问题实例、提单人、处理人、四类版本）以字符串返回，避免超出 JavaScript 安全整数导致前端精度失真。
- 新增白名单响应模型 `TicketEditModel`（`server/modules/ticket/entity/vo/ticket_read_vo.py`），查询逻辑在 `TicketReadService.get_edit_detail`（`server/modules/ticket/service/core/ticket_read_service.py`）。
- 前端：
  - `web/src/api/ticket/ticket.js` 新增 `getTicketEditDetail`。
  - 工单列表 `handleUpdate` 改用新接口回填编辑表单；编辑弹窗"所属项目"下拉的 option value 统一转为字符串，与接口返回的字符串 ID 匹配（模块下拉原本就是字符串、版本下拉后端本就返回字符串 ID，无需调整）。
  - 日志拉取管理页选择工单预填改用新接口。
- 字符串 ID 回传：更新接口 `TicketUpdateModel` 按 Pydantic 宽松模式把字符串解析回整数（已验证 `ticket_id/project_id/first_line_assignee_id/affected_version_id` 等字段），前端无需对这些 ID 使用 `Number()`。

## 兼容说明

- 旧完整详情接口 `GET /ticket/{ticket_id}` 契约保持不变，前端已无调用方，后续可评估精简其内部组装或废弃。
- 编辑表单回显字段与改造前一致（逐字段核对过 `createDefaultTicketForm` 与 `handleUpdate` 回填逻辑，补齐了旧全量接口有而轻量概览缺的 `tags`、`categoryName`、`problemPatternVerified` 三个字段）。

## 验证过程

- 后端：改动文件 `ruff check` 通过；按应用导入顺序验证模块导入、路由注册（`/ticket/{ticket_id:int}/edit-detail` 已挂载）、`TicketEditModel` 白名单校验、`TicketUpdateModel` 字符串 ID 解析均正常。
- 前端：`npm run build:prod` 构建通过（37.7s 无错误）；确认两个旧 `getTicket` 调用点已全部切换、无残留引用。
- 编辑回显链路逐字段核对：`handleUpdate` 用到的 `originalDescription`、`extraData.originDescription`、`extraData.ticketAutomation.logPullConfig`、`extraData.manualAutomation.autoTranslate`、版本 ID、处理人、`problemPatternVerified`、`tags` 均由新接口覆盖；日志拉取管理页预填的 `extraData` 来源链与 `latestLogPull` 兜底均覆盖。

## 剩余风险

- 建议实施后用带标签、问题分类、细分问题类型勾选的工单做一次编辑保存回归，确认回显与提交正常。
- 相似检索子系统自身的性能问题（向量缺失时同步外呼 Embedding、全量向量扫描、候选重排 N+1 补查）仍在，独立接口 `/ticket/{id}/similar-tickets` 与相似度重建功能使用时依旧会慢，需另行治理。
- 旧全量详情接口 `GET /ticket/{ticket_id}` 前端已无调用方，若确认无外部脚本依赖，可后续移除其消息/快照/相似组装逻辑。

## 相关说明

- [工单轻量读取接口](../../../server/docs/ticket_read_api.md)
- [工单详情页使用说明](../ticket_detail.md)
