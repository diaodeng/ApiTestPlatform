"""
只读盘点 hrm_module 的模块编码数据，不修改数据库。

用法：
    cd server
    uv run python scripts/audit_hrm_module_codes.py

脚本只输出空编码、首尾空白、项目内重复编码和跨项目复用编码，供执行
20260823_module_common_prompt.sql 前人工确认；会读取所有状态的模块记录，
不会合并模块或改写历史工单。
"""

from collections import defaultdict
from pathlib import Path

import pymysql
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env.prod", override=True)


def get_connection():
    """按项目生产环境变量创建只读盘点连接。"""
    return pymysql.connect(
        host=str(__import__("os").environ.get("DB_HOST") or __import__("os").environ.get("MYSQL_HOST") or "127.0.0.1"),
        port=int(__import__("os").environ.get("DB_PORT") or __import__("os").environ.get("MYSQL_PORT") or 3306),
        user=str(__import__("os").environ.get("DB_USERNAME") or __import__("os").environ.get("MYSQL_USER") or ""),
        password=str(__import__("os").environ.get("DB_PASSWORD") or __import__("os").environ.get("MYSQL_PASSWORD") or ""),
        database=str(__import__("os").environ.get("DB_DATABASE") or __import__("os").environ.get("MYSQL_DATABASE") or ""),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        read_timeout=30,
        write_timeout=30,
    )


def main() -> None:
    """读取并输出模块编码异常和复用情况。"""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT module_id, project_id, module_code, module_name, status
                FROM hrm_module
                ORDER BY project_id, module_code, module_id
                """
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    grouped = defaultdict(list)
    empty_rows = []
    whitespace_rows = []
    for row in rows:
        raw_code = row.get("module_code")
        normalized = str(raw_code or "").strip()
        if not normalized:
            empty_rows.append(row)
            continue
        if str(raw_code) != normalized:
            whitespace_rows.append(row)
        grouped[(row.get("project_id"), normalized)].append(row)

    print(f"扫描模块记录数: {len(rows)}")
    print(f"空编码记录数: {len(empty_rows)}")
    for row in empty_rows:
        print(f"  空编码 module_id={row['module_id']} project_id={row['project_id']} name={row['module_name']}")
    print(f"首尾空白编码记录数: {len(whitespace_rows)}")
    for row in whitespace_rows:
        print(f"  空白 module_id={row['module_id']} project_id={row['project_id']} code={row['module_code']!r}")

    duplicates = {key: values for key, values in grouped.items() if len(values) > 1}
    print(f"项目内重复编码组数: {len(duplicates)}")
    for (project_id, code), values in duplicates.items():
        ids = ",".join(str(item["module_id"]) for item in values)
        print(f"  project_id={project_id} module_code={code} module_ids={ids}")

    by_code = defaultdict(list)
    for (project_id, code), values in grouped.items():
        by_code[code].extend((project_id, item["module_id"]) for item in values)
    reused = {code: values for code, values in by_code.items() if len({item[0] for item in values}) > 1}
    print(f"跨项目复用编码数: {len(reused)}")
    for code, values in sorted(reused.items()):
        projects = ",".join(str(project_id) for project_id, _ in values)
        print(f"  module_code={code} project_ids={projects}")


if __name__ == "__main__":
    main()
