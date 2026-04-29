from __future__ import annotations

from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from config.env import DataBaseConfig


DATABASE_BACKEND = (DataBaseConfig.db_type or "mysql").strip().lower()


def _resolve_sqlite_path(raw_path: str) -> str:
    if raw_path == ":memory:":
        return raw_path
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def _build_database_url() -> str:
    if DataBaseConfig.db_url:
        return DataBaseConfig.db_url
    if DATABASE_BACKEND == "sqlite":
        sqlite_path = _resolve_sqlite_path(DataBaseConfig.db_sqlite_path)
        if sqlite_path == ":memory:":
            return "sqlite+pysqlite:///:memory:"
        return f"sqlite+pysqlite:///{sqlite_path}"
    return (
        f"mysql+pymysql://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@"
        f"{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}"
    )


SQLALCHEMY_DATABASE_URL = _build_database_url()


def _build_engine() -> Engine:
    common_kwargs = {
        "echo": DataBaseConfig.db_echo,
        "pool_pre_ping": True,
    }

    if DATABASE_BACKEND == "sqlite":
        connect_args = {
            "check_same_thread": False,
            "timeout": DataBaseConfig.db_connect_timeout,
        }
        if SQLALCHEMY_DATABASE_URL.endswith(":memory:"):
            return create_engine(
                SQLALCHEMY_DATABASE_URL,
                connect_args=connect_args,
                poolclass=StaticPool,
                **common_kwargs,
            )
        return create_engine(
            SQLALCHEMY_DATABASE_URL,
            connect_args=connect_args,
            **common_kwargs,
        )

    return create_engine(
        SQLALCHEMY_DATABASE_URL,
        max_overflow=DataBaseConfig.db_max_overflow,
        pool_size=DataBaseConfig.db_pool_size,
        pool_recycle=DataBaseConfig.db_pool_recycle,
        pool_timeout=DataBaseConfig.db_pool_timeout,
        connect_args={
            "connect_timeout": DataBaseConfig.db_connect_timeout,
            "read_timeout": DataBaseConfig.db_read_timeout,
            "write_timeout": DataBaseConfig.db_write_timeout,
        },
        **common_kwargs,
    )


def _sqlite_utf8_general_ci(value1: str | None, value2: str | None) -> int:
    left = (value1 or "").casefold()
    right = (value2 or "").casefold()
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


engine = _build_engine()


if DATABASE_BACKEND == "sqlite":
    @event.listens_for(engine, "connect")
    def _register_sqlite_compatibility(dbapi_connection, connection_record):  # type: ignore[unused-ignore]
        del connection_record
        dbapi_connection.create_collation("utf8_general_ci", _sqlite_utf8_general_ci)
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

my_metadata = MetaData()


class Base(DeclarativeBase):
    metadata = my_metadata
