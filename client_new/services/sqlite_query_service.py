import os
import sqlite3
from pathlib import Path

from model.config import SqliteScannedDatabaseModel, SqliteScannedDirectoryModel


class SqliteQueryService:
    SQLITE_HEADER = b"SQLite format 3\x00"

    @classmethod
    def scan_sqlite_directories(
        cls, work_dirs: list[str], max_depth: int
    ) -> list[SqliteScannedDirectoryModel]:
        grouped: dict[str, list[SqliteScannedDatabaseModel]] = {}
        normalized_depth = max(0, int(max_depth or 0))

        for work_dir in cls._normalize_work_dirs(work_dirs):
            for current_root, dirs, files in os.walk(work_dir):
                depth = cls._relative_depth(work_dir, current_root)
                if depth > normalized_depth:
                    dirs[:] = []
                    continue

                sqlite_files: list[SqliteScannedDatabaseModel] = []
                for file_name in sorted(files, key=str.lower):
                    file_path = os.path.join(current_root, file_name)
                    if not cls._is_sqlite_file(file_path):
                        continue
                    sqlite_files.append(
                        SqliteScannedDatabaseModel(
                            file_name=file_name,
                            file_path=file_path,
                            size=cls._safe_file_size(file_path),
                        )
                    )

                if sqlite_files:
                    grouped[current_root] = sqlite_files

                if depth >= normalized_depth:
                    dirs[:] = []

        results = [
            SqliteScannedDirectoryModel(
                directory_path=directory_path,
                database_files=database_files,
            )
            for directory_path, database_files in sorted(
                grouped.items(), key=lambda item: item[0].lower()
            )
        ]
        return results

    @classmethod
    def list_tables(cls, database_path: str) -> list[str]:
        with cls._connect(database_path) as conn:
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type IN ('table', 'view')
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY type = 'view', name COLLATE NOCASE
                """
            ).fetchall()
        return [str(row[0]) for row in rows if row and row[0]]

    @classmethod
    def list_columns(cls, database_path: str, table_name: str) -> list[str]:
        if not table_name:
            return []
        quoted_table = cls.quote_identifier(table_name)
        with cls._connect(database_path) as conn:
            rows = conn.execute(f"PRAGMA table_info({quoted_table})").fetchall()
        return [str(row[1]) for row in rows if len(row) > 1]

    @classmethod
    def fetch_table_page(
        cls,
        database_path: str,
        table_name: str,
        page: int,
        page_size: int,
        filter_field: str = "",
        filter_operator: str = "contains",
        filter_value: str = "",
    ) -> dict:
        if not table_name:
            return {"columns": [], "rows": [], "total": 0, "page": 1, "page_size": page_size}

        page_index = max(1, int(page or 1))
        current_page_size = max(1, int(page_size or 100))
        columns = cls.list_columns(database_path, table_name)
        quoted_table = cls.quote_identifier(table_name)
        quoted_columns = ", ".join(cls.quote_identifier(column) for column in columns) or "*"
        where_sql, params = cls._build_filter_clause(
            columns=columns,
            filter_field=filter_field,
            filter_operator=filter_operator,
            filter_value=filter_value,
        )
        offset = (page_index - 1) * current_page_size

        with cls._connect(database_path) as conn:
            total = conn.execute(
                f"SELECT COUNT(1) FROM {quoted_table}{where_sql}",
                params,
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT {quoted_columns} FROM {quoted_table}{where_sql} LIMIT ? OFFSET ?",
                [*params, current_page_size, offset],
            ).fetchall()

        return {
            "columns": columns,
            "rows": cls.normalize_rows(rows),
            "total": int(total or 0),
            "page": page_index,
            "page_size": current_page_size,
        }

    @classmethod
    def execute_sql(cls, database_path: str, sql_text: str) -> dict:
        normalized_sql = (sql_text or "").strip()
        if not normalized_sql:
            return {"columns": [], "rows": [], "total": 0, "message": "SQL 为空"}

        with cls._connect(database_path) as conn:
            cursor = conn.execute(normalized_sql)
            if cursor.description:
                columns = [
                    description[0] or f"column_{index + 1}"
                    for index, description in enumerate(cursor.description)
                ]
                rows = cursor.fetchall()
                return {
                    "columns": columns,
                    "rows": cls.normalize_rows(rows),
                    "total": len(rows),
                    "message": f"查询完成，共 {len(rows)} 行",
                }

            affected = cursor.rowcount if cursor.rowcount is not None else 0
            return {
                "columns": [],
                "rows": [],
                "total": 0,
                "message": f"SQL 执行完成，影响 {affected} 行",
            }

    @classmethod
    def paginate_rows(cls, rows: list[list], page: int, page_size: int) -> list[list]:
        page_index = max(1, int(page or 1))
        current_page_size = max(1, int(page_size or 100))
        offset = (page_index - 1) * current_page_size
        return rows[offset : offset + current_page_size]

    @classmethod
    def normalize_rows(cls, rows: list) -> list[list]:
        result = []
        for row in rows:
            result.append([cls.normalize_cell(value) for value in row])
        return result

    @staticmethod
    def normalize_cell(value):
        if value is None:
            return ""
        if isinstance(value, bytes):
            return f"<BLOB {len(value)} bytes>"
        if isinstance(value, (str, int, float)):
            return value
        return str(value)

    @staticmethod
    def quote_identifier(identifier: str) -> str:
        return '"' + str(identifier or "").replace('"', '""') + '"'

    @classmethod
    def _build_filter_clause(
        cls,
        columns: list[str],
        filter_field: str,
        filter_operator: str,
        filter_value: str,
    ) -> tuple[str, list]:
        normalized_field = (filter_field or "").strip()
        normalized_operator = (filter_operator or "contains").strip()
        normalized_value = (filter_value or "").strip()

        if not columns:
            return "", []

        target_columns = columns if not normalized_field or normalized_field == "*" else [normalized_field]
        if not target_columns:
            return "", []

        if normalized_operator not in {"is_null", "not_null"} and not normalized_value:
            return "", []

        clauses = []
        params: list = []

        for column in target_columns:
            quoted_column = cls.quote_identifier(column)
            if normalized_operator == "contains":
                clauses.append(f"CAST({quoted_column} AS TEXT) LIKE ?")
                params.append(f"%{normalized_value}%")
            elif normalized_operator == "equals":
                clauses.append(f"CAST({quoted_column} AS TEXT) = ?")
                params.append(normalized_value)
            elif normalized_operator == "starts_with":
                clauses.append(f"CAST({quoted_column} AS TEXT) LIKE ?")
                params.append(f"{normalized_value}%")
            elif normalized_operator == "ends_with":
                clauses.append(f"CAST({quoted_column} AS TEXT) LIKE ?")
                params.append(f"%{normalized_value}")
            elif normalized_operator == "gt":
                clauses.append(f"{quoted_column} > ?")
                params.append(normalized_value)
            elif normalized_operator == "gte":
                clauses.append(f"{quoted_column} >= ?")
                params.append(normalized_value)
            elif normalized_operator == "lt":
                clauses.append(f"{quoted_column} < ?")
                params.append(normalized_value)
            elif normalized_operator == "lte":
                clauses.append(f"{quoted_column} <= ?")
                params.append(normalized_value)
            elif normalized_operator == "is_null":
                clauses.append(f"{quoted_column} IS NULL")
            elif normalized_operator == "not_null":
                clauses.append(f"{quoted_column} IS NOT NULL")

        if not clauses:
            return "", []

        connector = " OR " if len(target_columns) > 1 else " AND "
        return f" WHERE ({connector.join(clauses)})", params

    @classmethod
    def _connect(cls, database_path: str) -> sqlite3.Connection:
        resolved_path = str(Path(database_path).resolve())
        connection = sqlite3.connect(resolved_path, timeout=5)
        connection.execute("PRAGMA query_only = 1")
        return connection

    @classmethod
    def _is_sqlite_file(cls, file_path: str) -> bool:
        try:
            if not os.path.isfile(file_path):
                return False
            if cls._safe_file_size(file_path) < len(cls.SQLITE_HEADER):
                return False
            with open(file_path, "rb") as file_obj:
                return file_obj.read(len(cls.SQLITE_HEADER)) == cls.SQLITE_HEADER
        except OSError:
            return False
        except Exception:
            return False

    @staticmethod
    def _safe_file_size(file_path: str) -> int:
        try:
            return int(os.path.getsize(file_path))
        except OSError:
            return 0

    @staticmethod
    def _normalize_work_dirs(work_dirs: list[str]) -> list[str]:
        result = []
        seen = set()
        for work_dir in work_dirs or []:
            normalized = str(Path(work_dir).expanduser())
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            result.append(normalized)
        return result

    @staticmethod
    def _relative_depth(root_path: str, current_path: str) -> int:
        if os.path.normcase(root_path) == os.path.normcase(current_path):
            return 0
        relative = os.path.relpath(current_path, root_path)
        return len([part for part in relative.split(os.sep) if part and part != "."])
