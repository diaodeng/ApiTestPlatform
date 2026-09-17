"""大数据查询业务编排服务：数据源解析 -> 统一凭证投影 -> Unidata 网关调用 -> 结果归一。"""
import time

from sqlalchemy.orm import Session

from modules.unidata.entity.vo.unidata_vo import (
    UnidataColumnModel,
    UnidataDatabaseModel,
    UnidataQueryColumnModel,
    UnidataQueryRequestModel,
    UnidataQueryResultModel,
    UnidataTableModel,
)
from modules.unidata.service.unidata_config_service import UnidataConfigService
from modules.unidata.service.unidata_gateway_service import UnidataGatewayService
from modules.unidata.util.unidata_format_util import resolve_db_layer, strip_highlight
from utils.log_util import logger


class UnidataQueryService:
    """大数据查询页面的后端编排入口。"""

    @classmethod
    def list_source_options(cls, db: Session) -> list[dict]:
        """数据源下拉选项。"""
        return UnidataConfigService.list_enabled_source_options(db)

    @classmethod
    def list_databases(cls, db: Session, source_code: str) -> list[UnidataDatabaseModel]:
        """权限驱动的库清单：以当前账号表权限去重得到可用库，并附分层与授权信息。"""
        client, source = UnidataGatewayService.build_source_client(db, source_code)
        try:
            permission_rows = UnidataGatewayService.list_database_permissions(client, source.workbench_code)
        finally:
            client.close()
        databases: dict[str, UnidataDatabaseModel] = {}
        for row in permission_rows:
            name = strip_highlight(row.get("dbName") or row.get("databaseName"))
            if not name:
                continue
            auth_type = str(row.get("authType") or "").strip()
            wildcard = str(row.get("tableName") or "") == "*"
            model = databases.get(name)
            if model is None:
                model = UnidataDatabaseModel(name=name, layer=resolve_db_layer(name), auth_types=[], wildcard=False)
                databases[name] = model
            if auth_type and auth_type not in model.auth_types:
                model.auth_types.append(auth_type)
            model.wildcard = model.wildcard or wildcard
        result = sorted(databases.values(), key=lambda item: (item.layer != "stable", item.name))
        logger.info(f"已获取大数据查询权限库清单: source={source_code} databases={len(result)}")
        return result

    @classmethod
    def list_tables(cls, db: Session, source_code: str, db_name: str, keyword: str, page_no: int, page_size: int):
        """枚举指定库下的表（精确匹配库名，支持表名/中文名过滤与分页）。"""
        normalized_db_name = strip_highlight(db_name)
        if not normalized_db_name:
            raise ValueError("库名不能为空")
        client, source = UnidataGatewayService.build_source_client(db, source_code)
        try:
            raw_rows = UnidataGatewayService.list_tables_by_database(client, source.workbench_code, normalized_db_name)
        finally:
            client.close()
        filtered_keyword = strip_highlight(keyword).lower()
        tables: list[UnidataTableModel] = []
        for row in raw_rows:
            table_name = strip_highlight(row.get("tableName") or "")
            full_name = strip_highlight(row.get("fullName") or f"{normalized_db_name}.{table_name}")
            chinese_name = strip_highlight(row.get("chineseName") or "")
            comment = strip_highlight(row.get("comment") or "")
            keyword_hit = filtered_keyword in table_name.lower() or filtered_keyword in chinese_name.lower()
            if filtered_keyword and not keyword_hit:
                continue
            tables.append(
                UnidataTableModel(
                    name=full_name,
                    table_name=table_name,
                    chinese_name=chinese_name,
                    comment=comment,
                    owner=strip_highlight(row.get("owner") or ""),
                )
            )
        total = len(tables)
        start = (page_no - 1) * page_size
        page_rows = tables[start:start + page_size]
        logger.info(f"已获取大数据查询库下表清单: source={source_code} db={normalized_db_name} total={total}")
        return {"total": total, "rows": page_rows}

    @classmethod
    def list_columns(cls, db: Session, source_code: str, table_full_name: str) -> list[UnidataColumnModel]:
        """获取表的字段清单（字段名/类型/备注），供左侧树展开表节点使用。"""
        normalized_table = strip_highlight(table_full_name)
        if "." not in normalized_table:
            raise ValueError(f"表全名格式错误：'{normalized_table}'，应为 db.table 格式")
        client, source = UnidataGatewayService.build_source_client(db, source_code)
        try:
            detail = UnidataGatewayService.get_table_detail(client, source.workbench_code, normalized_table)
        finally:
            client.close()
        fields = detail.get("fields") if isinstance(detail, dict) else None
        columns = [
            UnidataColumnModel(
                name=strip_highlight(field.get("name") or ""),
                type=strip_highlight(field.get("type") or ""),
                comment=strip_highlight(field.get("comment") or ""),
            )
            for field in (fields or [])
            if isinstance(field, dict) and field.get("name")
        ]
        logger.info(f"已获取大数据查询表字段: source={source_code} table={normalized_table} columns={len(columns)}")
        return columns

    @classmethod
    def execute_query(cls, db: Session, source_code: str, model: UnidataQueryRequestModel) -> UnidataQueryResultModel:
        """执行只读 SQL 并归一结果（列、行、行数、截断标记、耗时）。"""
        client, source = UnidataGatewayService.build_source_client(db, source_code)
        engine = model.engine or source.default_engine
        started_at = time.monotonic()
        try:
            data = UnidataGatewayService.execute_query(
                client,
                source.workbench_code,
                model.sql,
                model.max_rows,
                model.timeout_seconds,
                engine,
            )
        finally:
            client.close()
        columns = [
            UnidataQueryColumnModel(name=str(item.get("name") or ""), type=str(item.get("type") or ""))
            for item in (data.get("columns") or [])
            if isinstance(item, dict) and item.get("name")
        ]
        rows = [row for row in (data.get("rows") or []) if isinstance(row, dict)]
        result = UnidataQueryResultModel(
            sql_type=str(data.get("sqlType") or ""),
            columns=columns,
            rows=rows,
            row_count=int(data.get("rowCount") or len(rows)),
            truncated=bool(data.get("truncated")),
            elapsed_ms=int(data.get("elapsedMs") or (time.monotonic() - started_at) * 1000),
        )
        logger.info(
            f"大数据查询执行完成: source={source_code} engine={engine} "
            f"rowCount={result.row_count} elapsedMs={result.elapsed_ms} truncated={result.truncated}"
        )
        return result
