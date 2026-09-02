from collections.abc import Callable
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text
from sqlalchemy.orm import Session

from config.database import DATABASE_BACKEND, Base, SessionLocal, engine
from scripts.seed_sqlite_from_init_sql import auto_seed_current_sqlite_if_needed
from utils.log_util import logger


class AsyncSessionProxy:
    """把同步 SQLAlchemy Session 包装成可在 async 环境下调用的代理类。"""

    def __init__(self, sync_session: Session):
        self._sync_session = sync_session

    def __getattr__(self, item: str) -> Callable[..., Any]:
        """拦截方法调用，自动转成 run_in_threadpool。"""
        attr = getattr(self._sync_session, item)

        if callable(attr):

            async def async_attr(*args, **kwargs):
                return await run_in_threadpool(attr, *args, **kwargs)

            return async_attr
        return attr

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await run_in_threadpool(self._sync_session.close)


def get_db_pro():
    """
    每一个请求处理完毕后会关闭当前连接，不同的请求使用不同的连接
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
    """
    logger.info("初始化数据库连接...")
    Base.metadata.create_all(bind=engine)
    _ensure_large_sys_config_value_column()
    _ensure_ticket_log_pull_ticket_id_nullable()
    _ensure_ticket_log_pull_record_poll_deadline_column()
    _ensure_celery_task_execution_log_trace_id_column()
    _ensure_celery_periodic_task_execution_mode_column()
    _ensure_hrm_project_business_code_column()
    _ensure_hrm_module_business_code_column()
    _ensure_ticket_role_columns()
    _ensure_ticket_classification_columns()
    _ensure_ai_provider_preferred_executor_column()
    _ensure_ai_provider_observability_columns()
    _ensure_ticket_ai_analysis_token_columns()
    _ensure_ai_analysis_error_code_columns()
    _ensure_ticket_ai_analysis_fingerprint_columns()
    _ensure_ticket_ai_analysis_active_lock()
    _ensure_user_config_unique_index()
    logger.info("数据库连接成功")
    auto_seed_current_sqlite_if_needed()


get_db = get_db_pro


def _ensure_large_sys_config_value_column():
    if DATABASE_BACKEND != "mysql":
        return

    try:
        with engine.begin() as connection:
            result = (
                connection.execute(
                    text(
                        """
                    SELECT DATA_TYPE
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'sys_config'
                      AND COLUMN_NAME = 'config_value'
                    """
                    )
                )
                .mappings()
                .first()
            )
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
            result = (
                connection.execute(
                    text(
                        """
                    SELECT IS_NULLABLE
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'ticket_log_pull_record'
                      AND COLUMN_NAME = 'ticket_id'
                    """
                    )
                )
                .mappings()
                .first()
            )
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


def _ensure_ticket_log_pull_record_poll_deadline_column():
    """
    为 ticket_log_pull_record 补齐 poll_deadline_at 字段，兼容旧库。
    """
    if DATABASE_BACKEND != "mysql":
        return

    try:
        with engine.begin() as connection:
            result = (
                connection.execute(
                    text(
                        """
                        SELECT COLUMN_NAME
                        FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = 'ticket_log_pull_record'
                          AND COLUMN_NAME = 'poll_deadline_at'
                        """
                    )
                )
                .mappings()
                .first()
            )
            if result:
                return
            logger.info("检测到 ticket_log_pull_record 缺少 poll_deadline_at 列，自动补齐")
            connection.execute(
                text(
                    """
                    ALTER TABLE ticket_log_pull_record
                    ADD COLUMN poll_deadline_at DATETIME NULL COMMENT '轮询截止时间'
                    """
                )
            )
    except Exception as exc:
        logger.warning(f"检查或升级 ticket_log_pull_record.poll_deadline_at 字段失败: {exc}")


def _ensure_celery_task_execution_log_trace_id_column():
    """
    为 celery_task_execution_log 补齐 trace_id 字段，兼容旧库。
    """
    if DATABASE_BACKEND not in {"mysql", "sqlite"}:
        return

    try:
        with engine.begin() as connection:
            if DATABASE_BACKEND == "mysql":
                result = (
                    connection.execute(
                        text(
                            """
                            SELECT COLUMN_NAME
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'celery_task_execution_log'
                              AND COLUMN_NAME = 'trace_id'
                            """
                        )
                    )
                    .mappings()
                    .first()
                )
                if result:
                    return
                logger.info("检测到 celery_task_execution_log 缺少 trace_id 列，自动补齐")
                connection.execute(
                    text(
                        """
                        ALTER TABLE celery_task_execution_log
                        ADD COLUMN trace_id VARCHAR(64) NULL COMMENT '任务链路追踪ID' AFTER celery_task_id
                        """
                    )
                )
                return

            rows = connection.execute(text("PRAGMA table_info(celery_task_execution_log)")).mappings().all()
            existing_columns = {str(row.get("name") or "") for row in rows}
            if "trace_id" in existing_columns:
                return
            logger.info("检测到 sqlite celery_task_execution_log.trace_id 缺少，自动补齐")
            connection.execute(text("ALTER TABLE celery_task_execution_log ADD COLUMN trace_id VARCHAR(64)"))
    except Exception as exc:
        logger.warning(f"检查或升级 celery_task_execution_log.trace_id 字段失败: {exc}")


def _ensure_celery_periodic_task_execution_mode_column():
    """
    为 celery_periodic_task 补齐 execution_mode 字段，兼容旧库。
    """
    try:
        with engine.begin() as connection:
            if DATABASE_BACKEND == "mysql":
                result = (
                    connection.execute(
                        text(
                            """
                        SELECT COLUMN_NAME
                        FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = 'celery_periodic_task'
                          AND COLUMN_NAME = 'execution_mode'
                        """
                        )
                    )
                    .mappings()
                    .first()
                )
                if result:
                    return
                logger.info("检测到 celery_periodic_task 缺少 execution_mode 列，自动补齐")
                connection.execute(
                    text(
                        """
                        ALTER TABLE celery_periodic_task
                        ADD COLUMN execution_mode VARCHAR(16) NOT NULL DEFAULT 'thread'
                        COMMENT '执行方式：thread/process'
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


def _ensure_hrm_project_business_code_column():
    if DATABASE_BACKEND not in {"mysql", "sqlite"}:
        return

    try:
        with engine.begin() as connection:
            if DATABASE_BACKEND == "mysql":
                result = (
                    connection.execute(
                        text(
                            """
                        SELECT COLUMN_NAME
                        FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = 'hrm_project'
                          AND COLUMN_NAME = 'project_code'
                        """
                        )
                    )
                    .mappings()
                    .first()
                )
                if not result:
                    connection.execute(
                        text(
                            """
                            ALTER TABLE hrm_project
                            ADD COLUMN project_code VARCHAR(128) NULL COMMENT '项目业务码'
                            AFTER project_id
                            """
                        )
                    )
            else:
                rows = connection.execute(text("PRAGMA table_info(hrm_project)")).mappings().all()
                if not any(str(row.get("name") or "") == "project_code" for row in rows):
                    connection.execute(text("ALTER TABLE hrm_project ADD COLUMN project_code VARCHAR(128)"))
    except Exception as exc:
        logger.warning(f"检查或升级 hrm_project.project_code 字段失败: {exc}")


def _ensure_hrm_module_business_code_column():
    if DATABASE_BACKEND not in {"mysql", "sqlite"}:
        return

    try:
        with engine.begin() as connection:
            if DATABASE_BACKEND == "mysql":
                result = (
                    connection.execute(
                        text(
                            """
                        SELECT COLUMN_NAME
                        FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = 'hrm_module'
                          AND COLUMN_NAME = 'module_code'
                        """
                        )
                    )
                    .mappings()
                    .first()
                )
                if not result:
                    connection.execute(
                        text(
                            """
                            ALTER TABLE hrm_module
                            ADD COLUMN module_code VARCHAR(128) NULL COMMENT '模块业务码'
                            AFTER module_id
                            """
                        )
                    )
            else:
                rows = connection.execute(text("PRAGMA table_info(hrm_module)")).mappings().all()
                if not any(str(row.get("name") or "") == "module_code" for row in rows):
                    connection.execute(text("ALTER TABLE hrm_module ADD COLUMN module_code VARCHAR(128)"))
    except Exception as exc:
        logger.warning(f"检查或升级 hrm_module.module_code 字段失败: {exc}")


def _ensure_ticket_role_columns():
    """
    为工单主表补齐 1线人员和内部负责人字段，兼容旧库。
    """
    if DATABASE_BACKEND not in {"mysql", "sqlite"}:
        return

    column_specs = [
        ("first_line_assignee_id", "BIGINT", "1线人员ID", "first_line_assignee_name"),
        ("first_line_assignee_name", "VARCHAR(100)", "1线人员名称", "internal_owner_id"),
        ("internal_owner_id", "BIGINT", "内部工单负责人ID", "internal_owner_name"),
        ("internal_owner_name", "VARCHAR(100)", "内部工单负责人名称", None),
    ]

    try:
        with engine.begin() as connection:
            if DATABASE_BACKEND == "mysql":
                existing_columns = {
                    row["COLUMN_NAME"]
                    for row in connection.execute(
                        text(
                            """
                            SELECT COLUMN_NAME
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'ticket'
                            """
                        )
                    )
                    .mappings()
                    .all()
                }
                for column_name, column_type, _comment, after_column in column_specs:
                    if column_name in existing_columns:
                        continue
                    logger.info("检测到 ticket.%s 缺少，自动补齐", column_name)
                    after_clause = f" AFTER {after_column}" if after_column and after_column in existing_columns else ""
                    connection.execute(
                        text(
                            f"""
                            ALTER TABLE ticket
                            ADD COLUMN {column_name} {column_type} NULL COMMENT '{_comment}'{after_clause}
                            """
                        )
                    )
                return

            rows = connection.execute(text("PRAGMA table_info(ticket)")).mappings().all()
            existing_columns = {str(row.get("name") or "") for row in rows}
            for column_name, column_type, _comment, _ in column_specs:
                if column_name in existing_columns:
                    continue
                logger.info(f"检测到 sqlite ticket.{column_name} 缺少，自动补齐")
                connection.execute(text(f"ALTER TABLE ticket ADD COLUMN {column_name} {column_type}"))
    except Exception as exc:
        logger.warning(f"检查或升级 ticket 角色字段失败: {exc}")


def _ensure_ticket_classification_columns():
    """
    为工单主表补齐分类统计字段，兼容旧库。
    """
    if DATABASE_BACKEND not in {"mysql", "sqlite"}:
        return

    column_specs = [
        ("issue_type_id", "VARCHAR(64)", "工单类型编码", "category_name"),
        ("issue_type_name", "VARCHAR(128)", "工单类型名称", "issue_type_id"),
        ("root_cause_type", "VARCHAR(128)", "根因分类", "is_problem"),
        ("solution_type", "VARCHAR(128)", "解决方式", "root_cause_type"),
        ("resolution_code", "VARCHAR(64)", "关闭结果编码", "solution_type"),
        ("resolution_name", "VARCHAR(128)", "关闭结果名称", "resolution_code"),
        ("problem_pattern_code", "VARCHAR(128)", "细分问题类型编码", "resolution_name"),
        ("problem_pattern_name", "VARCHAR(256)", "细分问题类型名称", "problem_pattern_code"),
        ("problem_pattern_confidence", "INT", "细分问题类型置信度，0-100", "problem_pattern_name"),
        ("problem_pattern_source", "VARCHAR(32)", "细分问题类型来源", "problem_pattern_confidence"),
        ("problem_pattern_verified", "TINYINT(1)", "细分问题类型是否人工确认", "problem_pattern_source"),
        ("problem_pattern_verified_by", "VARCHAR(100)", "细分问题类型确认人", "problem_pattern_verified"),
        ("problem_pattern_verified_at", "DATETIME", "细分问题类型确认时间", "problem_pattern_verified_by"),
    ]

    try:
        with engine.begin() as connection:
            if DATABASE_BACKEND == "mysql":
                existing_columns = {
                    row["COLUMN_NAME"]
                    for row in connection.execute(
                        text(
                            """
                            SELECT COLUMN_NAME
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'ticket'
                            """
                        )
                    )
                    .mappings()
                    .all()
                }
                for column_name, column_type, _comment, after_column in column_specs:
                    if column_name in existing_columns:
                        continue
                    logger.info(f"检测到 ticket.{column_name} 缺少，自动补齐")
                    after_clause = f" AFTER {after_column}" if after_column and after_column in existing_columns else ""
                    connection.execute(
                        text(
                            f"""
                            ALTER TABLE ticket
                            ADD COLUMN {column_name} {column_type} NULL COMMENT '{_comment}'{after_clause}
                            """
                        )
                    )
                    existing_columns.add(column_name)
                return

            rows = connection.execute(text("PRAGMA table_info(ticket)")).mappings().all()
            existing_columns = {str(row.get("name") or "") for row in rows}
            for column_name, column_type, _comment, _ in column_specs:
                if column_name in existing_columns:
                    continue
                logger.info(f"检测到 sqlite ticket.{column_name} 缺少，自动补齐")
                connection.execute(text(f"ALTER TABLE ticket ADD COLUMN {column_name} {column_type}"))
    except Exception as exc:
        logger.warning(f"检查或升级 ticket 分类统计字段失败: {exc}")


def _ensure_ai_provider_preferred_executor_column():
    """
    为 sys_ai_provider 补齐 preferred_executor 字段，兼容旧库。
    """
    if DATABASE_BACKEND not in {"mysql", "sqlite"}:
        return

    try:
        with engine.begin() as connection:
            if DATABASE_BACKEND == "mysql":
                row = (
                    connection.execute(
                        text(
                            """
                            SELECT COLUMN_NAME
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'sys_ai_provider'
                              AND COLUMN_NAME = 'preferred_executor'
                            """
                        )
                    )
                    .mappings()
                    .first()
                )
                if row:
                    return
                logger.info("检测到 sys_ai_provider 缺少 preferred_executor，自动补齐")
                connection.execute(
                    text(
                        """
                        ALTER TABLE sys_ai_provider
                        ADD COLUMN preferred_executor VARCHAR(64) NULL COMMENT 'Provider默认执行器'
                        """
                    )
                )
                return

            rows = connection.execute(text("PRAGMA table_info(sys_ai_provider)")).mappings().all()
            if any(str(item.get("name") or "") == "preferred_executor" for item in rows):
                return
            logger.info("检测到 sqlite sys_ai_provider 缺少 preferred_executor，自动补齐")
            connection.execute(
                text("ALTER TABLE sys_ai_provider ADD COLUMN preferred_executor VARCHAR(64)")
            )
    except Exception as exc:
        logger.warning(f"检查或升级 sys_ai_provider.preferred_executor 字段失败: {exc}")


def _ensure_ai_provider_observability_columns():
    """
    为 sys_ai_provider 补齐可观测上报字段，兼容旧库。
    """
    if DATABASE_BACKEND not in {"mysql", "sqlite"}:
        return

    column_specs = [
        ("observability_enabled", "TINYINT(1) NOT NULL DEFAULT 0", "是否启用可观测上报", "AFTER worker_env"),
        ("observability_endpoint", "VARCHAR(500) NULL", "OTLP上报端点基础地址", "AFTER observability_enabled"),
        ("observability_auth_type", "VARCHAR(32) NULL", "可观测鉴权类型：bearer/basic", "AFTER observability_endpoint"),
        ("observability_api_key_prefix", "VARCHAR(128) NULL", "可观测密钥掩码前缀", "AFTER observability_auth_type"),
        ("observability_api_key_cipher_text", "TEXT NULL", "可观测鉴权密钥密文", "AFTER observability_api_key_prefix"),
        (
            "observability_service_name",
            "VARCHAR(128) NULL",
            "OTLP service.name",
            "AFTER observability_api_key_cipher_text",
        ),
        (
            "observability_cli_enabled",
            "TINYINT(1) NOT NULL DEFAULT 0",
            "是否向本地AI CLI注入原生遥测配置",
            "AFTER observability_service_name",
        ),
    ]

    try:
        with engine.begin() as connection:
            if DATABASE_BACKEND == "mysql":
                rows = (
                    connection.execute(
                        text(
                            """
                            SELECT COLUMN_NAME
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'sys_ai_provider'
                            """
                        )
                    )
                    .mappings()
                    .all()
                )
                existing_columns = {str(row.get("COLUMN_NAME") or "") for row in rows}
                for column_name, column_type, column_comment, column_position in column_specs:
                    if column_name in existing_columns:
                        continue
                    logger.info(f"检测到 sys_ai_provider 缺少 {column_name} 列，自动补齐")
                    connection.execute(
                        text(
                            f"""
                            ALTER TABLE sys_ai_provider
                            ADD COLUMN {column_name} {column_type} COMMENT '{column_comment}' {column_position}
                            """
                        )
                    )
                    existing_columns.add(column_name)
                return

            rows = connection.execute(text("PRAGMA table_info(sys_ai_provider)")).mappings().all()
            existing_columns = {str(row.get("name") or "") for row in rows}
            for column_name, column_type, _column_comment, _column_position in column_specs:
                if column_name in existing_columns:
                    continue
                logger.info(f"检测到 sqlite sys_ai_provider.{column_name} 缺少，自动补齐")
                connection.execute(text(f"ALTER TABLE sys_ai_provider ADD COLUMN {column_name} {column_type}"))
    except Exception as exc:
        logger.warning(f"检查或升级 sys_ai_provider 可观测字段失败: {exc}")

def _ensure_ticket_ai_analysis_token_columns():
    """
    为 ticket_ai_analysis_task 补齐 Token 统计与审计关联字段，兼容旧库。
    """
    if DATABASE_BACKEND not in {"mysql", "sqlite"}:
        return

    column_specs = [
        ("audit_execution_id", "BIGINT", "AI审计执行ID", "AFTER analysis_context"),
        ("input_token_count", "INT", "输入Token数", "AFTER audit_execution_id"),
        ("output_token_count", "INT", "输出Token数", "AFTER input_token_count"),
        ("total_token_count", "INT", "总Token数", "AFTER output_token_count"),
    ]

    try:
        with engine.begin() as connection:
            if DATABASE_BACKEND == "mysql":
                rows = (
                    connection.execute(
                        text(
                            """
                            SELECT COLUMN_NAME
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'ticket_ai_analysis_task'
                            """
                        )
                    )
                    .mappings()
                    .all()
                )
                existing_columns = {str(row.get("COLUMN_NAME") or "") for row in rows}
                for column_name, column_type, column_comment, column_position in column_specs:
                    if column_name in existing_columns:
                        continue
                    logger.info(f"检测到 ticket_ai_analysis_task 缺少 {column_name} 列，自动补齐")
                    connection.execute(
                        text(
                            f"""
                            ALTER TABLE ticket_ai_analysis_task
                            ADD COLUMN {column_name} {column_type} COMMENT '{column_comment}' {column_position}
                            """
                        )
                    )
                    existing_columns.add(column_name)
                return

            rows = connection.execute(text("PRAGMA table_info(ticket_ai_analysis_task)")).mappings().all()
            existing_columns = {str(row.get("name") or "") for row in rows}
            for column_name, column_type, _column_comment, _column_position in column_specs:
                if column_name in existing_columns:
                    continue
                logger.info(f"检测到 sqlite ticket_ai_analysis_task.{column_name} 缺少，自动补齐")
                connection.execute(text(f"ALTER TABLE ticket_ai_analysis_task ADD COLUMN {column_name} {column_type}"))
    except Exception as exc:
        logger.warning(f"检查或升级 ticket_ai_analysis_task token 统计字段失败: {exc}")


def _ensure_ai_analysis_error_code_columns():
    """
    为工单 AI 任务和 AI 审计表补齐结构化错误码字段，兼容旧库。
    :return: 无
    """
    if DATABASE_BACKEND not in {"mysql", "sqlite"}:
        return

    table_specs = {
        "ticket_ai_analysis_task": "失败错误码",
        "sys_ai_task_execution": "失败错误码",
    }
    try:
        with engine.begin() as connection:
            for table_name, column_comment in table_specs.items():
                if DATABASE_BACKEND == "mysql":
                    exists = connection.execute(
                        text(
                            """
                            SELECT 1
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = :table_name
                              AND COLUMN_NAME = 'error_code'
                            LIMIT 1
                            """
                        ),
                        {"table_name": table_name},
                    ).first()
                else:
                    columns = connection.execute(text(f"PRAGMA table_info({table_name})")).mappings().all()
                    exists = any(str(row.get("name") or "") == "error_code" for row in columns)
                if exists:
                    continue
                logger.info(f"检测到 {table_name} 缺少 error_code 列，自动补齐")
                if DATABASE_BACKEND == "mysql":
                    connection.execute(
                        text(
                            f"ALTER TABLE {table_name} ADD COLUMN error_code VARCHAR(100) NULL "
                            f"COMMENT '{column_comment}'"
                        )
                    )
                else:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN error_code VARCHAR(100)"))
    except Exception as exc:
        logger.warning(f"检查或升级 AI 分析错误码字段失败: {exc}")


def _ensure_ticket_ai_analysis_fingerprint_columns():
    """
    为工单 AI 任务补齐请求指纹字段及成功结果唯一索引，兼容旧库。
    :return: 无
    """
    if DATABASE_BACKEND not in {"mysql", "sqlite"}:
        return

    try:
        with engine.begin() as connection:
            if DATABASE_BACKEND == "mysql":
                existing_columns = {
                    str(row.get("COLUMN_NAME") or "")
                    for row in connection.execute(
                        text(
                            """
                            SELECT COLUMN_NAME
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'ticket_ai_analysis_task'
                            """
                        )
                    ).mappings().all()
                }
                if "request_fingerprint" not in existing_columns:
                    logger.info("检测到 ticket_ai_analysis_task 缺少 request_fingerprint，自动补齐")
                    connection.execute(
                        text(
                            "ALTER TABLE ticket_ai_analysis_task ADD COLUMN request_fingerprint VARCHAR(64) NULL "
                            "COMMENT '分析请求指纹' AFTER total_token_count"
                        )
                    )
                if "success_fingerprint" not in existing_columns:
                    logger.info("检测到 ticket_ai_analysis_task 缺少 success_fingerprint，自动补齐")
                    connection.execute(
                        text(
                            "ALTER TABLE ticket_ai_analysis_task ADD COLUMN success_fingerprint VARCHAR(64) NULL "
                            "COMMENT '成功结果唯一指纹' AFTER request_fingerprint"
                        )
                    )
                index_rows = connection.execute(
                    text(
                        """
                        SELECT INDEX_NAME
                        FROM information_schema.STATISTICS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = 'ticket_ai_analysis_task'
                        """
                    )
                ).mappings().all()
                index_names = {str(row.get("INDEX_NAME") or "") for row in index_rows}
                if "idx_ticket_ai_task_request_fingerprint" not in index_names:
                    connection.execute(
                        text(
                            "CREATE INDEX idx_ticket_ai_task_request_fingerprint "
                            "ON ticket_ai_analysis_task (request_fingerprint)"
                        )
                    )
                if "uk_ticket_ai_task_success_fingerprint" not in index_names:
                    connection.execute(
                        text(
                            "CREATE UNIQUE INDEX uk_ticket_ai_task_success_fingerprint "
                            "ON ticket_ai_analysis_task (success_fingerprint)"
                        )
                    )
                return

            columns = {
                str(row.get("name") or "")
                for row in connection.execute(text("PRAGMA table_info(ticket_ai_analysis_task)")).mappings().all()
            }
            if "request_fingerprint" not in columns:
                logger.info("检测到 sqlite ticket_ai_analysis_task 缺少 request_fingerprint，自动补齐")
                connection.execute(
                    text("ALTER TABLE ticket_ai_analysis_task ADD COLUMN request_fingerprint VARCHAR(64)")
                )
            if "success_fingerprint" not in columns:
                logger.info("检测到 sqlite ticket_ai_analysis_task 缺少 success_fingerprint，自动补齐")
                connection.execute(
                    text("ALTER TABLE ticket_ai_analysis_task ADD COLUMN success_fingerprint VARCHAR(64)")
                )
            index_names = {
                str(row.get("name") or "")
                for row in connection.execute(text("PRAGMA index_list(ticket_ai_analysis_task)")).mappings().all()
            }
            if "idx_ticket_ai_task_request_fingerprint" not in index_names:
                connection.execute(
                    text(
                        "CREATE INDEX idx_ticket_ai_task_request_fingerprint "
                        "ON ticket_ai_analysis_task (request_fingerprint)"
                    )
                )
            if "uk_ticket_ai_task_success_fingerprint" not in index_names:
                connection.execute(
                    text(
                        "CREATE UNIQUE INDEX uk_ticket_ai_task_success_fingerprint "
                        "ON ticket_ai_analysis_task (success_fingerprint)"
                    )
                )
    except Exception as exc:
        logger.warning(f"检查或升级 ticket_ai_analysis_task 指纹字段失败: {exc}")


def _ensure_ticket_ai_analysis_active_lock():
    """
    为工单 AI 任务表补齐活跃任务指纹锁字段及唯一索引，兼容旧库。

    活跃锁用于数据库级防重：任务进入 created/running 时写入请求指纹，
    终态置 NULL。唯一索引对 NULL 不去重，实现"同指纹最多一个活跃任务"。
    迁移时会把存量任务的活跃锁统一清空，避免历史执行中数据阻塞新任务。
    :return: 无
    """
    if DATABASE_BACKEND not in {"mysql", "sqlite"}:
        return

    try:
        with engine.begin() as connection:
            if DATABASE_BACKEND == "mysql":
                existing_columns = {
                    str(row.get("COLUMN_NAME") or "")
                    for row in connection.execute(
                        text(
                            """
                            SELECT COLUMN_NAME
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'ticket_ai_analysis_task'
                            """
                        )
                    ).mappings().all()
                }
                if "active_lock" not in existing_columns:
                    logger.info("检测到 ticket_ai_analysis_task 缺少 active_lock，自动补齐")
                    connection.execute(
                        text(
                            "ALTER TABLE ticket_ai_analysis_task ADD COLUMN active_lock VARCHAR(64) NULL "
                            "COMMENT '活跃任务指纹锁（created/running 时等于请求指纹，终态置空）' "
                            "AFTER success_fingerprint"
                        )
                    )
                # 补列后先清理存量值再建唯一索引，避免历史脏数据阻塞迁移。
                connection.execute(text("UPDATE ticket_ai_analysis_task SET active_lock = NULL"))
                index_names = {
                    str(row.get("INDEX_NAME") or "")
                    for row in connection.execute(
                        text(
                            """
                            SELECT INDEX_NAME
                            FROM information_schema.STATISTICS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'ticket_ai_analysis_task'
                            """
                        )
                    ).mappings().all()
                }
                if "uk_ticket_ai_task_active_lock" not in index_names:
                    connection.execute(
                        text(
                            "CREATE UNIQUE INDEX uk_ticket_ai_task_active_lock "
                            "ON ticket_ai_analysis_task (active_lock)"
                        )
                    )
                return

            columns = {
                str(row.get("name") or "")
                for row in connection.execute(text("PRAGMA table_info(ticket_ai_analysis_task)")).mappings().all()
            }
            if "active_lock" not in columns:
                logger.info("检测到 sqlite ticket_ai_analysis_task 缺少 active_lock，自动补齐")
                connection.execute(text("ALTER TABLE ticket_ai_analysis_task ADD COLUMN active_lock VARCHAR(64)"))
            connection.execute(text("UPDATE ticket_ai_analysis_task SET active_lock = NULL"))
            index_names = {
                str(row.get("name") or "")
                for row in connection.execute(text("PRAGMA index_list(ticket_ai_analysis_task)")).mappings().all()
            }
            if "uk_ticket_ai_task_active_lock" not in index_names:
                connection.execute(
                    text(
                        "CREATE UNIQUE INDEX uk_ticket_ai_task_active_lock "
                        "ON ticket_ai_analysis_task (active_lock)"
                    )
                )
    except Exception as exc:
        logger.warning(f"检查或升级 ticket_ai_analysis_task 活跃锁字段失败: {exc}")


def _ensure_user_config_unique_index():
    """
    为用户配置表补齐唯一索引，兼容旧库或create_all未创建约束的环境。
    """
    if DATABASE_BACKEND not in {"mysql", "sqlite"}:
        return

    try:
        with engine.begin() as connection:
            if DATABASE_BACKEND == "mysql":
                index_row = (
                    connection.execute(
                        text(
                            """
                            SELECT INDEX_NAME
                            FROM information_schema.STATISTICS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'sys_user_config'
                              AND INDEX_NAME = 'uk_sys_user_config_user_type_key'
                            """
                        )
                    )
                    .mappings()
                    .first()
                )
                if index_row:
                    return
                logger.info("检测到 sys_user_config 缺少唯一索引，自动补齐")
                connection.execute(
                    text(
                        """
                        ALTER TABLE sys_user_config
                        ADD UNIQUE KEY uk_sys_user_config_user_type_key (user_id, config_type, config_key)
                        """
                    )
                )
                return

            indexes = connection.execute(text("PRAGMA index_list(sys_user_config)")).mappings().all()
            if any(str(row.get("name") or "") == "uk_sys_user_config_user_type_key" for row in indexes):
                return
            logger.info("检测到 sqlite sys_user_config 缺少唯一索引，自动补齐")
            connection.execute(
                text(
                    """
                    CREATE UNIQUE INDEX uk_sys_user_config_user_type_key
                    ON sys_user_config (user_id, config_type, config_key)
                    """
                )
            )
    except Exception as exc:
        logger.warning(f"检查或升级 sys_user_config 唯一索引失败: {exc}")
