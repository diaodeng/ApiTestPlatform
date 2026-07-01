# 工单列表表头排序

## 背景

工单列表原先固定按本地创建时间倒序排序，不能按表头字段切换排序；业务侧希望默认按提交时间倒序，并支持点击表头按对应字段排序。

## 实现

1. 前端 `web/src/views/ticket/index.vue` 为工单列表表头启用 `sortable="custom"`，点击表头后通过 `sortField/sortOrder` 重新请求服务端分页数据。
2. 默认排序为 `submitTime desc`；清除排序时也恢复为提交时间倒序。
3. 后端 `TicketQueryModel` 新增 `sortField` 和 `sortOrder` 查询参数。
4. 后端 `TicketDao.get_ticket_list` 使用排序白名单映射 SQL 表达式，避免前端传入任意字段参与 SQL。
5. `submitTime` 使用既有提交时间表达式：外部同步 `externalCreateTime` 优先，缺失时回退本地 `create_time`。

## 当前可排序字段

- `ticketNo`：工单编号。
- `title`：标题。
- `status`：流程状态。
- `processStatus`：处理状态，按最新 AI 状态优先、最新日志状态次之。
- `project`：项目名称，当前落库字段为 `merchant_name`。
- `moduleName`：模块名称。
- `issueType`：工单类型。
- `isProblem`：问题性质。
- `rootCauseType`：根因分类。
- `solutionType`：解决方式。
- `resolution`：关闭结果。
- `problemPattern`：细分问题。
- `customerPriority`：对方优先级。
- `internalPriority`：内部优先级。
- `source`：来源。
- `firstLineAssigneeName`：1线人员。
- `internalOwnerName`：内部负责人。
- `currentAssigneeName`：当前处理人。
- `submitTime`：工单提交时间。
- `createTime`：本地创建时间。

## 风险与边界

- 排序作用于服务端分页结果，不是仅排序当前页。
- 项目列沿用历史兼容字段 `merchant_name` 排序；如果后续项目名称独立落库，需要同步调整排序映射。
- 处理状态来自关联子查询，排序会比普通字段略重，但只在列表分页查询中使用。
