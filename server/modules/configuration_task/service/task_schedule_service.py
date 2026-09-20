"""配置任务定时触发运行服务与录制转模板服务。

定时任务约定（module_task/scheduler_configuration.py 注册）：
- 任务参数：task_id（必填）、agent_code/version_no 可选覆盖；
- 触发时按配置的 cron 由调度器驱动，本服务只负责"创建一次运行并同步执行"；
- 运行复用 ConfigurationTaskRunService.create_run_and_execute 的同步编排，
  由定时任务线程直接调用（无事件循环，DB 操作天然在任务线程）。

录制转模板：复用 WebCaseService.recording_detail_services 的既有步骤重建，
按 mark_variables / upload_file_keys 标记后生成版本草稿（DRAFT）。
"""

import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.service.web_case_service import WebCaseService
from modules.configuration_task.dao.task_dao import (
    ConfigurationTaskDao,
    ConfigurationTaskVersionDao,
)
from modules.configuration_task.entity.vo.task_vo import (
    RecordingToTemplateModel,
    TaskRunCreateModel,
    TaskScheduleModel,
    TaskVersionCreateModel,
)
from modules.configuration_task.service.task_run_service import ConfigurationTaskRunService
from modules.configuration_task.service.task_service import ConfigurationTaskService


@dataclass
class ScheduledRunResult:
    """定时触发运行结果摘要。"""

    is_success: bool
    message: str
    task_run_id: str = ""


class SimpleUser:
    """定时任务链路的极简当前用户替身。"""

    def __init__(self, user_name: str):
        self.user = SimpleNamespace(user_name=user_name, admin=False)


class ConfigurationTaskScheduleService:
    """配置任务定时触发运行。"""

    @classmethod
    def get_schedule(cls, db: Session, task_id: int) -> TaskScheduleModel:
        """读取任务定时配置（保存在任务 remark 之前的专用 JSON 字段：variables_json 外的 schedule_json 不存在，
        首期把调度配置存放在任务扩展 JSON：remark 前缀 `@schedule:` 内）。"""
        task = ConfigurationTaskDao.get_task(db, task_id)
        if not task:
            return TaskScheduleModel()
        schedule_data = cls._extract_schedule_json(task.remark or "")
        if not schedule_data:
            return TaskScheduleModel()
        try:
            return TaskScheduleModel(**schedule_data)
        except Exception:
            logger.warning(f"任务定时配置解析失败，返回默认值: task_id={task_id}")
            return TaskScheduleModel()

    @classmethod
    def save_schedule(
        cls,
        db: Session,
        task_id: int,
        model: TaskScheduleModel,
        current_user: CurrentUserModel,
    ) -> ScheduledRunResult:
        """保存任务定时配置；启用时校验版本/Agent 可用。"""
        operator = current_user.user.user_name if current_user.user else "system"
        task = ConfigurationTaskDao.get_task(db, task_id)
        if not task:
            return ScheduledRunResult(False, "任务不存在")
        if model.enabled:
            if not model.cron:
                return ScheduledRunResult(False, "启用定时必须填写 cron 表达式")
            version_no = model.version_no
            if version_no:
                version = ConfigurationTaskVersionDao.get_by_task_and_no(db, task_id, version_no)
                if not version or version.status != "PUBLISHED":
                    return ScheduledRunResult(False, f"版本 {version_no} 不存在或未发布")
            elif not task.current_version_id:
                return ScheduledRunResult(False, "任务没有已发布版本，不能启用定时")
            agent_code = model.agent_code or task.agent_code
            if not agent_code:
                return ScheduledRunResult(False, "未指定执行 Agent")
        # 调度配置序列化进 remark 的 @schedule: 前缀段，保留 remark 其余内容。
        base_remark = cls._strip_schedule_json(task.remark or "")
        schedule_json = json.dumps(model.model_dump(by_alias=False), ensure_ascii=False, separators=(",", ":"))
        new_remark = f"@schedule:{schedule_json}" + (f"\n{base_remark}" if base_remark else "")
        ConfigurationTaskDao.update_task(
            db,
            task_id,
            {"remark": new_remark, "update_by": operator},
        )
        db.commit()
        logger.info(
            f"保存任务定时配置: task_id={task_id}, enabled={model.enabled}, cron={model.cron}, operator={operator}"
        )
        return ScheduledRunResult(True, "定时配置已保存")

    @classmethod
    def trigger_scheduled_run(cls, db: Session, task_id: int, **kwargs) -> dict[str, Any]:
        """定时任务入口：创建一次运行并同步执行；返回摘要 dict 供任务日志。

        该方法由定时任务线程调用（无运行中的事件循环），直接复用同步编排；
        agent_code/version_no 可由任务参数覆盖调度配置。
        """
        task = ConfigurationTaskDao.get_task(db, task_id)
        if not task:
            return {"is_success": False, "message": "任务不存在"}
        schedule = cls.get_schedule(db, task_id)
        if not schedule.enabled:
            return {"is_success": False, "message": "任务定时触发未启用，跳过"}

        agent_code = str(kwargs.get("agent_code") or schedule.agent_code or task.agent_code or "").strip()
        version_no = kwargs.get("version_no") or schedule.version_no
        operator = "scheduler"
        fake_user = SimpleUser(operator)
        model = TaskRunCreateModel(
            agentCode=agent_code or None,
            versionNo=int(version_no) if version_no else None,
            triggerType="scheduled",
        )
        result = ConfigurationTaskRunService.execute_run_sync(db, task_id, model, fake_user)
        result_payload = result.result.model_dump(by_alias=True) if result.result else {}
        summary = {
            "is_success": result.is_success,
            "message": result.message,
            "taskRunId": result_payload.get("taskRunId", ""),
        }
        logger.info(
            f"定时触发配置任务运行完成: task_id={task_id}, is_success={result.is_success}, "
            f"task_run_id={summary['taskRunId']}, message={result.message}"
        )
        return summary

    # ---------- 内部工具 ----------

    @staticmethod
    def _extract_schedule_json(remark: str) -> dict[str, Any]:
        """从 remark 中提取 @schedule: 前缀的 JSON 配置。"""
        if not remark.startswith("@schedule:"):
            return {}
        try:
            parsed = json.loads(remark.split("\n", 1)[0][len("@schedule:") :])
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _strip_schedule_json(remark: str) -> str:
        """去掉 remark 中的调度 JSON 段，保留其余内容。"""
        if not remark.startswith("@schedule:"):
            return remark
        lines = remark.split("\n", 1)
        return lines[1] if len(lines) > 1 else ""




class ConfigurationTaskTemplateService:
    """录制会话到任务版本草稿的转换。"""

    @classmethod
    def convert_recording_to_version(
        cls,
        db: Session,
        model: RecordingToTemplateModel,
        current_user: CurrentUserModel,
    ) -> Any:
        """把录制会话的重建步骤转成任务版本草稿。

        转换规则：
        - 版本 startUrl/browserName 取自录制会话；
        - fill/select 步骤按 mark_variables 把 value 替换为 ${var} 占位符；
        - upload_file 步骤按 upload_file_keys 标注 fileKey；
        - 其余步骤原样保留。
        """
        operator = current_user.user.user_name if current_user.user else "system"
        try:
            task_id = int(model.task_id)
            recording_id = int(model.recording_id)
        except (TypeError, ValueError):
            return cls._fail("任务或录制 ID 不合法")

        task = ConfigurationTaskDao.get_task(db, task_id)
        if not task:
            return cls._fail("任务不存在")
        detail = WebCaseService.recording_detail_services(db, recording_id)
        if detail is None:
            return cls._fail("录制会话不存在")
        if not detail.steps:
            return cls._fail("录制会话没有可转换的步骤")

        steps: list[dict[str, Any]] = []
        for index, step in enumerate(detail.steps):
            step_dict = step.model_dump(mode="json", by_alias=True)
            variable = model.mark_variables.get(str(index)) or model.mark_variables.get(index)
            if variable and step_dict.get("actionType") in {"fill", "select_option"}:
                params = step_dict.get("params") or {}
                placeholder = "${" + variable + "}"
                if step_dict.get("actionType") == "select_option":
                    # 下拉动作的执行器读取 values 数组，不能写入 fill 专用的 value 字段。
                    params["values"] = [placeholder]
                else:
                    params["value"] = placeholder
                step_dict["params"] = params
            file_key = model.upload_file_keys.get(index) or model.upload_file_keys.get(str(index))
            if file_key and step_dict.get("actionType") == "upload_file":
                params = step_dict.get("params") or {}
                params["fileKey"] = file_key
                step_dict["params"] = params
            steps.append(step_dict)

        version_model = TaskVersionCreateModel(
            startUrl=detail.start_url or "https://example.invalid/",
            browserName=detail.browser_name or "chromium",
            headless=False,
            steps=steps,
            inputBindings={},
        )
        result = ConfigurationTaskService.create_version(db, task_id, version_model, current_user)
        if not result.is_success:
            return result
        logger.info(
            f"录制转模板完成: recording_id={recording_id}, task_id={task_id}, "
            f"version_no={result.result.version_no if result.result else '?'}, operator={operator}"
        )
        return result

    @staticmethod
    def _fail(message: str):
        """构造失败结果，复用任务服务结果类型。"""
        from modules.configuration_task.service.task_service import ConfigurationTaskServiceResult

        return ConfigurationTaskServiceResult(False, message)
