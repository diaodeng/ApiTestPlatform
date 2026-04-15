import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, model_validator
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_form, as_query


def _normalize_json_text(value: Any, fallback: str) -> str:
    """
    归一化 JSON 文本字段，保证写库值始终可解析。

    :param value: 原始输入值，可以是字符串、字典、列表或 None。
    :param fallback: 当输入为空时使用的默认 JSON 文本。
    :return: 可直接落库的 JSON 字符串。
    """
    if value is None:
        return fallback
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return fallback
        try:
            json.loads(stripped)
            return stripped
        except Exception:
            return fallback
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return fallback


class JobModel(BaseModel):
    """
    Celery 任务模型（用于新增、详情、列表）。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)

    task_id: Optional[int] = None
    owner_type: Optional[str] = None
    owner_user_id: Optional[int] = None
    owner_dept_id: Optional[int] = None

    task_name: Optional[str] = None
    task_key: Optional[str] = None
    queue_name: Optional[str] = "celery"

    schedule_type: Optional[str] = "crontab"
    cron_expression: Optional[str] = None
    interval_every: Optional[int] = None
    interval_period: Optional[str] = None
    one_off_eta: Optional[datetime] = None
    one_off_consumed: Optional[bool] = False

    task_args: Optional[str] = "[]"
    task_kwargs: Optional[str] = "{}"

    enabled: Optional[bool] = True
    allow_concurrent: Optional[bool] = False
    lock_ttl_seconds: Optional[int] = 3600
    timezone: Optional[str] = "Asia/Shanghai"

    last_status: Optional[str] = None
    last_message: Optional[str] = None
    last_run_at: Optional[datetime] = None
    last_duration_ms: Optional[int] = None
    run_count: Optional[int] = 0

    create_by: Optional[str] = None
    create_time: Optional[datetime] = None
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None
    remark: Optional[str] = None

    @model_validator(mode="before")
    def normalize_json_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        """
        统一标准化任务参数字段为 JSON 文本。

        :param values: 原始入参字典。
        :return: 标准化后的参数字典。
        """
        if not isinstance(values, dict):
            return values
        if "taskArgs" in values:
            values["taskArgs"] = _normalize_json_text(values.get("taskArgs"), "[]")
        if "task_args" in values:
            values["task_args"] = _normalize_json_text(values.get("task_args"), "[]")
        if "taskKwargs" in values:
            values["taskKwargs"] = _normalize_json_text(values.get("taskKwargs"), "{}")
        if "task_kwargs" in values:
            values["task_kwargs"] = _normalize_json_text(values.get("task_kwargs"), "{}")
        return values


class EditJobModel(JobModel):
    """
    Celery 任务编辑模型。
    """

    task_id: int


class DeleteJobModel(BaseModel):
    """
    删除任务请求模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    job_ids: str


class RunJobModel(BaseModel):
    """
    手动执行任务请求模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    task_id: int


class ControlRunningTaskModel(BaseModel):
    """
    控制运行中 Celery 任务请求模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    celery_task_id: str


class JobLogModel(BaseModel):
    """
    Celery 任务日志模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)

    log_id: Optional[int] = None
    task_id: Optional[int] = None
    owner_type: Optional[str] = None
    task_name: Optional[str] = None
    task_key: Optional[str] = None
    queue_name: Optional[str] = None
    trigger_type: Optional[str] = None
    celery_task_id: Optional[str] = None
    schedule_desc: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None
    exception_info: Optional[str] = None
    args_json: Optional[str] = None
    kwargs_json: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    create_time: Optional[datetime] = None


class JobQueryModel(BaseModel):
    """
    任务查询模型（不分页）。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    task_name: Optional[str] = None
    task_key: Optional[str] = None
    schedule_type: Optional[str] = None
    enabled: Optional[bool] = None
    last_status: Optional[str] = None
    begin_time: Optional[str] = None
    end_time: Optional[str] = None


@as_query
@as_form
class JobPageQueryModel(JobQueryModel):
    """
    任务分页查询模型。
    """

    page_num: int = 1
    page_size: int = 10


class JobLogQueryModel(BaseModel):
    """
    任务日志查询模型（不分页）。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    task_id: Optional[int] = None
    task_name: Optional[str] = None
    status: Optional[str] = None
    trigger_type: Optional[str] = None
    begin_time: Optional[str] = None
    end_time: Optional[str] = None


@as_query
@as_form
class JobLogPageQueryModel(JobLogQueryModel):
    """
    任务日志分页查询模型。
    """

    page_num: int = 1
    page_size: int = 10


class DeleteJobLogModel(BaseModel):
    """
    删除任务日志请求模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    job_log_ids: str
