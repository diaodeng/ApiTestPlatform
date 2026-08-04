# 后台任务与定时任务日志追踪ID补齐

## 背景

HTTP 请求日志已经通过中间件写入 `tid`，但脱离请求生命周期的执行链路仍会显示 `[-]`，例如：

1. Celery 定时任务触发后的业务执行日志。
2. 手动执行定时任务后进入 Worker 的日志。
3. 工单外部同步入库成功后，延后后处理在 Celery 或 FastAPI 本地后台任务中的日志。
4. 工单相似度向量后台重建任务日志。

这些日志缺少统一追踪ID后，排查主动拉取、外部推单、自动 AI、群推送等跨线程/跨进程链路时很难按一次执行过滤。

## 变更内容

1. `context.request_context` 新增通用追踪工具：
   - `generate_trace_id(prefix)`：生成短追踪ID。
   - `get_current_trace_id(default)`：读取当前上下文追踪ID。
   - `trace_context(trace_id)`：在非 HTTP 入口临时设置追踪上下文并自动恢复。
2. HTTP 请求中间件改为复用 `trace_context`，继续返回 `X-Request-Id`。
3. Celery 统一任务入口 `module_task.execute_registered_job` 会为每次任务执行设置 tid：
   - 手动触发时优先继承当前 HTTP 请求 tid。
   - 定时触发或旧 payload 未携带 tid 时生成 `job-xxxxxxxx`。
   - 任务运行态 Redis 快照补充 `trace_id` 字段。
4. 工单外部同步延后后处理会传递 tid：
   - Celery 可用时，投递 `module_ticket.sync_deferred_post_process` 携带当前 tid。
   - Celery 不可用回退 FastAPI 本地后台任务时，也显式设置同一个 tid。
5. 工单相似度向量后台重建也继承提交请求的 tid。

## 影响范围

- 不改变业务数据结构和接口响应结构。
- 日志格式不变，仍使用现有 `[{extra[request_id]}]` 输出。
- Celery Worker 需要随代码发布重启，确保延后后处理任务签名支持新增的可选 `trace_id` 参数。

## 验证

已执行：

```bash
cd server
uv run ruff check context/request_context.py middlewares/cors_middleware.py module_task/celery_tasks.py module_task/celery_job_service.py modules/ticket/controller/ticket_controller.py modules/ticket/service/ticket_sync_service.py
uv run python -m py_compile context/request_context.py middlewares/cors_middleware.py module_task/celery_tasks.py module_task/celery_job_service.py modules/ticket/controller/ticket_controller.py modules/ticket/service/ticket_sync_service.py
```

结果：均通过。

## 排查建议

1. HTTP 直接触发的工单同步：按接口响应头 `X-Request-Id` 在 `logs/YYYY-MM-DD/app.log` 中检索。
2. 定时任务触发的主动拉取：在任务开始日志中查看 `job-xxxxxxxx`，再按该 tid 过滤整次执行。
3. 若看到延后后处理仍为 `[-]`，优先确认 Celery Worker 是否已重启，或是否存在绕过统一入口的自定义后台线程。
