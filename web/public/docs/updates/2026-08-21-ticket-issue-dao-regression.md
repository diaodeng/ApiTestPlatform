# 2026-08-21 - 问题实例详情查询回归修复

## 修复

- 恢复 `TicketIssueDao.list_tickets_by_issue_id`，修复问题实例详情、编辑回填和绑定工单区域因缺少 DAO 方法而返回 `TicketIssueDao has no attribute list_tickets_by_issue_id` 的问题。
- 保留新增的工单号搜索 DAO 方法，问题详情继续按 `ticket.issue_id` 查询有效绑定工单。

## 影响范围

- 问题实例列表详情
- 问题实例编辑
- 问题实例绑定工单区域
