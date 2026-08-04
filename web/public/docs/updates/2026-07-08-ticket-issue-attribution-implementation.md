# 工单真实问题实例归因层第二阶段实现记录

## 背景

2026-07-08 按 `2026-07-07-ticket-status-statistics-and-issue-plan.md` 第二阶段落地“真实问题实例”归因层。第一阶段继续由根因、根因分类、细分问题字段承接分类统计；本阶段新增 Issue 主归因能力，用于回答“多张工单是否属于同一个真实问题实例”和“一个真实问题影响多少工单”。

## 数据模型

新增迁移脚本：`server/sql/20260708_ticket_issue_relation_tables.sql`。

- `ticket_issue`：真实问题实例主表，保存 `issue_no/title/summary/status/severity/project/module/root_cause_type/problem_pattern/owner/first_ticket_id/affected_ticket_count`。
- `ticket` 新增 `issue_id/issue_relation_type/issue_confirmed`，作为工单主归因字段。
- `ticket_relation`：工单补充关系表，只保存相似、重复、相关等辅助关系，不替代 `ticket.issue_id`。

`affected_ticket_count` 只统计 `del_flag = '0'` 的有效工单；解绑工单不会删除 Issue。

## OceanBase 迁移脚本兼容性

2026-07-08 修正 `server/sql/20260708_ticket_issue_relation_tables.sql` 的 OceanBase MySQL 模式执行方式：原脚本通过 `SET @sql = (...)` + `PREPARE/EXECUTE` 做幂等 DDL，在部分 OceanBase 环境会报 `(1149) SQL syntax`，后续继续执行 `EXECUTE stmt` 时连带出现 `(1243) Unknown prepared statement handle`。

当前脚本改为一次性直写 DDL：

- `ticket_issue`、`ticket_relation` 使用 `CREATE TABLE IF NOT EXISTS`。
- `ticket_relation.source` 使用反引号转义为 `` `source` ``，避免工具或方言解析冲突。
- `ticket` 的新增字段和 `idx_ticket_del_issue` 索引用普通 `ALTER TABLE` / `CREATE INDEX` 执行。

如果目标库已部分执行过，先用以下检查 SQL 判断是否需要跳过对应 DDL：

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name IN ('ticket_issue', 'ticket_relation');

SELECT column_name
FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = 'ticket'
  AND column_name IN ('issue_id', 'issue_relation_type', 'issue_confirmed');

SELECT index_name
FROM information_schema.statistics
WHERE table_schema = DATABASE()
  AND table_name = 'ticket'
  AND index_name = 'idx_ticket_del_issue';
```

## 后端分层

- `controller/ticket_issue_controller.py`：新增 Issue 和补充关系 API，控制器只做协议、鉴权、响应转换。
- `entity/vo/ticket_issue_vo.py`：定义 Issue 查询、创建、更新、绑定、相似绑定和补充关系入参。
- `dao/ticket_issue_dao.py`：只做 Issue、工单归因字段、补充关系的查询与持久化。
- `service/issue/ticket_issue_service.py`：负责 Issue 创建、绑定、解绑、从相似工单确认归因、刷新影响工单数。
- `service/issue/ticket_relation_service.py`：负责补充关系创建、确认和删除，不修改主归因字段。

`TicketService` 只在列表和详情返回中附加 Issue 摘要，不作为 Issue 操作门面。

## API

- `GET /ticket/issues/list`
- `GET /ticket/issues/{issue_id}`
- `POST /ticket/issues`
- `PUT /ticket/issues`
- `POST /ticket/{ticket_id}/issue/bind`
- `POST /ticket/{ticket_id}/issue/create-and-bind`
- `POST /ticket/{ticket_id}/issue/bind-from-similar`
- `POST /ticket/{ticket_id}/issue/unbind`
- `POST /ticket/relations`
- `PUT /ticket/relations/{relation_id}/confirm`
- `DELETE /ticket/relations/{relation_id}`

## 前端

- 工单列表新增可选列：问题编号、归因确认、问题标题、归因类型；默认展示问题编号和确认状态。
- 工单详情基础信息展示所属 Issue、归因确认和归因类型。
- 详情页支持“新建问题实例并绑定”和“解除归因”。
- 相似工单卡片新增“归入同一问题”，点击后调用 `bind-from-similar`：相似工单已有 Issue 时复用；没有 Issue 时以相似工单创建 Issue，并绑定当前工单和相似工单。

## 验证

- `python -m py_compile` 已通过本次新增和改动的后端文件。
- `uv run ruff check` 已通过本次新增和改动的后端文件子集。
- `npm run build:prod` 已通过。
- `uv run pytest tests/test_ticket_issue_service.py` 未完成：当前环境 `uv run` 指向 Python 3.6.8，且缺少 `sqlalchemy`，测试收集阶段失败。
- 全量 `uv run ruff check .` 未通过：仓库已有大量历史 lint 问题，本次未做无关清理；本次改动文件子集已单独通过。
