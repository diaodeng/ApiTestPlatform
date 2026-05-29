from collections.abc import Callable
from typing import Any

from sqlalchemy import text
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from config.database import Base, DATABASE_BACKEND, SessionLocal, engine
from scripts.seed_sqlite_from_init_sql import auto_seed_current_sqlite_if_needed
from utils.log_util import logger


class AsyncSessionProxy:
    """把同步 SQLAlchemy Session 包装成可在 async 环境下调用的代理类"""

    def __init__(self, sync_session: Session):
        self._sync_session = sync_session

    def __getattr__(self, item: str) -> Callable[..., Any]:
        """拦截方法调用，自动转到 run_in_threadpool"""
        attr = getattr(self._sync_session, item)

        if callable(attr):
            async def async_attr(*args, **kwargs):
                return await run_in_threadpool(attr, *args, **kwargs)
            return async_attr
        else:
            return attr

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await run_in_threadpool(self._sync_session.close)


def get_db_pro():
    """
    每一个请求处理完毕后会关闭当前连接，不同的请求使用不同的连接
    :return:
    """
    current_db = SessionLocal()
    try:
        yield current_db
        current_db.commit()
    except Exception:
        current_db.rollback()
        raise
    finally:
        current_db.close()

async def async_get_db_pro():
    sync_session = SessionLocal()
    async with AsyncSessionProxy(sync_session) as session:
        yield session


async def init_create_table():
    """
    应用启动时初始化数据库连接
    :return:
    """
    logger.info("初始化数据库连接...")
    Base.metadata.create_all(bind=engine)
    _ensure_large_sys_config_value_column()
    _ensure_ticket_log_pull_ticket_id_nullable()
    _ensure_celery_periodic_task_execution_mode_column()
    logger.info("数据库连接成功")
    auto_seed_current_sqlite_if_needed()


get_db = get_db_pro


def _ensure_large_sys_config_value_column():
    if DATABASE_BACKEND != "mysql":
        return

    try:
        with engine.begin() as connection:
            result = connection.execute(
                text(
                    """
                    SELECT DATA_TYPE
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'sys_config'
                      AND COLUMN_NAME = 'config_value'
                    """
                )
            ).mappings().first()
            current_type = str((result or {}).get("DATA_TYPE") or "").lower()
            if current_type in {"longtext", ""}:
                return

            logger.info("检测到 sys_config.config_value 仍为短文本，升级为 LONGTEXT")
            connection.execute(
                text(
                    """
                    ALTER TABLE sys_config
                    MODIFY COLUMN config_value LONGTEXT NULL COMMENT '参数键值'
                    """
                )
            )
    except Exception as exc:
        logger.warning(f"检查或升级 sys_config.config_value 字段失败: {exc}")


def _ensure_ticket_log_pull_ticket_id_nullable():
    if DATABASE_BACKEND != "mysql":
        return

    try:
        with engine.begin() as connection:
            result = connection.execute(
                text(
                    """
                    SELECT IS_NULLABLE
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'ticket_log_pull_record'
                      AND COLUMN_NAME = 'ticket_id'
                    """
                )
            ).mappings().first()
            is_nullable = str((result or {}).get("IS_NULLABLE") or "").upper()
            if is_nullable == "YES":
                return

            logger.info("检测到 ticket_log_pull_record.ticket_id 仍为非空，升级为可空")
            connection.execute(
                text(
                    """
                    ALTER TABLE ticket_log_pull_record
                    MODIFY COLUMN ticket_id BIGINT NULL COMMENT '工单ID'
                    """
                )
            )
    except Exception as exc:
        logger.warning(f"检查或升级 ticket_log_pull_record.ticket_id 字段失败: {exc}")


def _ensure_celery_periodic_task_execution_mode_column():
    """
    为 celery_periodic_task 补齐 execution_mode 字段，兼容旧库。

    :return: 无返回值。
    """
    try:
        with engine.begin() as connection:
            if DATABASE_BACKEND == "mysql":
                result = connection.execute(
                    text(
                        """
                        SELECT COLUMN_NAME
                        FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = 'celery_periodic_task'
                          AND COLUMN_NAME = 'execution_mode'
                        """
                    )
                ).mappings().first()
                if result:
                    return
                logger.info("检测到 celery_periodic_task 缺少 execution_mode 列，自动补齐")
                connection.execute(
                    text(
                        """
                        ALTER TABLE celery_periodic_task
                        ADD COLUMN execution_mode VARCHAR(16) NOT NULL DEFAULT 'thread' COMMENT '执行方式：thread/process'
                        AFTER queue_name
                        """
                    )
                )
                return

            if DATABASE_BACKEND == "sqlite":
                rows = connection.execute(text("PRAGMA table_info(celery_periodic_task)")).mappings().all()
                if any(str(row.get("name") or "") == "execution_mode" for row in rows):
                    return
                logger.info("检测到 sqlite celery_periodic_task 缺少 execution_mode 列，自动补齐")
                connection.execute(
                    text(
                        """
                        ALTER TABLE celery_periodic_task
                        ADD COLUMN execution_mode VARCHAR(16) NOT NULL DEFAULT 'thread'
                        """
                    )
                )
    except Exception as exc:
        logger.warning(f"检查或升级 celery_periodic_task.execution_mode 字段失败: {exc}")
