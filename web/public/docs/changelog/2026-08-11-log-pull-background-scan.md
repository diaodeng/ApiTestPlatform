# 2026-08-11 - 日志拉取轮询改后台任务查询 + 停止功能落地

## 背景

- 原实现中 `_poll_external_result` 在后台线程池（`max_workers=2`）内同步阻塞轮询外部平台，单条任务最长占用线程 1800s（pollTimeoutSec），导致任务提交/轮询受并发数限制，批量提交时大量任务排队。
- 前端已有「停止」按钮（调用 `POST /ticket/log-pulls/{record_id}/stop`），但后端没有对应路由（404），`CANCELLED` 枚举定义后无任何消费。

## 变更

### 架构：阻塞轮询 → Celery 周期任务批量探测

- 拆分 `_process_record` 单线程全流程为三个独立阶段：
  - **提交申请阶段** `_process_submit`：幂等检查外部列表 → 提交外部申请 → 置 POLLING 并写 `poll_deadline_at`，立即结束线程（不再轮询）
  - **单次探测** `_probe_external_status`：单次查询外部列表，返回 matched / failed / pending 三态，替代原 while 循环
  - **下载解析阶段** `_process_download`：下载 → 归档 → 截取入库 → 后处理 → 触发 AI，含协作式取消检查点
- 新增 `scan_pending_records` 入口，由 Celery 周期任务 `module_task.scheduler_maintenance.scan_log_pull_records`（每 30 秒）驱动：
  - created 兜底投递提交申请
  - submitting/polling 超过 `poll_deadline_at` → 标记「轮询外部平台超时」失败
  - submitting/polling 未超时 → 单次探测，命中可下载则投递下载解析
- 数据模型：`ticket_log_pull_record` 新增 `poll_deadline_at`（提交申请成功时写入 `now + pollTimeoutSec`），`get_db.py` 增加兼容列升级
- 重启恢复：`resume_pending_records` 只清理 downloading/processing（线程丢失），submitting/polling/created 保留由周期任务接管，不再全部清成失败

### 停止功能

- 后端新增 `POST /ticket/log-pulls/{record_id}/stop`（权限 `ticket:logpull:remove`），置 `CANCELLED` 状态并写事件
- 协作式取消：周期任务跳过 CANCELLED 记录；下载/解析阶段在下载前、解析前检查 CANCELLED，命中则清理临时文件直接返回
- 前端：工单详情页日志拉取 Tab 新增「停止」按钮；修正 `useLogViewer.js` 的 `activeLogPullStatuses` 为 `['created','submitting','polling','downloading','processing']`（原为失效值）；管理页停止失败时给出错误提示

## 影响范围

- 后端：`ticket_log_pull_service.py`、`ticket_log_pull_dao.py`、`ticket_log_pull_controller.py`、`ticket_log_pull_do.py`、`config/get_db.py`、`module_task/scheduler_maintenance.py`
- 前端：`TicketDetailLogPullTab.vue`、`hooks/useLogViewer.js`、`logPullRecord/index.vue`

## 注意

- **周期任务需手动配置**（与项目其他定时任务一致，不在启动时自动注册）：到「系统监控-定时任务」新增任务，任务键选择 `module_task.scheduler_maintenance.scan_log_pull_records`，调度类型 interval、间隔 30 秒、队列 sys、执行方式 thread、允许并发关；若未配置，轮询中的记录不会被探测
- 若 Celery 未运行，任务提交仍成功但状态停留在 polling，不会被探测
- 旧的 `_poll_external_result` 阻塞轮询逻辑已删除，不再占用线程