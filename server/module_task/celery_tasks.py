import asyncio
import inspect
import json
import multiprocessing
import threading
import traceback
from datetime import datetime
from urllib.parse import quote

from redis import Redis
from sqlalchemy import update

from config.celery_app import celery_app
from config.database import SessionLocal
from config.env import RedisConfig
from module_task import scheduler_promo, scheduler_qtr, scheduler_test  # noqa: F401
from module_task.celery_contract import (
    CELERY_EXECUTE_JOB_TASK,
    parse_payload_args,
    parse_payload_kwargs,
)
from module_task.celery_job_models import CeleryPeriodicTask, CeleryTaskExecutionLog
from module_task.task_register import JOB_REGISTRY
from utils.log_util import logger

TASK_LOCK_PREFIX = "celery:task:lock"
TASK_STATE_PREFIX = "celery:task:state"
TASK_STOP_PREFIX = "celery:task:stop"
TASK_HEARTBEAT_SECONDS = 30
TASK_STATE_TTL_SECONDS = 90


def _build_redis_url(database: int) -> str:
    """
    生成 Redis URL，用于并发互斥锁。

    :param database: Redis 数据库编号。
    :return: Redis URL。
    """
    username = (RedisConfig.redis_username or "").strip()
    password = (RedisConfig.redis_password or "").strip()
    auth = ""
    if username and password:
        auth = f"{quote(username)}:{quote(password)}@"
    elif password:
        auth = f":{quote(password)}@"
    elif username:
        auth = f"{quote(username)}@"
    return f"redis://{auth}{RedisConfig.redis_host}:{RedisConfig.redis_port}/{database}"


def _build_lock_client() -> Redis:
    """
    创建互斥锁 Redis 客户端。

    :return: Redis 客户端实例。
    """
    return Redis.from_url(_build_redis_url(RedisConfig.redis_celery_database), decode_responses=True)


def _build_task_lock_key(task_id: int) -> str:
    """
    构建任务互斥锁键。

    :param task_id: 任务ID。
    :return: Redis 锁键。
    """
    return f"{TASK_LOCK_PREFIX}:{task_id}"


def _build_task_state_key(task_id: int) -> str:
    """
    构建任务运行态心跳键。

    :param task_id: 任务ID。
    :return: Redis 状态键。
    """
    return f"{TASK_STATE_PREFIX}:{task_id}"


def _build_task_stop_key(task_id: int) -> str:
    """
    构建任务停止请求键。

    :param task_id: 任务ID。
    :return: Redis 停止键。
    """
    return f"{TASK_STOP_PREFIX}:{task_id}"


def _serialize_task_state(
    *,
    task_id: int,
    celery_task_id: str,
    status: str,
    payload: dict,
    started_at: datetime,
) -> str:
    """
    序列化任务运行态快照。

    :param task_id: 任务ID。
    :param celery_task_id: Celery 任务ID。
    :param status: 当前状态。
    :param payload: 原始执行载荷。
    :param started_at: 开始时间。
    :return: JSON 字符串。
    """
    return json.dumps(
        {
            "task_id": task_id,
            "celery_task_id": celery_task_id,
            "status": status,
            "task_name": payload.get("task_name") or "",
            "task_key": payload.get("task_key") or "",
            "queue_name": payload.get("queue_name") or "celery",
            "trigger_type": payload.get("trigger_type") or "scheduler",
            "started_at": started_at.isoformat(),
            "heartbeat_at": datetime.now().isoformat(),
        },
        ensure_ascii=False,
    )


def _refresh_task_runtime_state(
    *,
    lock_client: Redis,
    task_id: int,
    celery_task_id: str,
    payload: dict,
    started_at: datetime,
    stop_event: threading.Event,
):
    """
    维护运行态心跳，用于状态可见性与失联恢复。

    :param lock_client: Redis 客户端。
    :param task_id: 任务ID。
    :param celery_task_id: Celery 任务ID。
    :param payload: 执行载荷。
    :param started_at: 开始时间。
    :param stop_event: 停止事件。
    :return: 无返回值。
    """
    state_key = _build_task_state_key(task_id)
    heartbeat_seconds = max(10, min(TASK_HEARTBEAT_SECONDS, max(int(payload.get("lock_ttl_seconds") or 30) // 3, 10)))
    state_ttl_seconds = max(TASK_STATE_TTL_SECONDS, heartbeat_seconds * 3)

    while not stop_event.wait(heartbeat_seconds):
        try:
            lock_client.set(
                state_key,
                _serialize_task_state(
                    task_id=task_id,
                    celery_task_id=celery_task_id,
                    status="running",
                    payload=payload,
                    started_at=started_at,
                ),
                ex=state_ttl_seconds,
            )
        except Exception as exc:
            logger.warning(f"刷新任务心跳失败[{task_id}]：{exc}")


def _send_child_result(result_conn, result: dict):
    """
    安全写入子进程执行结果。

    :param result_conn: 子进程结果连接。
    :param result: 结果字典。
    :return: 无返回值。
    """
    try:
        result_conn.send(result)
    except Exception as exc:
        logger.warning(f"写入任务子进程结果失败：{exc}")


def _run_registered_job_child(payload: dict, result_conn):
    """
    在子进程中执行注册任务函数。

    :param payload: 任务执行载荷。
    :param result_conn: 父进程结果连接。
    :return: 无返回值。
    """
    task_id = int(payload.get("task_id") or 0)
    celery_task_id = str(payload.get("celery_task_id") or "")
    lock_client = _build_lock_client()
    stop_event = threading.Event()
    heartbeat_thread = None
    started_at = datetime.now()

    try:
        state_key = _build_task_state_key(task_id)
        lock_client.set(
            state_key,
            _serialize_task_state(
                task_id=task_id,
                celery_task_id=celery_task_id,
                status="running",
                payload=payload,
                started_at=started_at,
            ),
            ex=max(TASK_STATE_TTL_SECONDS, 90),
        )
        heartbeat_thread = threading.Thread(
            target=_refresh_task_runtime_state,
            kwargs={
                "lock_client": lock_client,
                "task_id": task_id,
                "celery_task_id": celery_task_id,
                "payload": payload,
                "started_at": started_at,
                "stop_event": stop_event,
            },
            daemon=True,
        )
        heartbeat_thread.start()

        args = parse_payload_args(payload.get("args_json"))
        kwargs = parse_payload_kwargs(payload.get("kwargs_json"))
        _execute_job_function(task_key=str(payload.get("task_key") or ""), args=args, kwargs=kwargs)

        finished_at = datetime.now()
        _send_child_result(
            result_conn,
            {
                "status": "success",
                "message": "任务执行成功",
                "exception_info": "",
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
            },
        )
    except BaseException as exc:
        finished_at = datetime.now()
        status = "revoked" if str(exc.__class__.__name__) in {"TaskRevokedError", "SoftTimeLimitExceeded"} else "failed"
        message = "任务已手动终止" if status == "revoked" else "任务执行失败"
        _send_child_result(
            result_conn,
            {
                "status": status,
                "message": message,
                "exception_info": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
            },
        )
    finally:
        stop_event.set()
        try:
            if heartbeat_thread:
                heartbeat_thread.join(timeout=1)
        except Exception:
            pass
        try:
            state_key = _build_task_state_key(task_id)
            lock_key = _build_task_lock_key(task_id)
            stop_key = _build_task_stop_key(task_id)
            lock_client.delete(state_key, lock_key, stop_key)
        except Exception as exc:
            logger.warning(f"清理任务运行态失败[{task_id}]：{exc}")
        try:
            result_conn.close()
        except Exception:
            pass


def _execute_job_function(task_key: str, args: list, kwargs: dict):
    """
    执行注册任务函数并兼容异步函数。

    :param task_key: 注册任务键。
    :param args: 位置参数。
    :param kwargs: 关键字参数。
    :return: 任务执行返回值。
    """
    func = JOB_REGISTRY.get(task_key)
    if not func:
        raise KeyError(f"未注册的任务目标: {task_key}")

    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


def _update_task_status(
    task_id: int,
    *,
    status: str,
    message: str,
    duration_ms: int | None = None,
    add_run_count: int = 0,
    set_last_run_at: bool = False,
):
    """
    更新任务最近执行状态。

    :param task_id: 任务ID。
    :param status: 状态字符串。
    :param message: 状态说明。
    :param duration_ms: 执行耗时毫秒。
    :param add_run_count: 增加执行计数。
    :param set_last_run_at: 是否更新最近开始执行时间。
    :return: 无返回值。
    """
    session = SessionLocal()
    try:
        payload = {
            "last_status": status,
            "last_message": message,
            "update_time": datetime.now(),
        }
        if duration_ms is not None:
            payload["last_duration_ms"] = duration_ms
        if set_last_run_at:
            payload["last_run_at"] = datetime.now()

        if add_run_count > 0:
            stmt = (
                update(CeleryPeriodicTask)
                .where(CeleryPeriodicTask.task_id == task_id)
                .values(
                    **payload,
                    run_count=CeleryPeriodicTask.run_count + add_run_count,
                )
            )
            session.execute(stmt)
        else:
            session.query(CeleryPeriodicTask).filter(CeleryPeriodicTask.task_id == task_id).update(payload)
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception(f"更新任务状态失败[{task_id}]：{exc}")
    finally:
        session.close()


def _build_execution_log_fields(
    payload: dict,
    *,
    celery_task_id: str,
    status: str,
    message: str,
    exception_info: str,
    started_at: datetime,
    finished_at: datetime | None = None,
) -> dict:
    """
    构建任务执行日志字段。

    :param payload: Celery 执行载荷。
    :param celery_task_id: Celery Task UUID。
    :param status: 执行状态。
    :param message: 执行消息。
    :param exception_info: 异常信息。
    :param started_at: 开始时间。
    :param finished_at: 结束时间，运行中任务可为空。
    :return: 日志字段字典。
    """
    fields = {
        "task_id": int(payload.get("task_id") or 0),
        "owner_type": str(payload.get("owner_type") or "sys"),
        "task_name": str(payload.get("task_name") or ""),
        "task_key": str(payload.get("task_key") or ""),
        "queue_name": str(payload.get("queue_name") or "celery"),
        "trigger_type": str(payload.get("trigger_type") or "scheduler"),
        "celery_task_id": celery_task_id,
        "schedule_desc": str(payload.get("schedule_desc") or ""),
        "status": status,
        "message": message,
        "exception_info": exception_info or "",
        "args_json": str(payload.get("args_json") or "[]"),
        "kwargs_json": str(payload.get("kwargs_json") or "{}"),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": int((finished_at - started_at).total_seconds() * 1000) if finished_at else None,
    }
    return fields


def _create_execution_log(
    payload: dict,
    *,
    celery_task_id: str,
    status: str,
    message: str,
    exception_info: str,
    started_at: datetime,
    finished_at: datetime | None = None,
):
    """
    新建任务执行日志。

    :param payload: Celery 执行载荷。
    :param celery_task_id: Celery Task UUID。
    :param status: 执行状态。
    :param message: 执行消息。
    :param exception_info: 异常信息。
    :param started_at: 开始时间。
    :param finished_at: 结束时间，运行中任务可为空。
    :return: 无返回值。
    """
    session = SessionLocal()
    try:
        session.add(
            CeleryTaskExecutionLog(
                **_build_execution_log_fields(
                    payload,
                    celery_task_id=celery_task_id,
                    status=status,
                    message=message,
                    exception_info=exception_info,
                    started_at=started_at,
                    finished_at=finished_at,
                ),
                create_time=started_at,
            )
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception(f"写入任务日志失败[{payload.get('task_id')}]：{exc}")
    finally:
        session.close()


def _update_execution_log(
    payload: dict,
    *,
    celery_task_id: str,
    status: str,
    message: str,
    exception_info: str,
    started_at: datetime,
    finished_at: datetime,
):
    """
    更新任务执行日志。

    :param payload: Celery 执行载荷。
    :param celery_task_id: Celery Task UUID。
    :param status: 执行状态。
    :param message: 执行消息。
    :param exception_info: 异常信息。
    :param started_at: 开始时间。
    :param finished_at: 结束时间。
    :return: 无返回值。
    """
    session = SessionLocal()
    try:
        update_fields = _build_execution_log_fields(
            payload,
            celery_task_id=celery_task_id,
            status=status,
            message=message,
            exception_info=exception_info,
            started_at=started_at,
            finished_at=finished_at,
        )
        updated_count = (
            session.query(CeleryTaskExecutionLog)
            .filter(
                CeleryTaskExecutionLog.task_id == int(payload.get("task_id") or 0),
                CeleryTaskExecutionLog.owner_type == str(payload.get("owner_type") or "sys"),
                CeleryTaskExecutionLog.celery_task_id == celery_task_id,
            )
            .update(update_fields)
        )
        if not updated_count:
            session.add(
                CeleryTaskExecutionLog(
                    **update_fields,
                    create_time=started_at,
                )
            )
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception(f"更新任务日志失败[{payload.get('task_id')}]：{exc}")
    finally:
        session.close()


@celery_app.task(name=CELERY_EXECUTE_JOB_TASK, bind=True, ignore_result=True)
def execute_registered_job(self, payload: dict):
    """
    Celery Worker 统一任务执行入口。

    :param self: Celery task 实例（bind=True 自动注入）。
    :param payload: 任务执行载荷。
    :return: 执行结果摘要。
    """
    task_id = int(payload.get("task_id") or 0)
    allow_concurrent = bool(payload.get("allow_concurrent"))
    lock_ttl_seconds = int(payload.get("lock_ttl_seconds") or 3600)
    lock_key = _build_task_lock_key(task_id)
    state_key = _build_task_state_key(task_id)
    stop_key = _build_task_stop_key(task_id)
    lock_client = None
    lock_acquired = False
    started_at = datetime.now()
    child_process = None
    result_parent_conn = None
    result_child_conn = None
    runtime_client = None

    try:
        payload = dict(payload)
        payload["celery_task_id"] = self.request.id

        if not allow_concurrent:
            lock_client = _build_lock_client()
            lock_acquired = bool(lock_client.set(lock_key, "1", nx=True, ex=max(lock_ttl_seconds, 30)))
            if not lock_acquired:
                finished_at = datetime.now()
                duration_ms = int((finished_at - started_at).total_seconds() * 1000)
                _update_task_status(
                    task_id,
                    status="skipped",
                    message="任务并发冲突，已跳过",
                    duration_ms=duration_ms,
                    add_run_count=1,
                )
                _create_execution_log(
                    payload=payload,
                    celery_task_id=self.request.id,
                    status="skipped",
                    message="任务并发冲突，已跳过",
                    exception_info="已有同任务实例在执行",
                    started_at=started_at,
                    finished_at=finished_at,
                )
                return {"status": "skipped"}

        _update_task_status(
            task_id,
            status="running",
            message="任务开始执行",
            set_last_run_at=True,
        )
        _create_execution_log(
            payload=payload,
            celery_task_id=self.request.id,
            status="running",
            message="任务开始执行",
            exception_info="",
            started_at=started_at,
        )
        runtime_client = lock_client or _build_lock_client()

        result_parent_conn, result_child_conn = multiprocessing.get_context("spawn").Pipe()
        child_process = multiprocessing.get_context("spawn").Process(
            target=_run_registered_job_child,
            args=(payload, result_child_conn),
            daemon=True,
        )
        child_process.start()
        try:
            if result_child_conn:
                result_child_conn.close()
        except Exception:
            pass

        result = None
        while True:
            if runtime_client and runtime_client.get(stop_key):
                if child_process and child_process.is_alive():
                    child_process.terminate()
                    child_process.join(timeout=5)
                result = {
                    "status": "revoked",
                    "message": "任务已手动终止",
                    "exception_info": "收到停止请求",
                    "started_at": started_at.isoformat(),
                    "finished_at": datetime.now().isoformat(),
                }
                break

            if result_parent_conn and result_parent_conn.poll(1):
                result = result_parent_conn.recv()
                break

            if child_process and not child_process.is_alive():
                exitcode = child_process.exitcode
                result = {
                    "status": "failed",
                    "message": "任务执行失败",
                    "exception_info": f"子进程未返回结果，exitcode={exitcode}",
                    "started_at": started_at.isoformat(),
                    "finished_at": datetime.now().isoformat(),
                }
                break

        if result is None:
            result = {
                "status": "failed",
                "message": "任务执行失败",
                "exception_info": "子进程未返回结果",
                "started_at": started_at.isoformat(),
                "finished_at": datetime.now().isoformat(),
            }

        finished_at = datetime.fromisoformat(result["finished_at"])
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        final_status = str(result.get("status") or "failed")
        final_message = str(result.get("message") or "")
        final_exception = str(result.get("exception_info") or "")
        if final_status != "success":
            logger.error(
                f"任务执行结束[{task_id}]，状态={final_status}，消息={final_message}，异常={final_exception}"
            )

        _update_task_status(
            task_id,
            status=final_status,
            message=final_message,
            duration_ms=duration_ms,
            add_run_count=1,
        )
        _update_execution_log(
            payload=payload,
            celery_task_id=self.request.id,
            status=final_status,
            message=final_message,
            exception_info=final_exception,
            started_at=started_at,
            finished_at=finished_at,
        )
        if final_status == "success":
            return {"status": "success"}
        if final_status == "revoked":
            return {"status": "revoked"}
        if final_status == "skipped":
            return {"status": "skipped"}
        return {"status": final_status}
    except Exception as exc:
        finished_at = datetime.now()
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        logger.exception(f"任务执行失败[{task_id}]：{exc}")
        _update_task_status(
            task_id,
            status="failed",
            message=f"任务执行失败: {exc}",
            duration_ms=duration_ms,
            add_run_count=1,
        )
        _update_execution_log(
            payload=payload,
            celery_task_id=self.request.id,
            status="failed",
            message="任务执行失败",
            exception_info=str(exc),
            started_at=started_at,
            finished_at=finished_at,
        )
        raise
    finally:
        try:
            if child_process and child_process.is_alive():
                child_process.terminate()
                child_process.join(timeout=5)
        except Exception as exc:
            logger.warning(f"结束任务子进程失败[{task_id}]：{exc}")
        try:
            if lock_client and lock_acquired:
                lock_client.delete(lock_key)
            if runtime_client:
                runtime_client.delete(state_key, stop_key)
        except Exception as exc:
            logger.warning(f"释放任务锁失败[{task_id}]：{exc}")
        try:
            if result_parent_conn:
                result_parent_conn.close()
        except Exception:
            pass
        try:
            if result_child_conn:
                result_child_conn.close()
        except Exception:
            pass
