"""
临时脚本：将 ticket.module_name（工单现有模块名）与「工单同步自动化」配置中的 moduleMappings 进行映射，
解析出正确的模块后更新 ticket 的 module_id、module_code（不改 module_name）。

说明：
- 数据库连接配置从 server/.env.prod 读取，在当前环境的 server 虚拟环境可直接运行（需安装 pymysql、python-dotenv）。
- 映射配置来源：sys_config 表 config_key='ticket.sync.automation' 的 JSON 中 moduleMappings 字段
  （前端「工单同步配置 → 映射/规则」维护，与 .env.prod 同库）。
- 匹配语义与运行时 TicketSyncFieldMappingService 保持一致：
  1. 遍历 moduleMappings，映射条目设置了 projectId 时要求工单 project_id 与之相同，否则跳过；
  2. 关键字采用"包含"匹配（module_name 包含任意 keyword / alias / matchText 即命中），按配置顺序取第一条。
- 模块解析（hrm_module，仅取 status=2 正常模块）：
  1. 工单有 project_id：优先按 (project_id + module_code) 查询，其次 (project_id + module_id)，
     再其次 (project_id + module_name)，避免跨项目同 module_code 串模块；
  2. 工单无 project_id：先按 module_id（全局唯一）查询，再按 module_code（必须全局唯一，多条则跳过并提示），
     再按 module_name（必须全局唯一）。
- 只更新 module_id / module_code（取值来自 hrm_module 实际行，保证两字段与模块表一致），module_name 保持不变。
- 运行时会先预览将更新内容并按 Enter 确认后才执行，Ctrl+C 可随时取消。
- 可选参数：`python sync_ticket_module_mapping.py [limit]`，limit 为大于 0 的整数时只处理前
  limit 条工单（便于先小范围验证）。
"""

import os
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv

# server 目录（本文件位于 server/scripts/ 下）
BASE_DIR = Path(__file__).resolve().parent.parent

# 加载 .env.prod 数据库配置
env_file = BASE_DIR / ".env.prod"
if env_file.exists():
    load_dotenv(env_file, override=True)
    print(f"已加载数据库配置: {env_file}")
else:
    print(f"找不到配置文件: {env_file}")
    sys.exit(1)

# Windows 控制台默认编码处理，避免中文乱码
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# 工单同步配置键，对应 SysConfig 表
TICKET_SYNC_CONFIG_KEY = "ticket.sync.automation"
# hrm_module 正常状态（QtrDataStatusEnum.normal.value）
HRM_MODULE_STATUS_NORMAL = 2

# 预览时最多逐行展示的更新条数，超过则只展示前 N 条避免刷屏
PREVIEW_LINE_LIMIT = 300


def safe_int(value):
    """
    将配置值安全转换为 int，空值或转换失败返回 None。
    """
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def mapping_project_id(mapping):
    """
    取映射条目配置的项目 ID（兼容 projectId / project_id 两种命名）。
    """
    return safe_int(mapping.get("projectId") or mapping.get("project_id"))


def mapping_keywords(mapping):
    """
    归一化映射条目的匹配关键字：keywords / aliases（逗号分隔字符串或列表）+ matchText。
    :return: 去空后的关键字列表。
    """
    keywords = []
    raw_value = mapping.get("keywords")
    if raw_value is None or raw_value == "":
        raw_value = mapping.get("aliases")
    if isinstance(raw_value, list):
        keywords.extend(str(item).strip() for item in raw_value if item not in (None, ""))
    elif isinstance(raw_value, str):
        keywords.extend(kw.strip() for kw in raw_value.split(",") if kw.strip())
    match_text = str(mapping.get("matchText") or "").strip()
    if match_text:
        keywords.append(match_text)
    return [kw for kw in keywords if kw]


def match_module_mapping(module_name, mappings, ticket_project_id):
    """
    按运行时语义匹配 module_name 命中的映射条目。
    :param module_name: 工单现有模块名。
    :param mappings: 模块映射配置列表。
    :param ticket_project_id: 工单项目 ID（可能为空）。
    :return: 命中的映射条目；未命中返回 None。
    """
    target = str(module_name or "").strip()
    if not target or not mappings:
        return None
    for mapping in mappings:
        if not isinstance(mapping, dict):
            continue
        # projectId 项目隔离校验：映射带项目 ID 时要求与工单项目一致
        configured_project_id = mapping_project_id(mapping)
        if configured_project_id is not None and configured_project_id != ticket_project_id:
            continue
        keywords = mapping_keywords(mapping)
        if target in keywords:
            return mapping
    return None


class ModuleResolver:
    """
    基于内存索引的模块解析器：一次性加载 hrm_module 正常模块，按项目维度和全局维度查重。
    """

    def __init__(self, module_rows):
        # 全量模块列表
        self.rows = module_rows
        # module_id -> 模块行（全局唯一）
        self.by_id = {row["module_id"]: row for row in module_rows}
        # (project_id, module_code小写) -> 模块行，仅当该项目下唯一时建立
        self.by_project_code = self._index_project("module_code")
        # (project_id, module_name小写) -> 模块行
        self.by_project_name = self._index_project("module_name")
        # module_code小写 -> 模块行，仅当全局唯一时建立（无项目上下文时使用）
        self.by_global_code = self._index_global("module_code")
        # module_name小写 -> 模块行，仅当全局唯一时建立
        self.by_global_name = self._index_global("module_name")

    @staticmethod
    def _norm(value):
        """统一小写并去空格，便于大小写不敏感匹配。"""
        return str(value or "").strip().lower()

    @staticmethod
    def _first_unique_row(grouped):
        """分组内恰好一条时返回该行，否则返回 None（冲突不猜测）。"""
        if len(grouped) == 1:
            return grouped[0]
        return None

    def _index_project(self, field):
        """
        以 (project_id, 字段小写) 为键建立唯一索引；同一组合多条时丢弃（数据冲突不猜测）。
        """
        grouped = {}
        for row in self.rows:
            key = (row["project_id"], self._norm(row[field]))
            grouped.setdefault(key, []).append(row)
        return {key: self._first_unique_row(rows) for key, rows in grouped.items()}

    def _index_global(self, field):
        """
        以 字段小写 为键建立全局唯一索引；多条时丢弃。
        """
        grouped = {}
        for row in self.rows:
            key = self._norm(row[field])
            grouped.setdefault(key, []).append(row)
        return {key: self._first_unique_row(rows) for key, rows in grouped.items()}

    def resolve(self, mapping):
        """
        按映射条目 + 工单项目上下文解析模块。
        :param mapping: 含 resolve_project / moduleId / moduleCode / moduleName 的解析上下文。
        :return: (模块行, 跳过原因)。未解析成功时模块行为 None。
        """
        ticket_project_id = mapping.get("resolve_project")
        mapped_module_id = safe_int(mapping.get("moduleId") or mapping.get("module_id"))
        mapped_module_code = str(mapping.get("moduleCode") or mapping.get("module_code") or "").strip()
        mapped_module_name = str(mapping.get("moduleName") or mapping.get("module_name") or "").strip()

        if ticket_project_id:
            # 工单有项目：优先 (project_id + module_code)，避免跨项目同 code 串模块
            if mapped_module_code:
                row = self.by_project_code.get((ticket_project_id, self._norm(mapped_module_code)))
                if row:
                    return row, ""
            if mapped_module_id:
                row = self.by_id.get(mapped_module_id)
                if row and row["project_id"] == ticket_project_id:
                    return row, ""
            if mapped_module_name:
                row = self.by_project_name.get((ticket_project_id, self._norm(mapped_module_name)))
                if row:
                    return row, ""
            return None, "工单有项目但该项目下未找到对应模块"
        # 工单无项目：先按 module_id（全局唯一），再按 module_code / module_name（必须全局唯一）
        if mapped_module_id:
            row = self.by_id.get(mapped_module_id)
            if row:
                return row, ""
        if mapped_module_code:
            row = self.by_global_code.get(self._norm(mapped_module_code))
            if row:
                return row, ""
        if mapped_module_name:
            row = self.by_global_name.get(self._norm(mapped_module_name))
            if row:
                return row, ""
        return None, "工单无项目且 module_code 全局不唯一或未找到模块"


def load_sync_module_mappings(cursor):
    """
    从 sys_config 读取工单同步自动化配置并提取 moduleMappings。
    :return: 模块映射配置列表；配置缺失或解析失败时返回空列表。
    """
    cursor.execute(
        "SELECT config_key, config_value FROM sys_config WHERE config_key = %s",
        (TICKET_SYNC_CONFIG_KEY,),
    )
    row = cursor.fetchone()
    if not row:
        print(f"未找到配置 sys_config.config_key = {TICKET_SYNC_CONFIG_KEY}，脚本终止")
        sys.exit(1)
    raw_value = row.get("config_value") or ""
    try:
        import json

        config = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
    except Exception as exc:
        print(f"解析配置 {TICKET_SYNC_CONFIG_KEY} 失败: {exc}")
        sys.exit(1)
    mappings = config.get("moduleMappings") if isinstance(config, dict) else None
    if not isinstance(mappings, list):
        print("配置中 moduleMappings 不是列表，脚本终止")
        sys.exit(1)
    print(f"读取到 moduleMappings 映射条目数: {len(mappings)}")
    for index, mapping in enumerate(mappings[:20], start=1):
        print(
            f"  [{index}] keywords={mapping_keywords(mapping)} "
            f"projectId={mapping_project_id(mapping)} "
            f"moduleCode={mapping.get('moduleCode') or mapping.get('module_code') or ''} "
            f"moduleId={mapping.get('moduleId') or mapping.get('module_id') or ''}"
        )
    if len(mappings) > 20:
        print(f"  ... 其余 {len(mappings) - 20} 条省略")
    return mappings


def load_tickets(cursor, limit):
    """
    查询待处理工单：存在 module_name 且未删除。
    :param limit: 大于 0 时只取前 limit 条（按 ticket_id 排序）。
    :return: 工单行列表。
    """
    sql = (
        "SELECT ticket_id, project_id, module_name, module_id, module_code "
        "FROM ticket "
        "WHERE del_flag = '0' "
        "AND module_name IS NOT NULL AND module_name <> ''"
    )
    if limit and limit > 0:
        sql += " ORDER BY ticket_id LIMIT %s"
        cursor.execute(sql, (limit,))
    else:
        cursor.execute(sql)
    return cursor.fetchall()


def build_update_plan(rows, resolver, mappings):
    """
    逐条工单计算映射与模块解析，生成更新计划（含 skip 原因）。
    :return: (待更新列表, 统计字典)
    """
    stats = {
        "matched_and_resolved": 0,
        "matched_but_unresolved": 0,
        "unmatched": 0,
        "already_consistent": 0,
        "no_mapping_config": 0,
    }
    updates = []
    for row in rows:
        ticket_id = row["ticket_id"]
        ticket_project_id = safe_int(row["project_id"])
        module_name = str(row["module_name"] or "").strip()
        mapping = match_module_mapping(module_name, mappings, ticket_project_id)
        if mapping is None:
            stats["unmatched"] += 1
            continue
        resolve_context = {"resolve_project": ticket_project_id}
        resolve_context.update(mapping)
        resolved_row, skip_reason = resolver.resolve(resolve_context)
        if resolved_row is None:
            stats["matched_but_unresolved"] += 1
            print(
                f"[跳过] ticket_id={ticket_id} project_id={ticket_project_id} "
                f"module_name=\"{module_name}\" 原因: {skip_reason}"
            )
            continue
        new_module_id = resolved_row["module_id"]
        new_module_code = str(resolved_row["module_code"] or "").strip()
        old_module_id = safe_int(row["module_id"])
        old_module_code = str(row["module_code"] or "").strip()
        if old_module_id == new_module_id and old_module_code == new_module_code:
            stats["already_consistent"] += 1
            continue
        updates.append(
            {
                "ticket_id": ticket_id,
                "ticket_project_id": ticket_project_id,
                "module_name": module_name,
                "old_module_id": old_module_id,
                "old_module_code": old_module_code,
                "new_module_id": new_module_id,
                "new_module_code": new_module_code,
            }
        )
        stats["matched_and_resolved"] += 1
    return updates, stats


def preview_and_confirm(updates, stats, total_ticket_count):
    """
    打印统计与更新明细，并等待用户确认。
    :return: True 表示确认执行。
    """
    print("\n==================== 更新预览 ====================")
    print(
        f"待扫描工单数: {total_ticket_count}；"
        f"命中映射且解析成功将更新: {stats['matched_and_resolved']} 条；"
        f"命中映射但模块未解析: {stats['matched_but_unresolved']} 条；"
        f"未命中映射: {stats['unmatched']} 条；"
        f"解析结果与现状一致无需更新: {stats['already_consistent']} 条。"
    )
    if not updates:
        print("没有需要更新的工单，脚本退出")
        return False

    display_lines = updates[:PREVIEW_LINE_LIMIT]
    for item in display_lines:
        print(
            f"ticket_id={item['ticket_id']} "
            f"(project_id={item['ticket_project_id']}, module_name=\"{item['module_name']}\")"
        )
        print(
            f"  module_id: {item['old_module_id']} -> {item['new_module_id']} "
            f"| module_code: \"{item['old_module_code']}\" -> \"{item['new_module_code']}\""
        )
    if len(updates) > PREVIEW_LINE_LIMIT:
        print(f"  ... 其余 {len(updates) - PREVIEW_LINE_LIMIT} 条未逐行展示")

    answer = input(
        f"\n确认更新以上 {len(updates)} 条工单的 module_id/module_code？按 Enter 执行，Ctrl+C 取消: "
    ).strip().lower()
    if answer in ("y", "yes", "1", ""):
        return True
    print("已取消，未做任何更新")
    return False


def apply_updates(cursor, updates):
    """
    批量更新工单模块字段（不修改 module_name）。
    """
    update_sql = (
        "UPDATE ticket SET module_id = %s, module_code = %s, update_time = NOW() "
        "WHERE ticket_id = %s"
    )
    data = [
        (item["new_module_id"], item["new_module_code"], item["ticket_id"])
        for item in updates
    ]
    cursor.executemany(update_sql, data)
    return cursor.rowcount


def main():
    # 可选参数：limit 大于 0 时只处理前 N 条工单（按 ticket_id 排序），便于小范围验证
    limit = 0
    if len(sys.argv) > 1:
        limit = safe_int(sys.argv[1]) or 0
        print(f"本次只处理前 {limit} 条工单（按 ticket_id 排序）")

    conn = pymysql.connect(
        host=os.environ.get("DB_HOST", ""),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USERNAME", ""),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_DATABASE", ""),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
    )

    try:
        with conn.cursor() as cursor:
            # 1. 读取模块映射配置
            mappings = load_sync_module_mappings(cursor)
            if not mappings:
                print("moduleMappings 为空，无需处理，脚本退出")
                return

            # 2. 加载 hrm_module 正常模块到内存索引
            cursor.execute(
                "SELECT module_id, module_code, project_id, module_name "
                "FROM hrm_module WHERE status = %s",
                (HRM_MODULE_STATUS_NORMAL,),
            )
            module_rows = cursor.fetchall()
            resolver = ModuleResolver(module_rows)
            print(f"hrm_module 正常模块数: {len(module_rows)}")

            # 3. 加载待处理工单
            ticket_rows = load_tickets(cursor, limit)
            print(f"带 module_name 的工单数: {len(ticket_rows)}")

            # 4. 计算更新计划
            updates, stats = build_update_plan(ticket_rows, resolver, mappings)

            # 5. 预览并确认
            if not preview_and_confirm(updates, stats, len(ticket_rows)):
                return

            # 6. 执行更新（同一事务，异常整体回滚）
            affected = apply_updates(cursor, updates)
            conn.commit()
            print(f"\n执行完成，共更新 {affected} 条工单（module_name 未改动）")

    except Exception:
        conn.rollback()
        print("执行异常，已回滚所有更新")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()