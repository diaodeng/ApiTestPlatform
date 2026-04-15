import json
from typing import Any

CELERY_EXECUTE_JOB_TASK = "module_task.execute_registered_job"


def normalize_args_json(value: Any) -> str:
    """
    将任务位置参数归一化为 JSON 数组字符串。

    :param value: 原始参数，支持字符串、列表或 None。
    :return: 合法 JSON 数组字符串。
    """
    if value is None:
        return "[]"
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "[]"
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return text
        except Exception:
            pass
        return "[]"
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return "[]"


def normalize_kwargs_json(value: Any) -> str:
    """
    将任务关键字参数归一化为 JSON 对象字符串。

    :param value: 原始参数，支持字符串、字典或 None。
    :return: 合法 JSON 对象字符串。
    """
    if value is None:
        return "{}"
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "{}"
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return text
        except Exception:
            pass
        return "{}"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return "{}"


def parse_payload_args(raw_args: Any) -> list:
    """
    解析位置参数 JSON 文本为 Python 列表。

    :param raw_args: JSON 文本或列表对象。
    :return: 可执行参数列表。
    """
    if isinstance(raw_args, list):
        return raw_args
    if not raw_args:
        return []
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def parse_payload_kwargs(raw_kwargs: Any) -> dict:
    """
    解析关键字参数 JSON 文本为 Python 字典。

    :param raw_kwargs: JSON 文本或字典对象。
    :return: 可执行关键字参数字典。
    """
    if isinstance(raw_kwargs, dict):
        return raw_kwargs
    if not raw_kwargs:
        return {}
    if isinstance(raw_kwargs, str):
        try:
            parsed = json.loads(raw_kwargs)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def build_schedule_desc(task_row: Any) -> str:
    """
    构建任务调度描述文本，用于执行日志快照。

    :param task_row: 任务 ORM 行对象。
    :return: 调度描述字符串。
    """
    schedule_type = str(task_row.schedule_type or "").strip().lower()
    if schedule_type == "interval":
        return f"every {task_row.interval_every} {task_row.interval_period}"
    if schedule_type == "once":
        return f"once at {task_row.one_off_eta}"
    return f"cron {task_row.cron_expression}"


def build_task_payload(task_row: Any, trigger_type: str) -> dict:
    """
    从任务配置对象构建 Celery 统一执行载荷。

    :param task_row: 任务 ORM 行对象。
    :param trigger_type: 触发方式，支持 scheduler/manual/once。
    :return: Celery 可序列化载荷。
    """
    return {
        "task_id": task_row.task_id,
        "owner_type": task_row.owner_type,
        "task_name": task_row.task_name,
        "task_key": task_row.task_key,
        "queue_name": task_row.queue_name or "celery",
        "args_json": normalize_args_json(task_row.task_args_json),
        "kwargs_json": normalize_kwargs_json(task_row.task_kwargs_json),
        "allow_concurrent": bool(task_row.allow_concurrent),
        "lock_ttl_seconds": int(task_row.lock_ttl_seconds or 3600),
        "schedule_desc": build_schedule_desc(task_row),
        "trigger_type": trigger_type,
    }
