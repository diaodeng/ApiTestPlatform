# 2026-08-11 - 日志拉取停止功能与并发配置

## 新增
- 日志拉取记录新增停止按钮，可停止正在执行中的任务
- 停止采用协作式取消，在下一次检查点生效
- 停止后记录状态标记为已取消，保留已有进度，支持重新拉取
- 停止是否发送通知，遵循记录的通知配置

## 变更
- 日志拉取最大并发数从代码写死 2 改为可配置
- 配置路径：工单同步配置 - 拉日志默认值 - logPullConcurrency，默认 2
- 新增 TicketLogPullStatus.CANCELLED 状态枚举

## 影响范围
- 后端：ticket_log_pull_service.py, ticket_log_pull_controller.py, ticket_enums.py, ticket_sync_config_service.py
- 前端：logPullRecord/index.vue, constants.js, ticket.js, logPull.js, index.js
- 文档：新增 ticket_log_pull.md
