from loguru import logger

from server.config import SearchConfig, SqliteQueryConfig
from services.sqlite_query_service import SqliteQueryService


class SqliteApi:
    """
    SQLite 查询页面后端桥（替代原 Qt 页面 + Worker 线程）。

    业务全部复用纯 Python 的 SqliteQueryService；本类只做参数整理、
    配置持久化与结果返回。查询为同步 sqlite3 操作但均在 pywebview
    的 JS 调用线程执行，不阻塞界面事件循环。
    """

    def get_config(self) -> dict:
        """
        返回页面持久化配置（最近目录/库/表、SQL、收藏、列配置等）。
        """
        return {"ok": True, "config": SqliteQueryConfig.read_config().model_dump()}

    def save_config(self, data: dict) -> dict:
        """
        覆盖保存页面配置（前端在状态变化时调用）。
        """
        try:
            SqliteQueryConfig.save_config(data)
            return {"ok": True}
        except Exception as e:
            logger.exception(f"保存 SQLite 页面配置失败: {e}")
            return {"ok": False, "message": str(e)}

    def get_work_dirs(self) -> dict:
        return {"ok": True, "work_dirs": SearchConfig.read_work_dir()}

    def add_work_dir(self, path: str) -> dict:
        SearchConfig.add_work_dir(path)
        return {"ok": True, "work_dirs": SearchConfig.read_work_dir()}

    def remove_work_dir(self, path: str) -> dict:
        SearchConfig.remove_work_dir(path)
        return {"ok": True, "work_dirs": SearchConfig.read_work_dir()}

    def scan_databases(self) -> dict:
        """
        扫描工作目录下的 sqlite 文件，返回按目录分组的列表。
        """
        try:
            config = SqliteQueryConfig.read_config()
            work_dirs = SearchConfig.read_work_dir()
            # 扫描深度沿用 POS 搜索配置的递归深度（与原页面行为一致），缺省 3。
            try:
                depth = int(SearchConfig.read().max_depth)
            except Exception:
                depth = 3
            results = SqliteQueryService.scan_sqlite_directories(work_dirs, depth)
            scanned = [item.model_dump() for item in results]
            # 扫描结果持久化，下次进入页面可沿用
            config.scanned_directories = results
            SqliteQueryConfig.save_config(config)
            return {"ok": True, "directories": scanned}
        except Exception as e:
            logger.exception(f"扫描 sqlite 数据库失败: {e}")
            return {"ok": False, "message": str(e)}

    def list_tables(self, database_path: str) -> dict:
        try:
            tables = SqliteQueryService.list_tables(database_path)
            return {"ok": True, "tables": tables}
        except Exception as e:
            logger.exception(f"读取数据表失败: {e}")
            return {"ok": False, "message": str(e)}

    def fetch_table_page(
        self,
        database_path: str,
        table_name: str,
        page: int,
        page_size: int,
        filter_field: str = "",
        filter_operator: str = "contains",
        filter_value: str = "",
    ) -> dict:
        """
        分页查询表数据（支持快速过滤条件）。
        """
        try:
            result = SqliteQueryService.fetch_table_page(
                database_path,
                table_name,
                page,
                page_size,
                filter_field=filter_field,
                filter_operator=filter_operator,
                filter_value=filter_value,
            )
            return {"ok": True, **result}
        except Exception as e:
            logger.exception(f"查询表数据失败: {e}")
            return {"ok": False, "message": str(e)}

    def execute_sql(self, database_path: str, sql_text: str) -> dict:
        """
        执行自由 SQL，返回列与行数据（服务内部已做分页截断）。
        """
        try:
            result = SqliteQueryService.execute_sql(database_path, sql_text)
            return {"ok": True, **result}
        except Exception as e:
            logger.exception(f"执行 SQL 失败: {e}")
            return {"ok": False, "message": str(e)}
