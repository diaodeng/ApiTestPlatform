from datetime import datetime

from module_task.celery_job_vo import JobLogPageQueryModel
from module_task.celery_tasks import _build_execution_log_fields


def test_build_execution_log_fields_includes_trace_id():
    """执行日志入库字段应带上 trace_id，便于后续按 TID 串联查询。"""
    fields = _build_execution_log_fields(
        {
            "task_id": 100,
            "owner_type": "sys",
            "task_name": "同步后处理",
            "task_key": "ticket.sync",
            "queue_name": "celery",
            "trigger_type": "manual",
            "schedule_desc": "手动执行",
            "args_json": "[]",
            "kwargs_json": "{}",
            "trace_id": "ticket-sync-001",
        },
        celery_task_id="celery-001",
        status="running",
        message="执行中",
        exception_info="",
        started_at=datetime(2026, 8, 26, 10, 0, 0),
    )

    assert fields["trace_id"] == "ticket-sync-001"


def test_job_log_page_query_model_accepts_trace_id_alias():
    """任务日志查询模型应支持前端 traceId/TID 条件透传。"""
    model = JobLogPageQueryModel.model_validate({"traceId": "ticket-sync-001"})

    assert model.trace_id == "ticket-sync-001"
