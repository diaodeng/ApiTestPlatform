"""
临时诊断脚本（只读，不修改任何数据）：
针对用户反馈“全部映射成 pos_client”的问题，打印示例工单命中的映射条目与解析结果，
用于确认是配置问题还是脚本匹配问题。用后即删。
"""

import json
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_ticket_module_mapping as stm

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env.prod", override=True)

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SAMPLE_TICKET_IDS = [
    2020427658423296, 2020469916507136, 2020470161107968, 2020470652697600,
    2020508274637824, 2020719365909504, 2020734358973440, 2020736585079808,
    2020744922979328, 2020745426856960, 2020745511390208,
]

conn = pymysql.connect(
    host=__import__("os").environ.get("DB_HOST", ""),
    port=int(__import__("os").environ.get("DB_PORT", "3306")),
    user=__import__("os").environ.get("DB_USERNAME", ""),
    password=__import__("os").environ.get("DB_PASSWORD", ""),
    database=__import__("os").environ.get("DB_DATABASE", ""),
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
    connect_timeout=10,
)

try:
    with conn.cursor() as cursor:
        # 1. 读取完整 moduleMappings 配置
        cursor.execute(
            "SELECT config_value FROM sys_config WHERE config_key = %s",
            (stm.TICKET_SYNC_CONFIG_KEY,),
        )
        row = cursor.fetchone()
        config = json.loads(row["config_value"])
        mappings = config.get("moduleMappings") or []
        print(f"===== 配置 moduleMappings 共 {len(mappings)} 条 =====")
        for idx, m in enumerate(mappings):
            if not isinstance(m, dict):
                continue
            kws = stm.mapping_keywords(m)
            # 关注包含 pos 关键字或 moduleCode 含 pos 的条目
            if any("pos" in (k or "").lower() for k in kws) or "pos" in str(
                m.get("moduleCode") or m.get("module_code") or ""
            ).lower():
                print(
                    f"[{idx}] keywords={kws} projectId={stm.mapping_project_id(m)} "
                    f"moduleCode={m.get('moduleCode') or m.get('module_code') or ''} "
                    f"moduleId={m.get('moduleId') or m.get('module_id') or ''} "
                    f"moduleName={m.get('moduleName') or m.get('module_name') or ''}"
                )

        # 2. 加载 hrm_module 正常模块
        cursor.execute(
            "SELECT module_id, module_code, project_id, module_name, status "
            "FROM hrm_module WHERE status = %s",
            (stm.HRM_MODULE_STATUS_NORMAL,),
        )
        module_rows = cursor.fetchall()
        resolver = stm.ModuleResolver(module_rows)
        id2row = {r["module_id"]: r for r in module_rows}
        print(f"\n===== hrm_module 正常模块数 {len(module_rows)} =====")

        # 3. 查询示例工单并逐条打印命中映射与解析结果
        fmt = ",".join(["%s"] * len(SAMPLE_TICKET_IDS))
        cursor.execute(
            f"SELECT ticket_id, project_id, module_name, module_id, module_code "
            f"FROM ticket WHERE ticket_id IN ({fmt})",
            tuple(SAMPLE_TICKET_IDS),
        )
        tickets = cursor.fetchall()
        print(f"\n===== 示例工单 {len(tickets)} 条，匹配明细如下 =====")
        for t in tickets:
            tid = t["ticket_id"]
            pid = stm.safe_int(t["project_id"])
            name = str(t["module_name"] or "").strip()
            mapping = stm.match_module_mapping(name, mappings, pid)
            if mapping is None:
                print(f"ticket_id={tid} project_id={pid} module_name={name!r} -> 未命中映射")
                continue
            idx = mappings.index(mapping)
            print(f"ticket_id={tid} project_id={pid} module_name={name!r}")
            print(
                f"   命中映射[{idx}] keywords={stm.mapping_keywords(mapping)} "
                f"projectId={stm.mapping_project_id(mapping)} "
                f"moduleCode={mapping.get('moduleCode') or mapping.get('module_code') or ''} "
                f"moduleId={mapping.get('moduleId') or mapping.get('module_id') or ''} "
                f"moduleName={mapping.get('moduleName') or mapping.get('module_name') or ''}"
            )
            ctx = {"resolve_project": pid}
            ctx.update(mapping)
            resolved, reason = resolver.resolve(ctx)
            if resolved:
                r = id2row[resolved["module_id"]]
                same_name = str(r.get("module_name") or "").strip() == name
                print(
                    f"   解析模块 id={r['module_id']} code={r['module_code']!r} "
                    f"name={r['module_name']!r} (名称与工单一致={same_name})"
                )
            else:
                print(f"   解析失败: {reason}")

        # 4. 离线模拟：去掉第 0 条 keywords 中的裸 "POS" 后重新匹配
        print(f"\n===== 模拟（移除映射[0] keywords 中的裸 'POS'）=====")
        sim_mappings = []
        for i, m in enumerate(mappings):
            m2 = dict(m) if isinstance(m, dict) else m
            if i == 0:
                kws = stm.mapping_keywords(m)
                new_kws = [k for k in kws if k.lower() != "pos"]
                m2 = dict(m)
                m2["keywords"] = new_kws
            sim_mappings.append(m2)
        for t in tickets:
            tid = t["ticket_id"]
            pid = stm.safe_int(t["project_id"])
            name = str(t["module_name"] or "").strip()
            mapping = stm.match_module_mapping(name, sim_mappings, pid)
            if mapping is None:
                print(f"ticket_id={tid} module_name={name!r} -> 未命中映射")
                continue
            idx = sim_mappings.index(mapping)
            ctx = {"resolve_project": pid}
            ctx.update(mapping)
            resolved, reason = resolver.resolve(ctx)
            if resolved:
                print(
                    f"ticket_id={tid} module_name={name!r} -> 映射[{idx}] "
                    f"moduleCode={mapping.get('moduleCode') or mapping.get('module_code') or ''} "
                    f"| 解析 id={resolved['module_id']} code={resolved['module_code']!r} "
                    f"name={resolved['module_name']!r}"
                )
            else:
                print(
                    f"ticket_id={tid} module_name={name!r} -> 映射[{idx}] "
                    f"moduleCode={mapping.get('moduleCode') or mapping.get('module_code') or ''} "
                    f"| 解析失败: {reason}"
                )
finally:
    conn.close()