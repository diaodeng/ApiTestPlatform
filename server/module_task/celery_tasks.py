import asyncio
import inspect
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


def _write_execution_log(
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
    写入任务执行日志。

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
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        session.add(
            CeleryTaskExecutionLog(
                task_id=int(payload.get("task_id") or 0),
                owner_type=str(payload.get("owner_type") or "sys"),
                task_name=str(payload.get("task_name") or ""),
                task_key=str(payload.get("task_key") or ""),
                queue_name=str(payload.get("queue_name") or "celery"),
                trigger_type=str(payload.get("trigger_type") or "scheduler"),
                celery_task_id=celery_task_id,
                schedule_desc=str(payload.get("schedule_desc") or ""),
                status=status,
                message=message,
                exception_info=exception_info or "",
                args_json=str(payload.get("args_json") or "[]"),
                kwargs_json=str(payload.get("kwargs_json") or "{}"),
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                create_time=finished_at,
            )
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception(f"写入任务日志失败[{payload.get('task_id')}]：{exc}")
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
    task_key = str(payload.get("task_key") or "")
    allow_concurrent = bool(payload.get("allow_concurrent"))
    lock_ttl_seconds = int(payload.get("lock_ttl_seconds") or 3600)
    lock_key = f"celery:task:lock:{task_id}"
    lock_client = None
    lock_acquired = False
    started_at = datetime.now()

    _update_task_status(
        task_id,
        status="running",
        message="任务开始执行",
        set_last_run_at=True,
    )

    try:
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
                _write_execution_log(
                    payload=payload,
                    celery_task_id=self.request.id,
                    status="skipped",
                    message="任务并发冲突，已跳过",
                    exception_info="已有同任务实例在执行",
                    started_at=started_at,
                    finished_at=finished_at,
                )
                return {"status": "skipped"}

        args = parse_payload_args(payload.get("args_json"))
        kwargs = parse_payload_kwargs(payload.get("kwargs_json"))
        _execute_job_function(task_key=task_key, args=args, kwargs=kwargs)

        finished_at = datetime.now()
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        _update_task_status(
            task_id,
            status="success",
            message="任务执行成功",
            duration_ms=duration_ms,
            add_run_count=1,
        )
        _write_execution_log(
            payload=payload,
            celery_task_id=self.request.id,
            status="success",
            message="任务执行成功",
            exception_info="",
            started_at=started_at,
            finished_at=finished_at,
        )
        return {"status": "success"}
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
        _write_execution_log(
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
            if lock_client and lock_acquired:
                lock_client.delete(lock_key)
        except Exception as exc:
            logger.warning(f"释放任务锁失败[{task_id}]：{exc}")
