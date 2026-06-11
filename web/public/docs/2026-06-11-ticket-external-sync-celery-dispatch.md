# 2026-06-11 外部推单延后后处理改为优先 Celery 分发

## 背景

外部推单接口 `/ticket/sync/external` 已经是“先入库、后处理”的快速返回模式。  
本次需求要求：如果 Celery 可用，则将后处理任务交给 Celery 执行；若不可用，继续本地后台兜底。

## 变更点

1. 新增 Celery 任务常量：
   - `module_task.celery_contract.CELERY_TICKET_SYNC_DEFERRED_POST_PROCESS_TASK`
2. 新增 Celery 任务函数：
   - `module_task.celery_tasks.run_ticket_sync_deferred_post_process_task`
   - 任务内容：调用 `TicketSyncService.run_deferred_sync_post_process(...)`
3. `TicketSyncService` 新增分发能力：
   - `_is_celery_worker_available()`：通过 `inspect.ping` 判断 Worker 可用性
   - `dispatch_deferred_sync_post_process_task(...)`：优先投递 Celery，失败回退 background
4. 控制器 `/ticket/sync/external` 调整：
   - 入库成功后先调用分发方法
   - 分发模式不是 `celery` 时，才使用 FastAPI `background_tasks` 兜底
   - 返回体新增 `deferredDispatch` 字段，标识 `mode/taskId/reason`

## 行为说明

1. 外部推单请求仍“立即返回”，不等待 AI/自动化完成。
2. Celery 可用时，后处理在 Celery Worker 中执行。
3. Celery 不可用或投递失败时，自动回退到原有本地后台任务执行，不影响业务连续性。
