"""
工单群推送锚点与回帖幂等标记拆表迁移脚本（2026-09-11）。

背景：锚点（extra_data.external_sync.sync_state.group_push_message_refs）与回帖幂等
（ai_result_reply_task_ids）原存于工单 extra_data JSON，被同步更新链路的 build_meta
白名单重建静默擦除。现拆为独立表（ticket_group_push_anchor）与任务表列
（ticket_ai_analysis_task.result_replied_at），本脚本把 JSON 中的存量数据回填到新存储。

使用方式：
1. 先执行 DDL：sql/20260911_ticket_group_push_anchor.sql
2. 预览：uv run python scripts/migrate_group_push_anchor.py preview
3. 执行：uv run python scripts/migrate_group_push_anchor.py apply

说明：
- 读取 server/.env.prod 的生产库连接；
- preview 只统计不动库，apply 写入并输出逐单结果；
- 幂等可重跑：锚点按 message_id 唯一冲突自动跳过，幂等列已非 NULL 跳过；
- extra_data JSON 解析失败的工单计入失败清单输出，不静默跳过。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
from utils.snowflake import snowIdWorker  # noqa: E402  需先注入 server 根路径才能导入

ANCHOR_TABLE = "ticket_group_push_anchor"
TASK_TABLE = "ticket_ai_analysis_task"


def _load_conn() -> pymysql.connections.Connection:
    """
    从 .env.prod 读取生产库连接并建立 MySQL 连接。
    :return: pymysql 连接
    """
    load_dotenv(BASE_DIR / ".env.prod")
    return pymysql.connect(
        host=os.getenv("DB_HOST", ""),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USERNAME", ""),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_DATABASE", ""),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=15,
        autocommit=False,
    )


def _extract_targets(payload: dict) -> tuple[list[dict], list[str]]:
    """
    从工单 extra_data 解析存量锚点列表与已回帖任务 ID 列表。
    :param payload: extra_data 反序列化后的字典
    :return: (锚点列表, 已回帖任务ID列表)
    """
    external_sync = payload.get("external_sync") if isinstance(payload.get("external_sync"), dict) else {}
    sync_state = external_sync.get("sync_state") if isinstance(external_sync.get("sync_state"), dict) else {}
    refs = sync_state.get("group_push_message_refs")
    refs = refs if isinstance(refs, list) else []
    anchors = [item for item in refs if isinstance(item, dict) and str(item.get("messageId") or "").strip()]
    replied = sync_state.get("ai_result_reply_task_ids")
    replied = [str(item) for item in replied if str(item or "").strip()] if isinstance(replied, list) else []
    return anchors, replied


def _iter_tickets_with_legacy_data(db) -> list[dict]:
    """
    查询 extra_data 中仍含锚点或幂等记录的工单。
    :param db: 数据库连接
    :return: (ticket_id, extra_data) 行列表
    """
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT ticket_id, extra_data FROM ticket "
            "WHERE del_flag = '0' AND (extra_data LIKE '%group_push_message_refs%' "
            "OR extra_data LIKE '%ai_result_reply_task_ids%')"
        )
        return list(cursor.fetchall())


def _apply_anchors(db, ticket_id: int, anchors: list[dict], stats: dict) -> None:
    """
    把单个工单的存量锚点插入锚点表（message_id 冲突跳过）。
    :param db: 数据库连接
    :param ticket_id: 工单ID
    :param anchors: 锚点字典列表（camelCase 键）
    :param stats: 统计字典
    """
    with db.cursor() as cursor:
        for item in anchors:
            message_id = str(item.get("messageId") or "").strip()
            if not message_id:
                continue
            cursor.execute(
                f"INSERT IGNORE INTO {ANCHOR_TABLE} "
                "(id, ticket_id, chat_id, message_id, root_id, thread_id, receive_id, receive_id_type) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    snowIdWorker.get_id(),
                    ticket_id,
                    str(item.get("chatId") or item.get("receiveId") or "")[:64],
                    message_id[:64],
                    str(item.get("rootId") or message_id)[:64],
                    str(item.get("threadId") or "")[:64],
                    str(item.get("receiveId") or "")[:64],
                    str(item.get("receiveIdType") or "")[:20],
                ),
            )
            if cursor.rowcount > 0:
                stats["anchor_inserted"] += 1
            else:
                stats["anchor_duplicated"] += 1


def _apply_replied(db, ticket_id: int, task_ids: list[str], stats: dict) -> None:
    """
    把 JSON 幂等列表中的任务 ID 标记到任务表回帖列（已标记与不存在的任务跳过）。
    :param db: 数据库连接
    :param ticket_id: 工单ID
    :param task_ids: 已回帖任务 ID 字符串列表
    :param stats: 统计字典
    """
    with db.cursor() as cursor:
        for task_key in task_ids:
            try:
                task_id = int(task_key)
            except ValueError:
                stats["replied_invalid_task_id"] += 1
                continue
            cursor.execute(
                f"UPDATE {TASK_TABLE} SET result_replied_at = NOW() "
                "WHERE task_id = %s AND ticket_id = %s AND result_replied_at IS NULL",
                (task_id, ticket_id),
            )
            if cursor.rowcount > 0:
                stats["replied_marked"] += 1
            else:
                stats["replied_skipped"] += 1


def main() -> None:
    """脚本入口：preview 只统计，apply 执行回填并提交。"""
    parser = argparse.ArgumentParser(description="群推送锚点与回帖幂等拆表迁移回填")
    parser.add_argument("mode", choices=["preview", "apply"], help="preview 只统计不动库；apply 执行回填")
    args = parser.parse_args()

    db = _load_conn()
    try:
        rows = _iter_tickets_with_legacy_data(db)
        stats = {
            "ticket_scanned": len(rows),
            "ticket_with_anchor": 0,
            "ticket_with_replied": 0,
            "anchor_inserted": 0,
            "anchor_duplicated": 0,
            "replied_marked": 0,
            "replied_skipped": 0,
            "replied_invalid_task_id": 0,
        }
        failures: list[tuple[int, str]] = []
        for row in rows:
            ticket_id = int(row["ticket_id"])
            try:
                payload = json.loads(row["extra_data"]) if row["extra_data"] else {}
            except (TypeError, ValueError) as exc:
                failures.append((ticket_id, f"extra_data JSON 解析失败: {exc}"))
                continue
            anchors, replied = _extract_targets(payload)
            if anchors:
                stats["ticket_with_anchor"] += 1
            if replied:
                stats["ticket_with_replied"] += 1
            if args.mode == "apply":
                if anchors:
                    _apply_anchors(db, ticket_id, anchors, stats)
                if replied:
                    _apply_replied(db, ticket_id, replied, stats)
        if args.mode == "apply":
            db.commit()
        print(f"[{args.mode}] 迁移统计: {json.dumps(stats, ensure_ascii=False)}")
        if failures:
            print(f"[{args.mode}] 失败清单（{len(failures)} 条，需人工确认）:")
            for ticket_id, reason in failures:
                print(f"  ticket_id={ticket_id}: {reason}")
        elif args.mode == "preview":
            print("[preview] 未发现解析失败工单。apply 模式将按上述统计写入。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
