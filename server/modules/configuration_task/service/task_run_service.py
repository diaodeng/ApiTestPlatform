"""配置任务运行执行服务：运行快照、Agent 下发和终态落库。

复用现有 Web 用例 `run_case` 协议：输入绑定转换成 `runtimeOptions.resourceBindings`，
由 Agent 端既有 `upload_file` 资源解析逻辑消费，不新增第二套浏览器执行协议。
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi.concurrency import run_in_threadpool
from loguru import logger
from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.dao.agent_dao import AgentDao
from module_hrm.enums.enums import AgentResponseEnum
from module_hrm.service.web_case_service import WebCaseService
from module_qtr.service.agent_service import send_message
from modules.configuration_task.dao.resource_dao import ResourceDao
from modules.configuration_task.dao.task_dao import (
    ConfigurationTaskDao,
    ConfigurationTaskRunDao,
    ConfigurationTaskVersionDao,
    load_json_list,
    load_json_object,
)
from modules.configuration_task.entity.do.task_do import ConfigurationTask, ConfigurationTaskVersion
from modules.configuration_task.entity.do.task_run_do import ConfigurationTaskRun
from modules.configuration_task.entity.vo.task_vo import (
    TaskRunCreateModel,
    TaskRunDetailModel,
)

RUN_TERMINAL_STATUSES = {"SUCCESS", "FAILED", "CANCELLED"}
# 运行下发 Agent 的默认超时（秒）：配置任务可能包含多步骤页面操作，
# 不能沿用 send_message 内置的 120 秒默认值误杀长任务；后续可下沉到版本配置。
RUN_DEFAULT_TIMEOUT_SECONDS = 1800


@dataclass
class TaskRunServiceResult:
    """运行操作结果，供 Controller 转换为统一 HTTP 响应。"""

    is_success: bool
    message: str
    result: TaskRunDetailModel | None = None


def _dumps(value) -> str:
    """序列化为紧凑 JSON，供 ORM 文本列保存。"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class ConfigurationTaskRunService:
    """配置任务运行服务；不复制浏览器执行逻辑，只编排版本快照和 Agent 命令。"""

    @staticmethod
    def _operator(current_user: CurrentUserModel) -> str:
        """提取当前用户名，用于审计字段。"""
        user = current_user.user
        return user.user_name if user else "system"

    @classmethod
    def _prepare_run(
        cls,
        db: Session,
        task_id: int,
        model: TaskRunCreateModel,
        operator: str,
    ) -> tuple[Any, str, str, dict[str, Any], str]:
        """同步执行运行前置段：校验任务、Agent、版本，冻结快照并创建运行记录和 run_case 消息。

        供事件循环通过 run_in_threadpool 调用，避免同步 DB 操作阻塞异步接口。
        注意：commit 后 ORM 属性会过期并触发懒加载查询，因此本方法在线程池内
        一并构造 run_case 消息并返回普通 Python 值（run_id/agent_code/message），
        事件循环侧不得直接访问 ORM 属性。
        :return: (运行实体, agent_code, run_id, run_case 消息, 错误文本)；成功时错误文本为空串。
        """
        task = ConfigurationTaskDao.get_task(db, task_id)
        if not task:
            return None, "", "", {}, "任务不存在"
        if task.status != "ACTIVE":
            return None, "", "", {}, f"任务当前状态不允许运行：{task.status}"

        agent_code = (model.agent_code or task.agent_code or "").strip()
        agent = AgentDao.get_agent_by_code(db, agent_code)
        if not agent:
            return None, "", "", {}, "Agent 未登记"

        version = cls._resolve_version(db, task, model.version_no)
        if isinstance(version, str):
            return None, "", "", {}, version
        if version.status != "PUBLISHED":
            return None, "", "", {}, f"版本 {version.version_no} 未发布，不能运行"

        input_snapshot = cls._build_input_snapshot(db, version)
        snapshot_error = cls._validate_input_snapshot(task, version, input_snapshot)
        if snapshot_error:
            return None, "", "", {}, snapshot_error

        now = datetime.now()
        run_params = {
            "browserName": version.browser_name,
            "headless": bool(version.headless),
            "startUrl": version.start_url,
            "credentialBindingId": version.credential_binding_id or "",
            "variables": {**load_json_object(task.variables_json), **load_json_object(version.variables_json)},
        }
        run = ConfigurationTaskRunDao.add_run(
            db,
            {
                "task_id": task_id,
                "task_version_id": version.version_id,
                "version_no": version.version_no,
                "agent_code": agent_code,
                "trigger_type": model.trigger_type or "manual",
                "status": "RUNNING",
                "input_snapshot_json": _dumps(input_snapshot),
                "run_params_json": _dumps(run_params),
                "started_at": now,
                "create_by": operator,
                "create_time": now,
                "update_by": operator,
                "update_time": now,
            },
        )
        db.commit()
        # commit 后属性已过期，refresh 回读一次并在线程池内完成消息构造，
        # 后续事件循环只使用普通值，不再触碰 ORM 属性。
        db.refresh(run)
        message = cls._build_run_case_message(run, task, version, run_params)
        run_id = str(run.task_run_id)
        logger.info(
            f"创建配置任务运行，task_run_id={run_id}，task_id={task_id}，"
            f"version_no={version.version_no}，agent_code={agent_code}，operator={operator}"
        )
        return run, agent_code, run_id, message, ""

    @classmethod
    async def create_run_and_execute(
        cls,
        db: Session,
        task_id: int,
        model: TaskRunCreateModel,
        current_user: CurrentUserModel,
    ) -> TaskRunServiceResult:
        """创建运行实例并同步执行：冻结版本快照后下发 run_case。

        异步边界约定：事件循环内只做 await 和普通值操作；所有提交 SQL 的
        同步段（前置校验/建记录、成功终态、失败终态）通过 run_in_threadpool
        放到线程池执行；Agent 等待段本身是 Future 异步等待，不阻塞事件循环。
        """
        operator = cls._operator(current_user)
        run, agent_code, run_id, message, prepare_error = await run_in_threadpool(
            cls._prepare_run,
            db,
            task_id,
            model,
            operator,
        )
        if prepare_error:
            return TaskRunServiceResult(False, prepare_error)

        try:
            response = await send_message(
                agent_code,
                message,
                timeout_seconds=RUN_DEFAULT_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            logger.exception(f"配置任务运行下发异常，task_run_id={run_id}，error={exc}")
            return await run_in_threadpool(
                cls._finalize_failure, db, run, "AGENT_SEND_ERROR", str(exc), operator
            )

        if response.status_code != AgentResponseEnum.SUCCESS.value:
            return await run_in_threadpool(
                cls._finalize_failure, db, run, "AGENT_SEND_FAILED", response.message, operator
            )

        success, response_result, failure_message = WebCaseService._extract_webui_run_response(response)
        if success:
            return await run_in_threadpool(cls._finalize_success, db, run, response_result, operator)
        return await run_in_threadpool(
            cls._finalize_failure,
            db,
            run,
            "EXECUTION_FAILED",
            failure_message or "执行失败",
            operator,
            response_result,
        )

    @classmethod
    def _resolve_version(cls, db: Session, task: ConfigurationTask, version_no: int | None):
        """按版本号或任务当前版本解析执行版本；未发布当前版本时返回错误文本。"""
        if version_no:
            version = ConfigurationTaskVersionDao.get_by_task_and_no(db, task.task_id, version_no)
            if not version:
                return f"版本 {version_no} 不存在"
            return version
        current_version_id = task.current_version_id
        if not current_version_id:
            return "任务没有已发布的版本"
        version = ConfigurationTaskVersionDao.get_version(db, int(current_version_id))
        if not version:
            return "任务当前版本不存在"
        return version

    @classmethod
    def _build_input_snapshot(cls, db: Session, version: ConfigurationTaskVersion) -> dict[str, Any]:
        """把版本输入绑定复制为资源快照，记录资源元数据摘要。"""
        snapshot: dict[str, Any] = {}
        bindings = load_json_object(version.input_bindings_json)
        for file_key, resource_ids in bindings.items():
            entries = []
            for resource_id_text in resource_ids:
                try:
                    resource_id_int = int(resource_id_text)
                except (TypeError, ValueError):
                    continue
                resource = ResourceDao.get_resource(db, resource_id_int)
                if not resource:
                    entries.append({"resourceId": resource_id_text, "status": "MISSING"})
                    continue
                entries.append(
                    {
                        "resourceId": str(resource.resource_id),
                        "version": resource.version,
                        "fileSize": resource.file_size,
                        "sha256": resource.sha256,
                        "originalFileName": resource.original_file_name,
                        "agentCode": resource.agent_code,
                        "status": resource.status,
                    }
                )
            snapshot[file_key] = entries
        return snapshot

    @classmethod
    def _validate_input_snapshot(
        cls,
        task: ConfigurationTask,
        version: ConfigurationTaskVersion,
        snapshot: dict[str, Any],
    ) -> str:
        """校验快照中的资源必须 READY 且归属执行 Agent，返回错误文本或空串。"""
        for file_key, entries in snapshot.items():
            for entry in entries:
                if entry.get("status") == "MISSING":
                    return f"fileKey {file_key} 绑定的资源不存在"
                if entry.get("status") != "READY":
                    return f"fileKey {file_key} 绑定的资源未就绪：{entry.get('status')}"
                if entry.get("agentCode") != task.agent_code:
                    return f"fileKey {file_key} 绑定的资源不属于执行Agent"
        return ""

    @classmethod
    def _build_run_case_message(
        cls,
        run: ConfigurationTaskRun,
        task: ConfigurationTask,
        version: ConfigurationTaskVersion,
        run_params: dict[str, Any],
    ) -> dict[str, Any]:
        """构造 run_case 消息；输入绑定注入 runtimeOptions.resourceBindings。

        注意：必须在 run_in_threadpool 的同步段内调用（本方法读取 ORM 属性）。
        """
        resource_bindings: dict[str, list[str]] = {}
        for file_key, entries in load_json_object(run.input_snapshot_json).items():
            ids = [str(entry.get("resourceId")) for entry in entries if entry.get("resourceId")]
            if ids:
                resource_bindings[file_key] = ids
        steps = load_json_list(version.steps_json)
        case_data = {
            "caseName": f"配置任务-{task.task_name}-v{version.version_no}-run{run.task_run_id}",
            "startUrl": version.start_url,
            "browserName": version.browser_name,
            "headless": bool(version.headless),
            "steps": steps,
        }
        runtime_options = {
            "browserName": version.browser_name,
            "headless": bool(version.headless),
            "variables": run_params.get("variables") or {},
            "resourceBindings": resource_bindings,
        }
        if run_params.get("credentialBindingId"):
            runtime_options["credentialBindingId"] = run_params["credentialBindingId"]
            runtime_options["stateSourceType"] = "credential"
        else:
            runtime_options["stateSourceType"] = "none"
        return {
            "requestType": 3,
            "command": "run_case",
            "taskRunId": str(run.task_run_id),
            "caseData": case_data,
            "runtimeOptions": runtime_options,
        }

    @classmethod
    def _finalize_success(
        cls,
        db: Session,
        run: ConfigurationTaskRun,
        response_result: dict[str, Any],
        operator: str,
    ) -> TaskRunServiceResult:
        """运行成功终态落库并返回响应模型。

        同步 DB 段，供事件循环通过 run_in_threadpool 调用；只在调用线程内
        访问 ORM 属性，返回的 TaskRunServiceResult 为普通值对象。
        """
        now = datetime.now()
        duration_ms = int((now - (run.started_at or now)).total_seconds() * 1000)
        ConfigurationTaskRunDao.update_run(
            db,
            run.task_run_id,
            {
                "status": "SUCCESS",
                "result_json": _dumps(response_result),
                "error_code": "",
                "error_message": "",
                "ended_at": now,
                "duration_ms": duration_ms,
                "update_by": operator,
            },
        )
        db.commit()
        refreshed = ConfigurationTaskRunDao.get_run(db, run.task_run_id)
        logger.info(f"配置任务运行成功，task_run_id={run.task_run_id}，duration_ms={duration_ms}")
        return TaskRunServiceResult(True, "运行成功", cls.to_run_model(refreshed))

    @classmethod
    def _finalize_failure(
        cls,
        db: Session,
        run: ConfigurationTaskRun,
        error_code: str,
        error_message: str,
        operator: str,
        response_result: dict[str, Any] | None = None,
    ) -> TaskRunServiceResult:
        """运行失败终态落库并返回响应模型；错误消息截断保存。

        同步 DB 段，供事件循环通过 run_in_threadpool 调用；线程内完成
        update + commit + 重查，返回值为普通结果对象。
        """
        now = datetime.now()
        duration_ms = int((now - (run.started_at or now)).total_seconds() * 1000)
        safe_message = (error_message or "运行失败")[:2000]
        update_values: dict[str, Any] = {
            "status": "FAILED",
            "error_code": error_code,
            "error_message": safe_message,
            "ended_at": now,
            "duration_ms": duration_ms,
            "update_by": operator,
        }
        if response_result:
            update_values["result_json"] = _dumps(response_result)
        ConfigurationTaskRunDao.update_run(db, run.task_run_id, update_values)
        db.commit()
        refreshed = ConfigurationTaskRunDao.get_run(db, run.task_run_id)
        logger.warning(
            f"配置任务运行失败，task_run_id={run.task_run_id}，error_code={error_code}，message={safe_message[:200]}"
        )
        return TaskRunServiceResult(False, safe_message, cls.to_run_model(refreshed))

    @classmethod
    def get_run(cls, db: Session, task_run_id: int) -> TaskRunDetailModel | None:
        """查询运行详情。"""
        row = ConfigurationTaskRunDao.get_run(db, task_run_id)
        return cls.to_run_model(row) if row else None

    @classmethod
    def list_runs(
        cls,
        db: Session,
        task_id: str | None = None,
        agent_code: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[TaskRunDetailModel]:
        """查询运行列表，条件为空时按未传处理。"""
        task_id_int = int(task_id) if task_id else None
        rows = ConfigurationTaskRunDao.list_runs(
            db,
            task_id=task_id_int,
            agent_code=(agent_code or "").strip() or None,
            status=(status or "").strip() or None,
            limit=limit,
        )
        return [cls.to_run_model(row) for row in rows]

    @staticmethod
    def to_run_model(row: ConfigurationTaskRun | None) -> TaskRunDetailModel | None:
        """将运行 ORM 转为响应模型，BIGINT ID 字符串化。"""
        if row is None:
            return None
        return TaskRunDetailModel(
            taskRunId=str(row.task_run_id),
            taskId=str(row.task_id),
            taskVersionId=str(row.task_version_id),
            versionNo=row.version_no,
            agentCode=row.agent_code,
            triggerType=row.trigger_type,
            status=row.status,
            inputSnapshot=load_json_object(row.input_snapshot_json),
            result=load_json_object(row.result_json),
            errorCode=row.error_code or "",
            errorMessage=row.error_message or "",
            startedAt=row.started_at,
            endedAt=row.ended_at,
            durationMs=row.duration_ms,
            createBy=row.create_by or "",
            createTime=row.create_time,
        )
