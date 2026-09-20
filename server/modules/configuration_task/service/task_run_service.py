"""配置任务运行执行服务：运行快照、Agent 下发和终态落库。

复用现有 Web 用例 `run_case` 协议：输入绑定转换成 `runtimeOptions.resourceBindings`，
由 Agent 端既有 `upload_file` 资源解析逻辑消费，不新增第二套浏览器执行协议。

并发与取消约定：
- 同一 Agent 同时只允许一个 `RUNNING` 运行（数据库级状态约束，防止多浏览器会话互相干扰）；
- 取消复用 Agent 既有 `stop_run_case` 命令（run_id 数字兼容），服务端收敛为 `CANCELLED`；
- Agent 断开或进程重启导致 `RUNNING` 孤儿时，由恢复扫描任务收敛为 `FAILED`。
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
    TaskRunStopModel,
)

RUN_TERMINAL_STATUSES = {"SUCCESS", "FAILED", "CANCELLED"}
# 运行下发 Agent 的默认超时（秒）：配置任务可能包含多步骤页面操作，
# 不能沿用 send_message 内置的 120 秒默认值误杀长任务；可通过请求参数覆盖。
RUN_DEFAULT_TIMEOUT_SECONDS = 1800
# 手动登录场景下发送 prepare_run_case 的超时：浏览器启动加登录等待窗口。
_MANUAL_LOGIN_PREPARE_BASE_SECONDS = 120
# 允许手动确认继续执行的状态集合。
CONTINUABLE_RUN_STATUSES = {"RUNNING"}


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

        # 同一 Agent 并发租约：已有未完成运行时拒绝新运行，避免多个浏览器
        # 会话在同一 Agent 上互相抢占页面和登录态。
        active_run = ConfigurationTaskRunDao.get_active_by_agent(db, agent_code)
        if active_run:
            return (
                None,
                "",
                "",
                {},
                f"Agent {agent_code} 存在未完成的运行 {active_run.task_run_id}，请先等待完成或取消",
            )

        version = cls._resolve_version(db, task, model.version_no)
        if isinstance(version, str):
            return None, "", "", {}, version
        if version.status != "PUBLISHED":
            return None, "", "", {}, f"版本 {version.version_no} 未发布，不能运行"

        input_snapshot = cls._build_input_snapshot(db, version)
        snapshot_error = cls._validate_input_snapshot(task, version, input_snapshot)
        if snapshot_error:
            return None, "", "", {}, snapshot_error

        manual_login_enabled = bool(model.manual_login_enabled)
        manual_login_wait_sec = int(model.manual_login_wait_sec or 120)
        timeout_seconds = int(
            model.timeout_seconds
            or (max(_MANUAL_LOGIN_PREPARE_BASE_SECONDS, manual_login_wait_sec + 600) + 600)
            or RUN_DEFAULT_TIMEOUT_SECONDS
        )
        now = datetime.now()
        run_params = {
            "browserName": version.browser_name,
            "headless": bool(version.headless),
            "startUrl": version.start_url,
            "credentialBindingId": version.credential_binding_id or "",
            "variables": {**load_json_object(task.variables_json), **load_json_object(version.variables_json)},
            "manualLoginEnabled": manual_login_enabled,
            "manualLoginWaitSec": manual_login_wait_sec,
            "timeoutSeconds": timeout_seconds,
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
        # 阶段快照：运行创建时从版本阶段复制；WRITE 阶段创建即挂起审批。
        # 放在 run_case 消息构造之前，保证事件处理时阶段已存在。
        from modules.configuration_task.service.stage_service import ConfigurationTaskStageService

        ConfigurationTaskStageService.snapshot_run_stages(db, run, version)
        db.commit()
        message = cls._build_run_case_message(
            run,
            task,
            version,
            run_params,
            manual_login_enabled=manual_login_enabled,
            manual_login_wait_sec=manual_login_wait_sec,
        )
        run_id = str(run.task_run_id)
        logger.info(
            f"创建配置任务运行，task_run_id={run_id}，task_id={task_id}，"
            f"version_no={version.version_no}，agent_code={agent_code}，"
            f"manual_login={manual_login_enabled}，timeout_seconds={timeout_seconds}，operator={operator}"
        )
        return run, agent_code, run_id, message, ""

    @classmethod
    def execute_run_sync(
        cls,
        db: Session,
        task_id: int,
        model: TaskRunCreateModel,
        current_user: CurrentUserModel,
    ) -> TaskRunServiceResult:
        """同步执行入口：供定时任务线程（无事件循环）调用。

        内部用 asyncio.run 驱动异步编排；如果调用方已在事件循环内，
        必须直接 await create_run_and_execute，不得使用本方法。
        """
        import asyncio

        return asyncio.run(cls.create_run_and_execute(db, task_id, model, current_user))

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
        手动登录场景先发 prepare_run_case 等待登录完成，再发 run_case 续跑。
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

        manual_login_enabled = bool(model.manual_login_enabled)
        manual_login_wait_sec = int(model.manual_login_wait_sec or 120)
        timeout_seconds = int(
            model.timeout_seconds
            or (max(_MANUAL_LOGIN_PREPARE_BASE_SECONDS, manual_login_wait_sec + 600) + 600)
            or RUN_DEFAULT_TIMEOUT_SECONDS
        )

        try:
            if manual_login_enabled:
                # 手动登录两阶段：prepare 打开浏览器并等待登录，Agent 在登录完成后
                # 直接继续执行并返回最终结果（对应 Agent 端 _prepare_run_case 行为）。
                prepare_timeout = max(_MANUAL_LOGIN_PREPARE_BASE_SECONDS, manual_login_wait_sec + 90)
                response = await send_message(
                    agent_code,
                    {**message, "command": "prepare_run_case"},
                    timeout_seconds=prepare_timeout,
                )
            else:
                response = await send_message(
                    agent_code,
                    message,
                    timeout_seconds=timeout_seconds,
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
        *,
        manual_login_enabled: bool = False,
        manual_login_wait_sec: int = 120,
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
            "manualLoginEnabled": manual_login_enabled,
            "manualLoginWaitSec": manual_login_wait_sec,
            "manualLoginRequireConfirm": True,
        }
        if run_params.get("credentialBindingId"):
            runtime_options["credentialBindingId"] = run_params["credentialBindingId"]
            runtime_options["stateSourceType"] = "credential"
        else:
            runtime_options["stateSourceType"] = "none"
        return {
            "requestType": 3,
            "command": "run_case",
            # 事件与停止命令统一使用 webCaseRunId 数字键；Agent 事件上报与
            # 取消命令均按该字段解析，服务端按它路由到配置任务运行表。
            "webCaseRunId": int(run.task_run_id),
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
    async def stop_run(
        cls,
        db: Session,
        task_run_id: int,
        model: TaskRunStopModel,
        current_user: CurrentUserModel,
    ) -> TaskRunServiceResult:
        """停止运行：向 Agent 发送 stop_run_case，并把本地状态收敛为 CANCELLED。

        Agent 未连接或已结束时同样收敛本地状态，保证取消操作幂等。
        """
        operator = cls._operator(current_user)
        run, agent_code, stop_error = await run_in_threadpool(
            cls._prepare_stop, db, task_run_id, operator
        )
        if stop_error:
            return TaskRunServiceResult(False, stop_error)

        reason = (model.reason or "").strip() or "用户手动停止配置任务运行"
        try:
            response = await send_message(
                agent_code,
                {
                    "requestType": 3,
                    "command": "stop_run_case",
                    "webCaseRunId": int(run.task_run_id),
                    "reason": reason,
                },
                timeout_seconds=30,
            )
        except Exception as exc:
            logger.warning(f"停止配置任务运行时下发失败，将直接收敛本地状态: task_run_id={task_run_id}, error={exc}")
            return await run_in_threadpool(
                cls._finalize_cancelled, db, run, reason, operator
            )
        if response.status_code != AgentResponseEnum.SUCCESS.value:
            # Agent 拒绝或会话已变化：运行可能已结束，本地仍收敛为 CANCELLED 保持幂等。
            logger.warning(
                f"停止配置任务运行 Agent 返回失败，仍收敛本地状态: task_run_id={task_run_id}, "
                f"message={response.message}"
            )
        return await run_in_threadpool(cls._finalize_cancelled, db, run, reason, operator)

    @classmethod
    def _prepare_stop(cls, db: Session, task_run_id: int, operator: str):
        """同步查询待停止运行并校验状态；返回 (运行实体, agent_code, 错误文本)。"""
        del operator
        run = ConfigurationTaskRunDao.get_run(db, task_run_id)
        if not run:
            return None, "", "运行记录不存在"
        if run.status in RUN_TERMINAL_STATUSES:
            return None, "", f"运行已结束，无需停止：{run.status}"
        return run, run.agent_code, ""

    @classmethod
    def _finalize_cancelled(
        cls,
        db: Session,
        run: ConfigurationTaskRun,
        reason: str,
        operator: str,
    ) -> TaskRunServiceResult:
        """取消终态落库；状态不回退已完成的运行。"""
        now = datetime.now()
        duration_ms = int((now - (run.started_at or now)).total_seconds() * 1000)
        ConfigurationTaskRunDao.update_run(
            db,
            run.task_run_id,
            {
                "status": "CANCELLED",
                "error_code": "RUN_CANCELLED",
                "error_message": reason[:2000],
                "ended_at": now,
                "duration_ms": duration_ms,
                "update_by": operator,
            },
        )
        db.commit()
        refreshed = ConfigurationTaskRunDao.get_run(db, run.task_run_id)
        logger.warning(f"配置任务运行已取消: task_run_id={run.task_run_id}, operator={operator}, reason={reason}")
        return TaskRunServiceResult(True, "运行已取消", cls.to_run_model(refreshed))

    @classmethod
    def _advance_stage_by_step(cls, db: Session, task_run_id: int, step_payload: dict[str, Any]) -> None:
        """把步骤完成事件映射到运行阶段：阶段内全部步骤完成则阶段置 SUCCESS。

        任一步骤失败即把阶段置 FAILED 并跳过后续阶段（由 mark_stage_finished 统一处理）。
        映射失败只记日志，不阻塞事件主流程。
        """
        try:
            from modules.configuration_task.dao.stage_artifact_dao import ConfigurationTaskStageDao, load_json_list
            from modules.configuration_task.service.stage_service import ConfigurationTaskStageService

            stage_index = step_payload.get("stepIndex")
            status = str(step_payload.get("status") or "").strip().lower()
            if stage_index is None:
                return
            stages = ConfigurationTaskStageDao.list_run_stages(db, task_run_id)
            target = None
            for stage in stages:
                indexes = load_json_list(stage.step_range_json)
                if not indexes:
                    # 未声明阶段的单阶段模式：任意步骤都归属该阶段。
                    target = stage
                    break
                if int(stage_index) in indexes:
                    target = stage
                    break
            if not target or target.status in {"SUCCESS", "FAILED", "SKIPPED", "CANCELLED"}:
                return
            if status == "failed":
                ConfigurationTaskStageService.mark_stage_finished(
                    db,
                    target.run_stage_id,
                    False,
                    {"lastStep": step_payload},
                    error_code="STEP_FAILED",
                    error_message=str(step_payload.get("errorMessage") or "步骤执行失败"),
                )
                return
            indexes = load_json_list(target.step_range_json)
            if not indexes:
                # 单阶段模式无法判断完成度，保持 RUNNING 由 run_finished 收敛。
                if target.status != "RUNNING":
                    ConfigurationTaskStageService.mark_stage_running(db, target.run_stage_id)
                return
            if all(int(i) <= int(stage_index) for i in indexes if i > int(stage_index)) or int(stage_index) >= max(
                indexes
            ):
                ConfigurationTaskStageService.mark_stage_finished(
                    db, target.run_stage_id, True, {"lastStep": step_payload}
                )
        except Exception as exc:
            logger.warning(f"步骤阶段映射失败（不影响事件处理）: task_run_id={task_run_id}, error={exc}")

    @classmethod
    def handle_agent_run_event(cls, db: Session, agent_code: str, message_data: dict[str, Any]) -> bool:
        """处理配置任务运行的实时事件（web_run_step/status/error/finished）。

        Agent 事件按 webCaseRunId 上报；该 ID 在配置任务运行与 Web 用例运行之间
        可能冲突（不同表各自的 Snowflake/自增 ID），因此只有当 ID 命中配置任务
        运行表且 Agent 一致时才按配置任务处理，否则交回调用方走 Web 用例链路。
        :return: True 表示本事件属于配置任务运行并已处理。
        """
        payload = message_data.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        raw_run_id = (
            message_data.get("webCaseRunId")
            or message_data.get("web_case_run_id")
            or payload.get("webCaseRunId")
            or payload.get("web_case_run_id")
        )
        try:
            run_id_int = int(raw_run_id)
        except (TypeError, ValueError):
            return False
        run = ConfigurationTaskRunDao.get_run(db, run_id_int)
        if not run or run.agent_code != agent_code:
            return False
        if run.status in RUN_TERMINAL_STATUSES:
            # 终态运行不回退；同步返回路径已写过终态，事件只做日志。
            logger.debug(f"配置任务运行已是终态，忽略迟到事件: task_run_id={run_id_int}")
            return True

        message_type = str(message_data.get("type") or "").strip().lower()
        now = datetime.now()
        result_payload = load_json_object(run.result_json)
        if not isinstance(result_payload, dict):
            result_payload = {}

        def _attach_common() -> None:
            """把事件通用字段合并进结果 JSON。"""
            phase = str(payload.get("phase") or "").strip().lower()
            if phase:
                result_payload["runPhase"] = phase
            if payload.get("pageUrl"):
                result_payload["pageUrl"] = payload.get("pageUrl")
            progress = payload.get("progress")
            if isinstance(progress, dict):
                result_payload["progress"] = progress
            current_step = payload.get("currentStep")
            if isinstance(current_step, dict):
                result_payload["currentStep"] = current_step
            result_payload["lastProgressAt"] = now.isoformat()

        update_values: dict[str, Any] = {"update_by": run.update_by or run.create_by}
        if message_type == "web_run_step":
            _attach_common()
            step_payload = payload.get("step")
            if isinstance(step_payload, dict):
                steps = result_payload.get("steps")
                if not isinstance(steps, list):
                    steps = []
                step_id = step_payload.get("stepId") or step_payload.get("step_id")
                step_index = step_payload.get("stepIndex") or step_payload.get("step_index")
                replaced = False
                for position, item in enumerate(steps):
                    if not isinstance(item, dict):
                        continue
                    same_id = step_id is not None and item.get("stepId") == step_id
                    same_index = step_index is not None and item.get("stepIndex") == step_index
                    if same_id or same_index:
                        steps[position] = step_payload
                        replaced = True
                        break
                if not replaced:
                    steps.append(step_payload)
                result_payload["steps"] = steps
                # 步骤进度映射到运行阶段：步骤完成时推进所属阶段状态。
                cls._advance_stage_by_step(db, run_id_int, step_payload)
            update_values["result_json"] = _dumps(result_payload)
            update_values["update_time"] = now
            ConfigurationTaskRunDao.update_run(db, run_id_int, update_values)
            db.commit()
            return True

        if message_type == "web_run_status":
            _attach_common()
            update_values["result_json"] = _dumps(result_payload)
            update_values["update_time"] = now
            ConfigurationTaskRunDao.update_run(db, run_id_int, update_values)
            db.commit()
            return True

        if message_type in ("web_run_error", "web_run_finished"):
            _attach_common()
            steps_payload = payload.get("steps")
            if isinstance(steps_payload, list):
                result_payload["steps"] = [item for item in steps_payload if isinstance(item, dict)]
            success = payload.get("success")
            if message_type == "web_run_error":
                final_status = "FAILED"
                error_message = (
                    str(message_data.get("message") or "").strip()
                    or str(payload.get("message") or "").strip()
                    or "执行失败"
                )
            else:
                final_status = "SUCCESS" if success is not False else "FAILED"
                error_message = "" if final_status == "SUCCESS" else "执行失败"
            update_values.update(
                {
                    "status": final_status,
                    "error_code": "" if final_status == "SUCCESS" else "EXECUTION_FAILED",
                    "error_message": error_message,
                    "ended_at": now,
                    "result_json": _dumps(result_payload),
                }
            )
            started_at = run.started_at or now
            update_values["duration_ms"] = max(0, int((now - started_at).total_seconds() * 1000))
            update_values["update_by"] = run.update_by or run.create_by
            ConfigurationTaskRunDao.update_run(db, run_id_int, update_values)
            db.commit()
            logger.info(
                f"配置任务运行收到事件终态: task_run_id={run_id_int}, type={message_type}, status={final_status}"
            )
            return True
        return False

    @classmethod
    def recover_orphan_running(cls, db: Session, timeout_minutes: int = 60) -> dict[str, int]:
        """收敛重启或断线遗留的 RUNNING 孤儿运行。

        服务重启后异步等待段丢失，超过阈值仍无进展的 RUNNING 记录收敛为
        FAILED，供调用方重试；定时任务或启动钩子可周期调用。
        :return: {scanned, recovered} 摘要。
        """
        rows = ConfigurationTaskRunDao.list_runs(db, status="RUNNING", limit=200)
        now = datetime.now()
        recovered = 0
        for run in rows:
            last_progress = run.update_time or run.started_at or run.create_time or now
            if (now - last_progress).total_seconds() < timeout_minutes * 60:
                continue
            duration_ms = int((now - (run.started_at or now)).total_seconds() * 1000)
            ConfigurationTaskRunDao.update_run(
                db,
                run.task_run_id,
                {
                    "status": "FAILED",
                    "error_code": "RUN_ORPHAN_RECOVERED",
                    "error_message": "运行中断（服务重启或 Agent 断线），已被恢复扫描收敛",
                    "ended_at": now,
                    "duration_ms": duration_ms,
                    "update_by": "system",
                },
            )
            recovered += 1
        if recovered:
            db.commit()
            logger.warning(f"配置任务运行孤儿恢复完成: recovered={recovered}")
        return {"scanned": len(rows), "recovered": recovered}

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
