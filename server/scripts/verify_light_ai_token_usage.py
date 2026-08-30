"""
只读验证脚本：查询轻量 AI 与深度分析的 Token 统计真实落库情况。
使用 .env.prod 的数据库配置，仅执行 SELECT 查询，不写入任何数据。
"""
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]

import pymysql


def load_env_prod() -> dict[str, str]:
    """解析 .env.prod 中的 KEY = 'value' 配置。"""
    values: dict[str, str] = {}
    for raw_line in (SERVER_ROOT / ".env.prod").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def main() -> None:
    env = load_env_prod()
    conn = pymysql.connect(
        host=env["DB_HOST"],
        port=int(env["DB_PORT"]),
        user=env["DB_USERNAME"],
        password=env["DB_PASSWORD"],
        database=env["DB_DATABASE"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
    )
    try:
        with conn.cursor() as cursor:
            # 1. 审计执行记录表：轻量 AI 与深度分析的 token 覆盖率
            #    审计表只有 token_usage JSON 字段；input/total 明细列在任务表上
            cursor.execute(
                """
                SELECT task_type, status,
                       COUNT(*) AS total_count,
                       SUM(CASE WHEN token_usage IS NOT NULL AND JSON_LENGTH(token_usage) > 0 THEN 1 ELSE 0 END) AS with_token
                FROM sys_ai_task_execution
                GROUP BY task_type, status
                ORDER BY task_type, status
                """
            )
            print("=== sys_ai_task_execution 按 task_type/status 的 token 覆盖率 ===")
            for row in cursor.fetchall():
                print(row)

            # 2. 最近 12 条轻量 AI 执行记录的 token 字段实况
            cursor.execute(
                """
                SELECT execution_id, task_type, task_name, status, provider_code, model_name,
                       LEFT(IFNULL(token_usage, ''), 120) AS token_usage_preview,
                       create_time
                FROM sys_ai_task_execution
                ORDER BY execution_id DESC
                LIMIT 12
                """
            )
            print()
            print("=== 最近 AI 执行记录（含 token_usage 实况） ===")
            for row in cursor.fetchall():
                print(row)

            # 3. 深度分析任务表 token 汇总（修复后的新任务应有值）
            cursor.execute(
                """
                SELECT task_id, status,
                       input_token_count, output_token_count, total_token_count,
                       create_time
                FROM ticket_ai_analysis_task
                ORDER BY create_time DESC
                LIMIT 8
                """
            )
            print()
            print("=== ticket_ai_analysis_task 最近任务 token 字段 ===")
            for row in cursor.fetchall():
                print(row)

            # 4. 向量化记录表结构探测（确认是否有用量字段）
            cursor.execute("SHOW COLUMNS FROM embedding_record")
            cols = [r["Field"] for r in cursor.fetchall()]
            print()
            print("=== embedding_record 字段列表 ===")
            print(cols)
            cursor.execute("SELECT COUNT(*) AS c FROM embedding_record")
            print("记录数:", cursor.fetchone()["c"])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
