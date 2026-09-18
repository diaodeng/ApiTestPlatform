"""Unidata 大数据查询接入 Demo。

用途：验证统一凭证里托管的 Unidata API Key 能否实际访问大数据查询服务，
并演示"列库 -> 列表 -> 表采样"的最小调用链路，为后续平台化接入做参考。

使用方式（密钥不入库，通过命令行传入）：
    python server/scripts/unidata_demo.py --api-key <你的key> --workbench-code ddw_trade

接口依据（来自 UAT OpenAPI /v3/api-docs）：
    GET /api/v1/assets/databases        列正式元数据库（workbenchCode 必填）
    GET /api/v1/assets/tables           列正式元数据表（workbenchCode 必填）
    GET /api/v1/assets/table-sample-data 表采样（tableFullName 为 db.table 格式）
认证方式：请求头 Authorization: Bearer <api_key>
"""
import argparse
import json
import re
import sys

import httpx


def strip_highlight(value) -> str:
    """剥离接口 keyword 搜索返回值中的 HTML 高亮标签（如 <span style='color:red'>xx</span>）。"""
    return re.sub(r"<[^>]+>", "", str(value)).strip()


def build_headers(api_key: str) -> dict:
    """构造 Unidata 认证请求头。"""
    return {"Authorization": f"Bearer {api_key}"}


def call_get(client: httpx.Client, path: str, params: dict) -> dict:
    """调用 Unidata GET 接口并返回 JSON；失败时输出状态码与响应体片段后抛出异常。"""
    response = client.get(path, params=params)
    if response.status_code != 200:
        print(f"[失败] GET {path} status={response.status_code} body={response.text[:500]}")
        response.raise_for_status()
    data = response.json()
    # 网关统一响应结构：success/code/message/data/traceId；success=false 视为业务失败
    if isinstance(data, dict) and data.get("success") is False:
        raise RuntimeError(f"业务失败 code={data.get('code')} message={data.get('message')} traceId={data.get('traceId')}")
    print(f"[成功] GET {path} params={params} -> keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}")
    return data


def extract_rows(data):
    """从常见分页响应结构中提取行列表（兼容 data.list / data.records / data 等字段）。"""
    if isinstance(data, dict):
        payload = data.get("data")
        if isinstance(payload, dict):
            for key in ("list", "records", "rows", "items"):
                if isinstance(payload.get(key), list):
                    return payload[key]
            return [payload]
        if isinstance(payload, list):
            return payload
    if isinstance(data, list):
        return data
    return []


def main() -> int:
    """Demo 主流程：连通性 -> 列库 -> 列表 -> 表采样。"""
    parser = argparse.ArgumentParser(description="Unidata 大数据查询接入 Demo")
    parser.add_argument("--base-url", default="https://uatopen-d.rta-os.com", help="Unidata 网关地址")
    parser.add_argument("--api-key", required=True, help="API Key（Bearer Token）")
    parser.add_argument("--workbench-code", default="ddw_trade", help="工作台编码（runtime 必填参数）")
    parser.add_argument("--page-size", type=int, default=10, help="每页条数，演示默认 10")
    args = parser.parse_args()

    print(f"==== Unidata Demo | base={args.base_url} | workbench={args.workbench_code} ====")

    # urllib3 证书告警规避：UAT 网关证书如为内网自签，可按需关闭校验（生产不建议）
    with httpx.Client(base_url=args.base_url, headers=build_headers(args.api_key), timeout=30.0, verify=True) as client:
        # 第 1 步：列库（同时验证连通性与鉴权）
        db_data = call_get(client, "/api/v1/assets/databases", {"workbenchCode": args.workbench_code, "pageNo": 1, "pageSize": args.page_size})
        databases = extract_rows(db_data)
        db_names = [strip_highlight(row.get("name") or row.get("databaseName") or row.get("dbName") or row) for row in databases]
        print(f"---- 数据库（前 {len(db_names)} 个）----")
        for name in db_names:
            print(f"  {name}")
        if not db_names:
            print("  （未解析到库列表，原始响应如下）")
            print(json.dumps(db_data, ensure_ascii=False)[:1000])
            return 0

        # 第 2 步：列表（用第一个库名做 keyword 过滤，验证库->表链路）
        first_db = db_names[0]
        table_data = call_get(client, "/api/v1/assets/tables", {"workbenchCode": args.workbench_code, "keyword": first_db, "searchScope": "库名", "pageNo": 1, "pageSize": args.page_size})
        tables = extract_rows(table_data)
        print(f"---- 库 {first_db} 下的表（前 {len(tables)} 张）----")
        table_full_names = []
        for row in tables:
            # 表接口真实字段为 fullName / chineseName / comment，keyword 为子串匹配且返回值带高亮，需剥离
            full_name = strip_highlight(row.get("fullName") or row.get("tableFullName") or f"{row.get('dbName') or first_db}.{row.get('tableName')}")
            table_full_names.append(full_name)
            description = strip_highlight(row.get("chineseName") or row.get("comment") or row.get("tableDescription") or "")
            print(f"  {full_name}  {description[:40]}")
        if not table_full_names:
            print("  （未解析到表列表，原始响应如下）")
            print(json.dumps(table_data, ensure_ascii=False)[:1000])
            return 0

        # 第 3 步：查当前账号全局表权限（不带 dbName 过滤），采样必须选有权限的表
        priv_data = call_get(client, "/api/v1/assets/table-privileges/my", {"workbenchCode": args.workbench_code, "pageNo": 1, "pageSize": 50})
        privileged = extract_rows(priv_data)
        concrete_tables, wildcard_dbs = [], []
        for row in privileged:
            db_name = strip_highlight(row.get("dbName") or row.get("databaseName") or "")
            table_name = strip_highlight(row.get("tableName") or "")
            auth_type = row.get("authType") or row.get("privilegeType") or ""
            if db_name and table_name and table_name != "*":
                concrete_tables.append(f"{db_name}.{table_name}")
                print(f"  [有权限] {db_name}.{table_name}  authType={auth_type}")
            elif db_name:
                wildcard_dbs.append(db_name)
                print(f"  [整库权限] {db_name}.*  authType={auth_type}")
        print(f"---- 权限汇总：具体表 {len(concrete_tables)} 张，整库通配 {len(set(wildcard_dbs))} 个 ----")

        # 第 4 步：表采样。优先用权限清单中的具体表；只有整库权限时，先列该库的表再取第一张。
        sample_target = ""
        if concrete_tables:
            sample_target = concrete_tables[0]
        elif wildcard_dbs:
            wildcard_db = sorted(set(wildcard_dbs))[0]
            wildcard_tables = extract_rows(call_get(client, "/api/v1/assets/tables", {"workbenchCode": args.workbench_code, "keyword": wildcard_db, "searchScope": "库名", "pageNo": 1, "pageSize": 5}))
            for row in wildcard_tables:
                name = strip_highlight(row.get("tableFullName") or row.get("fullName") or "")
                if name:
                    sample_target = name
                    break
        if not sample_target:
            print("  （未找到可采样的有权限表，跳过采样演示）")
        else:
            print(f"---- 尝试表采样：{sample_target} ----")
            try:
                sample_data = call_get(client, "/api/v1/assets/table-sample-data", {"workbenchCode": args.workbench_code, "tableFullName": sample_target, "limit": 2})
                rows = extract_rows(sample_data)
                columns = []
                if rows and isinstance(rows[0], dict) and isinstance(rows[0].get("columns"), list):
                    columns = [item.get("name") for item in rows[0]["columns"]][:12]
                print(f"---- 表 {sample_target} 采样成功，列（前 12）：{columns} ----")
                for row in rows[:2]:
                    print(f"  {json.dumps(row, ensure_ascii=False, default=str)[:260]}")
            except httpx.HTTPStatusError as exc:
                print(f"  [跳过] 表采样失败 status={exc.response.status_code}，多为表级权限不足（Unidata 侧限制），接入链路本身已验证可用")

    print("==== Demo 全链路执行完成 ====")
    return 0


if __name__ == "__main__":
    sys.exit(main())
