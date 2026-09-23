# 配置任务前端页面、录制转模板与定时触发切片

## 变更

### 前端（web/src/views/hrm/configuration-task/）
- `index.vue`：任务管理 + 运行记录双 Tab 页面入口；
- `TaskTab.vue`：任务列表、新增/编辑（变量 JSON 编辑）、版本/运行/定时/录制转换入口；
- `VersionDrawer.vue`：版本列表（状态、输入绑定摘要）、新建草稿、步骤 JSON/输入绑定/变量编辑器、发布确认；
- `StageEditor.vue`：阶段切分编辑（模式选择、步骤索引区间，仅草稿可改）；
- `RunConfirmDialog.vue`：运行参数（Agent/版本/手动登录/超时）确认；
- `ScheduleDialog.vue`：定时配置（开关、cron、版本、Agent，附定时任务创建指引）；
- `ConvertDialog.vue`：录制 ID + 变量标记 + fileKey 标记转模板；
- `RunDetailDrawer.vue`：运行信息、阶段列表（审批通过/拒绝、重试）、步骤结果、产物清单、报告生成（可通知飞书）；
- `web/src/api/hrm/configuration_task.js`：全部接口封装。

### 后端
- `service/task_schedule_service.py`：`ConfigurationTaskScheduleService`（调度配置存任务 remark 的 `@schedule:` 受控 JSON 段，启用校验已发布版本/Agent/cron；`trigger_scheduled_run` 同步执行一次运行，未启用时跳过）与 `ConfigurationTaskTemplateService`（复用 `WebCaseService.recording_detail_services` 重建步骤，按 mark_variables 替换 fill/select 值为 `${var}`、按 upload_file_keys 标注 fileKey，生成 DRAFT 版本）；
- `module_task/scheduler_configuration.py`：定时任务入口 `trigger_configuration_task_run`（task_id 必填，agent_code/version_no 可覆盖；停止标记检查；SessionLocal 短会话）；
- `task_run_service.execute_run_sync`：无事件循环场景（定时线程）的同步执行入口（asyncio.run 包装）；
- 新增路由：`POST /templates/from-recording`、`GET/PUT /{taskId}/schedule`。

## 边界

- 运行记录 Tab 需按任务 ID 查询（后端运行列表接口为任务维度，全量跨任务查询未提供）；
- 定时配置保存在任务 remark，与备注文本共存；凭证/变量等敏感内容不放入 remark；
- 定时触发依赖调度器中人工创建定时任务（页面有指引），未自动注册 cron；
- 前端页面需通过系统菜单管理挂载路由后可见（组件路径 `hrm/configuration-task/index`）。

## 验证

- 新增 6 项调度测试：cron 校验、配置往返、未发布版本拒绝、缺 cron 拒绝、未启用跳过、启用后完整触发（triggerType=scheduled 且终态 SUCCESS）；全量相关 51 项测试通过。
- 前端生产构建通过；Ruff/编译通过。
