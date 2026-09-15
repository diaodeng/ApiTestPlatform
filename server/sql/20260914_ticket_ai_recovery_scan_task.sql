-- 工单 AI 分析连接中断恢复扫描定时任务（2026-09-14 Agent 静默断连问题修复配套）
-- 背景：Agent WebSocket 中途断开时，AI 分析任务进入 pending_recovery 状态等待补交结果；
-- 本任务周期扫描该状态任务，补交结果到达后自动排队恢复写回，超期未补交则置败并通知。
-- 不执行本 SQL 也可在「任务调度」页面手动创建：任务键
-- module_task.scheduler_maintenance.scan_pending_recovery_ai_tasks，间隔 60 秒。
-- 注意：MySQL DDL/DML 按环境执行后无需重启，Celery Beat 每 10 秒自动同步数据库任务。

INSERT INTO celery_periodic_task (
    owner_type, task_name, task_key, queue_name, execution_mode,
    schedule_type, interval_every, interval_period,
    task_args_json, task_kwargs_json,
    enabled, allow_concurrent, lock_ttl_seconds, timezone,
    create_by, create_time, update_by, update_time, remark
) SELECT
    'sys', '工单AI分析连接中断恢复扫描', 'module_task.scheduler_maintenance.scan_pending_recovery_ai_tasks', 'celery', 'thread',
    'interval', 60, 'seconds',
    '[]', '{}',
    1, 0, 120, 'Asia/Shanghai',
    'system', NOW(), 'system', NOW(), '扫描pending_recovery状态AI任务：补交结果自动写回，超期置败通知'
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1 FROM celery_periodic_task
    WHERE task_key = 'module_task.scheduler_maintenance.scan_pending_recovery_ai_tasks'
);
