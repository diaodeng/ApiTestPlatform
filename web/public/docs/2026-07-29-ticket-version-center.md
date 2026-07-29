# 2026-07-29 工单项目版本中心实施说明

## 目标

项目版本中心是工单、发布记录和 AI 仓库映射共同使用的唯一版本来源。工单不再把自由输入的版本文本作为唯一事实，AI 仓库映射也不再独立维护版本集合。

## 数据模型

- `ticket_version`：项目版本主数据。以 `project_id + version_key` 唯一，支持 `discovered`、`confirmed`、`deprecated` 三种状态。
- `ticket_version_release`：版本在环境和批次维度的发布事实。记录计划、实际发布时间、回滚时间、CI/CD 链接和说明。
- `ticket`：仅保存 `affected_version_id/planned_fix_version_id/fixed_version_id/released_version_id` 四个版本中心关联字段。
- `ticket_ai_repo_mapping`：新增 `version_id`，仓库、分支和 Worker 配置仍归映射表维护。

## 自动发现规则

Excel 导入、外部同步和日志提取会在输入边界解析版本文本；手工新增/编辑和版本批量维护直接提交版本 ID：

1. 按项目和规范化版本号查询 `ticket_version`。
2. 已存在时回写对应 `*_version_id`。
3. 不存在时创建 `lifecycle_status=discovered` 的候选版本，并保留来源和首次发现工单。
4. 候选版本不会自动创建 AI 仓库映射或发布记录，由版本管理员在版本管理页确认和维护。

工单编辑和批量版本维护仅提供版本中心下拉选项，不再允许在界面自由创建版本。

## 发布与关单

“登记发布”只写入 `ticket_version_release`，不会修改关联工单的流程状态，也不会自动关闭工单。发版后的工单应进入待验证；验证通过后再按现有工作流关闭。回滚仅登记回滚事实，保留发布历史。

## 接口与入口

- `GET /ticket/versions/list`：版本中心分页查询。
- `GET /ticket/versions/options`：工单和 AI 映射使用的版本选项。
- `POST/PUT /ticket/versions`：维护版本主数据。
- `GET /ticket/versions/{versionId}/releases`：查看版本发布历史。
- `POST/PUT /ticket/version-releases`：登记或更新发布事实。
- 菜单入口：`工单管理 > 版本管理`。

## 数据迁移

依次执行 `server/sql/20260729_ticket_version_center.sql` 和 `server/sql/20260729_ticket_version_id_only.sql`。第二个脚本回填 ID、预检未关联数据后删除旧文本列。

## 验证

- 后端：`uv run --with pytest python -m pytest tests/test_ticket_version_service.py tests/test_ticket_release_service.py`。
- 静态检查：`uv run ruff check` 覆盖版本中心及其接入文件。
- 前端：执行生产构建，确认版本管理页面与接口模块可编译。
