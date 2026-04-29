from __future__ import annotations

import argparse
import asyncio
import importlib
import os
import re
import sqlite3
import sys
from collections import OrderedDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


CREATE_TABLE_RE = re.compile(r"^\s*create\s+table\s+`?([A-Za-z0-9_]+)`?\s*(\()?\s*$", re.IGNORECASE)
INSERT_RE = re.compile(
    r"^\s*insert\s+into\s+`?([A-Za-z0-9_]+)`?\s+values\s*(\(.*\))\s*;\s*$",
    re.IGNORECASE,
)
FUNCTION_REPLACEMENTS = (
    (re.compile(r"\bsysdate\s*\(\s*\)", re.IGNORECASE), "CURRENT_TIMESTAMP"),
    (re.compile(r"`"), ""),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="将 MySQL 初始化 SQL 中的种子数据导入 SQLite。")
    parser.add_argument(
        "--env",
        default=os.environ.get("APP_ENV", "dev") or "dev",
        help="读取项目配置时使用的环境名，对应 .env.<env>。",
    )
    parser.add_argument(
        "--sql-file",
        default="sql/apitest.sql",
        help="初始化 SQL 文件路径，默认 server/sql/apitest.sql",
    )
    parser.add_argument(
        "--db-file",
        default="",
        help="SQLite 文件路径。默认从当前项目配置中读取。",
    )
    parser.add_argument(
        "--create-schema",
        action="store_true",
        help="导入前先按当前项目 ORM 创建 SQLite 表结构。",
    )
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="导入前先清空 SQL 文件中涉及到的目标表数据。",
    )
    parser.add_argument(
        "--table-prefix",
        default="sys_",
        help="仅导入指定前缀的表数据，默认 sys_。",
    )
    return parser.parse_args()


def prepare_project_env(env_name: str) -> None:
    os.environ["APP_ENV"] = env_name
    sys.argv = [sys.argv[0], "--env", env_name]


def normalize_sql_fragment(fragment: str) -> str:
    result = fragment
    for pattern, replacement in FUNCTION_REPLACEMENTS:
        result = pattern.sub(replacement, result)
    return result


def resolve_sql_file_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def parse_table_columns(sql_text: str) -> dict[str, list[str]]:
    table_columns: dict[str, list[str]] = {}
    current_table: str | None = None
    current_columns: list[str] = []
    pending_table: str | None = None

    for raw_line in sql_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("--"):
            continue

        if current_table is None:
            if pending_table is not None and line == "(":
                current_table = pending_table
                pending_table = None
                current_columns = []
                continue

            match = CREATE_TABLE_RE.match(line)
            if match:
                if match.group(2):
                    current_table = match.group(1)
                    current_columns = []
                else:
                    pending_table = match.group(1)
            continue

        if line.startswith(")"):
            table_columns[current_table] = current_columns[:]
            current_table = None
            current_columns = []
            continue

        lowered = line.lower()
        if lowered.startswith(("primary key", "unique key", "unique ", "key ", "constraint ", "index ")):
            continue

        column_name = line.split(None, 1)[0].rstrip(",").strip("`")
        if column_name:
            current_columns.append(column_name)

    return table_columns


def build_insert_statements(
    sql_text: str, table_columns: dict[str, list[str]], table_prefix: str
) -> list[tuple[str, str]]:
    statements: list[tuple[str, str]] = []
    for raw_line in sql_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = INSERT_RE.match(line)
        if not match:
            continue

        table_name = match.group(1)
        if table_prefix and not table_name.startswith(table_prefix):
            continue

        columns = table_columns.get(table_name)
        if not columns:
            raise ValueError(f"在初始化 SQL 中找不到表 {table_name} 的列定义，无法安全重写 INSERT。")

        values_clause = normalize_sql_fragment(match.group(2))
        column_clause = ", ".join(columns)
        statement = f"INSERT INTO {table_name} ({column_clause}) VALUES {values_clause};"
        statements.append((table_name, statement))

    return statements


def resolve_sqlite_db_path(db_file: str) -> Path:
    if db_file:
        return Path(db_file).expanduser().resolve()

    from config.database import DATABASE_BACKEND, SQLALCHEMY_DATABASE_URL

    if DATABASE_BACKEND != "sqlite":
        raise SystemExit("当前配置不是 sqlite，请先设置 DB_TYPE=sqlite，或通过 --db-file 指定 SQLite 文件。")

    if SQLALCHEMY_DATABASE_URL.endswith(":memory:"):
        raise SystemExit("不能向 :memory: SQLite 导入初始化文件，请改成文件型 SQLite。")

    prefix = "sqlite+pysqlite:///"
    if not SQLALCHEMY_DATABASE_URL.startswith(prefix):
        raise SystemExit(f"无法识别当前 SQLite URL：{SQLALCHEMY_DATABASE_URL}")

    return Path(SQLALCHEMY_DATABASE_URL[len(prefix):]).expanduser().resolve()


def load_model_modules() -> None:
    model_packages = {
        "module_admin.entity.do": BASE_DIR / "module_admin" / "entity" / "do",
        "module_hrm.entity.do": BASE_DIR / "module_hrm" / "entity" / "do",
    }
    for package_name, package_dir in model_packages.items():
        for file_path in sorted(package_dir.glob("*_do.py")):
            if file_path.name == "__init__.py":
                continue
            importlib.import_module(f"{package_name}.{file_path.stem}")


async def create_schema_if_needed() -> None:
    load_model_modules()
    from config.get_db import init_create_table

    await init_create_table()


def ensure_target_tables_exist(connection: sqlite3.Connection, table_names: list[str]) -> None:
    existing_tables = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    missing_tables = [table for table in table_names if table not in existing_tables]
    if missing_tables:
        missing_display = ", ".join(missing_tables)
        raise SystemExit(f"SQLite 中缺少目标表：{missing_display}。请先执行建表，再导入初始化数据。")


def import_seed_data(
    db_path: Path, statements: list[tuple[str, str]], clear_existing: bool
) -> tuple[int, int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tables_in_order = list(OrderedDict.fromkeys(table for table, _ in statements))

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        ensure_target_tables_exist(connection, tables_in_order)

        if clear_existing:
            for table_name in reversed(tables_in_order):
                connection.execute(f"DELETE FROM {table_name}")

        success_count = 0
        for table_name, statement in statements:
            try:
                connection.execute(statement)
                success_count += 1
            except sqlite3.IntegrityError as exc:
                raise SystemExit(f"导入 {table_name} 失败，通常是重复主键或唯一键冲突：{exc}") from exc
            except sqlite3.DatabaseError as exc:
                raise SystemExit(f"执行 SQL 失败，表 {table_name}：{exc}\nSQL: {statement}") from exc

        connection.commit()
        connection.execute("PRAGMA foreign_keys = ON")

    return len(tables_in_order), success_count


def get_non_empty_tables(db_path: Path, table_names: list[str]) -> list[str]:
    with sqlite3.connect(db_path) as connection:
        ensure_target_tables_exist(connection, table_names)
        non_empty_tables = []
        for table_name in table_names:
            row = connection.execute(f"SELECT 1 FROM {table_name} LIMIT 1").fetchone()
            if row is not None:
                non_empty_tables.append(table_name)
        return non_empty_tables


def auto_seed_current_sqlite_if_needed() -> tuple[int, int] | None:
    from config.database import DATABASE_BACKEND, SQLALCHEMY_DATABASE_URL
    from config.env import DataBaseConfig
    from utils.log_util import logger

    if DATABASE_BACKEND != "sqlite":
        return None
    if not DataBaseConfig.sqlite_auto_seed:
        return None
    if SQLALCHEMY_DATABASE_URL.endswith(":memory:"):
        logger.info("当前 SQLite 为 :memory:，跳过自动导入初始化数据")
        return None

    db_path = resolve_sqlite_db_path("")
    sql_file = resolve_sql_file_path(DataBaseConfig.sqlite_seed_sql_file)
    if not sql_file.exists():
        logger.warning(f"SQLite 自动导入已开启，但初始化 SQL 不存在：{sql_file}")
        return None

    sql_text = sql_file.read_text(encoding="utf-8")
    table_columns = parse_table_columns(sql_text)
    statements = build_insert_statements(sql_text, table_columns, DataBaseConfig.sqlite_seed_table_prefix)
    if not statements:
        logger.info("SQLite 自动导入未发现可导入的初始化数据，已跳过")
        return None

    table_names = list(OrderedDict.fromkeys(table_name for table_name, _ in statements))
    non_empty_tables = get_non_empty_tables(db_path, table_names)
    if non_empty_tables:
        preview = ", ".join(non_empty_tables[:3])
        suffix = "..." if len(non_empty_tables) > 3 else ""
        logger.info(f"SQLite 初始化数据已存在，跳过自动导入：{preview}{suffix}")
        return None

    table_count, statement_count = import_seed_data(db_path, statements, clear_existing=False)
    logger.info(f"SQLite 初始化数据导入完成：tables={table_count}, statements={statement_count}")
    return table_count, statement_count


def main() -> None:
    args = parse_args()
    prepare_project_env(args.env)
    sql_file = resolve_sql_file_path(args.sql_file)
    if not sql_file.exists():
        raise SystemExit(f"初始化 SQL 文件不存在：{sql_file}")

    if args.create_schema:
        asyncio.run(create_schema_if_needed())

    db_path = resolve_sqlite_db_path(args.db_file)
    sql_text = sql_file.read_text(encoding="utf-8")
    table_columns = parse_table_columns(sql_text)
    statements = build_insert_statements(sql_text, table_columns, args.table_prefix)

    if not statements:
        raise SystemExit("没有找到可导入的 INSERT 语句。")

    table_count, statement_count = import_seed_data(db_path, statements, args.clear_existing)
    print(f"seed_ok db={db_path}")
    print(f"tables={table_count} statements={statement_count}")


if __name__ == "__main__":
    main()
