"""配置任务定时触发运行任务。

在「系统监控 → 定时任务」创建任务时使用以下调用目标：
    module_task.scheduler_configuration.trigger_configuration_task_run

任务参数（JSON）：
    {"task_id": 123, "agent_code": "agent-xxx", "version_no": 3}
    - task_id 必填；
    - agent_code / version_no 可选，覆盖任务定时配置中的默认值；
    - cron 由调度器驱动，本任务只负责执行一次运行。
"""

from config.database import SessionLocal
from module_task.runtime_control import TaskStopRequestedError, is_task_stop_requested
from utils.log_util import logger

from .task_register import register_job


@register_job("module_task.scheduler_configuration.trigger_configuration_task_run")
def trigger_configuration_task_run(*args, **kwargs):
    """按任务参数触发一次配置任务运行。

    :param task_id: 配置任务 ID（必填）。
    :param agent_code: 可选覆盖执行 Agent。
    :param version_no: 可选覆盖执行版本号。
    :return: 运行摘要字典。
    """
    from modules.configuration_task.service.task_schedule_service import ConfigurationTaskScheduleService

    task_stop_id = int(kwargs.pop("_task_id", 0) or 0)
    if task_stop_id and is_task_stop_requested(task_stop_id):
        raise TaskStopRequestedError("任务已手动终止")

    task_id_text = kwargs.get("task_id") or kwargs.get("taskId") or ""
    try:
        task_id = int(task_id_text)
    except (TypeError, ValueError):
        raise ValueError("任务参数 task_id 必须是数字") from None

    overrides = {}
    if kwargs.get("agent_code"):
        overrides["agent_code"] = str(kwargs["agent_code"]).strip()
    if kwargs.get("version_no") or kwargs.get("versionNo"):
        overrides["version_no"] = int(kwargs.get("version_no") or kwargs.get("versionNo"))

    with SessionLocal() as db:
        result = ConfigurationTaskScheduleService.trigger_scheduled_run(db, task_id, **overrides)
    if not result.get("is_success"):
        logger.warning(f"定时触发配置任务运行失败: task_id={task_id}, message={result.get('message')}")
    return result
