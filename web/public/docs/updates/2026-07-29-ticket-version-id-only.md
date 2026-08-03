# 工单版本中心仅 ID 关联改造

## 变更结论

工单、AI 仓库映射和 AI 分析任务不再保存版本文本作为关联依据，只保存 `ticket_version.version_id`。版本名称、版本标识和分支等展示信息均由版本中心查询获得。

## 输入边界

外部同步、Excel 导入和日志解析仍可能得到版本文本。该文本只在当前处理过程中用于创建或匹配 `discovered` 候选版本，随后仅回写版本 ID；不会写入 `ticket` 或 `extra_data`。

## 数据库部署

按顺序执行：

1. `server/sql/20260729_ticket_version_center.sql`
2. `server/sql/20260729_ticket_version_id_only.sql`

第二个脚本会先回填工单、AI 映射和 AI 任务的版本 ID，并输出三项预检结果。预检存在记录时必须先人工补齐或删除对应历史记录，不能继续执行删列 DDL；预检通过后 AI 映射和 AI 任务的 `version_id` 都会设为非空。

若历史 `ticket` 文本列与新建 `ticket_version.version_key` 的排序规则不同，脚本已在跨表版本比较中统一使用 `utf8mb4_unicode_ci`，避免 MySQL 报 `Illegal mix of collations`。

## 行为约束

- 批量版本维护、状态流转、工单编辑和 AI 分析请求仅提交版本 ID。
- AI 仓库映射以 `project_id + version_id` 唯一。
- 发布记录仍只登记发布事实，不会自动关闭工单。
- 版本列表查询在服务层保留 `TicketVersion` ORM 实体，版本列表组合数据使用 `TicketVersionListItem` dataclass；版本选项、列表和发布记录接口均使用 Pydantic 契约。
- AI 仓库映射列表同样在服务层保留 `TicketAiRepoMapping` ORM 实体，使用 `TicketAiRepoMappingListItem` dataclass 反查版本中心，再输出 Pydantic 响应模型。
- 版本选项响应模型启用 `populate_by_name`：服务层可使用 snake_case 字段构造，HTTP 响应仍统一输出 camelCase，避免别名校验影响工单编辑、详情和仓库映射页面。
- 迁移生成的版本 ID 可能超过 JavaScript 安全整数范围；所有版本中心关联 ID 在 HTTP 响应中统一为字符串，前端提交时原样传回，由后端 Pydantic 解析为整数。
